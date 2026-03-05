from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse


@dataclass
class URLResolveInput:
    ticker: str
    issuer: str | None
    fund_name: str | None
    website: str | None


@dataclass
class URLResolveOutput:
    url: str | None
    method: str
    confidence: float


@dataclass
class IssuerAdapter:
    key: str
    hints: tuple[str, ...]
    search_urls: tuple[str, ...]
    sitemap_urls: tuple[str, ...]
    allowed_domains: tuple[str, ...]


class OfficialURLResolver:
    def __init__(self, cache_ttl_days: int = 14, cache_path: str | None = None) -> None:
        default_cache = Path(".cache/official_url_cache.json")
        self.cache_path = Path(cache_path) if cache_path else default_cache
        self.cache_ttl_seconds = cache_ttl_days * 24 * 3600
        self.adapters = self._build_adapters()
        self._cache = self._load_cache()

    def resolve(self, payload: URLResolveInput) -> URLResolveOutput:
        ticker = payload.ticker.strip().upper()
        cached = self._cache_get(ticker)
        if cached:
            cached_url = str(cached.get("url") or "")
            if self._validate_url(
                cached_url,
                ticker=ticker,
                issuer_hint=payload.issuer,
                name_hint=payload.fund_name,
            ):
                return URLResolveOutput(
                    url=cached_url,
                    method=f"cache:{cached['method']}",
                    confidence=float(cached["confidence"]),
                )
            self._cache_delete(ticker)

        if payload.website:
            validated = self._validate_url(
                payload.website,
                ticker=ticker,
                issuer_hint=payload.issuer,
                name_hint=payload.fund_name,
            )
            if validated:
                self._cache_set(ticker, payload.website, "yahoo_website", 0.93)
                return URLResolveOutput(
                    url=payload.website, method="yahoo_website", confidence=0.93
                )

        adapter = self._pick_adapter(payload.issuer, payload.fund_name)
        if adapter:
            discovered = self._discover_with_adapter(
                adapter=adapter,
                ticker=ticker,
                issuer_hint=payload.issuer,
                name_hint=payload.fund_name,
            )
            if discovered:
                url, method, confidence = discovered
                self._cache_set(ticker, url, method, confidence)
                return URLResolveOutput(url=url, method=method, confidence=confidence)

        # Issuer metadata can be missing; try all adapters as a global fallback.
        for any_adapter in self.adapters:
            discovered = self._discover_with_adapter(
                adapter=any_adapter,
                ticker=ticker,
                issuer_hint=payload.issuer,
                name_hint=payload.fund_name,
            )
            if discovered:
                url, method, confidence = discovered
                method = f"cross_issuer:{method}"
                confidence = max(0.60, confidence - 0.12)
                self._cache_set(ticker, url, method, confidence)
                return URLResolveOutput(url=url, method=method, confidence=confidence)

        return URLResolveOutput(url=None, method="not_found", confidence=0.0)

    def _build_adapters(self) -> list[IssuerAdapter]:
        return [
            IssuerAdapter(
                key="vanguard",
                hints=("vanguard",),
                search_urls=(
                    "https://investor.vanguard.com/investment-products/etfs/profile/{ticker_lc}",
                    "https://investor.vanguard.com/search?q={ticker}",
                ),
                sitemap_urls=("https://investor.vanguard.com/sitemaps/sitemap-index.xml",),
                allowed_domains=("investor.vanguard.com", "vanguard.com"),
            ),
            IssuerAdapter(
                key="ishares",
                hints=("ishares", "blackrock"),
                search_urls=(
                    "https://www.ishares.com/us/products?search={ticker}",
                    "https://www.ishares.com/us/search?query={ticker}",
                ),
                sitemap_urls=("https://www.ishares.com/us/sitemap.xml",),
                allowed_domains=("ishares.com",),
            ),
            IssuerAdapter(
                key="invesco",
                hints=("invesco", "powershares"),
                search_urls=(
                    "https://www.invesco.com/us/financial-products/etfs/product-detail?productId={ticker}",
                    "https://www.invesco.com/us/en/search.html?q={ticker}",
                ),
                sitemap_urls=("https://www.invesco.com/us/en/sitemap.xml",),
                allowed_domains=("invesco.com",),
            ),
            IssuerAdapter(
                key="vaneck",
                hints=("vaneck",),
                search_urls=(
                    "https://www.vaneck.com/us/en/etf/equity/{ticker_lc}/",
                    "https://www.vaneck.com/us/en/search/?query={ticker}",
                ),
                sitemap_urls=("https://www.vaneck.com/sitemap.xml",),
                allowed_domains=("vaneck.com",),
            ),
            IssuerAdapter(
                key="spdr",
                hints=("spdr", "state street", "ssga"),
                search_urls=(
                    "https://www.ssga.com/us/en/intermediary/etfs/funds?ticker={ticker}",
                    "https://www.ssga.com/us/en/intermediary/search?query={ticker}",
                ),
                sitemap_urls=("https://www.ssga.com/us/en/intermediary/sitemap.xml",),
                allowed_domains=("ssga.com", "spdrs.com"),
            ),
        ]

    def _pick_adapter(self, issuer: str | None, fund_name: str | None) -> IssuerAdapter | None:
        haystack = f"{issuer or ''} {fund_name or ''}".lower()
        for adapter in self.adapters:
            if any(hint in haystack for hint in adapter.hints):
                return adapter
        return None

    def _discover_with_adapter(
        self,
        adapter: IssuerAdapter,
        ticker: str,
        issuer_hint: str | None,
        name_hint: str | None,
    ) -> tuple[str, str, float] | None:
        # 1) Try deterministic and search URLs.
        for template in adapter.search_urls:
            url = template.format(ticker=ticker, ticker_lc=ticker.lower())
            if self._validate_url(url, ticker=ticker, issuer_hint=issuer_hint, name_hint=name_hint):
                return url, f"adapter_direct:{adapter.key}", 0.90
            discovered_links = self._extract_links_from_search(
                url=url,
                ticker=ticker,
                allowed_domains=adapter.allowed_domains,
            )
            for link in discovered_links:
                if self._validate_url(
                    link, ticker=ticker, issuer_hint=issuer_hint, name_hint=name_hint
                ):
                    return link, f"adapter_search:{adapter.key}", 0.85

        # 2) Fallback to sitemap crawl for ticker matches.
        for sitemap in adapter.sitemap_urls:
            links = self._extract_links_from_sitemap(
                sitemap_url=sitemap,
                ticker=ticker,
                allowed_domains=adapter.allowed_domains,
            )
            for link in links:
                if self._validate_url(
                    link, ticker=ticker, issuer_hint=issuer_hint, name_hint=name_hint
                ):
                    return link, f"adapter_sitemap:{adapter.key}", 0.80
        return None

    def _extract_links_from_search(
        self, url: str, ticker: str, allowed_domains: tuple[str, ...]
    ) -> list[str]:
        html = self._fetch_text(url)
        if not html:
            return []
        href_re = re.compile(r'href=["\']([^"\']+)["\']', flags=re.IGNORECASE)
        out: list[str] = []
        for href in href_re.findall(html):
            if href.startswith("/"):
                parsed = urlparse(url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"
            host = urlparse(href).netloc.lower()
            if allowed_domains and not any(d in host for d in allowed_domains):
                continue
            joined = f"{href} {urlparse(href).path}".lower()
            if ticker.lower() in joined:
                out.append(href)
        return _dedupe(out)

    def _extract_links_from_sitemap(
        self, sitemap_url: str, ticker: str, allowed_domains: tuple[str, ...]
    ) -> list[str]:
        xml = self._fetch_text(sitemap_url)
        if not xml:
            return []
        locs = re.findall(r"<loc>(.*?)</loc>", xml, flags=re.IGNORECASE | re.DOTALL)
        out: list[str] = []
        for loc in locs:
            loc = loc.strip()
            if loc.endswith(".xml"):
                nested = self._fetch_text(loc)
                if nested:
                    nested_locs = re.findall(
                        r"<loc>(.*?)</loc>", nested, flags=re.IGNORECASE | re.DOTALL
                    )
                    locs.extend([n.strip() for n in nested_locs])
                continue
            host = urlparse(loc).netloc.lower()
            if allowed_domains and not any(d in host for d in allowed_domains):
                continue
            if ticker.lower() in loc.lower() or quote(ticker.lower()) in loc.lower():
                out.append(loc)
        return _dedupe(out)

    def _validate_url(
        self, url: str, ticker: str, issuer_hint: str | None, name_hint: str | None
    ) -> bool:
        parsed = urlparse(url)
        path = parsed.path.lower()
        query_keys = {k.lower() for k in parse_qs(parsed.query).keys()}
        if "/search" in path:
            return False
        if {"query", "q", "search"} & query_keys and "/etf/" not in path and "/investments/" not in path:
            return False

        content = self._fetch_text(url)
        if not content:
            return False
        lc = content.lower()
        if "search results" in lc and "/etf/" not in path and "/investments/" not in path:
            return False
        ticker_ok = ticker.lower() in lc
        etf_ok = any(word in lc for word in ("etf", "exchange traded", "fund"))
        if not (ticker_ok and etf_ok):
            return False
        if issuer_hint:
            first = issuer_hint.split()[0].lower()
            if len(first) >= 4 and first not in lc:
                # Soft failure accepted only if ticker appears in URL path.
                if ticker.lower() not in url.lower():
                    return False
        if name_hint:
            key = name_hint.split()[0].lower()
            if len(key) >= 4 and key not in lc and ticker.lower() not in url.lower():
                return False
        return True

    def _fetch_text(self, url: str, timeout: int = 10) -> str | None:
        try:
            import requests
        except Exception:
            return None
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        }
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code >= 400:
                return None
            return resp.text
        except Exception:
            return None

    def _load_cache(self) -> dict[str, dict]:
        if not self.cache_path.is_file():
            return {}
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            return {}
        return {}

    def _cache_get(self, ticker: str) -> dict | None:
        item = self._cache.get(ticker)
        if not item:
            return None
        timestamp = float(item.get("ts", 0))
        if time.time() - timestamp > self.cache_ttl_seconds:
            return None
        return item

    def _cache_set(self, ticker: str, url: str, method: str, confidence: float) -> None:
        self._cache[ticker] = {
            "url": url,
            "method": method,
            "confidence": float(confidence),
            "ts": time.time(),
        }
        self._persist_cache()

    def _cache_delete(self, ticker: str) -> None:
        if ticker in self._cache:
            del self._cache[ticker]
            self._persist_cache()

    def _persist_cache(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            # Cache write failure should never break valuation execution.
            return


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
