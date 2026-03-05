from __future__ import annotations

from dataclasses import dataclass


@dataclass
class YahooData:
    profile: dict[str, str]
    metrics: dict[str, float]
    notes: list[str]


class YahooFallbackProvider:
    INFO_MAP = {
        "expenseRatio": "expense_ratio",
        "annualReportExpenseRatio": "expense_ratio",
        "totalAssets": "aum",
        "trailingPE": "pe",
        "forwardPE": "forward_pe",
        "priceToBook": "pb",
        "yield": "distribution_yield",
        "beta3Year": "beta_3y",
        "fundInceptionDate": "inception_date",
        "fundFamily": "fund_family",
        "category": "category",
        "bid": "bid",
        "ask": "ask",
        "regularMarketPrice": "market_price",
        "navPrice": "nav_price",
    }

    PROFILE_KEYS = {"longName", "shortName", "fundFamily", "category", "website"}

    def load(self, ticker: str) -> YahooData:
        notes: list[str] = []
        profile: dict[str, str] = {}
        metrics: dict[str, float] = {}
        try:
            import yfinance as yf
        except Exception as exc:
            notes.append(f"Yahoo dependency missing: {exc}")
            return YahooData(profile=profile, metrics=metrics, notes=notes)
        yf_ticker = yf.Ticker(ticker)

        try:
            info = yf_ticker.get_info()
        except AttributeError:
            info = getattr(yf_ticker, "info", {}) or {}
        except Exception as exc:
            notes.append(f"Yahoo get_info failed for {ticker}: {exc}")
            info = {}

        for key in self.PROFILE_KEYS:
            value = info.get(key)
            if value is not None:
                profile[key] = str(value)

        for source_key, metric_key in self.INFO_MAP.items():
            value = info.get(source_key)
            if value is None:
                continue
            if metric_key in {"distribution_yield", "expense_ratio"} and isinstance(
                value, (float, int)
            ):
                # Yahoo usually returns decimal fractions for these.
                metrics[metric_key] = float(value) * 100.0
            else:
                try:
                    metrics[metric_key] = float(value)
                except Exception:
                    continue

        self._hydrate_funds_data(yf_ticker, metrics, notes)
        return YahooData(profile=profile, metrics=metrics, notes=notes)

    def _hydrate_funds_data(
        self, ticker, metrics: dict[str, float], notes: list[str]
    ) -> None:
        try:
            funds_data = getattr(ticker, "funds_data", None)
            if funds_data is None:
                return
        except Exception as exc:
            notes.append(f"Yahoo funds_data unavailable: {exc}")
            return

        top_holdings = getattr(funds_data, "top_holdings", None)
        if top_holdings is not None:
            try:
                metrics["holdings_count"] = float(len(top_holdings))
            except Exception:
                pass
            try:
                if "holdingPercent" in top_holdings.columns:
                    top10 = top_holdings["holdingPercent"].head(10).sum()
                    metrics["top10_weight"] = float(top10) * 100.0
            except Exception:
                pass
