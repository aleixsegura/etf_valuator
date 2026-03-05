from __future__ import annotations

from .derived import apply_derived_metrics
from .issuer_specific import IssuerScraperRegistry, ScraperMatchContext
from .models import ETFSnapshot, ETFValuationResult
from .scoring import score_snapshot
from .url_resolver import OfficialURLResolver, URLResolveInput
from .yahoo_fallback import YahooFallbackProvider


class ETFValuationEngine:
    def __init__(self) -> None:
        self.scrapers = IssuerScraperRegistry()
        self.yahoo = YahooFallbackProvider()
        self.url_resolver = OfficialURLResolver()

    def evaluate(self, ticker: str, official_url: str | None = None) -> ETFValuationResult:
        symbol = ticker.strip().upper()
        snapshot = ETFSnapshot(ticker=symbol, official_url=official_url)

        yahoo_data = self.yahoo.load(symbol)
        snapshot.name = yahoo_data.profile.get("longName") or yahoo_data.profile.get("shortName")
        snapshot.issuer = yahoo_data.profile.get("fundFamily")
        snapshot.category = yahoo_data.profile.get("category")
        if not snapshot.official_url:
            resolved = self.url_resolver.resolve(
                URLResolveInput(
                    ticker=symbol,
                    issuer=snapshot.issuer,
                    fund_name=snapshot.name,
                    website=yahoo_data.profile.get("website"),
                )
            )
            snapshot.official_url = resolved.url
            snapshot.notes.append(
                "Official URL resolver -> "
                f"method={resolved.method}, confidence={resolved.confidence:.2f}"
            )

        if snapshot.official_url:
            scraper = self.scrapers.pick(
                ScraperMatchContext(
                    url=snapshot.official_url,
                    issuer=snapshot.issuer,
                    name=snapshot.name,
                )
            )
            snapshot.notes.append(f"Selected official scraper: {scraper.__class__.__name__}")
            official = scraper.scrape(snapshot.official_url)
            for key, value in official.metrics.items():
                snapshot.set_metric(key, value, source="official", confidence=0.95)
            snapshot.artifacts.update(official.artifacts)
            snapshot.notes.extend(official.notes)
        else:
            snapshot.notes.append(
                "No official URL found after resolver; skipping official scraping."
            )

        for key, value in yahoo_data.metrics.items():
            snapshot.set_metric(key, value, source="yahoo", confidence=0.6)
        snapshot.notes.extend(yahoo_data.notes)

        apply_derived_metrics(snapshot)
        score = score_snapshot(snapshot)
        return ETFValuationResult(snapshot=snapshot, score=score)
