import os
import streamlit as st
import geopandas as gpd
import pydeck as pdk
from datetime import datetime

# Config
st.set_page_config(layout="wide")
os.environ["MAPBOX_API_KEY"] = "pk.eyJ1IjoicGl2ZXMiLCJhIjoiY204bGVweHY5MTFnZDJscXluOTJ1OHI5OCJ9.3BHtAPkRsjGbwgNykec4VA"

# Session states
if "page" not in st.session_state:
    st.session_state.page = "upload"

# App layout
def show_upload_page():
    st.title("📤 Upload DMA Files")
    st.markdown("Upload your **pipes**, **assets**, **leaks**, and **valves** in GeoJSON format.")

    st.session_state.pipes = st.file_uploader("Pipes (GeoJSON)", type=["geojson"], key="pipes")
    st.session_state.assets = st.file_uploader("Assets (GeoJSON)", type=["geojson"], key="assets")
    st.session_state.leaks = st.file_uploader("Leaks (GeoJSON)", type=["geojson"], key="leaks")
    st.session_state.valves = st.file_uploader("Valves (GeoJSON)", type=["geojson"], key="valves")

    if st.button("🚀 Launch Dashboard"):
        st.session_state.page = "dashboard"
        st.experimental_rerun()

def load_geojson(uploaded_file):
    if uploaded_file:
        gdf = gpd.read_file(uploaded_file)
        if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        return gdf[gdf.geometry.notnull()]
    return None

def create_layer(gdf, layer_type):
    if gdf is None:
        return None
    gdf["lon"] = gdf.geometry.x
    gdf["lat"] = gdf.geometry.y

    if layer_type == "assets":
        return pdk.Layer(
            "ScatterplotLayer",
            data=gdf,
            get_position='[lon, lat]',
            get_fill_color=[0, 200, 255],
            get_radius=40,
            pickable=True
        )
    if layer_type == "leaks":
        gdf["year"] = pd.to_datetime(gdf.get("DateRepor"), errors="coerce").dt.year
        year = st.slider("Leak Year", int(gdf["year"].min()), int(gdf["year"].max()), int(gdf["year"].max()))
        gdf = gdf[gdf["year"] == year]
        return pdk.Layer(
            "ScatterplotLayer",
            data=gdf,
            get_position='[lon, lat]',
            get_fill_color=[255, 0, 0],
            get_radius=25,
            pickable=True
        )
    if layer_type == "valves":
        return pdk.Layer(
            "ScatterplotLayer",
            data=gdf,
            get_position='[lon, lat]',
            get_fill_color=[255, 255, 0],
            get_radius=30,
            pickable=True
        )
    return None

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
        get_color=[75, 181, 190],  # #4BB5BE
        get_width=4,
        pickable=True
    )

def show_dashboard():
    st.markdown("<style>footer, header, .stSidebar {display: none !important;}</style>", unsafe_allow_html=True)

    st.markdown("""
        <div style="position:absolute;top:30px;left:30px;z-index:9999;background:#35354B;padding:20px;border-radius:8px;color:white;">
            <h4>🧭 Layers</h4>
            <label><input type="checkbox" checked onchange="location.reload()"> Pipes</label><br>
            <label><input type="checkbox" checked onchange="location.reload()"> Assets</label><br>
            <label><input type="checkbox" checked onchange="location.reload()"> Leaks</label><br>
            <label><input type="checkbox" checked onchange="location.reload()"> Valves</label><br>
        </div>
    """, unsafe_allow_html=True)

    pipe_gdf = load_geojson(st.session_state.get("pipes"))
    asset_gdf = load_geojson(st.session_state.get("assets"))
    leak_gdf = load_geojson(st.session_state.get("leaks"))
    valve_gdf = load_geojson(st.session_state.get("valves"))

    center = [51.5, -0.1]
    if pipe_gdf is not None and not pipe_gdf.empty:
        center = [pipe_gdf.geometry.centroid.y.mean(), pipe_gdf.geometry.centroid.x.mean()]

    layers = []
    pipe_layer = create_pipe_layer(pipe_gdf)
    if pipe_layer: layers.append(pipe_layer)
    for layer_type, gdf in [("assets", asset_gdf), ("leaks", leak_gdf), ("valves", valve_gdf)]:
        l = create_layer(gdf, layer_type)
        if l: layers.append(l)

    view_state = pdk.ViewState(latitude=center[0], longitude=center[1], zoom=13, pitch=45)

    st.pydeck_chart(pdk.Deck(
        map_style="mapbox://styles/mapbox/dark-v10",
        initial_view_state=view_state,
        layers=layers,
        tooltip={"text": "{pipe_id} {Material} {Age}"}
    ), use_container_width=True, height=1100)

# Run
if st.session_state.page == "upload":
    show_upload_page()
else:
    show_dashboard()
