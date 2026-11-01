# Gold Sovereign Tracker

Personal project: track the value of the British gold sovereign (χρυσή λίρα Αγγλίας) in euros, with a daily-updated chart on GitHub Pages.

## How it works
- `scripts/fetch_price.py`: runs daily in GitHub Actions. Gets gold in USD/oz from API Ninjas (`/v1/goldprice`, key in repo secret `GOLD_API_KEY`) and USD→EUR from Frankfurter (ECB rates, no key). Writes one row per day to `data/prices.csv` (same-day reruns replace the row). Standard library only, no pip.
- `scripts/backfill.py`: one-time history fill. Gold USD history from freegoldapi.com (`/data/latest.csv`, monthly before 2025, daily after), converted with ECB rates fetched one year at a time. Only adds missing dates; never overwrites rows.
- `.github/workflows/update.yml`: cron daily at 07:23 UTC, plus on push and manual (`gh workflow run update.yml`). Fetches, commits the CSV, copies `site/*` and `prices.csv` into `_site`, deploys with the official Pages actions. Pages source is "GitHub Actions".
- `site/index.html`: static page, Chart.js from cdnjs, reads `prices.csv`. Tiles: sovereign gold value, estimated bank sell/buy, gold €/oz. Ranges 1M/3M/1Y/5Y/All, toggle sovereign vs €/oz. Light/dark via prefers-color-scheme.

## Key numbers and assumptions
- A sovereign holds 7.3224 g fine gold = 0.23542 troy oz. Sovereign value = gold €/oz × 0.23542.
- Estimated bank prices (not official): sell-to-bank ≈ 0.96 × gold value, buy-from-bank ≈ 1.125 × gold value, based on past Bank of Greece bulletins. Constants `SELL_FACTOR` / `BUY_FACTOR` in `site/index.html`.
- Official sovereign prices in Greece come from the Bank of Greece (bulletin reissued irregularly, not daily) and Piraeus Bank. Neither has an API.

## Decisions so far
- Free hosting: GitHub Actions + GitHub Pages (chosen over a VPS or a home server).
- `gh` installed from GitHub's apt repo, not the snap.
- CSV columns: `date,gold_usd_oz,usd_eur,gold_eur_oz`. Keep this schema; the page and both scripts depend on it.

## Possible next steps
- Price alerts when the sovereign crosses a chosen level.
- Show the real Bank of Greece / Piraeus prices if a reliable source is found.
