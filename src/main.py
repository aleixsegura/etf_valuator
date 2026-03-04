from typing import Optional, TypedDict

import yfinance as yf


class RatioResult(TypedDict):
    ticker: str
    pe_ratio: Optional[float]
    peg_ratio: Optional[float]


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

    pe = info.get("trailingPE") or info.get("forwardPE")
    peg = info.get("pegRatio")

    return {
        "ticker": ticker,
        "pe_ratio": pe,
        "peg_ratio": peg,
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


if __name__ == "__main__":
    # Example manual test usage; replace with any ticker you like.
    stock_example = get_stock_ratios("AAPL")
    etf_example = get_etf_ratios("VOO")

    print("Stock ratios:", stock_example)
    print("ETF ratios:", etf_example)

