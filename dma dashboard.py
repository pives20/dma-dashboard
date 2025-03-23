import streamlit as st
import pandas as pd
import pydeck as pdk
import geopandas as gpd
import networkx as nx
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
    Build a GIS-based water network from two CSVs (no EPANET):
      - Node CSV must have columns: [NodeID, XCoord, YCoord, ...]
      - Pipe CSV must have columns: [PipeID, StartID, EndID, ...]
    Returns (node_gdf, pipe_gdf) as GeoDataFrames, with geometry.
    """
    df_nodes = pd.read_csv(node_csv_path)
    df_pipes = pd.read_csv(pipe_csv_path)

    # 1) Create node GeoDataFrame
    node_records = []
    for idx, row in df_nodes.iterrows():
        node_id = str(row["NodeID"])
        x = float(row["XCoord"])
        y = float(row["YCoord"])
        geometry = Point(x, y)

        extra = row.to_dict()
        extra["node_id"] = node_id
        extra["geometry"] = geometry
        node_records.append(extra)

    node_gdf = gpd.GeoDataFrame(node_records, crs="EPSG:4326")  # If in lat/lon

    # 2) Create pipe GeoDataFrame by linking node coords
    node_coord_map = { row["node_id"]: row.geometry for idx, row in node_gdf.iterrows() }

    pipe_records = []
    for idx, row in df_pipes.iterrows():
        pipe_id = str(row["PipeID"])
        start_id = str(row["StartID"])
        end_id   = str(row["EndID"])

        start_geom = node_coord_map.get(start_id)
        end_geom   = node_coord_map.get(end_id)
        if start_geom is None or end_geom is None:
            raise ValueError(f"Pipe {pipe_id} references invalid node {start_id} or {end_id}")

        line_geom = LineString([start_geom.coords[0], end_geom.coords[0]])

        extra_p = row.to_dict()
        extra_p["pipe_id"] = pipe_id
        extra_p["geometry"] = line_geom
        pipe_records.append(extra_p)

    pipe_gdf = gpd.GeoDataFrame(pipe_records, crs="EPSG:4326")

    return node_gdf, pipe_gdf

def check_connectivity(node_gdf, pipe_gdf):
    """
    Simple topological check using NetworkX.
    Returns (G, list of connected components).
    """
    G = nx.Graph()

    # Add nodes
    for idx, row in node_gdf.iterrows():
        G.add_node(row["node_id"])

    # Add edges
    for idx, row in pipe_gdf.iterrows():
        start_id = row["StartID"]
        end_id   = row["EndID"]
        G.add_edge(start_id, end_id, pipe_id=row["pipe_id"])

    components = list(nx.connected_components(G))
    return G, components

def create_map_layers(node_gdf, pipe_gdf):
    """
    Create Pydeck layers for an interactive map.
    - A scatterplot for nodes
    - A path layer for pipes
    """
    # Convert node geometry to lon/lat
    node_df = node_gdf.copy()
    node_df["lon"] = node_df.geometry.x
    node_df["lat"] = node_df.geometry.y

    # Build path records for pipes
    pipe_records = []
    for idx, row in pipe_gdf.iterrows():
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
        get_fill_color=[0, 100, 255],
        pickable=True
    )

    pipe_layer = pdk.Layer(
        "PathLayer",
        data=pipe_records,
        get_path="path",
        get_width=3,
        width_min_pixels=2,
        get_color=[200, 30, 0],
        pickable=True
    )

    return node_layer, pipe_layer


###############################
# STREAMLIT APP
###############################

def main():
    st.set_page_config(layout="wide")
    st.title("GIS-Only DMA Map: Drill Down & Connectivity")

    st.write("""
    **Instructions**:
    1. Upload **Node CSV** and **Pipe CSV**.
    2. We'll create a GeoDataFrame (nodes as points, pipes as lines).
    3. See an interactive map to 'drill down' into the DMA.
    """)

    node_csv = st.file_uploader("Upload Node CSV", type=["csv"], key="node_csv")
    pipe_csv = st.file_uploader("Upload Pipe CSV", type=["csv"], key="pipe_csv")

    if st.button("Build & Map"):
        if not node_csv or not pipe_csv:
            st.error("Please upload both Node CSV and Pipe CSV.")
            return

        temp_dir = tempfile.mkdtemp()
        node_path = save_uploaded_file(node_csv, temp_dir)
        pipe_path = save_uploaded_file(pipe_csv, temp_dir)

        with st.spinner("Building GIS model..."):
            try:
                node_gdf, pipe_gdf = build_gis_model(node_path, pipe_path)
                st.success("GIS model built successfully!")
                st.write(f"Number of nodes: {len(node_gdf)}")
                st.write(f"Number of pipes: {len(pipe_gdf)}")

                # Display dataframes
                with st.expander("Node Data"):
                    st.dataframe(node_gdf.drop(columns="geometry"))
                with st.expander("Pipe Data"):
                    st.dataframe(pipe_gdf.drop(columns="geometry"))

                # Optional connectivity check
                G, components = check_connectivity(node_gdf, pipe_gdf)
                if len(components) == 1:
                    st.info("All nodes are in one connected component.")
                else:
                    st.warning(f"Network is split into {len(components)} components: {components}")

                # Create Pydeck map layers
                node_layer, pipe_layer = create_map_layers(node_gdf, pipe_gdf)

                # Center map on average location
                avg_lon = node_gdf.geometry.x.mean()
                avg_lat = node_gdf.geometry.y.mean()
                view_state = pdk.ViewState(latitude=avg_lat, longitude=avg_lon, zoom=14, pitch=0)

                deck_map = pdk.Deck(
                    layers=[pipe_layer, node_layer],
                    initial_view_state=view_state,
                    tooltip={
                        "html": "<b>Node:</b> {node_id} <br /><b>Pipe:</b> {pipe_id}",
                        "style": {"color": "white"}
                    },
                )
                st.pydeck_chart(deck_map, use_container_width=True)

                st.write("Use your mouse wheel or trackpad to zoom, and drag to pan. Hover over nodes/pipes to see details.")

            except Exception as e:
                st.error(f"Error building or mapping the network: {e}")
    else:
        st.info("Upload Node & Pipe CSV, then click 'Build & Map' to see the interactive GIS.")


if __name__ == "__main__":
    main()
