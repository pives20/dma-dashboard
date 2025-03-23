import streamlit as st
import pandas as pd
import pydeck as pdk
import geopandas as gpd
import tempfile
from shapely.geometry import Point, LineString

# Set your Mapbox token
pdk.settings.mapbox_api_key = "pk.eyJ1IjoicGl2ZXMiLCJhIjoiY204bGVweHY5MTFnZDJscXluOTJ1OHI5OCJ9.3BHtAPkRsjGbwgNykec4VA"

st.set_page_config(layout="wide")
st.title("🗺️ DMA Map (No Flow, No Elevation)")

# File uploads
st.sidebar.header("📁 Upload Data")
node_csv = st.sidebar.file_uploader("Upload Node CSV (NodeID, XCoord, YCoord)", type="csv")
pipe_csv = st.sidebar.file_uploader("Upload Pipe CSV (PipeID, StartID, EndID)", type="csv")

def save_uploaded_file(uploaded_file, directory):
    path = f"{directory}/{uploaded_file.name}"
    with open(path, "wb") as f:
        f.write(uploaded_file.read())
    return path

def build_geodata(node_path, pipe_path):
    nodes_df = pd.read_csv(node_path)
    pipes_df = pd.read_csv(pipe_path)

    # Create GeoDataFrame for nodes
    nodes_df["geometry"] = nodes_df.apply(lambda row: Point(row["XCoord"], row["YCoord"]), axis=1)
    nodes_gdf = gpd.GeoDataFrame(nodes_df, geometry="geometry", crs="EPSG:4326")

    # Map node IDs to geometry
    node_map = {row["NodeID"]: row.geometry for _, row in nodes_gdf.iterrows()}

    # Create GeoDataFrame for pipes
    pipe_records = []
    for _, row in pipes_df.iterrows():
        start = node_map.get(row["StartID"])
        end = node_map.get(row["EndID"])
        if start and end:
            line = LineString([start, end])
            pipe_records.append({"pipe_id": row["PipeID"], "geometry": line})

    pipes_gdf = gpd.GeoDataFrame(pipe_records, geometry="geometry", crs="EPSG:4326")
    return nodes_gdf, pipes_gdf

def create_map(nodes_gdf, pipes_gdf):
    # Prepare data for layers
    node_data = pd.DataFrame({
        "lat": nodes_gdf.geometry.y,
        "lon": nodes_gdf.geometry.x
    })

    pipe_data = []
    for _, row in pipes_gdf.iterrows():
        path = list(row.geometry.coords)
        pipe_data.append({"path": path})

    # Create layers
    node_layer = pdk.Layer(
        "ScatterplotLayer",
        data=node_data,
        get_position='[lon, lat]',
        get_color='[0, 150, 255]',
        get_radius=30,
        pickable=True
    )

    pipe_layer = pdk.Layer(
        "PathLayer",
        data=pipe_data,
        get_path="path",
        get_color='[0, 255, 100]',
        width_scale=20,
        width_min_pixels=2,
        pickable=True
    )

    # View centered on average node
    view = pdk.ViewState(
        latitude=node_data["lat"].mean(),
        longitude=node_data["lon"].mean(),
        zoom=14,
        pitch=30
    )

    return pdk.Deck(
        layers=[pipe_layer, node_layer],
        initial_view_state=view,
        map_style="mapbox://styles/mapbox/dark-v10"
    )

# Build map
if node_csv and pipe_csv:
    with tempfile.TemporaryDirectory() as tmpdir:
        node_path = save_uploaded_file(node_csv, tmpdir)
        pipe_path = save_uploaded_file(pipe_csv, tmpdir)

        try:
            nodes_gdf, pipes_gdf = build_geodata(node_path, pipe_path)
            deck = create_map(nodes_gdf, pipes_gdf)
            st.pydeck_chart(deck)
        except Exception as e:
            st.error(f"❌ Error rendering map: {e}")
else:
    st.info("📍 Upload node and pipe CSVs to display the map.")
