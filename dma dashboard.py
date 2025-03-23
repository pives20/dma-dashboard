import os
import streamlit as st
import pandas as pd
import geopandas as gpd
import pydeck as pdk
import tempfile
from shapely.geometry import Point, LineString

os.environ["MAPBOX_API_KEY"] = "pk.eyJ1IjoicGl2ZXMiLCJhIjoiY204bGVweHY5MTFnZDJscXluOTJ1OHI5OCJ9.3BHtAPkRsjGbwgNykec4VA"

st.set_page_config(layout="wide")

# Helper functions
def save_uploaded_file(uploaded_file, directory):
    file_path = os.path.join(directory, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())
    return file_path

def build_gis_data(node_csv_path, pipe_csv_path, asset_csv_path=None, leak_csv_path=None, original_crs="EPSG:27700"):
    df_nodes = pd.read_csv(node_csv_path)
    df_pipes = pd.read_csv(pipe_csv_path)

    node_gdf = gpd.GeoDataFrame(df_nodes, geometry=gpd.points_from_xy(df_nodes.XCoord, df_nodes.YCoord), crs=original_crs).to_crs("EPSG:4326")
    node_map = {str(row.NodeID): row for idx, row in node_gdf.iterrows()}

    pipe_records = []
    for _, row in df_pipes.iterrows():
        start_node = node_map.get(str(row["StartID"]))
        end_node = node_map.get(str(row["EndID"]))
        if start_node is None or end_node is None:
            continue
        avg_elev = (start_node["Elevation_m"] + end_node["Elevation_m"]) / 2
        pipe_records.append({"pipe_id": row["PipeID"], "geometry": LineString([start_node.geometry, end_node.geometry]), "elevation": avg_elev})

    pipe_gdf = gpd.GeoDataFrame(pipe_records, crs="EPSG:4326")

    asset_gdf, leak_gdf = None, None
    if asset_csv_path:
        df_assets = pd.read_csv(asset_csv_path)
        asset_gdf = gpd.GeoDataFrame(df_assets, geometry=gpd.points_from_xy(df_assets.XCoord, df_assets.YCoord), crs=original_crs).to_crs("EPSG:4326")

    if leak_csv_path:
        df_leaks = pd.read_csv(leak_csv_path)
        df_leaks_clean = df_leaks.dropna(subset=['XCoord', 'YCoord'])
        leak_gdf = gpd.GeoDataFrame(
            df_leaks_clean,
            geometry=gpd.points_from_xy(df_leaks_clean['XCoord'], df_leaks_clean['YCoord']),
            crs=original_crs
        ).to_crs("EPSG:4326")

    return node_gdf, pipe_gdf, asset_gdf, leak_gdf

# Layers creation
def create_pipe_layer(pipe_gdf):
    data = pipe_gdf.copy()
    pipe_records = [{"path": [[pt[0], pt[1]] for pt in row.geometry.coords], "color": [0, 255, 255], "pipe_id": row.pipe_id, "elevation": row.elevation} for idx, row in data.iterrows()]
    return pdk.Layer("PathLayer", data=pipe_records, get_path="path", get_color="color", width_min_pixels=3, pickable=True)

def create_asset_icon_layer(asset_gdf):
    ICON_URLS = {
        "Valve": "https://img.icons8.com/color/48/valve.png",
        "Hydrant": "https://img.icons8.com/color/48/fire-hydrant.png",
        "Meter": "https://img.icons8.com/color/48/speedometer.png",
        "Pump": "https://img.icons8.com/color/48/pump.png"
    }
    asset_gdf["icon_url"] = asset_gdf["AssetType"].map(lambda x: ICON_URLS.get(x, ICON_URLS["Valve"]))
    data = asset_gdf.copy()
    data["lon"], data["lat"] = data.geometry.x, data.geometry.y
    icon_data = [{"position": [row.lon, row.lat], "icon": row.icon_url} for idx, row in data.iterrows()]

    icon_layer = pdk.Layer("IconLayer", data=icon_data, get_icon="icon", size_scale=15, get_position="position", pickable=True)
    return icon_layer

def create_leak_layer(leak_gdf):
    data = leak_gdf.copy()
    data["lon"], data["lat"] = data.geometry.x, data.geometry.y
    return pdk.Layer("ScatterplotLayer", data=data, get_position=["lon", "lat"], get_fill_color=[255, 0, 0], get_radius=7, pickable=True)

# Streamlit App
st.title("DMA 3D Pipe, Asset & Leak Visualization")

node_csv = st.file_uploader("Node CSV", type=["csv"])
pipe_csv = st.file_uploader("Pipe CSV", type=["csv"])
asset_csv = st.file_uploader("Asset CSV", type=["csv"])
leak_csv = st.file_uploader("Leak CSV", type=["csv"])

if st.button("Render Map"):
    if not node_csv or not pipe_csv:
        st.error("Upload Node and Pipe CSV files.")
    else:
        tmp_dir = tempfile.mkdtemp()
        node_path = save_uploaded_file(node_csv, tmp_dir)
        pipe_path = save_uploaded_file(pipe_csv, tmp_dir)
        asset_path = save_uploaded_file(asset_csv, tmp_dir) if asset_csv else None
        leak_path = save_uploaded_file(leak_csv, tmp_dir) if leak_csv else None

        node_gdf, pipe_gdf, asset_gdf, leak_gdf = build_gis_data(node_path, pipe_path, asset_path, leak_path)

        layers = [create_pipe_layer(pipe_gdf)]
        if asset_gdf is not None:
            layers.append(create_asset_icon_layer(asset_gdf))
        if leak_gdf is not None:
            layers.append(create_leak_layer(leak_gdf))

        view_state = pdk.ViewState(latitude=node_gdf.geometry.y.mean(), longitude=node_gdf.geometry.x.mean(), zoom=13, pitch=45)
        deck_map = pdk.Deck(map_style="mapbox://styles/mapbox/dark-v10", initial_view_state=view_state, layers=layers, tooltip={"html": "{pipe_id}{elevation}", "style": {"color": "white"}})
        st.pydeck_chart(deck_map, use_container_width=True)
        st.success("Map rendered successfully!")
