# ETF Valuator

Official-source-first ETF valuation engine that estimates whether an ETF looks attractive, neutral, or potentially overvalued based on valuation, cost, portfolio quality, and liquidity signals.

## Why This Project

Most ETF tools rely heavily on aggregator APIs. This project flips the priority:

1. Extract metrics from the ETF issuer's official pages first.
2. Fill gaps with `yfinance`.
3. Compute derived metrics.
4. Produce a transparent score with reasons and data coverage confidence.

## Quick Start

```bash
uv sync
uv run python -m src.main VOO --json
```

Other examples:

```bash
uv run python -m src.main VOO QQQ REMX
uv run python -m src.main --csv tickers.csv --json
uv run python -m src.main VOO --official-url "https://investor.vanguard.com/investment-products/etfs/profile/voo"
```

Expected CSV format:

```csv
ticker
VOO
SPY
```

## Architecture

### 1) Issuer-Specific Scrapers
File: `src/etf_valuator/issuer_specific.py`

- `iSharesScraper` (BlackRock / iShares)
- `VanEckScraper`
- `InvescoScraper`
- `VanguardScraper`
- `SPDRScraper` (State Street)

If no issuer-specific match is available, the engine falls back to the generic official scraper.

### 2) Generic Official Scraper
File: `src/etf_valuator/official_scraper.py`

- Parses issuer pages (tables + page text + embedded JSON).
- Extracts metrics and official artifacts: `holdings_file`, `factsheet`, `prospectus`, `nav_page`.

### 3) Official URL Resolver (No Static Mapping Required)
File: `src/etf_valuator/url_resolver.py`

- Uses issuer adapters to discover product URLs.
- Validates candidate pages (ticker + ETF/fund context).
- Falls back to sitemap search when needed.
- Uses a TTL cache at `.cache/official_url_cache.json`.

### 4) Fallback Data Provider
File: `src/etf_valuator/yahoo_fallback.py`

- Uses `yfinance` only for missing official metrics.

### 5) Derived Metrics
File: `src/etf_valuator/derived.py`

- `earnings_yield = 100 / pe`
- `bid_ask_spread_bps = ((ask - bid) / mid) * 10000`
- `premium_discount = ((market_price - nav_price) / nav_price) * 100`

### 6) Scoring Engine
File: `src/etf_valuator/scoring.py`

- Produces `valuation`, `cost`, `quality`, `liquidity`, `coverage`, and `overall`.
- Adds textual recommendation and explanation reasons.

## Scoring Methodology

The model computes a weighted score from 0 to 100:

```text
overall_raw = valuation*0.40 + cost*0.20 + quality*0.25 + liquidity*0.15
overall = overall_raw * coverage
```

Where:

- `valuation` is driven by `pe`, `pb`, and `earnings_yield`.
- `cost` is primarily driven by `expense_ratio`.
- `quality` uses concentration/diversification and implementation proxies: `top10_weight`, `holdings_count`, `turnover`, `tracking_error`.
- `liquidity` uses tradability proxies: `aum`, `bid_ask_spread_bps`, `premium_discount`.
- `coverage` is a confidence multiplier based on how many key metrics are available.

Interpretation bands:

- `>= 75`: attractive entry point
- `60 - 74.99`: reasonable, monitor entry price
- `45 - 59.99`: neutral, no clear edge
- `< 45`: potentially overvalued or weak

## Target Metrics

- Valuation: `pe`, `pb`, `earnings_yield`
- Cost: `expense_ratio`, `management_fee`
- Portfolio quality: `holdings_count`, `top10_weight`, `turnover`, `tracking_error`
- Liquidity: `aum`, `bid_ask_spread_bps`, `premium_discount`
- Fixed income (when available): `sec_yield`, `duration_years`

## Output

Use `--json` for programmatic output:

```bash
uv run python -m src.main QQQ --json
```

You get:

- resolved official URL
- collected metrics with source (`official`, `yahoo`, `derived`)
- score breakdown
- recommendation
- reasons
- operational notes (resolver/scraper behavior)

## Score Example

Example command:

```bash
uv run python -m src.main VOO --json
```

Example output snippet:

```json
[
  {
    "ticker": "VOO",
    "official_url": "https://investor.vanguard.com/investment-products/etfs/profile/voo",
    "score": {
      "overall": 68.4,
      "valuation": 61.2,
      "cost": 92.0,
      "quality": 70.5,
      "liquidity": 74.8,
      "coverage": 0.86,
      "recommendation": "reasonable; monitor entry price",
      "reasons": [
        "Valuation, cost, and liquidity metrics are in a favorable range."
      ]
    }
  }
]
```

How to read it:

- `overall` is the final score after applying `coverage`.
- `coverage` close to `1.0` means higher confidence in the conclusion.
- If `cost` is high but `valuation` is low, it may be a strong ETF priced expensively.
- Always compare `overall` and sub-scores across peer ETFs in the same category.

## Limitations

- Issuer websites change frequently; parser adjustments are expected.
- Some metrics are not publicly exposed in HTML/JSON and require document parsing or holdings files.
- Current score is a practical heuristic, not an investment guarantee.

## Disclaimer

This repository is an educational project and not financial advice.

It was developed using agentic software engineering workflows with:

- OpenAI Codex CLI (`gpt-5.3-codex`, medium profile)
- Cursor

The goal is to learn and practice modern agentic AI software engineering patterns, including tool-driven implementation, iterative validation, and transparent system design.
