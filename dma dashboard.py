import os
import tempfile
import streamlit as st
import geopandas as gpd
import pydeck as pdk
from datetime import datetime

# Set page config
st.set_page_config(layout="wide")
os.environ["MAPBOX_API_KEY"] = "pk.eyJ1IjoicGl2ZXMiLCJhIjoiY204bGVweHY5MTFnZDJscXluOTJ1OHI5OCJ9.3BHtAPkRsjGbwgNykec4VA"

# Track toggles in session
if "layer_states" not in st.session_state:
    st.session_state.layer_states = {
        "Pipes": True,
        "Assets": True,
        "Leaks": True
    }
if "year_filter" not in st.session_state:
    st.session_state.year_filter = datetime.now().year

# Floating control panel CSS
st.markdown("""
<style>
.control-panel {
    position: fixed;
    top: 30px;
    left: 30px;
    background-color: #35354B;
    padding: 20px;
    border-radius: 8px;
    z-index: 9999;
    color: white;
    font-family: 'Segoe UI', sans-serif;
    box-shadow: 0px 0px 15px rgba(0,0,0,0.3);
}
.control-panel h4 {
    margin-top: 0;
    color: #FFFFFF;
}
.control-panel label {
    color: #B4B4CA;
    font-size: 14px;
}
</style>
""", unsafe_allow_html=True)

# File Uploads
pipe_file = st.file_uploader("Upload Pipes (GeoJSON preferred)", type=["geojson"])
asset_file = st.file_uploader("Upload Assets", type=["geojson"])
leak_file = st.file_uploader("Upload Leaks", type=["geojson"])

# Load GeoDataFrames
def load_geojson(uploaded_file):
    if uploaded_file:
        gdf = gpd.read_file(uploaded_file)
        if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        return gdf[gdf.geometry.notnull()]
    return None

pipe_gdf = load_geojson(pipe_file)
asset_gdf = load_geojson(asset_file)
leak_gdf = load_geojson(leak_file)

# Floating Control Panel UI
st.markdown("""
<div class="control-panel">
    <h4>🧭 Map Layers</h4>
    <label><input type="checkbox" onchange="fetch('/_stcore/streamlit-update?Pipes='+this.checked)" checked> Pipes</label><br>
    <label><input type="checkbox" onchange="fetch('/_stcore/streamlit-update?Assets='+this.checked)" checked> Assets</label><br>
    <label><input type="checkbox" onchange="fetch('/_stcore/streamlit-update?Leaks='+this.checked)" checked> Leaks</label><br>
    <hr style="border: 1px solid #4A4A68">
    <label for="year">🕓 Leak Year Filter</label>
</div>
""", unsafe_allow_html=True)

# Streamlit timeline slider
leak_years = []
if leak_gdf is not None and "DateRepor" in leak_gdf.columns:
    leak_gdf["year"] = pd.to_datetime(leak_gdf["DateRepor"], errors="coerce").dt.year
    leak_years = leak_gdf["year"].dropna().astype(int).unique().tolist()
    leak_years.sort()

if leak_years:
    year = st.slider("Select Leak Year", min_value=min(leak_years), max_value=max(leak_years), value=max(leak_years))
    st.session_state.year_filter = year

# Build Pydeck Layers
layers = []

if pipe_gdf is not None and st.session_state.layer_states["Pipes"]:
    pipe_layer = pdk.Layer(
        "PathLayer",
        data=[{
            "path": list(geom.coords),
            "pipe_id": str(row.get("PipeID", "")),
            "Material": str(row.get("Material", "")),
            "Age": row.get("Age", ""),
        } for _, row in pipe_gdf.iterrows() if row.geometry.type == "LineString" for geom in [row.geometry]],
        get_path="path",
        get_width=5,
        get_color=[0, 255, 255],
        pickable=True
    )
    layers.append(pipe_layer)

if asset_gdf is not None and st.session_state.layer_states["Assets"]:
    asset_gdf["lon"] = asset_gdf.geometry.x
    asset_gdf["lat"] = asset_gdf.geometry.y
    asset_layer = pdk.Layer(
        "ScatterplotLayer",
        data=asset_gdf,
        get_position='[lon, lat]',
        get_radius=30,
        get_fill_color=[0, 200, 255],
        pickable=True
    )
    layers.append(asset_layer)

if leak_gdf is not None and st.session_state.layer_states["Leaks"]:
    filtered_leaks = leak_gdf[leak_gdf["year"] == st.session_state.year_filter] if "year" in leak_gdf.columns else leak_gdf
    filtered_leaks["lon"] = filtered_leaks.geometry.x
    filtered_leaks["lat"] = filtered_leaks.geometry.y
    leak_layer = pdk.Layer(
        "ScatterplotLayer",
        data=filtered_leaks,
        get_position='[lon, lat]',
        get_radius=20,
        get_fill_color=[255, 0, 0],
        pickable=True
    )
    layers.append(leak_layer)

# Map View
if pipe_gdf is not None and not pipe_gdf.empty:
    center = pipe_gdf.geometry.centroid.unary_union.centroid
    view_state = pdk.ViewState(latitude=center.y, longitude=center.x, zoom=13, pitch=45)
else:
    view_state = pdk.ViewState(latitude=51.5, longitude=-0.1, zoom=12, pitch=45)

# Map Tooltip
tooltip = {
    "html": "<b>ID:</b> {pipe_id} {id}<br/><b>Type:</b> {type}<br/><b>Material:</b> {Material}<br/><b>Age:</b> {Age}",
    "style": {"color": "white"}
}

# Render Deck Map
st.pydeck_chart(pdk.Deck(
    map_style="mapbox://styles/mapbox/dark-v10",
    initial_view_state=view_state,
    layers=layers,
    tooltip=tooltip
), use_container_width=True, height=1100)
