from __future__ import annotations

from .models import ETFSnapshot


def apply_derived_metrics(snapshot: ETFSnapshot) -> None:
    pe = _metric(snapshot, "pe")
    if pe and pe > 0:
        snapshot.set_metric("earnings_yield", 100.0 / pe, source="derived", confidence=0.7)

    bid = _metric(snapshot, "bid")
    ask = _metric(snapshot, "ask")
    mid = None
    if bid and ask and bid > 0 and ask > 0:
        mid = (bid + ask) / 2.0
        spread_bps = ((ask - bid) / mid) * 10000.0
        snapshot.set_metric("bid_ask_spread_bps", spread_bps, source="derived", confidence=0.7)

    price = _metric(snapshot, "market_price")
    nav = _metric(snapshot, "nav_price")
    if price and nav and nav > 0:
        premium_discount = ((price - nav) / nav) * 100.0
        snapshot.set_metric(
            "premium_discount",
            premium_discount,
            source="derived",
            confidence=0.7,
        )


def _metric(snapshot: ETFSnapshot, key: str) -> float | None:
    metric = snapshot.metrics.get(key)
    return metric.value if metric else None
