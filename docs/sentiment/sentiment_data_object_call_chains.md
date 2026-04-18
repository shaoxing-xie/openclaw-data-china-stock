# Sentiment Data Object Call Chains (Proposed)

Status legend:
- `proposed`: waiting user confirmation
- `approved`: user confirmed

## 1) limit_up_pool (`approved`)

- Approved chain: `akshare.stock_zt_pool_em -> akshare.stock_zt_pool_previous_em -> akshare.stock_zt_pool_strong_em -> akshare.stock_zt_pool_sub_new_em -> cache`
- Switch conditions:
  - timeout > 12s or exception -> cache
  - `record_count < 5` -> cache
  - required fields missing (`代码/名称/涨跌幅`) -> cache

## 2) fund_flow_market/sector/stock_rank (`approved`)

- market_history:
  - `ths_industry + ths_concept aggregate(proxy) -> cache`
  - optional fallback (`FUND_FLOW_ENABLE_EASTMONEY_FALLBACK=true`): `eastmoney_http_direct`
- sector_rank:
  - `ths_industry/concept -> (optional) eastmoney_rank -> cache`
- stock_rank:
  - `ths_individual -> (optional) eastmoney_individual_rank -> cache`
- big_deal:
  - `ths_limited -> ths_full(akshare) -> (optional) eastmoney_proxy -> cache`
- Switch conditions:
  - query-kind timeout overrides:
    - `THS_STOCK_RANK_TIMEOUT_SEC` (default 120)
    - `THS_BIG_DEAL_TIMEOUT_SEC` (default 180)
  - null_ratio > 0.85
  - empty dataframe

## 3) northbound_summary (`approved`)

- Approved chain:
  - `tushare.moneyflow_hsgt -> eastmoney.legacy_hsgt -> cache`
- Switch conditions:
  - tushare token missing / tushare request failed / empty result
  - parse failure / json decode error on legacy source
  - lookback request not satisfiable

## 4) sector_snapshot (`approved`)

- Industry Approved Chain:
  - `ths_industry_summary -> sina.stock_sector_spot(新浪行业/行业) -> em_push2_industry -> akshare_industry_name_em -> cache`
- Concept Approved Chain:
  - `sina.stock_sector_spot(概念) -> em_concept_clist -> em_concept_jsonp -> cache`
- Switch conditions:
  - record_count thresholds: industry >= 30, concept >= 10
  - required fields `sector_name/change_percent`
  - excessive null ratio

## User review gate

All above chains stay `proposed` until explicit confirmation from user.  
Implementation only materializes `approved` ordering.
