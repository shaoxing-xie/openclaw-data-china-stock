"""
跨资产统一入口（MVP）

将 asset_type + view 统一映射到已有的 merged/index/etf/option 工具。
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def tool_fetch_market_data(
    asset_type: str,
    view: str,
    asset_code: Optional[str] = "",
    contract_code: Optional[str] = "",
    period: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    lookback_days: int = 5,
    mode: str = "production",
    **kwargs: Any,
) -> Dict[str, Any]:
    asset_type_n = _norm(asset_type)
    view_n = _norm(view)
    asset_code = (asset_code or "").strip()
    contract_code = (contract_code or "").strip()
    mode = mode or "production"

    if not asset_type_n:
        return {"success": False, "message": "缺少 asset_type", "data": None}
    if not view_n:
        return {"success": False, "message": "缺少 view", "data": None}

    # -------- index --------
    if asset_type_n == "index":
        from plugins.merged.fetch_index_data import tool_fetch_index_data

        if view_n in ("realtime", "historical", "minute", "opening", "global_spot"):
            index_code = asset_code or "000001"
            if view_n == "historical":
                # historical 的 period 语义是 daily/weekly/monthly；这里做一层容错。
                period_v = period or "daily"
                if period_v.isdigit():
                    period_v = "daily"
                return tool_fetch_index_data(
                    data_type="historical",
                    index_code=index_code,
                    period=period_v,
                    start_date=start_date,
                    end_date=end_date,
                    lookback_days=lookback_days,
                    mode=mode,
                )
            if view_n == "minute":
                period_v = period or "5"
                return tool_fetch_index_data(
                    data_type="minute",
                    index_code=index_code,
                    period=period_v,
                    start_date=start_date,
                    end_date=end_date,
                    lookback_days=lookback_days,
                    mode=mode,
                )
            if view_n == "opening":
                return tool_fetch_index_data(
                    data_type="opening",
                    index_code=index_code,
                    index_codes=asset_code,
                    mode=mode,
                )
            if view_n == "global_spot":
                return tool_fetch_index_data(
                    data_type="global_spot",
                    index_code=index_code,
                    index_codes=asset_code,
                )
            # realtime
            return tool_fetch_index_data(
                data_type=view_n,
                index_code=index_code,
                mode=mode,
            )

        return {"success": False, "message": f"不支持 index.view={view}", "data": None}

    # -------- etf --------
    if asset_type_n == "etf":
        if view_n == "iopv_snapshot":
            if not asset_code:
                asset_code = "510300"
            from plugins.data_collection.etf.fetch_realtime import tool_fetch_etf_iopv_snapshot

            return tool_fetch_etf_iopv_snapshot(etf_code=asset_code)

        from plugins.merged.fetch_etf_data import tool_fetch_etf_data

        if view_n in ("realtime", "historical", "minute"):
            etf_code = asset_code or "510300"
            if view_n == "historical":
                period_v = period or "daily"
                if period_v.isdigit():
                    period_v = "daily"
                return tool_fetch_etf_data(
                    data_type="historical",
                    etf_code=etf_code,
                    period=period_v,
                    start_date=start_date,
                    end_date=end_date,
                    lookback_days=lookback_days,
                )
            if view_n == "minute":
                period_v = period or "5"
                return tool_fetch_etf_data(
                    data_type="minute",
                    etf_code=etf_code,
                    period=period_v,
                    start_date=start_date,
                    end_date=end_date,
                    lookback_days=lookback_days,
                )
            # realtime
            return tool_fetch_etf_data(data_type="realtime", etf_code=etf_code, mode=mode)

        return {"success": False, "message": f"不支持 etf.view={view}", "data": None}

    # -------- option --------
    if asset_type_n == "option":
        if not contract_code:
            return {"success": False, "message": "缺少 contract_code", "data": None}

        from plugins.merged.fetch_option_data import tool_fetch_option_data

        if view_n in ("realtime", "greeks", "minute"):
            if view_n == "minute":
                period_v = period or "15"
                return tool_fetch_option_data(
                    data_type="minute",
                    contract_code=contract_code,
                    period=period_v,
                    mode=mode,
                )
            return tool_fetch_option_data(
                data_type=view_n,
                contract_code=contract_code,
                mode=mode,
            )

        return {"success": False, "message": f"不支持 option.view={view}", "data": None}

    # -------- stock --------
    if asset_type_n == "stock":
        from plugins.data_collection.stock.fetch_realtime import tool_fetch_stock_realtime
        from plugins.data_collection.stock.fetch_historical import tool_fetch_stock_historical
        from plugins.data_collection.stock.fetch_minute import tool_fetch_stock_minute
        from plugins.data_collection.stock.fetch_realtime import tool_fetch_stock_realtime as _realtime

        if not asset_code:
            return {"success": False, "message": "缺少 asset_code（stock_code）", "data": None}

        if view_n == "realtime":
            return tool_fetch_stock_realtime(stock_code=asset_code, mode=mode, include_depth=True)
        if view_n == "historical":
            period_v = "daily"
            return tool_fetch_stock_historical(
                stock_code=asset_code,
                period=period_v,
                start_date=start_date,
                end_date=end_date,
                use_cache=True,
            )
        if view_n == "minute":
            period_v = period or "5"
            return tool_fetch_stock_minute(
                stock_code=asset_code,
                period=period_v,
                start_date=start_date,
                end_date=end_date,
                lookback_days=lookback_days,
                mode=mode,
                use_cache=True,
            )

        return {"success": False, "message": f"不支持 stock.view={view}", "data": None}

    return {"success": False, "message": f"不支持 asset_type={asset_type}", "data": None}

