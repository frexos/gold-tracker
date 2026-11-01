#!/usr/bin/env python3
"""Daily price fetcher: appends one row to data/prices.csv.

Run from the repo root (or via GitHub Actions):
    python3 scripts/fetch_price.py

Requires env var GOLD_API_KEY (API Ninjas key).
No third-party packages needed.
"""

import csv
import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "prices.csv"
FIELDS = ["date", "gold_usd_oz", "usd_eur", "gold_eur_oz"]

GOLD_URL = "https://api.api-ninjas.com/v1/goldprice"
FX_URL = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=EUR"
FX_URL_FALLBACK = "https://api.frankfurter.app/latest?from=USD&to=EUR"


def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def fetch_gold_usd():
    api_key = os.environ.get("GOLD_API_KEY", "").strip()
    if not api_key:
        sys.exit("GOLD_API_KEY environment variable is not set.")
    data = json.loads(http_get(GOLD_URL, headers={"X-Api-Key": api_key}))
    # Response: {"price": 1234.56, "timestamp": ...}  (USD per troy oz)
    price = float(data["price"])
    if not (100 < price < 20000):
        sys.exit(f"Gold price looks wrong: {price}")
    return price


def fetch_usd_eur():
    last_error = None
    for url in (FX_URL, FX_URL_FALLBACK):
        try:
            data = json.loads(http_get(url))
            return float(data["rates"]["EUR"])
        except Exception as e:
            last_error = e
    sys.exit(f"Could not fetch USD/EUR rate: {last_error}")


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
    today = dt.date.today().isoformat()

    print("Fetching gold price…")
    gold_usd = fetch_gold_usd()
    print(f"  Gold: ${gold_usd:.2f}/oz")

    print("Fetching USD/EUR rate…")
    usd_eur = fetch_usd_eur()
    print(f"  Rate: {usd_eur:.5f}")

    gold_eur = gold_usd * usd_eur

    new_row = {
        "date": today,
        "gold_usd_oz": f"{gold_usd:.2f}",
        "usd_eur": f"{usd_eur:.5f}",
        "gold_eur_oz": f"{gold_eur:.2f}",
    }

    rows = load_rows()
    # Replace today's row if it already exists (safe to rerun)
    rows = [r for r in rows if r["date"] != today]
    rows.append(new_row)
    save_rows(rows)

    print(f"Saved: {today}  gold_eur_oz={gold_eur:.2f}  -> {DATA_FILE}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"fetch_price failed: {e}")
