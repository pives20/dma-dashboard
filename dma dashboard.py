import os
import streamlit as st
import geopandas as gpd
import pydeck as pdk
import pandas as pd
from datetime import datetime

# App setup
st.set_page_config(layout="wide")
os.environ["MAPBOX_API_KEY"] = "pk.eyJ1IjoicGl2ZXMiLCJhIjoiY204bGVweHY5MTFnZDJscXluOTJ1OHI5OCJ9.3BHtAPkRsjGbwgNykec4VA"

# State setup
if "page" not in st.session_state:
    st.session_state.page = "upload"
if "valve_status" not in st.session_state:
    st.session_state.valve_status = {}

# --- PAGE 1: Upload Interface ---
def go_to_dashboard():
    st.session_state.page = "dashboard"
    st.rerun()

def show_upload_page():
    st.title("📤 Upload Your DMA GeoJSON Files")

    pipes_file = st.file_uploader("Pipes (GeoJSON)", type=["geojson"], key="pipes")
    assets_file = st.file_uploader("Assets (GeoJSON)", type=["geojson"], key="assets")
    leaks_file = st.file_uploader("Leaks (GeoJSON)", type=["geojson"], key="leaks")
    valves_file = st.file_uploader("Valves (GeoJSON)", type=["geojson"], key="valves")

    if pipes_file: st.session_state["pipes_file"] = pipes_file
    if assets_file: st.session_state["assets_file"] = assets_file
    if leaks_file: st.session_state["leaks_file"] = leaks_file
    if valves_file: st.session_state["valves_file"] = valves_file

    st.button("🚀 Launch Dashboard", on_click=go_to_dashboard)

# --- DATA LOADERS ---
def load_geojson(file, name=""):
    if file:
        try:
            gdf = gpd.read_file(file)
            if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")
            gdf = gdf[gdf.geometry.notnull()]
            st.sidebar.success(f"{name}: {len(gdf)} features loaded")
            return gdf
        except Exception as e:
            st.sidebar.error(f"{name} failed to load: {e}")
    return None

# --- LAYER CREATORS ---
def create_pipe_layer(gdf, valve_shut_ids=None, highlight_disconnected=False):
    if gdf is None or gdf.empty:
        return None
    features = []
    for _, row in gdf.iterrows():
        coords = list(row.geometry.coords)
        color = [75, 181, 190]  # Default: Qatium blue
        if highlight_disconnected and valve_shut_ids:
            color = [150, 150, 150]
        features.append({
            "path": coords,
            "pipe_id": row.get("PipeID", ""),
            "Material": row.get("Material", ""),
            "Age": row.get("Age", ""),
            "color": color
        })
    return pdk.Layer(
        "PathLayer",
        data=features,
        get_path="path",
        get_color="color",
        get_width=5,
        pickable=True
    )

def create_point_layer(gdf, color, radius, id_field="ID"):
    if gdf is None or gdf.empty:
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

# --- PAGE 2: Map Dashboard ---
def show_dashboard():
    st.sidebar.title("🧭 Map Layers")
    show_pipes = st.sidebar.checkbox("Pipes", True)
    show_assets = st.sidebar.checkbox("Assets", True)
    show_leaks = st.sidebar.checkbox("Leaks", True)
    show_valves = st.sidebar.checkbox("Valves", True)
    show_criticality = st.sidebar.checkbox("Pipe Criticality (age)", False)

    if st.sidebar.button("⬅️ Back to Upload"):
        st.session_state.page = "upload"
        st.rerun()

    pipe_gdf = load_geojson(st.session_state.get("pipes_file"), "Pipes")
    asset_gdf = load_geojson(st.session_state.get("assets_file"), "Assets")
    leak_gdf = load_geojson(st.session_state.get("leaks_file"), "Leaks")
    valve_gdf = load_geojson(st.session_state.get("valves_file"), "Valves")

    if leak_gdf is not None and "DateRepor" in leak_gdf.columns:
        leak_gdf["year"] = pd.to_datetime(leak_gdf["DateRepor"], errors="coerce").dt.year
        years = leak_gdf["year"].dropna().astype(int).unique()
        if len(years) > 0:
            min_year = int(min(years))
            max_year = int(max(years))
            year = st.sidebar.slider("🕓 Leak Year", min_year, max_year, max_year)
            leak_gdf = leak_gdf[leak_gdf["year"] == year]
        else:
            st.sidebar.warning("No valid leak dates found.")

    if show_criticality and pipe_gdf is not None and "Age" in pipe_gdf.columns:
        def age_to_color(age):
            if age < 10: return [0, 255, 0]
            elif age < 30: return [255, 165, 0]
            else: return [255, 0, 0]
        pipe_gdf["color"] = pipe_gdf["Age"].apply(age_to_color)
    else:
        pipe_gdf["color"] = [[75, 181, 190]] * len(pipe_gdf)

    center = [51.5, -0.1]
    if pipe_gdf is not None and not pipe_gdf.empty:
        center = [pipe_gdf.geometry.centroid.y.mean(), pipe_gdf.geometry.centroid.x.mean()]
    view_state = pdk.ViewState(latitude=center[0], longitude=center[1], zoom=13, pitch=45)

    layers = []
    if show_pipes and pipe_gdf is not None:
        layers.append(create_pipe_layer(pipe_gdf))
    if show_assets and asset_gdf is not None:
        layers.append(create_point_layer(asset_gdf, [0, 200, 255], 40, "AssetID"))
    if show_leaks and leak_gdf is not None:
        layers.append(create_point_layer(leak_gdf, [255, 0, 0], 25, "LeakID"))
    if show_valves and valve_gdf is not None:
        layers.append(create_point_layer(valve_gdf, [255, 255, 0], 30, "ValveID"))

    tooltip = {
        "html": "<b>Pipe:</b> {pipe_id}<br><b>Material:</b> {Material}<br><b>Age:</b> {Age}",
        "style": {"color": "white"}
    }

    st.pydeck_chart(pdk.Deck(
        map_style="mapbox://styles/mapbox/dark-v10",
        initial_view_state=view_state,
        layers=layers,
        tooltip=tooltip
    ), use_container_width=True, height=1100)

# --- RUN ---
if st.session_state.page == "upload":
    show_upload_page()
else:
    show_dashboard()
