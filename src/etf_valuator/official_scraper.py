from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin

from typing import Any

from .utils import normalize_label, parse_number_with_suffix, parse_percent


@dataclass
class OfficialScrapeResult:
    metrics: dict[str, float]
    artifacts: dict[str, str]
    notes: list[str]


class OfficialETFScraper:
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )

    KEYWORD_MAP = {
        "expense ratio": "expense_ratio",
        "net expense ratio": "expense_ratio",
        "management fee": "management_fee",
        "assets under management": "aum",
        "aum": "aum",
        "fund assets": "aum",
        "net assets": "aum",
        "p/e ratio": "pe",
        "pe ratio": "pe",
        "price/earnings": "pe",
        "price to earnings": "pe",
        "p/b ratio": "pb",
        "price/book": "pb",
        "distribution yield": "distribution_yield",
        "dividend yield": "distribution_yield",
        "sec yield": "sec_yield",
        "30-day sec yield": "sec_yield",
        "duration": "duration_years",
        "effective duration": "duration_years",
        "turnover": "turnover",
        "tracking error": "tracking_error",
        "premium/discount": "premium_discount",
        "premium discount": "premium_discount",
        "number of holdings": "holdings_count",
        "holdings": "holdings_count",
    }

    METRIC_PATTERNS: dict[str, Iterable[re.Pattern[str]]] = {
        "expense_ratio": (
            re.compile(r"expense ratio[^0-9\-]*(-?\d+(?:[.,]\d+)?)\s*%", re.I),
            re.compile(r"net expense[^0-9\-]*(-?\d+(?:[.,]\d+)?)\s*%", re.I),
        ),
        "distribution_yield": (
            re.compile(r"distribution yield[^0-9\-]*(-?\d+(?:[.,]\d+)?)\s*%", re.I),
            re.compile(r"dividend yield[^0-9\-]*(-?\d+(?:[.,]\d+)?)\s*%", re.I),
        ),
        "sec_yield": (
            re.compile(r"(?:30[- ]day )?sec yield[^0-9\-]*(-?\d+(?:[.,]\d+)?)\s*%", re.I),
        ),
        "pe": (
            re.compile(r"p\/?e ratio[^0-9\-]*(-?\d+(?:[.,]\d+)?)", re.I),
            re.compile(r"price\/earnings[^0-9\-]*(-?\d+(?:[.,]\d+)?)", re.I),
        ),
        "pb": (
            re.compile(r"p\/?b ratio[^0-9\-]*(-?\d+(?:[.,]\d+)?)", re.I),
            re.compile(r"price\/book[^0-9\-]*(-?\d+(?:[.,]\d+)?)", re.I),
        ),
        "turnover": (re.compile(r"turnover[^0-9\-]*(-?\d+(?:[.,]\d+)?)\s*%", re.I),),
        "tracking_error": (
            re.compile(r"tracking error[^0-9\-]*(-?\d+(?:[.,]\d+)?)\s*%", re.I),
        ),
        "premium_discount": (
            re.compile(r"premium\/discount[^0-9\-]*(-?\d+(?:[.,]\d+)?)\s*%", re.I),
        ),
        "holdings_count": (
            re.compile(r"number of holdings[^0-9]*(\d+(?:[.,]\d+)?)", re.I),
        ),
        "duration_years": (
            re.compile(r"(?:effective )?duration[^0-9\-]*(-?\d+(?:[.,]\d+)?)", re.I),
        ),
        "aum": (
            re.compile(
                r"(?:assets under management|fund assets|net assets|aum)"
                r"[^0-9\-]*(\d+(?:[.,]\d+)?)\s*([kmbt])",
                re.I,
            ),
        ),
    }

    def scrape(self, url: str, timeout: int = 18) -> OfficialScrapeResult:
        metrics: dict[str, float] = {}
        artifacts: dict[str, str] = {}
        notes: list[str] = []
        headers = {"User-Agent": self.USER_AGENT}
        try:
            import requests
            from bs4 import BeautifulSoup
        except Exception as exc:
            notes.append(f"Official scrape dependencies missing: {exc}")
            return OfficialScrapeResult(metrics=metrics, artifacts=artifacts, notes=notes)

        try:
            response = requests.get(url, timeout=timeout, headers=headers)
            response.raise_for_status()
        except Exception as exc:
            notes.append(f"Official scrape failed for {url}: {exc}")
            return OfficialScrapeResult(metrics=metrics, artifacts=artifacts, notes=notes)

        soup = BeautifulSoup(response.text, "html.parser")
        text = " ".join(soup.stripped_strings)

        metrics.update(self._extract_from_patterns(text))
        metrics.update(self._extract_from_tables(soup))
        metrics.update(self._extract_from_embedded_json(soup))
        artifacts.update(self._extract_artifacts(soup, base_url=url))
        notes.append(f"Official source parsed: {url}")
        return OfficialScrapeResult(metrics=metrics, artifacts=artifacts, notes=notes)

    def _extract_from_patterns(self, text: str) -> dict[str, float]:
        out: dict[str, float] = {}
        for key, patterns in self.METRIC_PATTERNS.items():
            for pattern in patterns:
                match = pattern.search(text)
                if not match:
                    continue
                raw_num = match.group(1).replace(",", ".")
                try:
                    number = float(raw_num)
                except ValueError:
                    continue
                if key == "aum" and len(match.groups()) >= 2:
                    suffix = match.group(2).upper()
                    number = number * {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}.get(
                        suffix, 1.0
                    )
                out[key] = number
                break
        return out

    def _extract_from_tables(self, soup: Any) -> dict[str, float]:
        out: dict[str, float] = {}
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            label = normalize_label(cells[0].get_text(" ", strip=True))
            value_txt = cells[1].get_text(" ", strip=True)
            metric_key = self._label_to_metric(label)
            if not metric_key:
                continue
            parsed = self._parse_value(metric_key, value_txt)
            if parsed is not None:
                out[metric_key] = parsed
        return out

    def _label_to_metric(self, label: str) -> str | None:
        for keyword, metric in self.KEYWORD_MAP.items():
            if keyword in label:
                return metric
        return None

    def _parse_value(self, key: str, raw_value: str) -> float | None:
        if key in {
            "expense_ratio",
            "distribution_yield",
            "sec_yield",
            "turnover",
            "tracking_error",
            "premium_discount",
        }:
            return parse_percent(raw_value)
        if key in {"pe", "pb", "holdings_count", "duration_years"}:
            return parse_number_with_suffix(raw_value)
        if key == "aum":
            return parse_number_with_suffix(raw_value)
        return None

    def _extract_artifacts(self, soup: Any, base_url: str) -> dict[str, str]:
        artifact_rules = {
            "holdings_file": ("holdings", ".csv", ".xlsx", ".xls"),
            "factsheet": ("fact sheet", "factsheet", ".pdf"),
            "prospectus": ("prospectus", ".pdf"),
            "nav_page": ("nav", "premium/discount", "premium", "discount"),
        }
        out: dict[str, str] = {}

        for link in soup.find_all("a"):
            href = (link.get("href") or "").strip()
            if not href:
                continue
            absolute = urljoin(base_url, href)
            txt = normalize_label(link.get_text(" ", strip=True))
            full = f"{txt} {href.lower()}"

            for artifact_key, terms in artifact_rules.items():
                if artifact_key in out:
                    continue
                if any(term in full for term in terms):
                    out[artifact_key] = absolute
        return out

    def _extract_from_embedded_json(self, soup: Any) -> dict[str, float]:
        # Default generic implementation: no strict assumptions on key names.
        out: dict[str, float] = {}
        key_aliases = {
            "expenseratio": "expense_ratio",
            "totalexpenseratio": "expense_ratio",
            "netassets": "aum",
            "totalassets": "aum",
            "peratio": "pe",
            "pricetoearnings": "pe",
            "pricebookratio": "pb",
            "distributionyield": "distribution_yield",
            "secyield": "sec_yield",
            "numberofholdings": "holdings_count",
            "holdingscount": "holdings_count",
            "trackingerror": "tracking_error",
            "turnover": "turnover",
            "duration": "duration_years",
        }
        percent_like = {
            "expense_ratio",
            "distribution_yield",
            "sec_yield",
            "tracking_error",
            "turnover",
        }
        aum_like = {"aum"}

        for script in soup.find_all("script"):
            raw = script.string or script.get_text(strip=True)
            if not raw:
                continue
            if "{" not in raw and "[" not in raw:
                continue
            candidate = self._safe_json_load(raw)
            if candidate is None:
                continue
            for key, value in _iter_json_leafs(candidate):
                compact_key = re.sub(r"[^a-zA-Z0-9]+", "", key).lower()
                metric_key = key_aliases.get(compact_key)
                if not metric_key:
                    continue
                num = _try_float(value)
                if num is None:
                    continue
                if metric_key in percent_like:
                    num = self._normalize_embedded_percent(metric_key, num)
                if metric_key in aum_like and 1.0 <= num <= 1e4:
                    # Ignore suspiciously tiny AUM parsed from unrelated fields.
                    continue
                out.setdefault(metric_key, num)
        return out

    def _normalize_embedded_percent(self, metric_key: str, value: float) -> float:
        if value > 1.0:
            return value
        if metric_key != "expense_ratio":
            return value * 100.0
        # Expense ratio appears in both formats across issuers:
        # - Decimal fraction (0.0003 means 0.03%)
        # - Percentage points (0.03 already means 0.03%)
        # Convert only tiny values that are clearly fractions.
        if 0.0 <= value < 0.02:
            return value * 100.0
        return value

    def _safe_json_load(self, raw: str) -> Any:
        raw = raw.strip()
        if not raw:
            return None
        if raw.startswith("window.") and "=" in raw:
            raw = raw.split("=", 1)[1].strip().rstrip(";")
        if raw.startswith("var ") and "=" in raw:
            raw = raw.split("=", 1)[1].strip().rstrip(";")
        try:
            return json.loads(raw)
        except Exception:
            return None


def _iter_json_leafs(obj: Any, parent: str = ""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            compound = f"{parent}.{key}" if parent else str(key)
            yield from _iter_json_leafs(value, compound)
        return
    if isinstance(obj, list):
        for idx, value in enumerate(obj):
            compound = f"{parent}[{idx}]"
            yield from _iter_json_leafs(value, compound)
        return
    key = parent.split(".")[-1] if parent else ""
    if key:
        yield key, obj


def _try_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    cleaned = value.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None
