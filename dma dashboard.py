import os
import streamlit as st
import pandas as pd
import geopandas as gpd
import pydeck as pdk
import tempfile
from shapely.geometry import LineString
from datetime import datetime

os.environ["MAPBOX_API_KEY"] = "pk.eyJ1IjoicGl2ZXMiLCJhIjoiY204bGVweHY5MTFnZDJscXluOTJ1OHI5OCJ9.3BHtAPkRsjGbwgNykec4VA"

st.set_page_config(layout="wide")

# Helper functions
def save_uploaded_file(uploaded_file, directory):
    file_path = os.path.join(directory, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())
    return file_path

def build_gis_data(node_csv, pipe_csv, leak_csv, asset_csv=None, original_crs="EPSG:27700"):
    df_nodes = pd.read_csv(node_csv)
    df_pipes = pd.read_csv(pipe_csv)
    df_leaks = pd.read_csv(leak_csv)

    current_year = datetime.now().year

    node_gdf = gpd.GeoDataFrame(df_nodes, geometry=gpd.points_from_xy(df_nodes.XCoord, df_nodes.YCoord), crs=original_crs).to_crs("EPSG:4326")
    node_map = {str(row.NodeID): row for idx, row in node_gdf.iterrows()}

    pipe_records = []
    for _, row in df_pipes.iterrows():
        start_node = node_map.get(str(row["StartID"]))
        end_node = node_map.get(str(row["EndID"]))
        if start_node is not None and end_node is not None:
            try:
                year_laid = int(row["Age"])
                pipe_age = current_year - year_laid
            except (ValueError, TypeError):
                continue
            pipe_records.append({
                "pipe_id": row["PipeID"],
                "geometry": LineString([start_node.geometry, end_node.geometry]),
                "Age": pipe_age,
                "Material": row["Material"]
            })

    pipe_gdf = gpd.GeoDataFrame(pipe_records, crs="EPSG:4326")

    df_leaks = df_leaks.dropna(subset=['XCoord', 'YCoord', 'DateReported'])
    leak_gdf = gpd.GeoDataFrame(df_leaks, geometry=gpd.points_from_xy(df_leaks['XCoord'], df_leaks['YCoord']), crs=original_crs).to_crs("EPSG:4326")

    asset_gdf = None
    if asset_csv:
        df_assets = pd.read_csv(asset_csv)
        asset_gdf = gpd.GeoDataFrame(df_assets, geometry=gpd.points_from_xy(df_assets.XCoord, df_assets.YCoord), crs=original_crs).to_crs("EPSG:4326")

    return node_gdf, pipe_gdf, leak_gdf, asset_gdf

# Layers creation with criticality
def create_pipe_layer(pipe_gdf, criticality_on):
    def pipe_color(row):
        if criticality_on:
            if row['Material'] == "Cast Iron" or row['Age'] > 50:
                return [255, 0, 0]
            elif row['Age'] > 30:
                return [255, 165, 0]
            else:
                return [0, 255, 0]
        return [0, 255, 255]

    pipe_data = [{
        "path": [[pt[0], pt[1]] for pt in row.geometry.coords],
        "color": pipe_color(row),
        "pipe_id": row.pipe_id,
        "Age": row.Age,
        "Material": row.Material
    } for _, row in pipe_gdf.iterrows()]

    return pdk.Layer("PathLayer", pipe_data, get_path="path", get_color="color", width_min_pixels=4, pickable=True)

def create_leak_layer(leak_gdf):
    leak_data = [{
        "position": [geom.x, geom.y],
        "DateReported": row.DateReported,
        "LeakType": row.LeakType
    } for geom, row in zip(leak_gdf.geometry, leak_gdf.itertuples())]
    return pdk.Layer("ScatterplotLayer", leak_data, get_position="position", get_fill_color=[255, 0, 0], get_radius=10, pickable=True)

def create_asset_layer(asset_gdf):
    asset_data = [{"position": [geom.x, geom.y], "AssetID": row.AssetID, "AssetType": row.AssetType} for geom, row in zip(asset_gdf.geometry, asset_gdf.itertuples())]
    return pdk.Layer("ScatterplotLayer", asset_data, get_position="position", get_fill_color=[0, 255, 0], get_radius=10, pickable=True)

# Streamlit App
st.title("DMA Dashboard: Leak, Asset & Pipe Criticality Visualization")

node_csv = st.file_uploader("Upload Node CSV", type=["csv"])
pipe_csv = st.file_uploader("Upload Pipe CSV (column 'Age' should hold Year Laid)", type=["csv"])
leak_csv = st.file_uploader("Upload Leak CSV (include 'DateReported')", type=["csv"])
asset_csv = st.file_uploader("Upload Asset CSV", type=["csv"])

criticality_on = st.sidebar.checkbox("Toggle Pipe Criticality Visualization", value=False)

if st.button("Render Map"):
    if not node_csv or not pipe_csv or not leak_csv or not asset_csv:
        st.error("Please upload all CSV files.")
    else:
        tmp_dir = tempfile.mkdtemp()
        node_path = save_uploaded_file(node_csv, tmp_dir)
        pipe_path = save_uploaded_file(pipe_csv, tmp_dir)
        leak_path = save_uploaded_file(leak_csv, tmp_dir)
        asset_path = save_uploaded_file(asset_csv, tmp_dir)

        node_gdf, pipe_gdf, leak_gdf, asset_gdf = build_gis_data(node_path, pipe_path, leak_path, asset_path)

        layers = [
            create_pipe_layer(pipe_gdf, criticality_on),
            create_leak_layer(leak_gdf),
            create_asset_layer(asset_gdf)
        ]

        view_state = pdk.ViewState(latitude=node_gdf.geometry.y.mean(), longitude=node_gdf.geometry.x.mean(), zoom=13, pitch=45)

        deck_map = pdk.Deck(
            map_style="mapbox://styles/mapbox/dark-v10",
            initial_view_state=view_state,
            layers=layers,
            tooltip={"html": "<b>{pipe_id}{AssetID}</b><br>Material: {Material}<br>Age: {Age} years<br><b>Leak:</b> {LeakType} ({DateReported})", "style": {"color": "white"}}
        )

        st.pydeck_chart(deck_map, use_container_width=True)
        st.success("DMA Dashboard rendered successfully!")
