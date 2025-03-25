import os
import streamlit as st
import geopandas as gpd
import pydeck as pdk
import pandas as pd
from datetime import datetime

# Setup
st.set_page_config(layout="wide")
os.environ["MAPBOX_API_KEY"] = "pk.eyJ1IjoicGl2ZXMiLCJhIjoiY204bGVweHY5MTFnZDJscXluOTJ1OHI5OCJ9.3BHtAPkRsjGbwgNykec4VA"

if "page" not in st.session_state:
    st.session_state.page = "upload"

# 1. Upload Page
def show_upload_page():
    st.title("📤 Upload Your DMA GeoJSON Files")

    pipes_file = st.file_uploader("Pipes (GeoJSON)", type=["geojson"], key="pipes")
    assets_file = st.file_uploader("Assets (GeoJSON)", type=["geojson"], key="assets")
    leaks_file = st.file_uploader("Leaks (GeoJSON)", type=["geojson"], key="leaks")
    valves_file = st.file_uploader("Valves (GeoJSON)", type=["geojson"], key="valves")

    # Save to session state safely
    if pipes_file: st.session_state["pipes_file"] = pipes_file
    if assets_file: st.session_state["assets_file"] = assets_file
    if leaks_file: st.session_state["leaks_file"] = leaks_file
    if valves_file: st.session_state["valves_file"] = valves_file

    if st.button("🚀 Launch Dashboard"):
        st.session_state.page = "dashboard"
        st.experimental_rerun()

# 2. Load GeoJSON safely
def load_geojson(uploaded_file):
    if uploaded_file:
        gdf = gpd.read_file(uploaded_file)
        if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        return gdf[gdf.geometry.notnull()]
    return None

# 3. Layer Builders
def create_pipe_layer(gdf):
    if gdf is None:
        return None
    features = []
    for _, row in gdf.iterrows():
        if row.geometry.type == "LineString":
            coords = list(row.geometry.coords)
            features.append({
                "path": coords,
                "pipe_id": str(row.get("PipeID", "")),
                "Material": row.get("Material", ""),
                "Age": row.get("Age", ""),
            })
    return pdk.Layer(
        "PathLayer",
        data=features,
        get_path="path",
        get_color=[75, 181, 190],  # #4BB5BE Qatium blue
        get_width=4,
        pickable=True
    )

def create_point_layer(gdf, color, radius):
    if gdf is None:
        return None
    gdf["lon"] = gdf.geometry.x
    gdf["lat"] = gdf.geometry.y
    return pdk.Layer(
        "ScatterplotLayer",
        data=gdf,
        get_position='[lon, lat]',
        get_fill_color=color,
        get_radius=radius,
        pickable=True
    )

# 4. Map Page
def show_dashboard():
    st.markdown("<style>footer, header, .stSidebar {display: none !important;}</style>", unsafe_allow_html=True)

    # Floating Panel (styled on-map)
    st.markdown("""
        <div style="position:absolute;top:30px;left:30px;z-index:9999;background:#35354B;padding:20px;border-radius:8px;color:white;">
            <h4>🧭 Layers</h4>
            <label><input type="checkbox" checked onchange="location.reload()"> Pipes</label><br>
            <label><input type="checkbox" checked onchange="location.reload()"> Assets</label><br>
            <label><input type="checkbox" checked onchange="location.reload()"> Leaks</label><br>
            <label><input type="checkbox" checked onchange="location.reload()"> Valves</label><br>
        </div>
    """, unsafe_allow_html=True)

    # Load uploaded files
    pipe_gdf = load_geojson(st.session_state.get("pipes_file"))
    asset_gdf = load_geojson(st.session_state.get("assets_file"))
    leak_gdf = load_geojson(st.session_state.get("leaks_file"))
    valve_gdf = load_geojson(st.session_state.get("valves_file"))

    # Leak filtering
    if leak_gdf is not None and "DateRepor" in leak_gdf.columns:
        leak_gdf["year"] = pd.to_datetime(leak_gdf["DateRepor"], errors="coerce").dt.year
        leak_years = leak_gdf["year"].dropna().unique()
        if len(leak_years) > 0:
            selected_year = st.slider("🕓 Leak Year", int(leak_years.min()), int(leak_years.max()), int(leak_years.max()))
            leak_gdf = leak_gdf[leak_gdf["year"] == selected_year]

    # Center map
    center = [51.5, -0.1]
    if pipe_gdf is not None and not pipe_gdf.empty:
        center = [pipe_gdf.geometry.centroid.y.mean(), pipe_gdf.geometry.centroid.x.mean()]

    view_state = pdk.ViewState(latitude=center[0], longitude=center[1], zoom=13, pitch=45)

    # Assemble layers
    layers = []
    if pipe_gdf is not None: layers.append(create_pipe_layer(pipe_gdf))
    if asset_gdf is not None: layers.append(create_point_layer(asset_gdf, [0, 200, 255], 40))
    if leak_gdf is not None: layers.append(create_point_layer(leak_gdf, [255, 0, 0], 25))
    if valve_gdf is not None: layers.append(create_point_layer(valve_gdf, [255, 255, 0], 30))

    # Render Map
    st.pydeck_chart(pdk.Deck(
        map_style="mapbox://styles/mapbox/dark-v10",
        initial_view_state=view_state,
        layers=layers,
        tooltip={"text": "{pipe_id} {Material} {Age}"}
    ), use_container_width=True, height=1100)

# Run App
if st.session_state.page == "upload":
    show_upload_page()
else:
    show_dashboard()
