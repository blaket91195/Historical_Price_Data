"""
fetch_prices.py — Download daily adjusted close prices for ASX tickers via yfinance.

Design note: auto_adjust=True is set on every yfinance download call, which makes
the returned 'Close' column the dividend- and split-adjusted close. The raw 'Adj Close'
column is therefore redundant and is not used.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_PERIODS = {"1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}
DATE_FMT = "%Y-%m-%d"
EXCHANGE_SUFFIX = ".AX"
DATA_DIR = Path(__file__).parent / "data"
TICKERS_FILE = Path(__file__).parent / "tickers.txt"


# ---------------------------------------------------------------------------
# Ticker loading
# ---------------------------------------------------------------------------

def load_tickers(path: Path) -> list[str]:
    """Return ticker symbols from *path*, ignoring blank lines and # comments."""
    tickers: list[str] = []
    with path.open() as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            tickers.append(stripped.upper())
    if not tickers:
        raise ValueError(f"No tickers found in {path}")
    return tickers


# ---------------------------------------------------------------------------
# User input / validation
# ---------------------------------------------------------------------------

def _today_str() -> str:
    return date.today().strftime(DATE_FMT)


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, DATE_FMT).date()
    except ValueError:
        raise ValueError(f"Expected YYYY-MM-DD, got '{value}'")


def prompt_timeframe() -> dict[str, str]:
    """
    Interactively ask the user for a timeframe.

    Returns a dict with either:
      {"period": "<period>"}                         — for period shortcuts
      {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}  — for explicit dates
    """
    print()
    print("Timeframe options:")
    print(f"  Period shortcut : {', '.join(sorted(VALID_PERIODS))}")
    print("  Date range      : START [END]   (YYYY-MM-DD; END defaults to today)")
    print()

    while True:
        raw = input("Enter timeframe: ").strip()
        if not raw:
            print("  [!] Input cannot be empty. Try again.")
            continue

        parts = raw.split()

        # --- period shortcut ---
        if len(parts) == 1 and parts[0].lower() in VALID_PERIODS:
            return {"period": parts[0].lower()}

        # --- explicit date(s) ---
        try:
            if len(parts) == 1:
                start = _parse_date(parts[0])
                end = date.today()
            elif len(parts) == 2:
                start = _parse_date(parts[0])
                end = _parse_date(parts[1])
            else:
                raise ValueError("Too many tokens.")

            if start >= end:
                raise ValueError(f"Start ({start}) must be before end ({end}).")
            if start > date.today():
                raise ValueError("Start date is in the future.")

            return {"start": str(start), "end": str(end)}

        except ValueError as exc:
            print(f"  [!] {exc} Try again.")


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_ticker(
    symbol: str,
    *,
    period: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> pd.Series | None:
    """
    Download adjusted close prices for a single ticker.

    Returns a named pd.Series indexed by date (datetime.date), or None on failure.
    """
    kwargs: dict = {"auto_adjust": True, "interval": "1d", "progress": False}
    if period:
        kwargs["period"] = period
    else:
        kwargs["start"] = start
        kwargs["end"] = end

    try:
        df = yf.download(symbol, **kwargs, multi_level_index=False)
    except Exception as exc:  # noqa: BLE001
        print(f"  [{symbol}] Download error: {exc}")
        return None

    if df is None or df.empty:
        return None

    # With auto_adjust=True the 'Close' column is already the adjusted close.
    if "Close" not in df.columns:
        return None

    series = df["Close"].dropna()
    series.index = pd.to_datetime(series.index).date  # type: ignore[assignment]
    series.name = symbol.replace(EXCHANGE_SUFFIX, "")
    return series


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def fetch_all(
    tickers: list[str],
    timeframe: dict[str, str],
) -> pd.DataFrame:
    """Fetch all tickers and return a combined wide DataFrame."""
    series_list: list[pd.Series] = []

    for base in tickers:
        symbol = base + EXCHANGE_SUFFIX
        s = fetch_ticker(symbol, **timeframe)  # type: ignore[arg-type]

        if s is None or s.empty:
            print(f"  {base:<12} rows=0   range=n/a          status=FAILED")
        else:
            date_range = f"{s.index[0]} → {s.index[-1]}"
            print(f"  {base:<12} rows={len(s):<5} range={date_range}  status=OK")
            series_list.append(s)

    if not series_list:
        raise RuntimeError("No data was retrieved for any ticker.")

    # Outer join on date index — NaN where a ticker didn't trade / didn't exist yet.
    combined = pd.concat(series_list, axis=1, join="outer")
    combined.sort_index(inplace=True)
    combined.index.name = "Date"
    return combined


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def resolve_output_path(timeframe: dict[str, str], df: pd.DataFrame) -> Path:
    """Build the output path from the actual date range present in *df*."""
    start_str = str(df.index[0])
    end_str = str(df.index[-1])
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / f"prices_{start_str}_{end_str}.csv"


def save_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, date_format=DATE_FMT)
    print(f"\nSaved → {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch daily adjusted close prices for ASX tickers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python fetch_prices.py\n"
            "  python fetch_prices.py --tickers my_tickers.txt\n"
        ),
    )
    parser.add_argument(
        "--tickers",
        type=Path,
        default=TICKERS_FILE,
        metavar="FILE",
        help="Path to tickers file (default: tickers.txt next to this script)",
    )
    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    tickers_path: Path = args.tickers
    if not tickers_path.exists():
        parser.error(f"Tickers file not found: {tickers_path}")

    try:
        tickers = load_tickers(tickers_path)
    except ValueError as exc:
        parser.error(str(exc))
        return  # unreachable; silences type-checker

    print(f"Loaded {len(tickers)} ticker(s) from {tickers_path.name}")

    timeframe = prompt_timeframe()

    print(f"\nFetching {len(tickers)} ticker(s) …\n")
    df = fetch_all(tickers, timeframe)

    output_path = resolve_output_path(timeframe, df)
    save_csv(df, output_path)


if __name__ == "__main__":
    main()
