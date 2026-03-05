from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SOURCE_PRIORITY = {"official": 3, "derived": 2, "yahoo": 1}


@dataclass
class MetricValue:
    key: str
    value: float
    source: str
    confidence: float = 1.0
    raw: Any = None


@dataclass
class ETFSnapshot:
    ticker: str
    name: str | None = None
    issuer: str | None = None
    category: str | None = None
    official_url: str | None = None
    metrics: dict[str, MetricValue] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def set_metric(
        self,
        key: str,
        value: float | None,
        source: str,
        confidence: float = 1.0,
        raw: Any = None,
    ) -> None:
        if value is None:
            return
        previous = self.metrics.get(key)
        if previous is None:
            self.metrics[key] = MetricValue(
                key=key, value=value, source=source, confidence=confidence, raw=raw
            )
            return
        prev_rank = SOURCE_PRIORITY.get(previous.source, 0)
        current_rank = SOURCE_PRIORITY.get(source, 0)
        if current_rank > prev_rank:
            self.metrics[key] = MetricValue(
                key=key, value=value, source=source, confidence=confidence, raw=raw
            )


@dataclass
class ScoreBreakdown:
    valuation: float
    cost: float
    quality: float
    liquidity: float
    coverage: float
    overall: float
    recommendation: str
    reasons: list[str]


@dataclass
class ETFValuationResult:
    snapshot: ETFSnapshot
    score: ScoreBreakdown
