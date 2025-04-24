import os
import re
import pandas as pd
import geopandas as gpd
import streamlit as st
import pydeck as pdk

# ── Page config
st.set_page_config("Ontario Ag Census Dashboard", layout="wide")

# ── CSS to shrink & widen both the selectbox and its dropdown items
st.markdown(
    """
    <style>
    /* Selected value */
    [data-baseweb="select"] > div {
      font-size: 12px !important;
      min-width: 300px !important;
    }
    /* Dropdown container */
    div[role="listbox"] {
      max-width: 300px !important;
    }
    /* Dropdown items */
    div[role="listbox"] [role="option"] {
      font-size: 12px !important;
      white-space: normal !important;
      line-height: 1.2em !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── File paths
BASE         = os.path.dirname(__file__)
CENSUS_PATH  = os.path.join(BASE, "data", "agcensus_wide.parquet")
GEOJSON_PATH = os.path.join(BASE, "data", "divisions_simp.geojson")

# ── Helpers
def normalize_key(name):
    if pd.isnull(name):
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", name).upper()

@st.cache_data(show_spinner=False)
def load_shapefile(path):
    # Read our pre-simplified GeoJSON
    gdf = gpd.read_file(path)
    gdf["join_key"] = gdf["Municipality_Clean"].apply(normalize_key)
    return gdf[["Municipality_Clean", "geometry", "join_key"]]

@st.cache_data(show_spinner=False)
def load_census(path):
    # Now read Parquet instead of CSV for speed
    df = pd.read_parquet(path)
    df["join_key"] = df["join_key"].apply(normalize_key)
    df_long = df.melt(
        id_vars="join_key",
        var_name="variable_year",
        value_name="value"
    )
    df_long["year"]     = df_long["variable_year"].str.extract(r"_(\d{4})$")
    df_long["variable"] = df_long["variable_year"].str.replace(r"_(\d{4})$", "", regex=True)
    return df_long

# ── Load data
gdf     = load_shapefile(GEOJSON_PATH)
df_long = load_census(CENSUS_PATH)

# ── Cached GeoJSON builder
@st.cache_data(show_spinner=False)
def build_geojson(year: str, variable: str):
    df_filt = df_long.query("year == @year and variable == @variable")[["join_key","value"]]
    df_filt = df_filt[df_filt["value"].notna()]
    g = gdf.merge(df_filt, on="join_key", how="inner").copy()

    vmin = df_filt["value"].min()
    vmax = df_filt["value"].max()
    def _make_color(v):
        norm = (v - vmin) / (vmax - vmin) if vmax > vmin else 0
        return [
            int(255 * (0.3 + 0.7 * norm)),
            int(255 * (0.8 - 0.8 * norm)),
            0,
            180
        ]

    features = []
    for _, row in g.iterrows():
        features.append({
            "type": "Feature",
            "geometry": row.geometry.__geo_interface__,
            "properties": {
                "Municipality_Clean": row.Municipality_Clean,
                "value_fmt": f"{int(row.value):,}",
                "fill_color": _make_color(row.value)
            }
        })
    return {"type": "FeatureCollection", "features": features}

# ── Sidebar filters with sticky variable
st.sidebar.title("Filters")
years = sorted(df_long["year"].dropna().unique())
year  = st.sidebar.selectbox("Year", years, key="year")

vars_for_year = sorted(df_long.query("year == @year")["variable"].dropna().unique())
if "variable" not in st.session_state:
    st.session_state.variable = vars_for_year[0] if vars_for_year else None
if st.session_state.variable not in vars_for_year:
    st.session_state.variable = vars_for_year[0] if vars_for_year else None

variable = st.sidebar.selectbox(
    "Variable",
    vars_for_year,
    index=vars_for_year.index(st.session_state.variable),
    key="variable"
)

# ── Compute legend bounds
filtered = df_long.query("year == @year and variable == @variable")[["join_key","value"]]
vmin = filtered["value"].min()
vmax = filtered["value"].max()

# ── Header
st.title("🚜 Ontario Agricultural Census Dashboard")
st.subheader(f"Year: {year} | Variable: {variable.replace('_',' ').title()}")

# ── Color bar legend
low_rgb  = [int(255*(0.3+0.7*0))]*3 if vmin == vmax else [
    int(255*(0.3+0.7*((vmin-vmin)/(vmax-vmin)))),
    int(255*(0.8-0.8*((vmin-vmin)/(vmax-vmin)))),
    0
]
high_rgb = [
    int(255*(0.3+0.7*1)),
    int(255*(0.8-0.8*1)),
    0
]
legend_html = f"""
<div style="display:flex; align-items:center; margin:10px 0;">
  <span style="margin-right:10px;">{vmin:,.0f}</span>
  <div style="flex:1; height:12px; background:linear-gradient(to right,
       rgb({low_rgb[0]},{low_rgb[1]},{low_rgb[2]}),
       rgb({high_rgb[0]},{high_rgb[1]},{high_rgb[2]}));"></div>
  <span style="margin-left:10px;">{vmax:,.0f}</span>
</div>
"""
st.markdown(legend_html, unsafe_allow_html=True)

# ── Build map
tile_layer = pdk.Layer(
    "TileLayer", None,
    get_tile_data="https://stamen-tiles.a.ssl.fastly.net/toner-lite/{z}/{x}/{y}.png",
    tile_size=256, opacity=0.7
)
geojson = build_geojson(year, variable)
choropleth = pdk.Layer(
    "GeoJsonLayer", geojson,
    pickable=True, stroked=True, filled=True,
    get_fill_color="properties.fill_color",
    get_line_color=[80,80,80,200], line_width_min_pixels=1
)
view_state = pdk.ViewState(latitude=50, longitude=-85, zoom=5)
tooltip = {
    "html": "<b>Division:</b> {Municipality_Clean}<br/><b>Value:</b> {value_fmt}",
    "style": {"color": "white"}
}
deck = pdk.Deck(
    map_style=None,
    layers=[tile_layer, choropleth],
    initial_view_state=view_state,
    tooltip=tooltip
)
st.pydeck_chart(deck, use_container_width=True)
