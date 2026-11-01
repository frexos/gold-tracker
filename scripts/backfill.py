#!/usr/bin/env python3
"""One-time backfill: fill data/prices.csv with past gold prices in euros.

Run once from the repo folder:   python3 scripts/backfill.py

Sources (all free, no key):
  - Gold history in USD/oz: Free Gold API (freegoldapi.com)
    daily for recent years, monthly before that
  - Supplementary recent gold history: Yahoo Finance v8 JSON API (GC=F futures)
    used to fill dates after the freegoldapi.com data ends
  - USD -> EUR history: ECB reference rates via Frankfurter (from 1999, when the euro started)

Rows already in prices.csv (from the daily job) are kept as they are.
Safe to run again; it only adds dates that are missing.
"""

import csv
import datetime as dt
import io
import json
import sys
import urllib.request
from bisect import bisect_right
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "prices.csv"
FIELDS = ["date", "gold_usd_oz", "usd_eur", "gold_eur_oz"]

GOLD_URL = "https://freegoldapi.com/data/latest.csv"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF?range=2y&interval=1d"
FX_URL_TEMPLATES = [
    "https://api.frankfurter.dev/v1/{start}..{end}?base=USD&symbols=EUR",
    "https://api.frankfurter.app/{start}..{end}?from=USD&to=EUR",
]
EURO_START = dt.date(1999, 1, 4)  # first ECB euro reference rate


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "gold-tracker/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


def parse_date(text):
    """Accept YYYY-MM-DD, YYYY-MM or YYYY; return a date or None."""
    text = text.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return dt.datetime.strptime(text[: len(dt.date.today().strftime(fmt))], fmt).date()
        except ValueError:
            continue
    return None


def fetch_gold_history():
    """Return {date: usd_per_oz} from Free Gold API, euro era only."""
    reader = csv.DictReader(io.StringIO(http_get(GOLD_URL)))
    prices = {}
    for row in reader:
        d = parse_date(row.get("date", ""))
        try:
            price = float(row.get("price", ""))
        except ValueError:
            continue
        if d is None or d.year < EURO_START.year or not 100 < price < 20000:
            continue  # skip pre-euro dates, annual GBP-era rows and bad values
        prices[d] = price
    if not prices:
        raise RuntimeError("Free Gold API returned no usable rows (has the format changed?)")
    return prices


def fetch_gold_yahoo(after):
    """Return {date: usd_per_oz} from Yahoo Finance for dates strictly after `after`."""
    req = urllib.request.Request(
        YAHOO_URL,
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    result = data["chart"]["result"][0]
    timestamps = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]
    prices = {}
    for ts, price in zip(timestamps, closes):
        if price is None:
            continue
        d = dt.datetime.utcfromtimestamp(ts).date()
        if d > after and 100 < price < 20000:
            prices[d] = price
    return prices


def fetch_fx_history(start, end):
    """Return sorted list of (date, usd_eur), fetched one year at a time."""
    rates = {}
    year = start.year
    while year <= end.year:
        s = max(start, dt.date(year, 1, 1))
        e = min(end, dt.date(year, 12, 31))
        last_error = None
        for template in FX_URL_TEMPLATES:
            try:
                data = json.loads(http_get(template.format(start=s.isoformat(), end=e.isoformat())))
                for day, r in data["rates"].items():
                    rates[dt.date.fromisoformat(day)] = float(r["EUR"])
                break
            except Exception as err:
                last_error = err
        else:
            raise RuntimeError(f"Could not get USD/EUR rates for {year}: {last_error}")
        print(f"  exchange rates {year} ok")
        year += 1
    return sorted(rates.items())


def rate_on(fx, day):
    """Most recent ECB rate on or before `day` (weekends/holidays use the last business day)."""
    i = bisect_right([d for d, _ in fx], day)
    if i == 0:
        return fx[0][1]
    return fx[i - 1][1]


def load_rows():
    if not DATA_FILE.exists():
        return []
    with DATA_FILE.open(newline="") as f:
        return list(csv.DictReader(f))


def save_rows(rows):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: r["date"]))


def main():
    print("Downloading gold history (freegoldapi.com)…")
    gold = fetch_gold_history()
    first, last = min(gold), max(gold)
    print(f"  {len(gold)} prices from {first} to {last}")

    print("Downloading supplementary gold history (Yahoo Finance)…")
    yahoo = fetch_gold_yahoo(after=last)
    if yahoo:
        y_last = max(yahoo)
        print(f"  {len(yahoo)} additional prices from {min(yahoo)} to {y_last}")
        gold.update(yahoo)
        last = max(gold)
    else:
        print("  none needed")

    print("Downloading exchange rates…")
    fx = fetch_fx_history(first, last)

    existing = load_rows()
    have = {r["date"] for r in existing}
    added = []
    for day, usd in sorted(gold.items()):
        key = day.isoformat()
        if key in have:
            continue
        rate = rate_on(fx, day)
        added.append({
            "date": key,
            "gold_usd_oz": f"{usd:.2f}",
            "usd_eur": f"{rate:.5f}",
            "gold_eur_oz": f"{usd * rate:.2f}",
        })

    save_rows(existing + added)
    print(f"Done: added {len(added)} rows, kept {len(existing)} existing rows -> {DATA_FILE}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(f"Backfill failed: {e}")
