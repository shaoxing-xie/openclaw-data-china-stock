"""
Utility to temporarily disable proxy environment variables.

Some market data sources may be blocked when requests are forced through a corporate proxy
(e.g. 403 Tunnel connection failed). For those calls, we explicitly bypass proxy env vars.
"""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from threading import RLock
from typing import Any, Dict, Iterator, Optional

_PROXY_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)

_ENV_LOCK = RLock()


def _normalize_proxy_url(value: Optional[str]) -> str:
    return str(value or "").strip().rstrip("/")


def _env_proxy_matches(proxy_url: str) -> bool:
    import os

    target = _normalize_proxy_url(proxy_url)
    if not target:
        return False
    current = [
        _normalize_proxy_url(os.environ.get("HTTP_PROXY")),
        _normalize_proxy_url(os.environ.get("HTTPS_PROXY")),
        _normalize_proxy_url(os.environ.get("http_proxy")),
        _normalize_proxy_url(os.environ.get("https_proxy")),
    ]
    return target in current


def _backup_proxy_env() -> Dict[str, Optional[str]]:
    import os

    return {k: os.environ.get(k) for k in _PROXY_KEYS}


def _restore_proxy_env(backup: Dict[str, Optional[str]]) -> None:
    import os

    for k, v in backup.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@contextmanager
def without_proxy_env(no_proxy_value: str = "*") -> Iterator[None]:
    """
    Temporarily unset proxy-related environment variables for the current process.
    """
    import os

    with _ENV_LOCK:
        backup = _backup_proxy_env()
        try:
            # Unset proxy vars
            for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
                if k in os.environ:
                    os.environ.pop(k, None)
            # Force bypass
            os.environ["NO_PROXY"] = no_proxy_value
            os.environ["no_proxy"] = no_proxy_value
            yield
        finally:
            _restore_proxy_env(backup)


@contextmanager
def with_proxy_env(proxy_url: str) -> Iterator[None]:
    """
    Temporarily set HTTP(S) proxy environment variables for current process.
    """
    import os

    proxy = str(proxy_url or "").strip()
    if not proxy:
        with nullcontext():
            yield
        return
    with _ENV_LOCK:
        backup = _backup_proxy_env()
        try:
            for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
                os.environ[k] = proxy
            # Do not force NO_PROXY when explicitly enabling proxy.
            yield
        finally:
            _restore_proxy_env(backup)


def resolve_proxy_policy(config: Dict[str, Any], source_name: str) -> Dict[str, str]:
    """
    Resolve per-source proxy policy from config.

    Returns:
        {"mode": "force_proxy|force_bypass|inherit", "url": "<proxy_url or empty>"}
    """
    import os

    # Total kill-switch: keep behavior compatible with existing deployment knobs.
    raw = (os.getenv("OPENCLAW_DISABLE_PROXY_FOR_MARKET_DATA") or "").strip().lower()
    if raw in {"1", "true", "on", "yes"}:
        return {"mode": "force_bypass", "url": ""}

    cfg = config if isinstance(config, dict) else {}
    net = cfg.get("network") if isinstance(cfg.get("network"), dict) else {}
    px = net.get("proxy") if isinstance(net.get("proxy"), dict) else {}
    default_cfg = px.get("default") if isinstance(px.get("default"), dict) else {}
    per_source = px.get("per_source") if isinstance(px.get("per_source"), dict) else {}
    src_cfg = per_source.get(str(source_name)) if isinstance(per_source.get(str(source_name)), dict) else {}

    mode = "inherit"
    url = ""
    if src_cfg:
        if bool(src_cfg.get("enabled", False)):
            mode = "force_proxy"
            url = str(src_cfg.get("url") or "").strip()
            if not url:
                mode = "inherit"
            elif _env_proxy_matches(url):
                # If runtime env already has the same proxy, inherit to avoid
                # overriding existing proxy chain behavior.
                mode = "inherit"
        else:
            mode = "force_bypass"
    else:
        if bool(default_cfg.get("enabled", False)):
            mode = "force_proxy"
            url = str(default_cfg.get("url") or "").strip()
            if not url:
                mode = "inherit"
            elif _env_proxy_matches(url):
                mode = "inherit"
    return {"mode": mode, "url": url}


def proxy_context_for_source(config: Dict[str, Any], source_name: str):
    """
    Return context manager based on source-level proxy policy.
    """
    policy = resolve_proxy_policy(config, source_name)
    mode = policy.get("mode", "inherit")
    if mode == "force_bypass":
        return without_proxy_env()
    if mode == "force_proxy":
        return with_proxy_env(policy.get("url", ""))
    return nullcontext()

