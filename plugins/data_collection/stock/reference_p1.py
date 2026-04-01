"""
P1 参考类工具：股东持股、新股 IPO、指数成分、个股新闻/研报。

返回约定与 fundamentals_extended 一致；支持 provider_preference 调整多源顺序。
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd


@contextmanager
def _pandas_string_storage_python() -> Any:
    """
    AkShare news_stock.stock_news_em 等对全角空格使用 str.replace(..., regex=True)；
    Pandas 3 + pyarrow 字符串后端会触发 ArrowInvalid: invalid escape sequence \\u。
    临时改用 python 字符串存储可兼容。
    """
    opt = pd.options.mode
    key = "string_storage"
    old = getattr(opt, key, None)
    try:
        setattr(opt, key, "python")
        yield
    finally:
        if old is not None:
            setattr(opt, key, old)

from plugins.data_collection.utils.provider_preference import normalize_provider_preference, reorder_provider_chain

from plugins.data_collection.stock.fundamentals_extended import (
    _df_records,
    _err_payload,
    _norm_code_6,
    _ok_payload,
)

logger = logging.getLogger(__name__)


def _norm_index_code(raw: str) -> str:
    """
    中证/常用行情指数代码多为 6 位数字（如 000300、399001）。
    误粘贴多余位（如 00030010）时按纯数字前 6 位截断，避免各源无数据或 AkShare 内部异常。
    """
    s = (raw or "").strip()
    if not s:
        return ""
    if s.isdigit() and len(s) > 6:
        return s[:6]
    return s


try:
    import akshare as ak

    AKSHARE_AVAILABLE = True
except Exception:  # noqa: BLE001
    AKSHARE_AVAILABLE = False
    ak = None  # type: ignore[assignment]


def tool_fetch_stock_shareholders(
    stock_code: str,
    holder_kind: str = "top10",
    start_date: str = "20091227",
    end_date: str = "20991231",
    provider_preference: str = "auto",
    max_rows: int = 0,
) -> Dict[str, Any]:
    """
    股东与持股变动（AkShare）。

    holder_kind:
      - top10: 十大股东 stock_main_stock_holder
      - top10_float: 十大流通股东 stock_circulate_stock_holder
      - holder_count: 股东户数 stock_share_change_cninfo
      - holder_change_ths: 同花顺股东户数 stock_shareholder_change_ths
      - fund_holder: 基金持股 stock_fund_stock_holder
    """
    if not AKSHARE_AVAILABLE:
        return _err_payload("AkShare 未安装")

    kind = (holder_kind or "top10").strip().lower()
    code6 = _norm_code_6(stock_code)
    if not code6 or len(code6) != 6:
        return _err_payload("需要有效 6 位 stock_code")

    pref = normalize_provider_preference(provider_preference)

    # 多源：户数控 —— 巨潮与同花顺可选顺序
    if kind == "holder_count":

        def cninfo() -> pd.DataFrame:
            return ak.stock_share_change_cninfo(symbol=code6, start_date=start_date, end_date=end_date)  # type: ignore[union-attr]

        def ths() -> pd.DataFrame:
            return ak.stock_shareholder_change_ths(symbol=code6)  # type: ignore[union-attr]

        chain: List[Tuple[str, str, Callable[[], pd.DataFrame]]] = [
            ("cninfo", "stock_share_change_cninfo", cninfo),
            ("ths", "stock_shareholder_change_ths", ths),
        ]
        chain = reorder_provider_chain(pref, chain)
        attempts: Dict[str, int] = {}
        routes: List[str] = []
        last_err: Optional[str] = None
        for tag, name, fn in chain:
            try:
                attempts[name] = attempts.get(name, 0) + 1
                df = fn()
                routes.append(name)
                recs = _df_records(df, max_rows)
                return _ok_payload(recs, source="akshare", route=routes, attempts=attempts, count=len(recs))
            except Exception as e:  # noqa: BLE001
                last_err = str(e)
                logger.debug("%s failed: %s", name, e)
        return _err_payload(last_err or "股东户数数据源均失败")

    try:
        if kind == "top10":
            df = ak.stock_main_stock_holder(stock=code6)  # type: ignore[union-attr]
            name = "stock_main_stock_holder"
        elif kind == "top10_float":
            df = ak.stock_circulate_stock_holder(symbol=code6)  # type: ignore[union-attr]
            name = "stock_circulate_stock_holder"
        elif kind == "holder_change_ths":
            df = ak.stock_shareholder_change_ths(symbol=code6)  # type: ignore[union-attr]
            name = "stock_shareholder_change_ths"
        elif kind == "fund_holder":
            df = ak.stock_fund_stock_holder(symbol=code6)  # type: ignore[union-attr]
            name = "stock_fund_stock_holder"
        else:
            return _err_payload(
                f"不支持的 holder_kind={holder_kind}，请用 top10|top10_float|holder_count|holder_change_ths|fund_holder"
            )
        recs = _df_records(df, max_rows)
        return _ok_payload(recs, source="akshare", route=[name], attempts={name: 1}, count=len(recs))
    except Exception as e:  # noqa: BLE001
        _ = pref  # 预留与其他源扩展时复用
        return _err_payload(f"股东数据查询失败: {e}")


def tool_fetch_ipo_calendar(
    ipo_kind: str = "declare_em",
    stock_code: str = "",
    provider_preference: str = "auto",
    max_rows: int = 0,
) -> Dict[str, Any]:
    """
    新股 / IPO 相关结构化数据。

    ipo_kind:
      - declare_em: 首发申报企业 stock_ipo_declare_em
      - new_list_cninfo: 新股上市列表 stock_new_ipo_cninfo
      - review_em: 发审委 stock_ipo_review_em
      - tutor_em: 辅导名录 stock_ipo_tutor_em
      - stock_detail: 个股 IPO 资料 stock_ipo_info（需 stock_code）
      - stock_summary: 个股 IPO 摘要 stock_ipo_summary_cninfo（需 stock_code）
    """
    if not AKSHARE_AVAILABLE:
        return _err_payload("AkShare 未安装")

    kind = (ipo_kind or "declare_em").strip().lower()
    pref = normalize_provider_preference(provider_preference)

    no_code_kinds = {"declare_em", "new_list_cninfo", "review_em", "tutor_em"}
    if kind in no_code_kinds:
        fns: List[Tuple[str, str, Callable[[], pd.DataFrame]]] = []
        if kind == "declare_em":
            fns.append(("eastmoney", "stock_ipo_declare_em", lambda: ak.stock_ipo_declare_em()))  # type: ignore[union-attr]
        elif kind == "new_list_cninfo":
            fns.append(("cninfo", "stock_new_ipo_cninfo", lambda: ak.stock_new_ipo_cninfo()))  # type: ignore[union-attr]
        elif kind == "review_em":
            fns.append(("eastmoney", "stock_ipo_review_em", lambda: ak.stock_ipo_review_em()))  # type: ignore[union-attr]
        elif kind == "tutor_em":
            fns.append(("eastmoney", "stock_ipo_tutor_em", lambda: ak.stock_ipo_tutor_em()))  # type: ignore[union-attr]

        fns = reorder_provider_chain(pref, fns)
        attempts: Dict[str, int] = {}
        routes: List[str] = []
        last_err: Optional[str] = None
        for _tag, name, fn in fns:
            try:
                attempts[name] = attempts.get(name, 0) + 1
                df = fn()
                routes.append(name)
                recs = _df_records(df, max_rows)
                return _ok_payload(recs, source="akshare", route=routes, attempts=attempts, count=len(recs))
            except Exception as e:  # noqa: BLE001
                last_err = str(e)
        return _err_payload(last_err or "IPO 数据获取失败")

    code6 = _norm_code_6(stock_code)
    if not code6 or len(code6) != 6:
        return _err_payload("stock_detail / stock_summary 需要 stock_code")

    try:
        if kind == "stock_detail":
            df = ak.stock_ipo_info(stock=code6)  # type: ignore[union-attr]
            name = "stock_ipo_info"
        elif kind == "stock_summary":
            df = ak.stock_ipo_summary_cninfo(symbol=code6)  # type: ignore[union-attr]
            name = "stock_ipo_summary_cninfo"
        else:
            return _err_payload(
                f"不支持的 ipo_kind={ipo_kind}，请用 declare_em|new_list_cninfo|review_em|tutor_em|stock_detail|stock_summary"
            )
        recs = _df_records(df, max_rows)
        return _ok_payload(recs, source="akshare", route=[name], attempts={name: 1}, count=len(recs))
    except Exception as e:  # noqa: BLE001
        return _err_payload(f"IPO 查询失败: {e}")


def tool_fetch_index_constituents(
    index_code: str,
    include_weight: bool = False,
    provider_preference: str = "auto",
    max_rows: int = 0,
) -> Dict[str, Any]:
    """
    指数成份股；可选权重（中证 index_stock_cons_weight_csindex）。

    降级顺序（auto）：[权重?] → 中证成份 → 新浪 → 东财 index_stock_cons。
    """
    if not AKSHARE_AVAILABLE:
        return _err_payload("AkShare 未安装")

    raw = (index_code or "").strip()
    sym = _norm_index_code(raw)
    if not sym:
        return _err_payload("需要 index_code（如沪深300=000300、深证成指=399001）")
    if raw != sym:
        logger.info("index_code normalized: %r -> %r", raw, sym)

    pref = normalize_provider_preference(provider_preference)

    chain: List[Tuple[str, str, Callable[[], pd.DataFrame]]] = []
    if include_weight:
        chain.append(
            (
                "csindex",
                "index_stock_cons_weight_csindex",
                lambda: ak.index_stock_cons_weight_csindex(symbol=sym),  # type: ignore[union-attr]
            )
        )
    chain.extend(
        [
            (
                "csindex",
                "index_stock_cons_csindex",
                lambda: ak.index_stock_cons_csindex(symbol=sym),  # type: ignore[union-attr]
            ),
            ("sina", "index_stock_cons_sina", lambda: ak.index_stock_cons_sina(symbol=sym)),  # type: ignore[union-attr]
            ("eastmoney", "index_stock_cons", lambda: ak.index_stock_cons(symbol=sym)),  # type: ignore[union-attr]
        ]
    )
    chain = reorder_provider_chain(pref, chain)

    attempts: Dict[str, int] = {}
    routes: List[str] = []
    last_err: Optional[str] = None
    for _tag, name, fn in chain:
        try:
            attempts[name] = attempts.get(name, 0) + 1
            df = fn()
            if df is None or df.empty:
                raise ValueError("empty")
            routes.append(name)
            recs = _df_records(df, max_rows)
            return _ok_payload(recs, source="akshare", route=routes, attempts=attempts, count=len(recs))
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            logger.debug("%s failed: %s", name, e)
    return _err_payload(last_err or "指数成份获取失败（各源均无数据或异常）")


def tool_fetch_stock_research_news(
    content_kind: str = "news",
    stock_code: str = "600000",
    provider_preference: str = "auto",
    max_rows: int = 200,
) -> Dict[str, Any]:
    """
    个股新闻 / 研报（结构化）。

    content_kind:
      - news: 东财个股新闻 stock_news_em
      - research: 东财研报 stock_research_report_em
      - main_feed: 财联社主新闻流 stock_news_main_cx（无需 stock_code）
    """
    if not AKSHARE_AVAILABLE:
        return _err_payload("AkShare 未安装")

    kind = (content_kind or "news").strip().lower()
    pref = normalize_provider_preference(provider_preference)

    if kind == "main_feed":
        try:
            with _pandas_string_storage_python():
                df = ak.stock_news_main_cx()  # type: ignore[union-attr]
            recs = _df_records(df, max_rows)
            return _ok_payload(recs, source="akshare", route=["stock_news_main_cx"], attempts={"stock_news_main_cx": 1}, count=len(recs))
        except Exception as e:  # noqa: BLE001
            return _err_payload(f"主新闻流失败: {e}")

    code6 = _norm_code_6(stock_code)
    if not code6 or len(code6) != 6:
        return _err_payload("news / research 需要有效 stock_code")

    # 可选：news 走东财为主；预留 sina 等可在后续接入
    chain: List[Tuple[str, str, Callable[[], pd.DataFrame]]] = []
    if kind == "news":
        chain.append(
            ("eastmoney", "stock_news_em", lambda: ak.stock_news_em(symbol=code6))  # type: ignore[union-attr]
        )
    elif kind == "research":
        chain.append(
            ("eastmoney", "stock_research_report_em", lambda: ak.stock_research_report_em(symbol=code6))  # type: ignore[union-attr]
        )
    else:
        return _err_payload(f"不支持的 content_kind={content_kind}，请用 news|research|main_feed")

    chain = reorder_provider_chain(pref, chain)
    attempts: Dict[str, int] = {}
    routes: List[str] = []
    last_err: Optional[str] = None
    for _tag, name, fn in chain:
        try:
            attempts[name] = attempts.get(name, 0) + 1
            with _pandas_string_storage_python():
                df = fn()
            routes.append(name)
            recs = _df_records(df, max_rows)
            return _ok_payload(recs, source="akshare", route=routes, attempts=attempts, count=len(recs))
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
    return _err_payload(last_err or "新闻/研报获取失败")
