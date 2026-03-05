from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable

from .engine import ETFValuationEngine


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ETF valuer with official-source-first pipeline.")
    parser.add_argument("tickers", nargs="*", help="ETF tickers to evaluate, e.g. VOO SPY.")
    parser.add_argument(
        "--csv",
        dest="csv_path",
        help="CSV file with at least one column named 'ticker' (or first column as ticker).",
    )
    parser.add_argument(
        "--official-url",
        dest="official_url",
        help="Optional official ETF URL (only valid for single ticker mode).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit result as JSON.",
    )
    return parser.parse_args(argv)


def load_tickers_from_csv(path: str) -> list[str]:
    csv_path = Path(path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    tickers: list[str] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        rows = [r for r in reader if r and not r[0].strip().startswith("#")]
    if not rows:
        return tickers

    header = [c.strip().lower() for c in rows[0]]
    if "ticker" in header:
        idx = header.index("ticker")
        for row in rows[1:]:
            if idx < len(row) and row[idx].strip():
                tickers.append(row[idx].strip().upper())
        return tickers

    # Fallback: first column is ticker.
    for row in rows:
        symbol = row[0].strip().upper()
        if symbol and symbol != "TICKER":
            tickers.append(symbol)
    return tickers


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.csv_path and args.tickers:
        raise SystemExit("Use either positional tickers or --csv, not both.")

    tickers: list[str]
    if args.csv_path:
        tickers = load_tickers_from_csv(args.csv_path)
    else:
        tickers = [t.strip().upper() for t in args.tickers if t.strip()]

    if not tickers:
        raise SystemExit("No tickers provided. Use tickers or --csv.")
    if args.official_url and len(tickers) != 1:
        raise SystemExit("--official-url only supports a single ticker run.")

    engine = ETFValuationEngine()
    results = []
    for ticker in tickers:
        official_url = args.official_url if len(tickers) == 1 else None
        results.append(engine.evaluate(ticker=ticker, official_url=official_url))

    if args.json:
        print(json.dumps([_to_dict(r) for r in results], ensure_ascii=False, indent=2))
    else:
        _print_human(results)
    return 0


def _print_human(results: Iterable) -> None:
    for result in results:
        snap = result.snapshot
        score = result.score
        print(f"\nTicker: {snap.ticker}")
        print(f"Name: {snap.name or 'N/A'}")
        print(f"Issuer: {snap.issuer or 'N/A'}")
        print(f"Category: {snap.category or 'N/A'}")
        print(f"Official URL: {snap.official_url or 'N/A'}")
        print(f"Recommendation: {score.recommendation}")
        print(
            "Scores -> "
            f"overall={score.overall}/100, valuation={score.valuation}, cost={score.cost}, "
            f"quality={score.quality}, liquidity={score.liquidity}, coverage={score.coverage}"
        )
        print("Metrics:")
        for key in sorted(snap.metrics.keys()):
            metric = snap.metrics[key]
            print(f"  - {key}: {metric.value:.6g} ({metric.source})")
        if snap.artifacts:
            print("Official artifacts:")
            for key, value in snap.artifacts.items():
                print(f"  - {key}: {value}")
        print("Reasons:")
        for reason in score.reasons:
            print(f"  - {reason}")


def _to_dict(result) -> dict:
    snap = result.snapshot
    score = result.score
    return {
        "ticker": snap.ticker,
        "name": snap.name,
        "issuer": snap.issuer,
        "category": snap.category,
        "official_url": snap.official_url,
        "metrics": {
            k: {"value": v.value, "source": v.source, "confidence": v.confidence}
            for k, v in snap.metrics.items()
        },
        "artifacts": snap.artifacts,
        "notes": snap.notes,
        "score": {
            "overall": score.overall,
            "valuation": score.valuation,
            "cost": score.cost,
            "quality": score.quality,
            "liquidity": score.liquidity,
            "coverage": score.coverage,
            "recommendation": score.recommendation,
            "reasons": score.reasons,
        },
    }
