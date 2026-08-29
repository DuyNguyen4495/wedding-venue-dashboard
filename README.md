# Wedding Venue Dashboard

## Run it

```
cd "Wedding Packages/dashboard"
streamlit run app.py
```

Opens in your browser at `http://localhost:8501`. Leave the terminal running while you use it.

## Data model

`data/venues.csv` is the **single source of truth**. Everything else (the dashboard, the Excel
export) is generated from it — don't hand-edit `Coyote_Hills_Venue_Tracker.xlsx` directly, since
it gets overwritten by `export_excel.py`.

| Column | Type | Notes |
|---|---|---|
| `status` | text | `Baseline` / `Sourced` / `Not Sourced` |
| `venue_type` | text | `All-Inclusive Package` / `Ceremony Only` / `Reception Only` |
| `venue` | text | name |
| `city` | text | |
| `region` | text | one of: Orange County, LA County, Inland Empire, San Diego County, Ventura County, Riverside / Wine Country, Central Coast |
| `category` | text | Golf Course, Estate / Manor, All-Inclusive Chain, Restaurant Buyout, etc. |
| `price_low` / `price_high` | number | estimated total cost in USD (100 guests, where applicable). Leave blank if unknown — don't guess. |
| `price_per_guest_low` / `price_per_guest_high` | number | per-guest USD. Blank for flat-fee venues (most ceremony-only spots). |
| `price_basis` | text | free text explaining what the price numbers actually represent, e.g. "100 guests", "starting fee, not confirmed at 100" |
| `bar_included` | text | `Included` / `Not Included` / `Unconfirmed` / `Ambiguous` / `Not applicable - ceremony only` |
| `confidence` | text | `Confirmed` (from the venue's own brochure/quote) / `Medium` (pieced together from official page + aggregators) / `Low` (thin public data) |
| `notes` | text | everything else — what's included, caveats, contact info, next steps |
| `source_urls` | text | optional, semicolon-separated |
| `date_sourced` | date | `YYYY-MM-DD` |

## How to add new venues

Just ask Claude to research more places — same as this session. Claude appends new rows directly
to `data/venues.csv` following the schema above:

- Fill numeric price fields only when a number is actually confirmed or reasonably derivable.
- Leave numeric fields blank (not zero, not a guess) when unknown, and explain why in `notes`.
- Keep any field containing a comma wrapped in double quotes (standard CSV escaping) — a stray
  unquoted comma will break the file. If you edit the CSV by hand, validate it afterward:

```
python -c "import pandas as pd; print(len(pd.read_csv('data/venues.csv')))"
```

No changes to `app.py` are needed for ordinary new rows — the dashboard reads whatever is in the
CSV. Two exceptions:
- **New column** — only if you introduce a genuinely new field.
- **New city** — the map geocodes by city name using the `CITY_COORDS` dict at the top of `app.py`
  (approximate city-center coordinates, not exact addresses). If a new venue's `city` value isn't
  already a key in that dict, add one `"City Name": (lat, lon)` entry — otherwise that venue just
  won't show a pin on the map (it'll still appear in every table/filter normally).

## Seeing new data

The dashboard caches on the CSV's last-modified time. After new rows are added:
- If the app isn't running, just start it (`streamlit run app.py`) — it'll show the latest data.
- If it's already running, press **R** in the browser tab (Streamlit's rerun shortcut) or refresh
  the page.

## Refreshing the Excel export

```
python export_excel.py
```

Regenerates `../Coyote_Hills_Venue_Tracker.xlsx` from the current CSV, with the same color-coded,
filterable-table styling as before. Run this whenever you want an up-to-date Excel copy to browse
or share outside the dashboard.
