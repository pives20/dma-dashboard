import os
import tempfile
import streamlit as st
import geopandas as gpd
import pydeck as pdk
from datetime import datetime

# Setup
st.set_page_config(layout="wide")
os.environ["MAPBOX_API_KEY"] = "your-mapbox-token-here"  # ⬅ Replace this!

if "show_map" not in st.session_state:
    st.session_state.show_map = False

# Load shapefile
def load_shapefile(files, expected_geom):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            for file in files:
                with open(os.path.join(tmpdir, file.name), "wb") as f:
                    f.write(file.read())
            shp_path = [f.name for f in files if f.name.endswith(".shp")]
            if not shp_path:
                st.sidebar.error("Missing .shp file.")
                return None
            gdf = gpd.read_file(os.path.join(tmpdir, shp_path[0]))

            if expected_geom == "Line" and not gdf.geom_type.isin(["LineString", "MultiLineString"]).any():
                st.sidebar.error("Expected Line geometry.")
                return None
            if expected_geom == "Point" and not gdf.geom_type.isin(["Point"]).any():
                st.sidebar.error("Expected Point geometry.")
                return None

            return gdf
    except Exception as e:
        st.sidebar.error(f"Shapefile error: {e}")
        return None

# Pipe layer
def create_pipe_layer(pipe_gdf, criticality_on):
    current_year = datetime.now().year

    def color(row):
        try:
            age = current_year - int(row["Age"])
        except:
            age = 0
        if not criticality_on:
            return [0, 255, 255]
        if age > 50 or str(row.get("Material", "")).lower() == "cast iron":
            return [255, 0, 0]
        elif age > 30:
            return [255, 165, 0]
        return [0, 255, 0]

    features = []
    for _, row in pipe_gdf.iterrows():
        coords = list(row.geometry.coords)
        features.append({
            "path": coords,
            "pipe_id": str(row.get("PipeID", "")),
            "Material": str(row.get("Material", "")),
            "Age": row.get("Age", ""),
            "color": color(row)
        })

    return pdk.Layer(
        "PathLayer",
        features,
        get_path="path",
        get_color="color",
        width_min_pixels=4,
        pickable=True
    )

# Point layer
def create_point_layer(gdf, color, radius, id_col, type_col, extra_col=None):
    gdf["lon"] = gdf.geometry.x
    gdf["lat"] = gdf.geometry.y

    records = []
    for _, row in gdf.iterrows():
        rec = {
            "lon": row["lon"],
            "lat": row["lat"],
            "id": str(row.get(id_col, "")),
            "type": str(row.get(type_col, "")),
        }
        if extra_col:
            rec["extra"] = str(row.get(extra_col, ""))
        records.append(rec)

    return pdk.Layer(
        "ScatterplotLayer",
        data=records,
        get_position=["lon", "lat"],
        get_fill_color=color,
        get_radius=radius,
        pickable=True
    )

# UI
st.title("💧 DMA Dashboard — Fullscreen Map Mode")

criticality_on = st.sidebar.checkbox("Show Pipe Criticality", value=True)

pipe_files = st.sidebar.file_uploader("Upload Pipes", type=["shp", "shx", "dbf", "prj"], accept_multiple_files=True, key="pipes")
asset_files = st.sidebar.file_uploader("Upload Assets", type=["shp", "shx", "dbf", "prj"], accept_multiple_files=True, key="assets")
leak_files = st.sidebar.file_uploader("Upload Leaks", type=["shp", "shx", "dbf", "prj"], accept_multiple_files=True, key="leaks")
node_files = st.sidebar.file_uploader("Upload Nodes (optional)", type=["shp", "shx", "dbf", "prj"], accept_multiple_files=True, key="nodes")

pipe_gdf = load_shapefile(pipe_files, "Line") if pipe_files else None
asset_gdf = load_shapefile(asset_files, "Point") if asset_files else None
leak_gdf = load_shapefile(leak_files, "Point") if leak_files else None
node_gdf = load_shapefile(node_files, "Point") if node_files else None

# Render map
if not st.session_state.show_map:
    if st.button("Render Map"):
        if pipe_gdf is None:
            st.error("Please upload at least a Pipes shapefile.")
        else:
            st.session_state.show_map = True
else:
    if st.button("🔄 Reset View"):
        st.session_state.show_map = False

    # Hide UI for fullscreen effect
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {display: none;}
            [data-testid="stHeader"] {display: none;}
            .block-container {padding: 0rem;}
        </style>
    """, unsafe_allow_html=True)

    # Layers
    layers = [create_pipe_layer(pipe_gdf, criticality_on)]
    if asset_gdf is not None:
        layers.append(create_point_layer(asset_gdf, [0, 200, 255], 40, "AssetID", "AssetType"))
    if leak_gdf is not None:
        layers.append(create_point_layer(leak_gdf, [255, 0, 0], 25, "LeakID", "LeakType", "DateRepor"))

    # Map center
    if node_gdf is not None and not node_gdf.empty:
        lat = node_gdf.geometry.y.mean()
        lon = node_gdf.geometry.x.mean()
    elif pipe_gdf is not None and not pipe_gdf.empty:
        lat = pipe_gdf.geometry.centroid.y.mean()
        lon = pipe_gdf.geometry.centroid.x.mean()
    else:
        lat, lon = 0, 0

    view = pdk.ViewState(latitude=lat, longitude=lon, zoom=13, pitch=45)

    st.pydeck_chart(
        pdk.Deck(
            map_style="mapbox://styles/mapbox/dark-v10",
            initial_view_state=view,
            layers=layers,
            tooltip={
                "html": """
                    <b>Pipe ID:</b> {pipe_id}<br>
                    <b>Material:</b> {Material}<br>
                    <b>Age:</b> {Age}<br>
                    <b>ID:</b> {id}<br>
                    <b>Type:</b> {type}<br>
                    <b>Date:</b> {extra}
                """,
                "style": {"color": "white"}
            }
        ),
        use_container_width=True
    )
