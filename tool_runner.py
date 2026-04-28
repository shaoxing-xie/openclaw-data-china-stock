#!/usr/bin/env python3
"""
OpenClaw工具调用脚本
通过命令行参数调用不同的工具函数
从本地目录导入工具并执行
"""

import sys
import json
import os
from pathlib import Path
import io
from contextlib import redirect_stdout, redirect_stderr
from typing import Any, Callable, Dict, Optional, Type

from pydantic import BaseModel, ValidationError

# 始终使用当前脚本所在目录作为项目根，保证可导入 src / plugins
project_root = Path(__file__).parent
plugins_dir = project_root / "plugins"
if plugins_dir.exists():
    sys.path.insert(0, str(plugins_dir))
sys.path.insert(0, str(project_root))


def _read_plugin_version() -> str:
    try:
        p = project_root / "openclaw.plugin.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        return str(data.get("version") or "0.0.0")
    except Exception:
        return "0.0.0"


def _load_dotenv_for_tools() -> None:
    """
    与 OpenClaw Gateway 对齐：从项目根 .env 与 ~/.openclaw/.env 注入环境变量。
    使用 plugins/utils/env_loader：无 python-dotenv 时仍可解析 KEY=VALUE。
    override=False：已在 shell 中 export 的值优先。
    """
    try:
        from utils.env_loader import load_env_file
    except ImportError:
        return
    # 独立插件只加载本仓库根 `.env`，避免污染/依赖主项目平台环境（如 `~/.openclaw/.env`）
    load_env_file(project_root / ".env", override=False)


_load_dotenv_for_tools()


def _apply_market_data_proxy_policy() -> None:
    """
    统一代理策略总闸（兼容开关）：
    - 代理决策由 plugins.utils.proxy_env + config.yaml(network.proxy) 按 source 控制。
    - 这里不再默认清理全局代理环境变量，避免影响非 market-data 调用与并发行为。

    控制方式：
    - OPENCLAW_DISABLE_PROXY_FOR_MARKET_DATA=1/true/on/yes -> 由 source 策略层强制 bypass（见 proxy_env.resolve_proxy_policy）
    - OPENCLAW_DISABLE_PROXY_FOR_MARKET_DATA=0/false/off/no 或未设置 -> 使用配置文件 network.proxy.* 策略
    """
    # No-op by design; kept for backward compatibility and discoverability.
    return


_apply_market_data_proxy_policy()

# 旧工具名 -> (新工具名, 注入参数) 用于兼容 cron/工作流
ALIASES = {
    "tool_fetch_index_realtime": ("tool_fetch_index_data", {"data_type": "realtime"}),
    "tool_fetch_index_historical": ("tool_fetch_index_data", {"data_type": "historical"}),
    "tool_fetch_index_minute": ("tool_fetch_index_data", {"data_type": "minute"}),
    "tool_fetch_index_opening": ("tool_fetch_index_data", {"data_type": "opening"}),
    "tool_fetch_global_index_spot": ("tool_fetch_index_data", {"data_type": "global_spot"}),
    "tool_fetch_etf_realtime": ("tool_fetch_etf_data", {"data_type": "realtime"}),
    "tool_fetch_etf_historical": ("tool_fetch_etf_data", {"data_type": "historical"}),
    # ETF 分钟数据改为走 plugins.data_collection.etf.fetch_minute（新浪优先），而不是 akshare-only
    "tool_fetch_etf_minute": ("tool_fetch_etf_minute_direct", {}),
    "tool_fetch_option_realtime": ("tool_fetch_option_data", {"data_type": "realtime"}),
    "tool_fetch_option_greeks": ("tool_fetch_option_data", {"data_type": "greeks"}),
    "tool_fetch_option_minute": ("tool_fetch_option_data", {"data_type": "minute"}),
    "tool_read_index_daily": ("tool_read_market_data", {"data_type": "index_daily"}),
    "tool_read_index_minute": ("tool_read_market_data", {"data_type": "index_minute"}),
    "tool_read_etf_daily": ("tool_read_market_data", {"data_type": "etf_daily"}),
    "tool_read_etf_minute": ("tool_read_market_data", {"data_type": "etf_minute"}),
    "tool_read_option_minute": ("tool_read_market_data", {"data_type": "option_minute"}),
    "tool_read_option_greeks": ("tool_read_market_data", {"data_type": "option_greeks"}),
    "tool_send_feishu_message": ("tool_send_feishu_notification", {"notification_type": "message"}),
    "tool_send_signal_alert": ("tool_send_feishu_notification", {"notification_type": "signal_alert"}),
    # 市场日报也走钉钉（兼容旧工具名）：复用 tool_send_analysis_report 的 SEC 加签与关键词校验
    "tool_send_daily_report": ("tool_send_analysis_report", {}),
    "tool_send_risk_alert": ("tool_send_feishu_notification", {"notification_type": "risk_alert"}),
    "tool_analyze_after_close": ("tool_analyze_market", {"moment": "after_close"}),
    "tool_analyze_before_open": ("tool_analyze_market", {"moment": "before_open"}),
    "tool_analyze_opening_market": ("tool_analyze_market", {"moment": "opening"}),
    "tool_predict_volatility": ("tool_volatility", {"mode": "predict"}),
    "tool_calculate_historical_volatility": ("tool_volatility", {"mode": "historical"}),
    "tool_calculate_position_size": ("tool_position_limit", {"action": "calculate"}),
    "tool_check_position_limit": ("tool_position_limit", {"action": "check"}),
    "tool_apply_hard_limit": ("tool_position_limit", {"action": "apply"}),
    "tool_calculate_stop_loss_take_profit": ("tool_stop_loss_take_profit", {"action": "calculate"}),
    "tool_check_stop_loss_take_profit": ("tool_stop_loss_take_profit", {"action": "check"}),
    "tool_get_strategy_performance": ("tool_strategy_analytics", {"action": "performance"}),
    "tool_calculate_strategy_score": ("tool_strategy_analytics", {"action": "score"}),
    "tool_get_strategy_weights": ("tool_strategy_weights", {"action": "get"}),
    "tool_adjust_strategy_weights": ("tool_strategy_weights", {"action": "adjust"}),
    # 股票行情工具（直接映射到 plugins.data_collection.stock）
    "tool_fetch_stock_historical": ("tool_fetch_stock_historical", {}),
    "tool_fetch_stock_minute": ("tool_fetch_stock_minute", {}),
    "tool_fetch_stock_realtime": ("tool_fetch_stock_realtime", {}),
    "tool_fetch_etf_iopv_snapshot": ("tool_fetch_etf_iopv_snapshot", {}),
    "tool_fetch_cni_index_daily": ("tool_fetch_cni_index_daily", {}),
    "tool_fetch_csindex_index_daily": ("tool_fetch_csindex_index_daily", {}),
}

class TradingCopilotParams(BaseModel):
    focus_etfs: Optional[str] = None
    focus_stocks: Optional[str] = None
    mode: Optional[str] = "normal"
    run_signal: Optional[bool] = False
    signal_etf: Optional[str] = None
    throttle_minutes: Optional[int] = 5
    timezone: Optional[str] = "Asia/Shanghai"
    disable_network_fetch: Optional[bool] = False
    output_format: Optional[str] = "feishu_card"
    include_snapshot: Optional[bool] = False
    send_feishu_card: Optional[bool] = False
    feishu_webhook_url: Optional[str] = None


class ToolSpec(BaseModel):
    module_path: str
    function_name: str
    params_model: Optional[Type[BaseModel]] = None
    """调用前将参数名从 key 映射为 value，例如 underlying -> symbol"""
    param_mapping: Optional[Dict[str, str]] = None


# 统一错误码（供 Agent/工作流分支处理）
TOOL_ERROR_CODES = {
    "VALIDATION_ERROR": "参数校验失败",
    "UNKNOWN_TOOL": "未知工具",
    "IMPORT_ERROR": "导入错误",
    "RUNTIME_ERROR": "执行异常",
}


# 工具函数映射（合并后 21 个主工具 + 未合并的保留）
TOOL_MAP: Dict[str, ToolSpec] = {
    # 合并工具 - 数据采集
    "tool_fetch_index_data": ToolSpec(
        module_path="merged.fetch_index_data",
        function_name="tool_fetch_index_data",
    ),
    "tool_fetch_etf_data": ToolSpec(
        module_path="merged.fetch_etf_data",
        function_name="tool_fetch_etf_data",
    ),
    # 直连版 ETF 分钟数据（新浪优先 + 东方财富 + 可选缓存）
    "tool_fetch_etf_minute_direct": ToolSpec(
        module_path="plugins.data_collection.etf.fetch_minute",
        function_name="tool_fetch_etf_minute",
    ),
    "tool_fetch_option_data": ToolSpec(
        module_path="merged.fetch_option_data",
        function_name="tool_fetch_option_data",
    ),
    # 跨资产统一入口（推荐）
    "tool_fetch_market_data": ToolSpec(
        module_path="data.fetch_market_data",
        function_name="tool_fetch_market_data",
    ),
    # 数据采集 - 期货与工具（保留）
    "tool_fetch_a50_data": ToolSpec(
        module_path="plugins.data_collection.futures.fetch_a50",
        function_name="tool_fetch_a50_data",
    ),
    "tool_fetch_etf_iopv_snapshot": ToolSpec(
        module_path="plugins.data_collection.etf.fetch_realtime",
        function_name="tool_fetch_etf_iopv_snapshot",
    ),
    "tool_fetch_cni_index_daily": ToolSpec(
        module_path="plugins.data_collection.index.fetch_cni_daily",
        function_name="tool_fetch_cni_index_daily",
    ),
    "tool_fetch_csindex_index_daily": ToolSpec(
        module_path="plugins.data_collection.index.fetch_csindex_daily",
        function_name="tool_fetch_csindex_index_daily",
    ),
    "tool_get_option_contracts": ToolSpec(
        module_path="plugins.data_collection.utils.get_contracts",
        function_name="tool_get_option_contracts",
    ),
    "tool_check_trading_status": ToolSpec(
        module_path="plugins.data_collection.utils.check_trading_status",
        function_name="tool_check_trading_status",
    ),
    "tool_get_a_share_market_regime": ToolSpec(
        module_path="plugins.data_collection.utils.a_share_market_regime",
        function_name="tool_get_a_share_market_regime",
    ),
    "tool_filter_a_share_tradability": ToolSpec(
        module_path="plugins.data_collection.utils.a_share_tradability_filter",
        function_name="tool_filter_a_share_tradability",
    ),
    # Copilot（编排入口）
    "tool_trading_copilot": ToolSpec(
        module_path="copilot.trading_copilot",
        function_name="tool_trading_copilot",
        params_model=TradingCopilotParams,
    ),
    # 事件哨兵
    "tool_event_sentinel": ToolSpec(
        module_path="sentinel.event_sentinel",
        function_name="tool_event_sentinel",
    ),
    # 飞书交互卡片（webhook）
    "tool_send_feishu_card_webhook": ToolSpec(
        module_path="notification.send_feishu_card_webhook",
        function_name="tool_send_feishu_card_webhook",
    ),
    # 合并工具 - 数据访问
    "tool_read_market_data": ToolSpec(
        module_path="data.read_market_data",
        function_name="tool_read_market_data",
    ),
    "tool_metrics_snapshot": ToolSpec(
        module_path="plugins.utils.tool_metrics",
        function_name="tool_metrics_snapshot",
    ),
    "tool_batch_fetch": ToolSpec(
        module_path="merged.tool_batch_fetch",
        function_name="tool_batch_fetch",
    ),
    # 分析工具（保留）
    "tool_calculate_technical_indicators": ToolSpec(
        module_path="plugins.data_collection.tools.tool_calculate_technical_indicators",
        function_name="tool_calculate_technical_indicators",
    ),
    "tool_generate_signals": ToolSpec(
        module_path="src.signal_generation",
        function_name="tool_generate_signals",
    ),
    "tool_assess_risk": ToolSpec(
        module_path="analysis.risk_assessment",
        function_name="tool_assess_risk",
    ),
    "tool_predict_intraday_range": ToolSpec(
        module_path="analysis.intraday_range",
        function_name="tool_predict_intraday_range",
        param_mapping={"underlying": "symbol"},
    ),
    # 合并工具 - 分析
    "tool_analyze_market": ToolSpec(
        module_path="merged.analyze_market",
        function_name="tool_analyze_market",
    ),
    "tool_volatility": ToolSpec(
        module_path="merged.volatility",
        function_name="tool_volatility",
    ),
    # ETF趋势（保留）
    "tool_check_etf_index_consistency": ToolSpec(
        module_path="analysis.etf_trend_tracking",
        function_name="tool_check_etf_index_consistency",
    ),
    "tool_generate_trend_following_signal": ToolSpec(
        module_path="analysis.etf_trend_tracking",
        function_name="tool_generate_trend_following_signal",
    ),
    "tool_strategy_engine": ToolSpec(
        module_path="strategy_engine.tool_strategy_engine",
        function_name="tool_strategy_engine",
    ),
    # Market Regime / Research
    "tool_detect_market_regime": ToolSpec(
        module_path="analysis.market_regime",
        function_name="tool_detect_market_regime",
    ),
    "tool_etf_rotation_research": ToolSpec(
        module_path="plugins.analysis.etf_rotation_research",
        function_name="tool_etf_rotation_research",
    ),
    "tool_fetch_sector_constituents": ToolSpec(
        module_path="plugins.analysis.sector_constituents",
        function_name="tool_fetch_sector_constituents",
    ),
    "tool_calculate_sector_breadth": ToolSpec(
        module_path="plugins.analysis.sector_breadth",
        function_name="tool_calculate_sector_breadth",
    ),
    "tool_calculate_sector_leadership": ToolSpec(
        module_path="plugins.analysis.sector_leadership",
        function_name="tool_calculate_sector_leadership",
    ),
    "tool_fetch_etf_share": ToolSpec(
        module_path="plugins.analysis.etf_share",
        function_name="tool_fetch_etf_share",
    ),
    "tool_calculate_share_trend": ToolSpec(
        module_path="plugins.analysis.etf_share",
        function_name="tool_calculate_share_trend",
    ),
    "tool_calculate_sector_momentum_v2": ToolSpec(
        module_path="plugins.analysis.sector_momentum_v2",
        function_name="tool_calculate_sector_momentum_v2",
    ),
    "tool_strategy_research": ToolSpec(
        module_path="analysis.strategy_research",
        function_name="tool_strategy_research",
    ),
    "tool_get_strategy_research_history": ToolSpec(
        module_path="analysis.strategy_research",
        function_name="tool_get_strategy_research_history",
    ),
    # 合并工具 - 风险控制
    "tool_position_limit": ToolSpec(
        module_path="merged.position_limit",
        function_name="tool_position_limit",
    ),
    "tool_stop_loss_take_profit": ToolSpec(
        module_path="merged.stop_loss_take_profit",
        function_name="tool_stop_loss_take_profit",
    ),
    # 策略效果（保留 + 合并）
    "tool_record_signal_effect": ToolSpec(
        module_path="analysis.strategy_tracker",
        function_name="tool_record_signal_effect",
    ),
    "tool_strategy_analytics": ToolSpec(
        module_path="merged.strategy_analytics",
        function_name="tool_strategy_analytics",
    ),
    "tool_strategy_weights": ToolSpec(
        module_path="merged.strategy_weights",
        function_name="tool_strategy_weights",
    ),
    # 合并工具 - 通知
    "tool_send_feishu_notification": ToolSpec(
        module_path="merged.send_feishu_notification",
        function_name="tool_send_feishu_notification",
    ),
    # 通知（钉钉）
    "tool_send_dingtalk_message": ToolSpec(
        module_path="notification.send_dingtalk_message",
        function_name="tool_send_dingtalk_message",
    ),
    # 分析类报告（钉钉发送，替代 flyish 报日）
    "tool_send_analysis_report": ToolSpec(
        module_path="notification.send_analysis_report",
        function_name="tool_send_analysis_report",
    ),
    # 股票行情
    "tool_fetch_stock_historical": ToolSpec(
        module_path="plugins.data_collection.stock.fetch_historical",
        function_name="tool_fetch_stock_historical",
    ),
    "tool_fetch_stock_minute": ToolSpec(
        module_path="plugins.data_collection.stock.fetch_minute",
        function_name="tool_fetch_stock_minute",
    ),
    "tool_fetch_stock_realtime": ToolSpec(
        module_path="plugins.data_collection.stock.fetch_realtime",
        function_name="tool_fetch_stock_realtime",
    ),
    # 个股数据聚合
    "tool_stock_data_fetcher": ToolSpec(
        module_path="plugins.data_collection.stock.stock_data_fetcher",
        function_name="tool_stock_data_fetcher",
    ),
    "tool_stock_monitor": ToolSpec(
        module_path="plugins.data_collection.stock.stock_data_fetcher",
        function_name="tool_stock_monitor",
    ),
    # 涨停回马枪 - 数据与回测
    "tool_fetch_limit_up_stocks": ToolSpec(
        module_path="plugins.data_collection.limit_up.fetch_limit_up",
        function_name="tool_fetch_limit_up_stocks",
    ),
    "tool_sector_heat_score": ToolSpec(
        module_path="plugins.data_collection.limit_up.sector_heat",
        function_name="tool_sector_heat_score",
    ),
    "tool_write_limit_up_with_sector": ToolSpec(
        module_path="plugins.data_collection.limit_up.daily_report",
        function_name="tool_write_limit_up_with_sector",
    ),
    "tool_limit_up_daily_flow": ToolSpec(
        module_path="plugins.data_collection.limit_up.daily_report",
        function_name="tool_limit_up_daily_flow",
    ),
    # 涨停回马枪相关技能封装
    "tool_dragon_tiger_list": ToolSpec(
        module_path="plugins.data_collection.dragon_tiger",
        function_name="tool_dragon_tiger_list",
    ),
    "tool_capital_flow": ToolSpec(
        module_path="plugins.data_collection.capital_flow",
        function_name="tool_capital_flow",
    ),
    "tool_fetch_northbound_flow": ToolSpec(
        module_path="plugins.data_collection.northbound",
        function_name="tool_fetch_northbound_flow",
    ),
    "tool_fetch_a_share_fund_flow": ToolSpec(
        module_path="plugins.data_collection.a_share_fund_flow",
        function_name="tool_fetch_a_share_fund_flow",
    ),
    "tool_fetch_a_share_technical_screener": ToolSpec(
        module_path="plugins.data_collection.a_share_technical_screener",
        function_name="tool_fetch_a_share_technical_screener",
    ),
    "tool_fetch_policy_news": ToolSpec(
        module_path="plugins.data_collection.morning_brief_fetchers",
        function_name="tool_fetch_policy_news",
    ),
    "tool_fetch_macro_commodities": ToolSpec(
        module_path="plugins.data_collection.morning_brief_fetchers",
        function_name="tool_fetch_macro_commodities",
    ),
    "tool_fetch_overnight_futures_digest": ToolSpec(
        module_path="plugins.data_collection.morning_brief_fetchers",
        function_name="tool_fetch_overnight_futures_digest",
    ),
    "tool_conditional_overnight_futures_digest": ToolSpec(
        module_path="plugins.data_collection.morning_brief_fetchers",
        function_name="tool_conditional_overnight_futures_digest",
    ),
    "tool_fetch_announcement_digest": ToolSpec(
        module_path="plugins.data_collection.morning_brief_fetchers",
        function_name="tool_fetch_announcement_digest",
    ),
    # Macro (unified + compatibility wrappers)
    "tool_fetch_macro_data": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_data",
    ),
    "tool_fetch_macro_snapshot": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_snapshot",
    ),
    "tool_fetch_macro_pmi": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_pmi",
    ),
    "tool_fetch_macro_cx_pmi": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_cx_pmi",
    ),
    "tool_fetch_macro_cx_services_pmi": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_cx_services_pmi",
    ),
    "tool_fetch_macro_enterprise_boom": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_enterprise_boom",
    ),
    "tool_fetch_macro_lpi": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_lpi",
    ),
    "tool_fetch_macro_cpi": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_cpi",
    ),
    "tool_fetch_macro_ppi": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_ppi",
    ),
    "tool_fetch_macro_m2": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_m2",
    ),
    "tool_fetch_macro_social_financing": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_social_financing",
    ),
    "tool_fetch_macro_new_credit": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_new_credit",
    ),
    "tool_fetch_macro_lpr": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_lpr",
    ),
    "tool_fetch_macro_fx_reserves": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_fx_reserves",
    ),
    "tool_fetch_macro_gdp": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_gdp",
    ),
    "tool_fetch_macro_industrial_value": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_industrial_value",
    ),
    "tool_fetch_macro_fixed_asset": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_fixed_asset",
    ),
    "tool_fetch_macro_leverage": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_leverage",
    ),
    "tool_fetch_macro_exports_imports": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_exports_imports",
    ),
    "tool_fetch_macro_trade_balance": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_trade_balance",
    ),
    "tool_fetch_macro_exports_yoy": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_exports_yoy",
    ),
    "tool_fetch_macro_unemployment": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_unemployment",
    ),
    "tool_fetch_macro_tax_receipts": ToolSpec(
        module_path="plugins.data_collection.macro.tools",
        function_name="tool_fetch_macro_tax_receipts",
    ),
    "tool_fetch_industry_news_brief": ToolSpec(
        module_path="plugins.data_collection.morning_brief_fetchers",
        function_name="tool_fetch_industry_news_brief",
    ),
    "tool_overnight_calibration": ToolSpec(
        module_path="plugins.analysis.overnight_calibration",
        function_name="tool_overnight_calibration",
    ),
    "tool_build_limitup_scenarios": ToolSpec(
        module_path="plugins.analysis.scenario_analysis",
        function_name="tool_build_limitup_scenarios",
    ),
    "tool_compute_index_key_levels": ToolSpec(
        module_path="plugins.analysis.key_levels",
        function_name="tool_compute_index_key_levels",
    ),
    "tool_record_before_open_prediction": ToolSpec(
        module_path="plugins.analysis.accuracy_tracker",
        function_name="tool_record_before_open_prediction",
    ),
    "tool_get_yesterday_prediction_review": ToolSpec(
        module_path="plugins.analysis.accuracy_tracker",
        function_name="tool_get_yesterday_prediction_review",
    ),
    "tool_record_limitup_watch_outcome": ToolSpec(
        module_path="plugins.analysis.accuracy_tracker",
        function_name="tool_record_limitup_watch_outcome",
    ),
    "tool_fetch_sector_data": ToolSpec(
        module_path="plugins.data_collection.sector",
        function_name="tool_fetch_sector_data",
    ),
    "tool_fetch_stock_financials": ToolSpec(
        module_path="plugins.data_collection.financials",
        function_name="tool_fetch_stock_financials",
    ),
    "tool_fetch_a_share_universe": ToolSpec(
        module_path="plugins.data_collection.stock.fundamentals_extended",
        function_name="tool_fetch_a_share_universe",
    ),
    "tool_fetch_stock_financial_reports": ToolSpec(
        module_path="plugins.data_collection.stock.fundamentals_extended",
        function_name="tool_fetch_stock_financial_reports",
    ),
    "tool_fetch_stock_corporate_actions": ToolSpec(
        module_path="plugins.data_collection.stock.fundamentals_extended",
        function_name="tool_fetch_stock_corporate_actions",
    ),
    "tool_fetch_margin_trading": ToolSpec(
        module_path="plugins.data_collection.stock.fundamentals_extended",
        function_name="tool_fetch_margin_trading",
    ),
    "tool_fetch_block_trades": ToolSpec(
        module_path="plugins.data_collection.stock.fundamentals_extended",
        function_name="tool_fetch_block_trades",
    ),
    "tool_fetch_stock_shareholders": ToolSpec(
        module_path="plugins.data_collection.stock.reference_p1",
        function_name="tool_fetch_stock_shareholders",
    ),
    "tool_fetch_ipo_calendar": ToolSpec(
        module_path="plugins.data_collection.stock.reference_p1",
        function_name="tool_fetch_ipo_calendar",
    ),
    "tool_fetch_index_constituents": ToolSpec(
        module_path="plugins.data_collection.stock.reference_p1",
        function_name="tool_fetch_index_constituents",
    ),
    "tool_fetch_stock_research_news": ToolSpec(
        module_path="plugins.data_collection.stock.reference_p1",
        function_name="tool_fetch_stock_research_news",
    ),
    "tool_screen_equity_factors": ToolSpec(
        module_path="plugins.analysis.equity_factor_screening",
        function_name="tool_screen_equity_factors",
    ),
    # 回测
    "tool_backtest_limit_up_pullback": ToolSpec(
        module_path="backtest.limit_up_pullback",
        function_name="tool_backtest_limit_up_pullback",
    ),
    "tool_backtest_limit_up_sensitivity": ToolSpec(
        module_path="backtest.limit_up_pullback",
        function_name="tool_backtest_limit_up_sensitivity",
    ),
    "tool_backtest_etf_rotation": ToolSpec(
        module_path="backtest.etf_rotation_backtest",
        function_name="tool_backtest_etf_rotation",
    ),
    # 组合风险（VaR / 回撤 / 仓位）
    "tool_portfolio_risk_snapshot": ToolSpec(
        module_path="risk.portfolio_risk_snapshot",
        function_name="tool_portfolio_risk_snapshot",
    ),
    "tool_compliance_rules_check": ToolSpec(
        module_path="risk.institutional_risk",
        function_name="tool_compliance_rules_check",
    ),
    "tool_stop_loss_lines_check": ToolSpec(
        module_path="risk.institutional_risk",
        function_name="tool_stop_loss_lines_check",
    ),
    "tool_stress_test_linear_scenarios": ToolSpec(
        module_path="risk.institutional_risk",
        function_name="tool_stress_test_linear_scenarios",
    ),
    "tool_risk_attribution_stub": ToolSpec(
        module_path="risk.institutional_risk",
        function_name="tool_risk_attribution_stub",
    ),
}

def main():
    if len(sys.argv) < 2:
        print(
            json.dumps(
                {
                    "error": "缺少工具名称",
                    "usage": "python3 tool_runner.py <tool_name> [args_json|@path/to/args.json]",
                }
            )
        )
        sys.exit(1)

    tool_name = sys.argv[1]
    args_json = sys.argv[2] if len(sys.argv) > 2 else "{}"
    if isinstance(args_json, str) and args_json.startswith("@"):
        arg_path = Path(args_json[1:]).expanduser()
        if not arg_path.is_file():
            print(json.dumps({"error": f"参数文件不存在: {arg_path}"}, ensure_ascii=False))
            sys.exit(1)
        args_json = arg_path.read_text(encoding="utf-8")

    # 解析参数
    try:
        args = json.loads(args_json) if args_json else {}
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"参数JSON格式错误: {e}"}))
        sys.exit(1)
    
    # 别名解析：旧工具名 -> 新工具名 + 注入参数（兼容 cron/工作流）
    if tool_name in ALIASES:
        new_name, inject = ALIASES[tool_name]
        args = {**inject, **args}
        tool_name = new_name
    
    # 查找工具
    if tool_name not in TOOL_MAP:
        print(
            json.dumps(
                {
                    "error": f"未知工具: {tool_name}",
                    "error_code": TOOL_ERROR_CODES["UNKNOWN_TOOL"],
                    "available_tools": list(TOOL_MAP.keys()),
                },
                ensure_ascii=False,
            )
        )
        sys.exit(1)

    spec = TOOL_MAP[tool_name]
    module_path, function_name = spec.module_path, spec.function_name

    log_tool_exec = os.environ.get("OPTION_TRADING_ASSISTANT_LOG_TOOL_EXEC", "").strip() in ("1", "true", "yes")
    import time as _time

    t0 = _time.perf_counter()

    def _elapsed_ms() -> int:
        return int(round((_time.perf_counter() - t0) * 1000))

    def _envelope(dst: Dict[str, Any], *, ok: bool) -> Dict[str, Any]:
        dst.setdefault("elapsed_ms", _elapsed_ms())
        dst.setdefault("tool", tool_name)
        dst.setdefault("plugin_version", _read_plugin_version())
        try:
            from plugins.utils.tool_metrics import record_tool_call

            record_tool_call(tool_name, int(dst.get("elapsed_ms") or _elapsed_ms()), ok=ok)
        except Exception:
            pass
        return dst

    buf_out = io.StringIO()
    buf_err = io.StringIO()
    try:
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            module = __import__(module_path, fromlist=[function_name])
            tool_func: Callable[..., Any] = getattr(module, function_name)

            if spec.params_model is not None:
                try:
                    model_instance = spec.params_model(**args)
                    args = model_instance.model_dump()
                except ValidationError as ve:
                    payload = _envelope(
                        {
                            "error": "参数校验失败",
                            "error_code": "VALIDATION_ERROR",
                            "details": json.loads(ve.json()),
                        },
                        ok=False,
                    )
                    print(json.dumps(payload, ensure_ascii=False))
                    sys.exit(1)

            if spec.param_mapping:
                for from_key, to_key in spec.param_mapping.items():
                    if from_key in args:
                        args[to_key] = args.pop(from_key)

            result = tool_func(**args)

        if log_tool_exec:
            import logging

            logging.getLogger(__name__).info(
                "tool_exec %s duration_ms=%d success=true", tool_name, _elapsed_ms()
            )
        ok = True
        if isinstance(result, dict):
            ok = bool(result.get("success", True))
            _envelope(result, ok=ok)
        else:
            try:
                from plugins.utils.tool_metrics import record_tool_call

                record_tool_call(tool_name, _elapsed_ms(), ok=True)
            except Exception:
                pass
        print(json.dumps(result, ensure_ascii=False, default=str))
    except ImportError as e:
        if log_tool_exec:
            import logging

            logging.getLogger(__name__).info(
                "tool_exec %s duration_ms=%d success=false error_code=IMPORT_ERROR", tool_name, _elapsed_ms()
            )
        payload = {
            "error": f"导入错误: {e}",
            "error_code": TOOL_ERROR_CODES["IMPORT_ERROR"],
            "module": module_path,
            "function": function_name,
        }
        if buf_out.getvalue().strip():
            payload["captured_stdout"] = buf_out.getvalue()[-2000:]
        if buf_err.getvalue().strip():
            payload["captured_stderr"] = buf_err.getvalue()[-2000:]
        _envelope(payload, ok=False)
        print(json.dumps(payload, ensure_ascii=False, default=str))
        sys.exit(1)
    except Exception as e:
        if log_tool_exec:
            import logging

            logging.getLogger(__name__).info(
                "tool_exec %s duration_ms=%d success=false error_code=RUNTIME_ERROR", tool_name, _elapsed_ms()
            )
        payload = {
            "error": str(e),
            "error_code": TOOL_ERROR_CODES["RUNTIME_ERROR"],
            "type": type(e).__name__,
        }
        if buf_out.getvalue().strip():
            payload["captured_stdout"] = buf_out.getvalue()[-2000:]
        if buf_err.getvalue().strip():
            payload["captured_stderr"] = buf_err.getvalue()[-2000:]
        _envelope(payload, ok=False)
        print(json.dumps(payload, ensure_ascii=False, default=str))
        sys.exit(1)

if __name__ == "__main__":
    main()
