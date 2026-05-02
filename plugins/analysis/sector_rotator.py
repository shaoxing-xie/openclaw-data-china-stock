from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from plugins.analysis.rps_engine import calculate_rps_for_etfs
from plugins.analysis.sector_etf_mapping import SectorEtfMapping, load_sector_etf_mappings


def _now_run_id() -> str:
    return datetime.now().strftime("%Y%m%dT%H%M%S")


def _trade_date(trade_date: str) -> str:
    s = (trade_date or "").strip()
    if not s:
        return datetime.now().strftime("%Y-%m-%d")
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except Exception:
        pass
    try:
        dt = datetime.strptime(s, "%Y%m%d")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def _env_gate_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "sector_rotation_env_gate.yaml"


def _default_env_gate_config() -> Dict[str, Any]:
    return {
        "enabled": True,
        "strong_rps_threshold": 85.0,
        "go_strong_ratio_min": 0.30,
        "caution_strong_ratio_min": 0.10,
        "caution_allocation_multiplier": 0.5,
        "stop_allocation_multiplier": 0.0,
        "volume_signals": {
            "enabled": True,
            "lookback_days": 30,
            "surge_ratio_min": 1.2,
            "shrink_ratio_max": 0.7,
        },
    }


def _load_env_gate_config() -> Dict[str, Any]:
    cfg = dict(_default_env_gate_config())
    path = _env_gate_config_path()
    if not path.exists():
        return cfg
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            for key in cfg.keys():
                if key not in raw or raw[key] is None:
                    continue
                if key == "volume_signals" and isinstance(raw[key], dict) and isinstance(cfg.get("volume_signals"), dict):
                    merged = dict(cfg["volume_signals"])
                    merged.update({k: v for k, v in raw[key].items() if v is not None})
                    cfg["volume_signals"] = merged
                else:
                    cfg[key] = raw[key]
    except Exception:
        pass
    return cfg


def _rps20_values_from_payload(rps20: Dict[str, Any]) -> List[float]:
    rps_map = (rps20.get("data") or {}).get("rps") if isinstance(rps20, dict) else None
    if not isinstance(rps_map, dict):
        return []
    vals: List[float] = []
    for v in rps_map.values():
        if isinstance(v, dict) and v.get("rps") is not None:
            try:
                vals.append(float(v["rps"]))
            except Exception:
                continue
    return vals


def _assess_environment(*, rps20: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    GO / CAUTION / STOP from RPS(20d) breadth (strong sector ratio).
    When cfg.enabled is false, returns UNKNOWN + env_gate_disabled (legacy allocation).
    """
    if not bool(cfg.get("enabled", True)):
        return {
            "gate": "UNKNOWN",
            "allocation_multiplier": 1.0,
            "reason_codes": ["env_gate_disabled"],
            "human_notes": "环境门闸已关闭，沿用历史 UNKNOWN 语义；仓位未按门闸缩放。",
            "metrics": {},
            "cautions": [],
        }

    vals = _rps20_values_from_payload(rps20)
    n = len(vals)
    if n <= 0:
        return {
            "gate": "UNKNOWN",
            "allocation_multiplier": 1.0,
            "reason_codes": ["env_rps_universe_empty"],
            "human_notes": "RPS(20d) 全市场无有效样本，无法评估环境门闸。",
            "metrics": {"n": 0},
            "cautions": [],
        }

    thr = float(cfg.get("strong_rps_threshold") or 85.0)
    strong = sum(1 for x in vals if x >= thr) / float(n)
    breadth = sum(1 for x in vals if x >= 50.0) / float(n)
    sorted_vals = sorted(vals)
    median_rps = float(sorted_vals[n // 2])

    go_min = float(cfg.get("go_strong_ratio_min") if cfg.get("go_strong_ratio_min") is not None else 0.30)
    caution_min = float(cfg.get("caution_strong_ratio_min") if cfg.get("caution_strong_ratio_min") is not None else 0.10)
    _cm = cfg.get("caution_allocation_multiplier")
    caut_mult = float(_cm) if _cm is not None else 0.5
    _sm = cfg.get("stop_allocation_multiplier")
    stop_mult = float(_sm) if _sm is not None else 0.0

    if strong > go_min:
        gate = "GO"
        mult = 1.0
        reasons = ["env_gate_go"]
        notes = "市场结构性偏强：可正常参考轮动建议。"
        cautions: List[str] = []
    elif strong > caution_min:
        gate = "CAUTION"
        mult = caut_mult
        reasons = ["env_gate_caution"]
        notes = "市场广度一般：建议降仓参与轮动（allocation 已按倍数缩放）。"
        cautions = ["env_gate_caution_reduce_allocation"]
    else:
        gate = "STOP"
        mult = stop_mult
        reasons = ["env_gate_stop"]
        notes = "市场环境偏弱：不建议轮动；展示 allocation_pct=0 但保留行业/ETF 行以便审计。"
        cautions = ["rotation_paused_env_stop"]

    return {
        "gate": gate,
        "allocation_multiplier": float(mult),
        "reason_codes": reasons,
        "human_notes": notes,
        "metrics": {
            "strong_sector_ratio": float(strong),
            "strong_rps_threshold": thr,
            "median_rps20": median_rps,
            "breadth_rps_ge_50": float(breadth),
            "n": n,
        },
        "cautions": cautions,
    }


def _volume_ratio_from_klines(klines: List[Dict[str, Any]]) -> Tuple[Optional[float], Optional[str]]:
    vols: List[float] = []
    for row in klines:
        if not isinstance(row, dict):
            continue
        v = row.get("volume")
        if v is None:
            v = row.get("vol")
        if v is None:
            continue
        try:
            vols.append(float(v))
        except Exception:
            continue
    if len(vols) < 2:
        return None, "volume_series_too_short"
    last = float(vols[-1])
    prev = vols[:-1]
    tail = prev[-20:] if len(prev) >= 20 else prev
    if not tail:
        return None, "volume_series_too_short"
    mean_tail = float(sum(tail) / float(len(tail)))
    if mean_tail <= 0:
        return None, "volume_mean_nonpositive"
    return float(last / mean_tail), None


def _apply_volume_signals(*, items: List[Dict[str, Any]], gate_cfg: Dict[str, Any]) -> None:
    vraw = gate_cfg.get("volume_signals")
    vcfg = vraw if isinstance(vraw, dict) else {}
    if not bool(vcfg.get("enabled", True)):
        return
    lb = max(22, int(vcfg.get("lookback_days") or 30))
    _sr = vcfg.get("surge_ratio_min")
    surge_thr = float(_sr) if _sr is not None else 1.2
    _sh = vcfg.get("shrink_ratio_max")
    shrink_thr = float(_sh) if _sh is not None else 0.7

    from plugins.merged.fetch_market_data import tool_fetch_market_data

    for x in items:
        code = str(x.get("etf_code") or "").strip()
        if not code:
            continue
        sig = x.get("signals")
        if not isinstance(sig, dict):
            sig = {}
            x["signals"] = sig
        cautions = x.get("cautions")
        if not isinstance(cautions, list):
            cautions = []
            x["cautions"] = cautions
        try:
            resp = tool_fetch_market_data(
                asset_type="etf",
                view="historical",
                asset_code=code,
                period="daily",
                lookback_days=lb,
            )
            data = resp.get("data") if isinstance(resp, dict) else {}
            klines = data.get("klines") if isinstance(data, dict) else None
            if not isinstance(klines, list) or len(klines) < 2:
                cautions.append("volume_data_unavailable")
                continue
            ratio, err = _volume_ratio_from_klines(klines)
            if err or ratio is None:
                cautions.append("volume_ratio_unavailable")
                continue
            sig["volume_ratio"] = round(float(ratio), 4)
            if ratio >= surge_thr:
                sig["volume_status"] = "surge"
            elif ratio <= shrink_thr:
                sig["volume_status"] = "shrink"
                cautions.append("volume_shrink_fake_breakout_risk")
            else:
                sig["volume_status"] = "normal"
        except Exception:
            cautions.append("volume_signal_failed")


def _explain_bullets_for_row(x: Dict[str, Any], *, env_gate: str) -> List[str]:
    sig = x.get("signals") if isinstance(x.get("signals"), dict) else {}
    bullets: List[str] = []
    if sig.get("rps_20d") is not None:
        bullets.append(f"RPS(20d)={float(sig['rps_20d']):.1f}，RPS(5d)={float(sig.get('rps_5d') or 0):.1f}，Δ={float(sig.get('rps_change') or 0):.1f}")
    if sig.get("momentum_score") is not None:
        bullets.append(f"动量分项 score≈{float(sig.get('momentum_score') or 0):.2f}")
    vs = sig.get("volume_status")
    vr = sig.get("volume_ratio")
    if vs and vr is not None:
        bullets.append(f"成交量状态={vs}（近1日/近20日均量比≈{float(vr):.2f}）")
    bullets.append(f"环境门闸={env_gate}")
    return bullets


def _extract_latest_amount(resp: Dict[str, Any]) -> Optional[float]:
    try:
        data = resp.get("data") if isinstance(resp, dict) else None
        if not isinstance(data, dict):
            return None
        klines = data.get("klines")
        if not isinstance(klines, list) or not klines:
            return None
        last = klines[-1]
        if not isinstance(last, dict):
            return None
        amt = last.get("amount")
        if amt is None:
            return None
        return float(amt)
    except Exception:
        return None


def _score_items(
    *,
    mappings: List[SectorEtfMapping],
    rps_20: Dict[str, Any],
    rps_5: Dict[str, Any],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    rps20_map = (rps_20.get("data") or {}).get("rps") if isinstance(rps_20, dict) else None
    rps5_map = (rps_5.get("data") or {}).get("rps") if isinstance(rps_5, dict) else None
    if not isinstance(rps20_map, dict) or not isinstance(rps5_map, dict):
        return out

    for m in mappings:
        code = m.etf_code
        e20 = rps20_map.get(code) if isinstance(rps20_map, dict) else None
        e5 = rps5_map.get(code) if isinstance(rps5_map, dict) else None
        if not isinstance(e20, dict) or not isinstance(e5, dict):
            continue
        rps20 = float(e20.get("rps") or 0.0)
        rps5 = float(e5.get("rps") or 0.0)
        rps_change = rps5 - rps20
        ret20 = float(e20.get("return") or 0.0)

        cautions: List[str] = []

        # Phase A scoring: momentum + RPS change (simple and stable)
        momentum_score = max(min((ret20 + 0.1) / 0.2, 1.0), 0.0)  # roughly map [-10%,+10%] -> [0,1]
        rps_abs = max(min((rps20 - 50.0) / 50.0, 1.0), 0.0)
        rps_change_score = max(min((rps_change + 20.0) / 40.0, 1.0), 0.0)  # [-20,+20] -> [0,1]
        rps_score = (0.6 * rps_abs) + (0.4 * rps_change_score)
        total = (0.55 * rps_score) + (0.45 * momentum_score)

        out.append(
            {
                "sector": m.sector_name,
                "index_code": m.index_code,
                "etf_code": code,
                "etf_name": m.etf_name,
                "composite_score": float(total),
                "signals": {
                    "momentum_20d_return": ret20,
                    "momentum_score": momentum_score,
                    "rps_20d": rps20,
                    "rps_5d": rps5,
                    "rps_change": rps_change,
                    "rps_score": rps_score,
                },
                "cautions": cautions,
            }
        )
    return out


def _apply_liquidity_cautions(
    *,
    items: List[Dict[str, Any]],
    mappings: List[SectorEtfMapping],
    min_liquidity: float,
) -> None:
    """
    Liquidity checks are done only for shortlisted candidates to keep runtime stable.
    """
    if not items:
        return
    liq_floor = float(min_liquidity or 0.0)
    if liq_floor <= 0:
        return
    map_by_code = {m.etf_code: m for m in mappings if m.etf_code}

    from plugins.merged.fetch_market_data import tool_fetch_market_data

    for x in items:
        code = str(x.get("etf_code") or "").strip()
        if not code:
            continue
        m = map_by_code.get(code)
        liq_threshold = float(getattr(m, "min_liquidity", 0.0) or 0.0) or liq_floor
        cautions = x.get("cautions")
        if not isinstance(cautions, list):
            cautions = []
            x["cautions"] = cautions
        try:
            resp = tool_fetch_market_data(
                asset_type="etf",
                view="historical",
                asset_code=code,
                period="daily",
                lookback_days=3,
            )
            amt = _extract_latest_amount(resp if isinstance(resp, dict) else {})
            if amt is not None and amt < liq_threshold:
                cautions.append(f"low_liquidity:amount<{int(liq_threshold)}")
        except Exception:
            cautions.append("liquidity_check_failed")


def tool_sector_rotation_recommend(
    *,
    top_k: int = 5,
    trade_date: str = "",
    min_liquidity: float = 100000000,
    mode: str = "production",
) -> Dict[str, Any]:
    """
    Tool: recommend next-day sector ETFs (Phase A).

    - Uses configured sector ETF mapping as universe.
    - Computes RPS(20) and RPS(5) across the universe.
    - Outputs Top-K with factor breakdown and cautions.
    """
    td = _trade_date(trade_date)
    mappings = load_sector_etf_mappings()
    if not mappings:
        return {
            "success": False,
            "message": "sector_etf_mapping 为空",
            "quality_status": "error",
            "data": None,
        }
    etf_codes = [m.etf_code for m in mappings if m.etf_code]

    rps20 = calculate_rps_for_etfs(etf_codes=etf_codes, lookback_days=20, trade_date=td, mode=mode)
    rps5 = calculate_rps_for_etfs(etf_codes=etf_codes, lookback_days=5, trade_date=td, mode=mode)
    if not rps20.get("success") or not rps5.get("success"):
        return {
            "success": False,
            "message": "rps calculation failed",
            "quality_status": "error",
            "data": {"trade_date": td, "rps20": rps20, "rps5": rps5},
        }

    items = _score_items(
        mappings=mappings,
        rps_20=rps20,
        rps_5=rps5,
    )
    items = sorted(items, key=lambda x: float(x.get("composite_score") or 0.0), reverse=True)
    k = max(1, min(int(top_k or 0), len(items)))
    top = items[:k]
    _apply_liquidity_cautions(items=top, mappings=mappings, min_liquidity=float(min_liquidity or 0.0))

    gate_cfg = _load_env_gate_config()
    _apply_volume_signals(items=top, gate_cfg=gate_cfg)
    env = _assess_environment(rps20=rps20, cfg=gate_cfg)
    base_alloc = min(20, int(round(100 / max(5, k))))
    _raw_mult = env.get("allocation_multiplier")
    mult = 1.0 if _raw_mult is None else float(_raw_mult)
    gate_name = str(env.get("gate") or "")
    if gate_name == "UNKNOWN":
        alloc_pct = base_alloc
    else:
        alloc_pct = int(round(base_alloc * mult))

    env_block: Dict[str, Any] = {
        "gate": env["gate"],
        "allocation_multiplier": env["allocation_multiplier"],
        "reason_codes": list(env.get("reason_codes") or []),
        "human_notes": env.get("human_notes") or "",
        "metrics": dict(env.get("metrics") or {}),
    }
    env_cautions = env.get("cautions")
    if isinstance(env_cautions, list) and env_cautions:
        env_block["cautions"] = list(env_cautions)

    recs: List[Dict[str, Any]] = []
    for i, x in enumerate(top):
        row = {
            **x,
            "rank": i + 1,
            "allocation_pct": alloc_pct,
            "explain_bullets": _explain_bullets_for_row(x, env_gate=gate_name),
        }
        if gate_name == "STOP":
            cautions = row.get("cautions")
            if not isinstance(cautions, list):
                cautions = []
                row["cautions"] = cautions
            if "rotation_paused_env_stop" not in cautions:
                cautions.append("rotation_paused_env_stop")
        recs.append(row)

    quality = "ok"
    if (rps20.get("quality_status") != "ok") or (rps5.get("quality_status") != "ok"):
        quality = "degraded"

    return {
        "success": True,
        "message": "sector rotation recommend ok",
        "quality_status": quality,
        "_meta": {
            "schema_name": "decision_sector_rotation_recommendations_v1",
            "schema_version": "1.0.0",
            "task_id": "etf-rotation-research",
            "run_id": _now_run_id(),
            "data_layer": "L3",
            "generated_at": datetime.now().isoformat(),
            "trade_date": td,
            "source_tools": ["tool_fetch_market_data"],
            "lineage_refs": [],
            "quality_status": quality,
        },
        "data": {
            "trade_date": td,
            "environment": env_block,
            "recommendations": recs,
            "universe": {"count": len(items), "mappings": [asdict(m) for m in mappings]},
            "fundamentals_lane": {
                "quality_status": "degraded",
                "reason_code": "fundamental_data_unavailable",
                "message": "基本面因子尚未接通可靠数据源；不做硬填或替代指标。",
            },
        },
    }

