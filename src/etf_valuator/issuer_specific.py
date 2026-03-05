from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from .official_scraper import OfficialETFScraper, OfficialScrapeResult


@dataclass(frozen=True)
class ScraperMatchContext:
    url: str | None
    issuer: str | None
    name: str | None


class IssuerSpecificScraper(OfficialETFScraper):
    domains: tuple[str, ...] = ()
    issuer_hints: tuple[str, ...] = ()

    def matches(self, ctx: ScraperMatchContext) -> bool:
        url = (ctx.url or "").strip().lower()
        if url:
            host = urlparse(url).netloc.lower()
            if any(domain in host for domain in self.domains):
                return True
        hint_text = f"{ctx.issuer or ''} {ctx.name or ''}".lower()
        return any(hint in hint_text for hint in self.issuer_hints)

    def scrape(self, url: str, timeout: int = 18) -> OfficialScrapeResult:
        result = super().scrape(url=url, timeout=timeout)
        result.notes.append(f"Issuer-specific scraper used: {self.__class__.__name__}")
        return result


class IsharesScraper(IssuerSpecificScraper):
    domains = ("ishares.com",)
    issuer_hints = ("ishares", "blackrock")
    KEYWORD_MAP = {
        **OfficialETFScraper.KEYWORD_MAP,
        "acquired fund fees and expenses": "expense_ratio",
        "weighted avg pe ratio": "pe",
        "weighted avg pb ratio": "pb",
        "price to book ratio": "pb",
    }


class VanEckScraper(IssuerSpecificScraper):
    domains = ("vaneck.com",)
    issuer_hints = ("vaneck",)
    KEYWORD_MAP = {
        **OfficialETFScraper.KEYWORD_MAP,
        "gross expense ratio": "expense_ratio",
        "total fund assets": "aum",
        "weighted average market cap": "weighted_market_cap",
        "weighted avg market cap": "weighted_market_cap",
        "median market cap": "median_market_cap",
    }


class InvescoScraper(IssuerSpecificScraper):
    domains = ("invesco.com",)
    issuer_hints = ("invesco", "powershares")
    KEYWORD_MAP = {
        **OfficialETFScraper.KEYWORD_MAP,
        "net expense ratio": "expense_ratio",
        "gross expense ratio": "expense_ratio",
        "weighted average pe": "pe",
        "weighted average pb": "pb",
        "fund aum": "aum",
    }


class VanguardScraper(IssuerSpecificScraper):
    domains = ("vanguard.com",)
    issuer_hints = ("vanguard",)
    KEYWORD_MAP = {
        **OfficialETFScraper.KEYWORD_MAP,
        "expense ratio as of": "expense_ratio",
        "portfolio turnover rate": "turnover",
        "weighted average pe": "pe",
        "weighted average pb": "pb",
    }


class SPDRScraper(IssuerSpecificScraper):
    domains = ("ssga.com", "spdrs.com")
    issuer_hints = ("state street", "spdr")
    KEYWORD_MAP = {
        **OfficialETFScraper.KEYWORD_MAP,
        "gross expense ratio": "expense_ratio",
        "net asset value": "nav_price",
        "shares outstanding": "shares_outstanding",
        "weighted average pe ratio": "pe",
        "weighted average pb ratio": "pb",
    }


class IssuerScraperRegistry:
    def __init__(self) -> None:
        self._scrapers: list[IssuerSpecificScraper] = [
            IsharesScraper(),
            VanEckScraper(),
            InvescoScraper(),
            VanguardScraper(),
            SPDRScraper(),
        ]
        self._generic = OfficialETFScraper()

    def pick(self, ctx: ScraperMatchContext) -> OfficialETFScraper:
        for scraper in self._scrapers:
            if scraper.matches(ctx):
                return scraper
        return self._generic
