from __future__ import annotations

import re


_PERCENT_RE = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*%")
_NUMBER_RE = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*([KMBT]?)", flags=re.IGNORECASE)


def normalize_label(text: str) -> str:
    return " ".join(text.lower().strip().split())


def parse_percent(text: str) -> float | None:
    match = _PERCENT_RE.search(text)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def parse_number_with_suffix(text: str) -> float | None:
    match = _NUMBER_RE.search(text.replace("$", "").replace("€", ""))
    if not match:
        return None
    num = float(match.group(1).replace(",", "."))
    suffix = match.group(2).upper()
    multiplier = {"": 1.0, "K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}.get(suffix, 1.0)
    return num * multiplier


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
