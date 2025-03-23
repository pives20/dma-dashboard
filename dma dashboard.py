import streamlit as st
import pandas as pd
import pydeck as pdk
import geopandas as gpd
from shapely.geometry import Point, LineString
import os
import tempfile

def save_uploaded_file(uploaded_file, directory):
    """Save a Streamlit-uploaded file to a local temp directory."""
    file_path = os.path.join(directory, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())
    return file_path

def build_gis_model(node_csv_path, pipe_csv_path):
    """
    Build a GIS-based water network from two CSVs:
    Node CSV must have columns: NodeID, XCoord, YCoord
    Pipe CSV must have: PipeID, StartID, EndID
    (No EPANET / no reservoir needed, just geometry)
    """
    df_nodes = pd.read_csv(node_csv_path)
    df_pipes = pd.read_csv(pipe_csv_path)

    # 1) Create node GeoDataFrame
    node_records = []
    for _, row in df_nodes.iterrows():
        node_id = str(row["NodeID"])
        x = float(row["XCoord"])  # Should be LONGITUDE
        y = float(row["YCoord"])  # Should be LATITUDE
        geometry = Point(x, y)
        
        rec = row.to_dict()
        rec["node_id"] = node_id
        rec["geometry"] = geometry
        node_records.append(rec)
    node_gdf = gpd.GeoDataFrame(node_records, crs="EPSG:4326")  # lat/lon

    # 2) Create pipe GeoDataFrame by linking node coords
    node_map = { r["node_id"]: r.geometry for _, r in node_gdf.iterrows() }
    pipe_records = []
    for _, row in df_pipes.iterrows():
        pipe_id = str(row["PipeID"])
        start_id = str(row["StartID"])
        end_id   = str(row["EndID"])

        start_geom = node_map.get(start_id)
        end_geom   = node_map.get(end_id)
        if not start_geom or not end_geom:
            raise ValueError(f"Pipe {pipe_id} references invalid node {start_id} or {end_id}")

        line = LineString([start_geom.coords[0], end_geom.coords[0]])

        rec = row.to_dict()
        rec["pipe_id"] = pipe_id
        rec["geometry"] = line
        pipe_records.append(rec)

    pipe_gdf = gpd.GeoDataFrame(pipe_records, crs="EPSG:4326")

    return node_gdf, pipe_gdf

def create_map_layers(node_gdf, pipe_gdf):
    # Convert node geometry to lon/lat for Pydeck
    node_df = node_gdf.copy()
    node_df["lon"] = node_df.geometry.x
    node_df["lat"] = node_df.geometry.y

    # Build path coords for pipes
    pipe_records = []
    for _, row in pipe_gdf.iterrows():
        coords = list(row.geometry.coords)
        path_coords = [[float(x), float(y)] for (x, y) in coords]
        pipe_records.append({
            "pipe_id": row["pipe_id"],
            "path": path_coords,
            "start": row["StartID"],
            "end": row["EndID"]
        })

    node_layer = pdk.Layer(
        "ScatterplotLayer",
        data=node_df,
        get_position=["lon", "lat"],
        get_radius=40,
        get_fill_color=[0, 200, 255],
        pickable=True
    )

    pipe_layer = pdk.Layer(
        "PathLayer",
        data=pipe_records,
        get_path="path",
        get_width=5,
        get_color=[255, 180, 0],
        pickable=True
    )

    return node_layer, pipe_layer

def main():
    st.set_page_config(layout="wide")
    st.title("GIS Map of DMA (Dark Basemap)")

    st.markdown("Upload Node & Pipe CSV, then see a dark Mapbox background, with your network on top.")

    node_csv = st.file_uploader("Node CSV (XCoord, YCoord must be lat/lon!)", type=["csv"])
    pipe_csv = st.file_uploader("Pipe CSV (references NodeID)", type=["csv"])

    if st.button("Build Map"):
        if not node_csv or not pipe_csv:
            st.error("Please upload both CSV files.")
            return

        temp_dir = tempfile.mkdtemp()
        node_path = save_uploaded_file(node_csv, temp_dir)
        pipe_path = save_uploaded_file(pipe_csv, temp_dir)

        with st.spinner("Building model & creating map..."):
            try:
                node_gdf, pipe_gdf = build_gis_model(node_path, pipe_path)
                
                # Create Pydeck layers
                node_layer, pipe_layer = create_map_layers(node_gdf, pipe_gdf)

                # Center map on average location
                mean_lon = node_gdf.geometry.x.mean()
                mean_lat = node_gdf.geometry.y.mean()

                view_state = pdk.ViewState(
                    longitude=mean_lon,
                    latitude=mean_lat,
                    zoom=13,
                    pitch=0
                )

                deck_map = pdk.Deck(
                    map_style="mapbox://styles/mapbox/dark-v10",  # Dark style
                    initial_view_state=view_state,
                    layers=[pipe_layer, node_layer],
                    tooltip={
                        "html": "<b>Node:</b> {node_id} <br /><b>Pipe:</b> {pipe_id}",
                        "style": {"color": "white"}
                    },
                )

                st.pydeck_chart(deck_map, use_container_width=True)
                st.success("Done! Scroll/zoom around the map.")
                st.info("If the map is blank, check your lat/lon or you may need a Mapbox token.")
            except Exception as e:
                st.error(f"Failed to build map: {e}")
    else:
        st.info("Upload Node & Pipe CSV, then click 'Build Map'.")


if __name__ == "__main__":
    main()
