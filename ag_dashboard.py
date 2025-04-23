import os
import re
import pandas as pd
import geopandas as gpd
import streamlit as st
import pydeck as pdk

# ── Page config
st.set_page_config("Ontario Ag Census Dashboard", layout="wide")

# ── File paths (relative)
BASE = os.path.dirname(__file__)
CENSUS_PATH    = os.path.join(BASE, "data", "agcensus_wide.csv")
SHAPEFILE_PATH = os.path.join(BASE, "data", "Ontario_Census_Divisions_simp.gpkg")

# ── Helpers
def normalize_key(name):
    if pd.isnull(name):
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", name).upper()

@st.cache_data(show_spinner=False)
def load_shapefile(path):
    gdf = gpd.read_file(path).to_crs(epsg=4326)
    gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.01, preserve_topology=True)
    gdf["join_key"] = gdf["Municipality_Clean"].apply(normalize_key)
    return gdf

@st.cache_data(show_spinner=False)
def load_census(path):
    df = pd.read_csv(path)
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
gdf     = load_shapefile(SHAPEFILE_PATH)
df_long = load_census(CENSUS_PATH)

# ── Sidebar filters
st.sidebar.title("Filters")
year     = st.sidebar.selectbox("Year", sorted(df_long["year"].dropna().unique()))
variable = st.sidebar.selectbox(
    "Variable",
    sorted(df_long.query("year == @year")["variable"].dropna().unique())
)

# ── Prepare data
filtered = df_long.query("year == @year and variable == @variable")[["join_key","value"]]
full = (
    gdf[["join_key","Municipality_Clean","geometry"]]
    .merge(filtered, on="join_key", how="left")
)

# ── Color ramp helper
vmin, vmax = filtered["value"].min(), filtered["value"].max()
def make_color(v):
    if pd.isna(v):
        return [200, 200, 200, 50]
    norm = (v - vmin) / (vmax - vmin)
    r = int(255 * (0.3 + 0.7 * norm))
    g = int(255 * (0.8 - 0.8 * norm))
    b = 0
    return [r, g, b, 180]

full["fill_color"] = full["value"].apply(make_color)
full["value_fmt"]  = full["value"].apply(lambda v: f"{v:,.0f}" if pd.notna(v) else "N/A")

# ── Header
st.title("🚜 Ontario Agricultural Census Dashboard")
st.subheader(f"Year: {year} | Variable: {variable.replace('_',' ').title()}")

# ── Color bar legend
min_val = filtered["value"].min()
max_val = filtered["value"].max()
low_col = make_color(min_val)
high_col = make_color(max_val)

legend_html = f"""
<div style="display:flex; align-items:center; margin:10px 0;">
  <span style="margin-right:10px;">{min_val:,.0f}</span>
  <div style="flex:1; height:12px; background: linear-gradient(to right,
       rgb({low_col[0]},{low_col[1]},{low_col[2]}),
       rgb({high_col[0]},{high_col[1]},{high_col[2]}));"></div>
  <span style="margin-left:10px;">{max_val:,.0f}</span>
</div>
"""
st.markdown(legend_html, unsafe_allow_html=True)

# ── Build Stamen “toner-lite” basemap + choropleth
tile_layer = pdk.Layer(
    "TileLayer",
    data=None,
    get_tile_data="https://stamen-tiles.a.ssl.fastly.net/toner-lite/{z}/{x}/{y}.png",
    tile_size=256,
    opacity=0.7
)

choropleth = pdk.Layer(
    "GeoJsonLayer",
    data=full.__geo_interface__,
    pickable=True,
    stroked=True,
    filled=True,
    get_fill_color="properties.fill_color",
    get_line_color=[80, 80, 80, 200],
    line_width_min_pixels=1,
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
