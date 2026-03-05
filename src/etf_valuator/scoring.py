from __future__ import annotations

from .models import ETFSnapshot, ScoreBreakdown
from .utils import clamp


def score_snapshot(snapshot: ETFSnapshot) -> ScoreBreakdown:
    valuation = _score_valuation(snapshot)
    cost = _score_cost(snapshot)
    quality = _score_quality(snapshot)
    liquidity = _score_liquidity(snapshot)

    coverage = _coverage(snapshot)
    raw_overall = valuation * 0.4 + cost * 0.2 + quality * 0.25 + liquidity * 0.15
    overall = raw_overall * coverage
    recommendation = _recommendation(overall)
    reasons = _reasons(snapshot, valuation, cost, quality, liquidity, coverage)

    return ScoreBreakdown(
        valuation=round(valuation, 2),
        cost=round(cost, 2),
        quality=round(quality, 2),
        liquidity=round(liquidity, 2),
        coverage=round(coverage, 2),
        overall=round(overall, 2),
        recommendation=recommendation,
        reasons=reasons,
    )


def _metric(snapshot: ETFSnapshot, key: str) -> float | None:
    metric = snapshot.metrics.get(key)
    return metric.value if metric else None


def _score_valuation(snapshot: ETFSnapshot) -> float:
    pe = _metric(snapshot, "pe")
    pb = _metric(snapshot, "pb")
    earnings_yield = _metric(snapshot, "earnings_yield")

    score = 50.0
    if pe:
        # 12-25x considered neutral corridor for broad equity ETFs.
        score += (25.0 - pe) * 1.6
    if pb:
        score += (3.0 - pb) * 8.0
    if earnings_yield:
        score += (earnings_yield - 4.0) * 3.0
    return clamp(score, 0.0, 100.0)


def _score_cost(snapshot: ETFSnapshot) -> float:
    expense = _metric(snapshot, "expense_ratio")
    if expense is None:
        return 50.0
    # <=0.10% excellent, >=1.20% poor.
    score = 100.0 - ((expense - 0.10) / 1.10) * 100.0
    return clamp(score, 0.0, 100.0)


def _score_quality(snapshot: ETFSnapshot) -> float:
    score = 50.0
    top10 = _metric(snapshot, "top10_weight")
    holdings = _metric(snapshot, "holdings_count")
    turnover = _metric(snapshot, "turnover")
    tracking_error = _metric(snapshot, "tracking_error")

    if top10 is not None:
        score += (40.0 - top10) * 0.8
    if holdings is not None:
        score += min(25.0, holdings / 20.0)
    if turnover is not None:
        score += (40.0 - turnover) * 0.5
    if tracking_error is not None:
        score += (0.6 - tracking_error) * 25.0
    return clamp(score, 0.0, 100.0)


def _score_liquidity(snapshot: ETFSnapshot) -> float:
    score = 50.0
    aum = _metric(snapshot, "aum")
    spread = _metric(snapshot, "bid_ask_spread_bps")
    premium_discount = _metric(snapshot, "premium_discount")

    if aum is not None:
        if aum >= 5e9:
            score += 30.0
        elif aum >= 1e9:
            score += 20.0
        elif aum >= 3e8:
            score += 10.0
        else:
            score -= 10.0
    if spread is not None:
        score += (20.0 - spread) * 1.5
    if premium_discount is not None:
        score -= abs(premium_discount) * 10.0
    return clamp(score, 0.0, 100.0)


def _coverage(snapshot: ETFSnapshot) -> float:
    important = [
        "expense_ratio",
        "aum",
        "pe",
        "pb",
        "top10_weight",
        "holdings_count",
        "tracking_error",
        "bid_ask_spread_bps",
    ]
    got = sum(1 for k in important if k in snapshot.metrics)
    return 0.45 + (got / len(important)) * 0.55


def _recommendation(overall: float) -> str:
    if overall >= 75:
        return "attractive entry point"
    if overall >= 60:
        return "reasonable; monitor entry price"
    if overall >= 45:
        return "neutral; no clear edge"
    return "potentially overvalued or weak"


def _reasons(
    snapshot: ETFSnapshot,
    valuation: float,
    cost: float,
    quality: float,
    liquidity: float,
    coverage: float,
) -> list[str]:
    reasons: list[str] = []
    if valuation < 45:
        reasons.append("Valuation looks stretched based on aggregate multiples.")
    if cost < 45:
        reasons.append("High cost (expense ratio) versus alternatives.")
    if quality < 45:
        reasons.append("Portfolio structure shows weaker quality signals.")
    if liquidity < 45:
        reasons.append("Limited liquidity (AUM/spread/premium-discount).")
    if coverage < 0.7:
        reasons.append("Partial data coverage; lower confidence in the conclusion.")
    if not reasons:
        reasons.append("Valuation, cost, and liquidity metrics are in a favorable range.")
    return reasons
