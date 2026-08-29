"""
Coyote Hills Wedding Venue Dashboard
Reads dashboard/data/venues.csv (the single source of truth) and lets you
filter/compare all-inclusive packages, ceremony-only venues, and
reception-only venues against the Coyote Hills baseline.

Run with:  streamlit run app.py
"""

import textwrap
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

DATA_PATH = Path(__file__).parent / "data" / "venues.csv"

st.set_page_config(
    page_title="Wedding Venue Dashboard",
    page_icon="\U0001F49D",
    layout="wide",
)

# ----------------------------------------------------------------------
# Approximate city-center coordinates. Not exact venue addresses — good
# enough for a "which part of SoCal is this" overview map. Keyed on the
# exact `city` string used in venues.csv. When you add a venue in a new
# city, add one entry here (lat, lon) — everything else about the map
# keeps working automatically.
# ----------------------------------------------------------------------
CITY_COORDS = {
    "Fullerton": (33.8704, -117.9243),
    "La Verne / Camarillo": (34.1008, -117.7692),
    "Fountain Valley": (33.7092, -117.9536),
    "Menifee": (33.6971, -117.1850),
    "Downey": (33.9401, -118.1332),
    "Irvine": (33.6846, -117.8265),
    "San Clemente": (33.4269, -117.6120),
    "Norco": (33.9312, -117.5486),
    "Temecula": (33.4936, -117.1484),
    "Santa Barbara": (34.4208, -119.6982),
    "Rancho Palos Verdes": (33.7445, -118.3870),
    "Laguna Beach / Newport Beach": (33.5427, -117.7854),
    "Pacific Palisades": (34.0480, -118.5265),
    "Garden Grove": (33.7743, -117.9382),
    "Los Angeles": (34.0522, -118.2437),
    "Santa Monica": (34.0195, -118.4912),
    "Aliso Viejo": (33.5765, -117.7256),
    "Long Beach": (33.7701, -118.1937),
    "Fallbrook (near Temecula)": (33.3764, -117.2511),
    "Orange County": (33.7879, -117.8531),
    "Riverside": (33.9806, -117.3755),
    "Inland Empire": (34.0633, -117.6509),
    "Beaumont": (33.9295, -116.9770),
    "Alpine": (32.8351, -116.7664),
    "San Marcos": (33.1434, -117.1661),
    "Fallbrook": (33.3764, -117.2511),
    "La Jolla (near Torrey Pines)": (32.8328, -117.2713),
    "San Diego (Mission Bay)": (32.7853, -117.2213),
    "Ramona": (33.0417, -116.8672),
    "Near Pasadena": (34.1478, -118.1445),
    "Palos Verdes": (33.7845, -118.3670),
    "Malibu": (34.0259, -118.7798),
    "Beverly Hills": (34.0736, -118.4004),
    "Beverly Hills / Santa Monica Mountains": (34.1119, -118.4136),
    "San Juan Capistrano": (33.5017, -117.6625),
}

CATEGORY_EMOJI = {
    "Golf Course": "⛳",
    "Estate / Manor": "\U0001F3DB️",
    "All-Inclusive Chain": "\U0001F38A",
    "All-Inclusive Chain / Garden": "\U0001F38A",
    "All-Inclusive Chain / Clubhouse": "\U0001F38A",
    "All-Inclusive Chain / Coastal": "\U0001F38A",
    "Chapel": "⛪",
    "Beach / Park": "\U0001F3D6️",
    "Restaurant Buyout": "\U0001F37D️",
    "Farm / Rustic": "\U0001F33E",
    "Resort / Inn": "\U0001F3E8",
    "Country Club": "⛳",
    "Garden Terrace": "\U0001F33F",
    "Historic Mission Garden": "⛪",
    "Meditation Garden / Lake": "\U0001F54A️",
    "Courthouse Garden": "\U0001F3DB️",
    "Historic House / Garden": "\U0001F3E1",
    "Banquet Hall": "\U0001F389",
    "Hotel Ballroom": "\U0001F3E8",
    "Castle / Estate": "\U0001F3F0",
    "Ranch": "\U0001F40E",
    "Garden / Resort-style": "\U0001F338",
    "Golf Course / Resort": "⛳",
    "Estate": "\U0001F3DB️",
    "Winery": "\U0001F347",
}
DEFAULT_CATEGORY_EMOJI = "\U0001F4CD"

STATUS_EMOJI = {"Baseline": "⭐", "Sourced": "✅", "Not Sourced": "\U0001F50D"}
TYPE_EMOJI = {
    "All-Inclusive Package": "\U0001F381",
    "Ceremony Only": "\U0001F48D",
    "Reception Only": "\U0001F942",
}

MAP_COLORS = {
    "Baseline": "#A8752B",
    ("Sourced", "All-Inclusive Package"): "#3F5233",
    ("Sourced", "Ceremony Only"): "#3A5A72",
    ("Sourced", "Reception Only"): "#9A4433",
    "Not Sourced": "#8C8C82",
}
MAP_SIZE = {"Baseline": 2600, "Sourced": 1600, "Not Sourced": 900}


@st.cache_data
def load_data(path: str, mtime: float) -> pd.DataFrame:
    """mtime is part of the cache key so editing venues.csv and rerunning
    the app (or just refreshing the page) always picks up new rows."""
    df = pd.read_csv(path)
    for col in ["price_low", "price_high", "price_per_guest_low", "price_per_guest_high"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_current() -> pd.DataFrame:
    mtime = DATA_PATH.stat().st_mtime
    return load_data(str(DATA_PATH), mtime)


def geocode(frame: pd.DataFrame) -> pd.DataFrame:
    """Adds lat/lon (with small deterministic jitter for venues sharing a
    city) so overlapping markers stay visible on the map."""
    out = frame.copy()
    lats, lons = [], []
    seen_counts: dict[str, int] = {}
    for city in out["city"]:
        base = CITY_COORDS.get(city)
        if base is None:
            lats.append(None)
            lons.append(None)
            continue
        n = seen_counts.get(city, 0)
        seen_counts[city] = n + 1
        # spiral a tiny jitter outward for the 2nd, 3rd... venue in the same city
        jitter = 0.012 * n
        angle = n * 2.4
        lat = base[0] + jitter * (0.6 * (angle % 2 - 1))
        lon = base[1] + jitter * ((angle % 3) - 1)
        lats.append(lat)
        lons.append(lon)
    out["lat"] = lats
    out["lon"] = lons
    return out


def map_color(row) -> str:
    if row["status"] == "Baseline":
        return MAP_COLORS["Baseline"]
    if row["status"] == "Not Sourced":
        return MAP_COLORS["Not Sourced"]
    return MAP_COLORS.get((row["status"], row["venue_type"]), MAP_COLORS["Not Sourced"])


def map_size(row) -> int:
    return MAP_SIZE.get(row["status"], MAP_SIZE["Sourced"])


df = geocode(load_current())
baseline = df[df["status"] == "Baseline"].iloc[0]


def money(val) -> str:
    if pd.isna(val):
        return "—"
    return f"${val:,.0f}"


def fmt_range(low, high) -> str:
    if pd.isna(low) and pd.isna(high):
        return "—"
    if pd.isna(high) or low == high:
        return money(low)
    return f"{money(low)} – {money(high)}"


# ----------------------------------------------------------------------
# Sidebar filters
# ----------------------------------------------------------------------
st.sidebar.title("\U0001F50E Filters")

status_opts = sorted(df["status"].unique())
status_sel = st.sidebar.multiselect("Status", status_opts, default=status_opts)

type_opts = sorted(df["venue_type"].unique())
type_sel = st.sidebar.multiselect("Venue type", type_opts, default=type_opts)

region_opts = sorted(df["region"].dropna().unique())
region_sel = st.sidebar.multiselect("Region", region_opts, default=region_opts)

category_opts = sorted(df["category"].dropna().unique())
category_sel = st.sidebar.multiselect("Category", category_opts, default=category_opts)

confidence_opts = sorted(df["confidence"].dropna().unique())
confidence_sel = st.sidebar.multiselect("Confidence", confidence_opts, default=confidence_opts)

max_price = int(df["price_high"].fillna(df["price_low"]).max())
price_range = st.sidebar.slider(
    "\U0001F4B0 Total price range ($)", 0, max_price if max_price > 0 else 1000, (0, max_price if max_price > 0 else 1000)
)

search = st.sidebar.text_input("\U0001F50D Search venue / notes")

st.sidebar.markdown("---")
st.sidebar.caption(f"\U0001F4C1 Data source: `dashboard/data/venues.csv`")


def apply_filters(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame[
        frame["status"].isin(status_sel)
        & frame["venue_type"].isin(type_sel)
        & frame["region"].isin(region_sel)
        & frame["category"].isin(category_sel)
    ]
    out = out[out["confidence"].isin(confidence_sel) | out["confidence"].isna()]
    effective_high = out["price_high"].fillna(out["price_low"])
    in_range = effective_high.between(price_range[0], price_range[1]) | effective_high.isna()
    out = out[in_range]
    if search:
        s = search.lower()
        mask = out["venue"].str.lower().str.contains(s, na=False) | out["notes"].str.lower().str.contains(
            s, na=False
        )
        out = out[mask]
    return out


filtered = apply_filters(df)

# ----------------------------------------------------------------------
# Header + KPIs
# ----------------------------------------------------------------------
st.title("\U0001F48D\U0001F942 Coyote Hills Wedding Venue Dashboard")
st.caption(
    "Filter and compare Southern California venues against the Coyote Hills baseline — "
    "all-inclusive packages \U0001F381, ceremony-only \U0001F48D, and reception-only \U0001F942, all in one place."
)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("\U0001F4CD Venues tracked", len(df))
k2.metric("✅ Sourced", int((df["status"] == "Sourced").sum()))
k3.metric("\U0001F50D Not yet sourced", int((df["status"] == "Not Sourced").sum()))
cheapest_pkg = df[(df["venue_type"] == "All-Inclusive Package") & (df["status"] == "Sourced")]["price_low"].min()
k4.metric("\U0001F3C6 Cheapest package found", money(cheapest_pkg))
k5.metric("⭐ Coyote Hills baseline", money(baseline["price_low"]), help="$18k package + 2-hr Premium bar, 100 guests")

st.markdown("---")

# ----------------------------------------------------------------------
# Tabs
# ----------------------------------------------------------------------
tab_pkg, tab_cer, tab_rec, tab_combo, tab_all = st.tabs(
    [
        "\U0001F381 All-Inclusive Packages",
        "\U0001F48D Ceremony Only",
        "\U0001F942 Reception Only",
        "\U0001F9E9 Build a Combo",
        "\U0001F4CB All Venues",
    ]
)


def render_table(frame: pd.DataFrame, price_cols=True):
    view = frame.copy()
    view["Icon"] = view.apply(
        lambda r: f"{STATUS_EMOJI.get(r['status'], '')} {CATEGORY_EMOJI.get(r['category'], DEFAULT_CATEGORY_EMOJI)}",
        axis=1,
    )
    if price_cols:
        view["Total (100 gs.)"] = view.apply(lambda r: fmt_range(r["price_low"], r["price_high"]), axis=1)
        view["$ / Guest"] = view.apply(
            lambda r: fmt_range(r["price_per_guest_low"], r["price_per_guest_high"]), axis=1
        )
    display_cols = [
        "Icon",
        "status",
        "venue",
        "city",
        "region",
        "category",
        "Total (100 gs.)",
        "$ / Guest",
        "bar_included",
        "confidence",
        "notes",
    ]
    display_cols = [c for c in display_cols if c in view.columns]
    st.dataframe(
        view[display_cols].rename(
            columns={
                "status": "Status",
                "venue": "Venue",
                "city": "City",
                "region": "Region",
                "category": "Category",
                "bar_included": "Bar",
                "confidence": "Confidence",
                "notes": "Notes",
            }
        ),
        width="stretch",
        hide_index=True,
    )


with tab_pkg:
    pkg = filtered[filtered["venue_type"] == "All-Inclusive Package"]
    st.subheader(f"\U0001F381 All-inclusive packages ({len(pkg)})")
    st.caption("⭐ Coyote Hills baseline is included for reference even if it doesn't match every filter.")
    combined = pd.concat([pkg, df[df["status"] == "Baseline"]]).drop_duplicates(subset=["venue"])
    render_table(combined.sort_values("price_low"))

    chart_df = combined.dropna(subset=["price_per_guest_low"]).copy()
    if not chart_df.empty:
        chart_df = chart_df.sort_values("price_per_guest_low")
        chart_df["label"] = chart_df["venue"] + chart_df["status"].apply(
            lambda s: " ⭐" if s == "Baseline" else ""
        )
        # wrap long venue names onto multiple lines so labels stay horizontal and legible
        chart_df["wrapped_label"] = chart_df["label"].apply(
            lambda s: "\n".join(textwrap.wrap(s, width=28)) or s
        )
        bar_chart = (
            alt.Chart(chart_df)
            .mark_bar()
            .encode(
                x=alt.X("price_per_guest_low:Q", title="$ / guest (low estimate)"),
                y=alt.Y(
                    "wrapped_label:N",
                    sort="-x",
                    title=None,
                    axis=alt.Axis(labelAngle=0, labelLimit=260, labelFontSize=12),
                ),
                color=alt.condition(
                    alt.datum.status == "Baseline", alt.value("#A8752B"), alt.value("#3F5233")
                ),
                tooltip=[
                    alt.Tooltip("venue:N", title="Venue"),
                    alt.Tooltip("price_per_guest_low:Q", title="$ / guest", format="$,.0f"),
                ],
            )
            .properties(height=max(220, 38 * len(chart_df)))
        )
        st.altair_chart(bar_chart, width="stretch")

with tab_cer:
    cer = filtered[filtered["venue_type"] == "Ceremony Only"]
    st.subheader(f"\U0001F48D Ceremony-only venues ({len(cer)})")
    st.caption("Flat fees, not scaled per guest — pair one of these with a Reception Only venue in Build a Combo.")
    render_table(cer.sort_values("price_low"))

with tab_rec:
    rec = filtered[filtered["venue_type"] == "Reception Only"]
    st.subheader(f"\U0001F942 Reception-only venues ({len(rec)})")
    render_table(rec.sort_values("price_low"))

with tab_combo:
    st.subheader("\U0001F9E9 Build a combo: ceremony + reception at two different venues")
    st.caption(
        "Pick one ceremony-only venue and one reception-only venue. The estimated totals are summed and compared "
        "against the Coyote Hills baseline and the cheapest all-inclusive package found."
    )

    cer_all = df[df["venue_type"] == "Ceremony Only"]
    rec_all = df[df["venue_type"] == "Reception Only"]

    c1, c2 = st.columns(2)
    with c1:
        cer_choice = st.selectbox("\U0001F48D Ceremony venue", cer_all["venue"], index=0)
    with c2:
        rec_choice = st.selectbox("\U0001F942 Reception venue", rec_all["venue"], index=0)

    cer_row = cer_all[cer_all["venue"] == cer_choice].iloc[0]
    rec_row = rec_all[rec_all["venue"] == rec_choice].iloc[0]

    cer_cost = cer_row["price_high"] if pd.notna(cer_row["price_high"]) else cer_row["price_low"]
    rec_cost = rec_row["price_high"] if pd.notna(rec_row["price_high"]) else rec_row["price_low"]

    missing = pd.isna(cer_cost) or pd.isna(rec_cost)

    m1, m2, m3 = st.columns(3)
    m1.metric(f"\U0001F48D {cer_choice}", money(cer_cost))
    m2.metric(f"\U0001F942 {rec_choice}", money(rec_cost))

    if missing:
        st.warning(
            "One or both venues don't have a confirmed price yet (see Notes below) — the combo total below is "
            "incomplete. Request a direct quote before treating this pairing as final."
        )
    else:
        combo_total = cer_cost + rec_cost
        m3.metric("\U0001F9E9 Combo total", money(combo_total))

        delta_baseline = combo_total - baseline["price_low"]
        cheapest_pkg_row = df[(df["venue_type"] == "All-Inclusive Package") & (df["status"] == "Sourced")].nsmallest(
            1, "price_low"
        ).iloc[0]
        delta_cheapest = combo_total - cheapest_pkg_row["price_low"]

        d1, d2 = st.columns(2)
        d1.metric(
            "vs. ⭐ Coyote Hills baseline",
            f"{'+' if delta_baseline >= 0 else '−'}{money(abs(delta_baseline))}",
            help=f"Baseline: {money(baseline['price_low'])}",
        )
        d2.metric(
            f"vs. cheapest package ({cheapest_pkg_row['venue']})",
            f"{'+' if delta_cheapest >= 0 else '−'}{money(abs(delta_cheapest))}",
            help=f"Cheapest package: {money(cheapest_pkg_row['price_low'])}",
        )

    st.markdown("**\U0001F48D Ceremony venue notes:** " + str(cer_row["notes"]))
    st.markdown("**\U0001F942 Reception venue notes:** " + str(rec_row["notes"]))

with tab_all:
    st.subheader(f"\U0001F4CB All venues ({len(filtered)} shown of {len(df)} total)")
    render_table(filtered.sort_values(["status", "venue_type", "price_low"]))

st.markdown("---")

# ----------------------------------------------------------------------
# Map
# ----------------------------------------------------------------------
st.subheader(f"\U0001F5FA️ Where these venues are ({len(filtered)} shown)")
map_df = filtered.dropna(subset=["lat", "lon"]).copy()
if map_df.empty:
    st.info("No venues with a known location match the current filters.")
else:
    map_df["color"] = map_df.apply(map_color, axis=1)
    map_df["size"] = map_df.apply(map_size, axis=1)
    st.map(map_df, latitude="lat", longitude="lon", color="color", size="size", zoom=7)

st.markdown(
    f"""
<div style="display:flex; gap:24px; flex-wrap:wrap; font-size:0.85rem; margin-top:-8px; margin-bottom:8px;">
  <span><span style="color:{MAP_COLORS['Baseline']};">&#9679;</span> Baseline</span>
  <span><span style="color:{MAP_COLORS[('Sourced','All-Inclusive Package')]};">&#9679;</span> Sourced package \U0001F381</span>
  <span><span style="color:{MAP_COLORS[('Sourced','Ceremony Only')]};">&#9679;</span> Sourced ceremony \U0001F48D</span>
  <span><span style="color:{MAP_COLORS[('Sourced','Reception Only')]};">&#9679;</span> Sourced reception \U0001F942</span>
  <span><span style="color:{MAP_COLORS['Not Sourced']};">&#9679;</span> Not yet sourced \U0001F50D</span>
</div>
""",
    unsafe_allow_html=True,
)
st.caption("Pins are city-center approximations, not exact venue addresses.")

st.markdown("---")
with st.expander("ℹ️ How this dashboard stays up to date"):
    st.markdown(
        """
`dashboard/data/venues.csv` is the single source of truth — this app just reads it.

**To add new venues:** ask Claude to research more places. Claude appends new rows directly to
`venues.csv` following the schema documented in `dashboard/README.md` (numeric price fields where
confirmed, blank + a note where not). If a new venue is in a city not already on the map, Claude
also adds one `CITY_COORDS` entry at the top of `app.py`. No other code changes are needed for
ordinary new-venue additions.

**To see new data:** if this app is already running, use Streamlit's rerun (press **R**, or the
"Rerun" option in the menu) or just refresh the browser tab — the cache is keyed on the CSV's
last-modified time, so edits are picked up automatically.

**To refresh the Excel export:** run `python export_excel.py` from the `dashboard/` folder to
regenerate a styled `.xlsx` snapshot of the same data.
        """
    )
