import csv
import argparse
import yfinance as yf
from pathlib import Path
from typing import Optional, TypedDict, List, Tuple

class RatioResult(TypedDict):
    ticker: str
    trailing_pe_ratio: Optional[float]
    forward_pe_ratio: Optional[float]
    trailing_peg_ratio: Optional[float]


def _get_ratios_for_ticker(ticker: str) -> RatioResult:
    """
    Fetch P/E and PEG ratios for a given ticker (stock or ETF) using yfinance.

    Values may be None if the data is not available from the data source.
    """
    yf_ticker = yf.Ticker(ticker)

    # yfinance 2.x uses get_info; older versions expose .info.
    try:
        info = yf_ticker.get_info()
    except AttributeError:
        info = getattr(yf_ticker, "info", {}) or {}

    trailing_pe_ratio = info.get("trailingPE")
    forward_pe_ratio = info.get("forwardPE")
    trailing_peg_ratio = info.get("trailingPegRatio")

    return {
        "ticker": ticker,
        "trailing_pe_ratio": round(trailing_pe_ratio, 2) if trailing_pe_ratio is not None else None,
        "forward_pe_ratio": round(forward_pe_ratio, 2) if forward_pe_ratio is not None else None,
        "trailing_peg_ratio": round(trailing_peg_ratio, 2) if trailing_peg_ratio is not None else None,
    }


def get_stock_ratios(ticker: str) -> RatioResult:
    """
    Get P/E and PEG ratios for an individual stock.

    Example:
        get_stock_ratios("AAPL")
    """
    return _get_ratios_for_ticker(ticker)


def get_etf_ratios(ticker: str) -> RatioResult:
    """
    Get P/E and PEG ratios for an ETF.

    Example:
        get_etf_ratios("VOO")
    """
    return _get_ratios_for_ticker(ticker)


def load_tickers_from_csv(path: str) -> List[Tuple[str, str]]:
    """
    Load (type, ticker) pairs from a CSV file.

    Expected format:
        type,ticker
        stock,AAPL
        etf,VOO

    Lines starting with '#' or empty lines are ignored.
    """
    result: List[Tuple[str, str]] = []
    csv_path = Path(path)

    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            # Allow comments
            if row[0].lstrip().startswith("#"):
                continue
            if len(row) < 2:
                raise ValueError(f"Invalid row in CSV (need type,ticker): {row}")

            raw_type, raw_ticker = row[0].strip(), row[1].strip()
            type_lower = raw_type.lower()
            if type_lower not in {"stock", "etf"}:
                raise ValueError(
                    f"Invalid type '{raw_type}' in CSV, expected 'stock' or 'etf'"
                )

            ticker = raw_ticker.upper()
            if not ticker:
                raise ValueError(f"Empty ticker in row: {row}")

            result.append((type_lower, ticker))

    return result


def process_tickers_file(path: str) -> None:
    """
    Read tickers from a CSV file and print their ratios.
    """
    pairs = load_tickers_from_csv(path)
    print(f"[Processing] {len(pairs)} tickers from CSV '{path}':")
    print("type,ticker,trailing_pe_ratio,forward_pe_ratio,trailing_peg_ratio")

    for type_lower, ticker in pairs:
        if type_lower == "stock":
            ratios = get_stock_ratios(ticker)
        else:
            ratios = get_etf_ratios(ticker)

        trailing_pe = (
            str(ratios["trailing_pe_ratio"])
            if ratios["trailing_pe_ratio"] is not None
            else "N/A"
        )
        forward_pe = (
            str(ratios["forward_pe_ratio"])
            if ratios["forward_pe_ratio"] is not None
            else "N/A"
        )
        trailing_peg = (
            str(ratios["trailing_peg_ratio"])
            if ratios["trailing_peg_ratio"] is not None
            else "N/A"
        )

        print(
            f"{type_lower},{ratios['ticker']},"
            f"{trailing_pe},{forward_pe},{trailing_peg}"
        )


def process_tickers_args(tickers: List[str]) -> None:
    """
    Process tickers provided as positional CLI arguments.

    All tickers are treated as stocks by default.
    """
    normalized = [t.strip().upper() for t in tickers if t.strip()]
    print(f"Processing {len(normalized)} tickers from CLI arguments:")
    print("type,ticker,trailing_pe_ratio,forward_pe_ratio,trailing_peg_ratio")

    for ticker in normalized:
        ratios = get_stock_ratios(ticker)

        trailing_pe = (
            str(ratios["trailing_pe_ratio"])
            if ratios["trailing_pe_ratio"] is not None
            else "N/A"
        )
        forward_pe = (
            str(ratios["forward_pe_ratio"])
            if ratios["forward_pe_ratio"] is not None
            else "N/A"
        )
        trailing_peg = (
            str(ratios["trailing_peg_ratio"])
            if ratios["trailing_peg_ratio"] is not None
            else "N/A"
        )

        print(
            f"stock,{ratios['ticker']},"
            f"{trailing_pe},{forward_pe},{trailing_peg}"
        )


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate P/E and PEG ratios for stocks and ETFs."
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        help="Path to a CSV file with 'type,ticker' rows (type is 'stock' or 'etf').",
    )
    parser.add_argument(
        "tickers",
        nargs="*",
        help="Ticker symbols as positional arguments (treated as stocks).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    if args.csv_path and args.tickers:
        raise SystemExit(
            "Error: specify either --csv <file> or positional tickers, but not both."
        )

    if args.csv_path:
        process_tickers_file(args.csv_path)
    elif args.tickers:
        process_tickers_args(args.tickers)
    else:
        raise SystemExit(
            "No tickers provided. Use positional tickers, e.g. "
            "'python -m src.main AAPL MSFT', or --csv tickers.csv."
        )


if __name__ == "__main__":
    main()
