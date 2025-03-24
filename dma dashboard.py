import os
import tempfile
import streamlit as st
import pandas as pd
import geopandas as gpd
import pydeck as pdk
from shapely.geometry import LineString
from datetime import datetime

st.set_page_config(layout="wide")
os.environ["MAPBOX_API_KEY"] = "your-mapbox-token-here"

def load_shapefile(files, expected_geom):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            for file in files:
                with open(os.path.join(tmpdir, file.name), "wb") as f:
                    f.write(file.read())
            shp_path = [f.name for f in files if f.name.endswith(".shp")]
            if not shp_path:
                st.sidebar.error("Missing .shp file in upload.")
                return None
            full_path = os.path.join(tmpdir, shp_path[0])
            gdf = gpd.read_file(full_path)

            if expected_geom == "Line" and not gdf.geom_type.isin(["LineString", "MultiLineString"]).any():
                st.sidebar.error("Shapefile does not contain Line geometries.")
                return None
            if expected_geom == "Point" and not gdf.geom_type.isin(["Point"]).any():
                st.sidebar.error("Shapefile does not contain Point geometries.")
                return None

            st.sidebar.success(f"Loaded {len(gdf)} features.")
            return gdf
    except Exception as e:
        st.sidebar.error(f"Shapefile error: {e}")
        return None

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
            "pipe_id": row.get("PipeID", ""),
            "Material": row.get("Material", "Unknown"),
            "Age": row.get("Age", "Unknown"),
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

def create_point_layer(gdf, color, radius):
    gdf["lon"] = gdf.geometry.x
    gdf["lat"] = gdf.geometry.y
    return pdk.Layer(
        "ScatterplotLayer",
        data=gdf,
        get_position=["lon", "lat"],
        get_fill_color=color,
        get_radius=radius,
        pickable=True
    )

# --------------------------
# Sidebar File Uploads
# --------------------------
st.title("💧 DMA Dashboard – Shapefile Support for Pipes")

criticality_on = st.sidebar.checkbox("Show Pipe Criticality", value=True)

st.sidebar.header("Upload Pipes")
pipe_files = st.sidebar.file_uploader(
    "Upload pipe shapefile components (shp, shx, dbf, prj)",
    type=["shp", "shx", "dbf", "prj"],
    accept_multiple_files=True,
    key="pipes"
)

st.sidebar.header("Upload Nodes")
node_files = st.sidebar.file_uploader(
    "Upload node shapefile (point)",
    type=["shp", "shx", "dbf", "prj"],
    accept_multiple_files=True,
    key="nodes"
)

st.sidebar.header("Upload Assets")
asset_files = st.sidebar.file_uploader(
    "Upload asset shapefile (point)",
    type=["shp", "shx", "dbf", "prj"],
    accept_multiple_files=True,
    key="assets"
)

st.sidebar.header("Upload Leaks")
leak_files = st.sidebar.file_uploader(
    "Upload leak shapefile (point)",
    type=["shp", "shx", "dbf", "prj"],
    accept_multiple_files=True,
    key="leaks"
)

# --------------------------
# Load Layers
# --------------------------
pipe_gdf = load_shapefile(pipe_files, "Line") if pipe_files else None
node_gdf = load_shapefile(node_files, "Point") if node_files else None
asset_gdf = load_shapefile(asset_files, "Point") if asset_files else None
leak_gdf = load_shapefile(leak_files, "Point") if leak_files else None

# --------------------------
# Render Map
# --------------------------
if st.button("Render Map"):
    if node_gdf is None or pipe_gdf is None:
        st.error("Please upload both Pipes and Nodes shapefiles.")
    else:
        layers = [create_pipe_layer(pipe_gdf, criticality_on)]
        if asset_gdf is not None:
            layers.append(create_point_layer(asset_gdf, [0, 200, 255], 30))
        if leak_gdf is not None:
            layers.append(create_point_layer(leak_gdf, [255, 0, 0], 20))

        view = pdk.ViewState(
            latitude=node_gdf.geometry.y.mean(),
            longitude=node_gdf.geometry.x.mean(),
            zoom=13,
            pitch=45
        )

        st.pydeck_chart(pdk.Deck(
            map_style="mapbox://styles/mapbox/dark-v10",
            initial_view_state=view,
            layers=layers,
            tooltip={
                "html": """
                    <b>Pipe ID:</b> {pipe_id}<br>
                    <b>Material:</b> {Material}<br>
                    <b>Age:</b> {Age}
                """,
                "style": {"color": "white"}
            }
        ))
