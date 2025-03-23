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

def build_gis_data(node_csv_path, pipe_csv_path, asset_csv_path=None, original_crs="EPSG:27700"):
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
        asset_gdf = gpd.GeoDataFrame(
            df_assets,
            geometry=gpd.points_from_xy(df_assets.XCoord, df_assets.YCoord),
            crs=original_crs
        ).to_crs("EPSG:4326")

    return node_gdf, pipe_gdf, asset_gdf

def create_pipe_layer(pipe_gdf):
    data = pipe_gdf.copy()

    pipe_records = [{
        "pipe_id": f"Pipe: {row.pipe_id}",
        "path": [[pt[0], pt[1]] for pt in row.geometry.coords],
        "color": [0, 255, 255],
        "elevation": f"Elevation: {row.elevation:.2f} m"
    } for idx, row in data.iterrows()]

    return pdk.Layer(
        "PathLayer",
        data=pipe_records,
        get_path="path",
        get_color="color",
        width_min_pixels=2,
        get_width=5,
        pickable=True
    )

def create_asset_layer(asset_gdf):
    data = asset_gdf.copy()
    data["lon"] = data.geometry.x
    data["lat"] = data.geometry.y

    return pdk.Layer(
        "ScatterplotLayer",
        data=data,
        get_position=["lon", "lat"],
        get_fill_color=[255, 0, 0],
        get_radius=10,
        pickable=True
    )

#############################
# 4) STREAMLIT APP
#############################
def main():
    st.title("3D DMA Elevation, Pipe & Asset Visualization")

    st.sidebar.header("Map Settings")

    node_csv = st.file_uploader("Upload Node CSV", type=["csv"], key="node_csv")
    pipe_csv = st.file_uploader("Upload Pipe CSV", type=["csv"], key="pipe_csv")
    asset_csv = st.file_uploader("Upload Asset CSV (Valves, Hydrants, etc.)", type=["csv"], key="asset_csv")

    if st.button("Render Map"):
        if not node_csv or not pipe_csv:
            st.error("Please upload Node and Pipe CSV files.")
            return

        tmp_dir = tempfile.mkdtemp()
        node_path = save_uploaded_file(node_csv, tmp_dir)
        pipe_path = save_uploaded_file(pipe_csv, tmp_dir)
        asset_path = save_uploaded_file(asset_csv, tmp_dir) if asset_csv else None

        with st.spinner("Building map..."):
            try:
                node_gdf, pipe_gdf, asset_gdf = build_gis_data(node_path, pipe_path, asset_path)

                pipe_layer = create_pipe_layer(pipe_gdf)
                layers = [pipe_layer]

                if asset_gdf is not None:
                    asset_layer = create_asset_layer(asset_gdf)
                    layers.append(asset_layer)

                mean_lon, mean_lat = node_gdf.geometry.x.mean(), node_gdf.geometry.y.mean()

                view_state = pdk.ViewState(
                    longitude=mean_lon,
                    latitude=mean_lat,
                    zoom=13,
                    pitch=45,
                    bearing=30
                )

                deck_map = pdk.Deck(
                    map_style="mapbox://styles/mapbox/dark-v10",
                    initial_view_state=view_state,
                    layers=layers,
                    tooltip={"html": "{pipe_id}<br>{elevation}", "style": {"color": "white", "font-size": "14px"}}
                )

                st.pydeck_chart(deck_map, use_container_width=True)
                st.success("Map successfully rendered!")

            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.info("Upload CSV files and click Render Map.")

if __name__ == "__main__":
    main()
