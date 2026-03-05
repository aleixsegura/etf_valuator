# ETF Valuator (Official-Source-First)

ETF valuation tool that prioritizes metrics from the fund's official website and uses Yahoo Finance (`yfinance`) as a fallback when data is missing.

## Architecture

1. Issuer-specific official scrapers (`src/etf_valuator/issuer_specific.py`)
- Automatic registry and selector based on domain/issuer.
- `IsharesScraper` (BlackRock / iShares)
- `VanEckScraper`
- `InvescoScraper`
- `VanguardScraper`
- `SPDRScraper` (State Street)
- Falls back to the generic `OfficialETFScraper` when no issuer match is found.

2. `OfficialETFScraper` (`src/etf_valuator/official_scraper.py`)
- Tries to extract metrics from the ETF official page (tables + free text).
- Also parses embedded JSON when available.
- Detects key artifacts: `holdings_file`, `factsheet`, `prospectus`, `nav_page`.
- Source priority: `official`.

3. `YahooFallbackProvider` (`src/etf_valuator/yahoo_fallback.py`)
- Completes missing metrics with `yfinance` (`get_info`, `funds_data`).
- Source: `yahoo`.

4. Derived metrics (`src/etf_valuator/derived.py`)
- `earnings_yield` from `P/E`.
- `bid_ask_spread_bps` from `bid` and `ask`.
- `premium_discount` from `price` and `nav`.
- Source: `derived`.

5. Scoring (`src/etf_valuator/scoring.py`)
- Subscores: `valuation`, `cost`, `quality`, `liquidity`.
- Applies a penalty for low data coverage (`coverage`).
- Output: global score 0-100 + text recommendation.

6. Orchestration (`src/etf_valuator/engine.py`)
- Final pipeline: `official -> yahoo -> derived -> score`.
- Includes official URL resolver (`src/etf_valuator/url_resolver.py`) when Yahoo does not provide `website`.
- Resolver v2 uses issuer adapters, URL validation, sitemap fallback, and TTL cache in `.cache/official_url_cache.json`.

## Target metrics

- Valuation: `pe`, `pb`, `earnings_yield`.
- Cost: `expense_ratio`, `management_fee`.
- Portfolio quality: `holdings_count`, `top10_weight`, `turnover`, `tracking_error`.
- Liquidity and execution: `aum`, `bid_ask_spread_bps`, `premium_discount`.
- Fixed income (when available): `sec_yield`, `duration_years`.

## Usage

### 1) Single ticker

```bash
python -m src.main VOO
```

### 2) Single ticker + forced official URL

```bash
python -m src.main VOO --official-url "https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf"
```

### 3) CSV tickers

```bash
python -m src.main --csv tickers.csv
```

Expected CSV:

```csv
ticker
VOO
SPY
```

### 4) JSON output

```bash
python -m src.main VOO --json
```

## Implementation notes

- If the official site does not expose a metric in public HTML/JSON, the tool does not infer fake values and falls back to alternative/derived sources.
- Issuer parsers are designed to work across iShares, VanEck, Vanguard, and SPDR pages, but each issuer may still require additional HTML-specific tuning.
- For production, consider adding deeper issuer-specific parsers.
- For production, consider adding direct holdings CSV/XLS download and parsing for real concentration metrics.
- For production, consider adding historical percentile benchmarks for relative cheap/expensive valuation.
