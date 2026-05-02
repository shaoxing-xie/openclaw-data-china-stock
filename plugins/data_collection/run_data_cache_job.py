from __future__ import annotations

from typing import Any, Dict, Optional


_VALID_JOBS = {"morning_daily", "intraday_minute", "close_minute"}


def tool_run_data_cache_job(
    job: str,
    *,
    throttle_stock: bool = False,
    notify: Optional[bool] = None,
    feishu_title: Optional[str] = None,
) -> Dict[str, Any]:
    """Compatibility wrapper used by tests/legacy imports."""
    from src.data_cache_collection_core import (
        feishu_notify_title_and_body_for_cache_job,
        run_data_cache_collection,
        summary_success,
    )

    job_name = str(job or "").strip()
    if job_name not in _VALID_JOBS:
        return {
            "success": False,
            "collection_success": False,
            "notify": False,
            "notify_result": None,
            "error": f"invalid job: {job_name}",
        }

    notify_effective = bool(job_name in {"morning_daily", "close_minute"}) if notify is None else bool(notify)
    summary = run_data_cache_collection(job_name, throttle_stock=bool(throttle_stock))
    collection_ok = bool(summary_success(summary))
    out: Dict[str, Any] = {
        "success": collection_ok,
        "collection_success": collection_ok,
        "job": job_name,
        "notify": notify_effective,
        "notify_result": None,
        "summary": summary,
    }

    if not notify_effective:
        return out

    from plugins.merged.send_feishu_notification import tool_send_feishu_notification

    title, body = feishu_notify_title_and_body_for_cache_job(
        job_name,
        summary,
        collection_ok=collection_ok,
        title_override=feishu_title,
    )
    notify_result = tool_send_feishu_notification(
        notification_type="message",
        title=title,
        message=body,
        cooldown_minutes=0,
    )
    out["notify_result"] = notify_result
    out["success"] = bool(collection_ok) and bool(notify_result.get("success"))
    return out
