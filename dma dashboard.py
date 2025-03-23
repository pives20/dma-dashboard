import os
import streamlit as st
import pandas as pd
import geopandas as gpd
import pydeck as pdk
import tempfile
from shapely.geometry import Point, LineString

#############################
# 1) SETUP MAPBOX TOKEN
#############################
os.environ["MAPBOX_API_KEY"] = "pk.eyJ1IjoicGl2ZXMiLCJhIjoiY204bGVweHY5MTFnZDJscXluOTJ1OHI5OCJ9.3BHtAPkRsjGbwgNykec4VA"

#############################
# 2) CUSTOM DARK THEME
#############################
dark_css = """
<style>
.block-container { background-color: #1E1E1E !important; }
.sidebar .sidebar-content { background-color: #2F2F2F !important; color: white !important; }
body, .css-145kmo2, .css-12oz5g7, .css-15zrgzn { color: #FFFFFF !important; }
</style>
"""

st.set_page_config(layout="wide")
st.markdown(dark_css, unsafe_allow_html=True)

#############################
# 3) HELPER FUNCTIONS
#############################
def save_uploaded_file(uploaded_file, directory):
    file_path = os.path.join(directory, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())
    return file_path

def build_gis_data(node_csv_path, pipe_csv_path, asset_csv_path=None, leak_csv_path=None, original_crs="EPSG:27700"):
    df_nodes = pd.read_csv(node_csv_path)
    df_pipes = pd.read_csv(pipe_csv_path)

    if "Elevation_m" in df_nodes.columns:
        df_nodes.rename(columns={"Elevation_m": "elevation"}, inplace=True)

    node_gdf = gpd.GeoDataFrame(
        df_nodes,
        geometry=gpd.points_from_xy(df_nodes.XCoord, df_nodes.YCoord),
        crs=original_crs
    ).to_crs("EPSG:4326")

    node_map = {str(row.NodeID): row for idx, row in node_gdf.iterrows()}

    pipe_records = []
    for _, row in df_pipes.iterrows():
        pipe_id = str(row["PipeID"])
        start_node = node_map.get(str(row["StartID"]))
        end_node = node_map.get(str(row["EndID"]))

        if start_node is None or end_node is None:
            raise ValueError(f"Pipe {pipe_id} references invalid nodes.")

        avg_elev = (start_node["elevation"] + end_node["elevation"]) / 2

        pipe_records.append({
            "pipe_id": pipe_id,
            "geometry": LineString([start_node.geometry, end_node.geometry]),
            "elevation": avg_elev
        })

    pipe_gdf = gpd.GeoDataFrame(pipe_records, crs="EPSG:4326")

    asset_gdf = None
    if asset_csv_path:
        df_assets = pd.read_csv(asset_csv_path)
        coord_cols = [('XCoord', 'YCoord'), ('Longitude', 'Latitude'), ('Easting', 'Northing'), ('lon', 'lat')]
        for x_col, y_col in coord_cols:
            if x_col in df_assets.columns and y_col in df_assets.columns:
                asset_gdf = gpd.GeoDataFrame(
                    df_assets,
                    geometry=gpd.points_from_xy(df_assets[x_col], df_assets[y_col]),
                    crs=original_crs
                ).to_crs("EPSG:4326")
                break
        else:
            raise ValueError("Asset CSV missing coordinate columns.")

    leak_gdf = None
    if leak_csv_path:
        df_leaks = pd.read_csv(leak_csv_path)
        for x_col, y_col in coord_cols:
            if x_col in df_leaks.columns and y_col in df_leaks.columns:
                leak_gdf = gpd.GeoDataFrame(
                    df_leaks,
                    geometry=gpd.points_from_xy(df_leaks[x_col], df_leaks[y_col]),
                    crs=original_crs
                ).to_crs("EPSG:4326")
                break
        else:
            raise ValueError("Leak CSV missing coordinate columns.")

    return node_gdf, pipe_gdf, asset_gdf, leak_gdf

def create_pipe_layer(pipe_gdf):
    data = pipe_gdf.copy()
    pipe_records = [{
        "pipe_id": f"Pipe: {row.pipe_id}",
        "path": [[pt[0], pt[1]] for pt in row.geometry.coords],
        "color": [0, 255, 255],
        "elevation": f"Elevation: {row.elevation:.2f} m"
    } for idx, row in data.iterrows()]
    return pdk.Layer("PathLayer", data=pipe_records, get_path="path", get_color="color", width_min_pixels=2, get_width=5, pickable=True)

def create_point_layer(gdf, color, radius=10):
    data = gdf.copy()
    data["lon"] = data.geometry.x
    data["lat"] = data.geometry.y
    return pdk.Layer("ScatterplotLayer", data=data, get_position=["lon", "lat"], get_fill_color=color, get_radius=radius, pickable=True)

#############################
# 4) STREAMLIT APP
#############################
def main():
    st.title("3D DMA Elevation, Pipe, Asset & Leak Visualization")

    node_csv = st.file_uploader("Upload Node CSV", type=["csv"], key="node_csv")
    pipe_csv = st.file_uploader("Upload Pipe CSV", type=["csv"], key="pipe_csv")
    asset_csv = st.file_uploader("Upload Asset CSV (Valves, Hydrants, etc.)", type=["csv"], key="asset_csv")
    leak_csv = st.file_uploader("Upload Leak CSV (Historic Leak Locations)", type=["csv"], key="leak_csv")

    if st.button("Render Map"):
        if not node_csv or not pipe_csv:
            st.error("Please upload Node and Pipe CSV files.")
            return

        tmp_dir = tempfile.mkdtemp()
        node_path = save_uploaded_file(node_csv, tmp_dir)
        pipe_path = save_uploaded_file(pipe_csv, tmp_dir)
        asset_path = save_uploaded_file(asset_csv, tmp_dir) if asset_csv else None
        leak_path = save_uploaded_file(leak_csv, tmp_dir) if leak_csv else None

        with st.spinner("Building map..."):
            try:
                node_gdf, pipe_gdf, asset_gdf, leak_gdf = build_gis_data(node_path, pipe_path, asset_path, leak_path)

                layers = [create_pipe_layer(pipe_gdf)]
                if
