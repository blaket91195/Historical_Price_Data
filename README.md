# ASX Historical Price Fetcher

Downloads daily **adjusted close** prices for ASX stocks and ETFs from Yahoo
Finance using [yfinance](https://github.com/ranaroussi/yfinance), and saves
them as a single wide CSV.

## Setup

```bash
pip install -r requirements.txt
```

## tickers.txt format

One ASX ticker per line, **without** the `.AX` exchange suffix.  
Blank lines and lines starting with `#` are ignored.

```
# ETFs
VGS
VAS
NDQ

# Blue chips
CBA
BHP
CSL
```

## Usage

```bash
# Interactive — the script will prompt for a timeframe
python fetch_prices.py

# Use a custom tickers file
python fetch_prices.py --tickers /path/to/my_tickers.txt
```

### Timeframe input

When prompted, enter one of:

| Format | Example | Meaning |
|--------|---------|---------|
| Period shortcut | `1y` | Last 1 year |
| Period shortcut | `5y` | Last 5 years |
| Period shortcut | `ytd` | Year-to-date |
| Period shortcut | `max` | Full history |
| Start date only | `2020-01-01` | 2020-01-01 → today |
| Start + end date | `2020-01-01 2023-12-31` | Explicit range |

Valid period shortcuts: `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `10y`, `ytd`, `max`

## Output

A CSV file at `data/prices_{START}_{END}.csv`:

- **Rows** — trading dates (`YYYY-MM-DD`), sorted ascending.
- **Columns** — ticker symbols (without `.AX` suffix).
- **Values** — dividend- and split-adjusted close price (AUD).
- Missing data (ticker didn't exist yet, trading halt, etc.) appears as blank
  cells (`NaN`). No forward-filling is applied.

Example output path: `data/prices_2020-01-02_2024-12-31.csv`

### Adjusted close

`auto_adjust=True` is passed to yfinance so the `Close` column returned is
already the fully-adjusted close. The raw `Adj Close` column is not used.

## Example session

```
$ python fetch_prices.py
Loaded 20 ticker(s) from tickers.txt

Timeframe options:
  Period shortcut : 1mo, 1y, 2y, 3mo, 5y, 6mo, 10y, max, ytd
  Date range      : START [END]   (YYYY-MM-DD; END defaults to today)

Enter timeframe: 1y

Fetching 20 ticker(s) …

  VGS          rows=251   range=2024-05-07 → 2025-05-06  status=OK
  VAS          rows=251   range=2024-05-07 → 2025-05-06  status=OK
  …
  BADTICKER    rows=0     range=n/a                       status=FAILED

Saved → data/prices_2024-05-07_2025-05-06.csv
```
