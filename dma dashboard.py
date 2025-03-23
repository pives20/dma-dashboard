import streamlit as st
import pandas as pd
import pydeck as pdk
import geopandas as gpd
from shapely.geometry import Point, LineString
import networkx as nx
import os
import tempfile

def save_uploaded_file(uploaded_file, directory):
    """Save a Streamlit-uploaded file to a local temp directory."""
    file_path = os.path.join(directory, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())
    return file_path

def build_gis_model(node_csv, pipe_csv):
    """
    Build a GIS-based water network (no EPANET) from two CSVs:
      1) Node CSV: [NodeID, XCoord, YCoord, ...]
      2) Pipe CSV: [PipeID, StartID, EndID, ...]
    Returns (node_gdf, pipe_gdf) as GeoDataFrames.
    """
    df_nodes = pd.read_csv(node_csv)
    df_pipes = pd.read_csv(pipe_csv)

    # 1) Build node GeoDataFrame
    #   - We'll assume XCoord, YCoord are numeric. If lat/lon, keep in mind your CRS.
    node_records = []
    for idx, row in df_nodes.iterrows():
        node_id = str(row["NodeID"])
        x = float(row["XCoord"])
        y = float(row["YCoord"])
        # Store any extra columns as well
        extra_attrs = row.to_dict()
        geometry = Point(x, y)
        extra_attrs["geometry"] = geometry
        extra_attrs["node_id"] = node_id
        node_records.append(extra_attrs)

    node_gdf = gpd.GeoDataFrame(node_records, crs="EPSG:4326")  # or whatever your coordinate system

    # 2) Build pipe GeoDataFrame
    #   - For each pipe, we look up the StartID and EndID in node_gdf to get coordinates.
    pipe_records = []
    # Create a dictionary for quick node lookup: node_id -> shapely Point
    node_coord_map = { row["node_id"]: row.geometry for idx, row in node_gdf.iterrows() }

    for idx, row in df_pipes.iterrows():
        pipe_id = str(row["PipeID"])
        start_id = str(row["StartID"])
        end_id = str(row["EndID"])

        start_geom = node_coord_map.get(start_id)
        end_geom = node_coord_map.get(end_id)
        if start_geom is None or end_geom is None:
            # Missing reference, skip or raise an error
            raise ValueError(f"Pipe {pipe_id} references a node that doesn't exist: {start_id} or {end_id}")

        line_geom = LineString([start_geom.coords[0], end_geom.coords[0]])

        extra_attrs = row.to_dict()
        extra_attrs["pipe_id"] = pipe_id
        extra_attrs["geometry"] = line_geom
        pipe_records.append(extra_attrs)

    pipe_gdf = gpd.GeoDataFrame(pipe_records, crs="EPSG:4326")

    return node_gdf, pipe_gdf

def check_connectivity(node_gdf, pipe_gdf):
    """
    Perform a simple topological connectivity check using NetworkX.
    We'll create a graph where each node is a 'node_id' and each pipe
    is an edge. Then see if it's fully connected or not.
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

    # Check connected components
    components = list(nx.connected_components(G))
    return G, components

def create_pydeck_layers(node_gdf, pipe_gdf):
    """
    Create Pydeck layers for nodes and pipes.
    We'll do a ScatterplotLayer for nodes, PathLayer for pipes.
    """
    # Convert node geometry to lon/lat columns
    # If your data is in meters, you can still plot in pydeck, but the scale will be different.
    node_df = node_gdf.copy()
    node_df["lon"] = node_df.geometry.x
    node_df["lat"] = node_df.geometry.y

    # Build a path list for each pipe
    pipe_records = []
    for idx, row in pipe_gdf.iterrows():
        coords = list(row.geometry.coords)
        # path is a list of [lon, lat] pairs
        path_coords = [[float(x), float(y)] for (x, y) in coords]
        pipe_records.append({
            "pipe_id": row["pipe_id"],
            "path": path_coords,
            "start": row["StartID"],
            "end": row["EndID"]
        })

    # Nodes layer
    node_layer = pdk.Layer(
        "ScatterplotLayer",
        data=node_df,
        get_position=["lon", "lat"],
        get_radius=50,
        get_fill_color=[0, 128, 255],
        pickable=True
    )

    # Pipes layer
    pipe_layer = pdk.Layer(
        "PathLayer",
        data=pipe_records,
        get_path="path",
        get_width=5,
        get_color=[200, 30, 0],
        width_min_pixels=1,
        pickable=True
    )

    return node_layer, pipe_layer

###############################
# 2) STREAMLIT APP
###############################

def main():
    st.set_page_config(layout="wide")
    st.title("GIS-Only Water Network Model (No EPANET)")

    st.write("""
    **Instructions**:
    1. Upload **Node CSV** (with columns: NodeID, XCoord, YCoord, ...).  
    2. Upload **Pipe CSV** (with columns: PipeID, StartID, EndID, ...).  
    3. We'll build a GIS-based model (nodes as points, pipes as lines).  
    4. See connectivity results (if you want) and an interactive map.
    """)

    node_csv = st.file_uploader("Upload Node CSV", type=["csv"], key="node_csv")
    pipe_csv = st.file_uploader("Upload Pipe CSV", type=["csv"], key="pipe_csv")

    if st.button("Build GIS Model"):
        if not node_csv or not pipe_csv:
            st.error("Please upload both Node and Pipe CSV first.")
            return

        temp_dir = tempfile.mkdtemp()
        node_path = save_uploaded_file(node_csv, temp_dir)
        pipe_path = save_uploaded_file(pipe_csv, temp_dir)

        with st.spinner("Building the GIS model from CSV..."):
            try:
                node_gdf, pipe_gdf = build_gis_model(node_path, pipe_path)
                st.success("GIS model built successfully!")
                st.write(f"Nodes: {len(node_gdf)}, Pipes: {len(pipe_gdf)}")

                # Show dataframes
                st.subheader("Node Data")
                st.dataframe(node_gdf.drop(columns="geometry").head(10))

                st.subheader("Pipe Data")
                st.dataframe(pipe_gdf.drop(columns="geometry").head(10))

                # Connectivity check
                G, components = check_connectivity(node_gdf, pipe_gdf)
                st.subheader("Connectivity Analysis")
                if len(components) == 1:
                    st.write("All nodes are in a single connected component.")
                else:
                    st.warning(f"Network is split into {len(components)} components: {components}")

                # Build Pydeck layers
                node_layer, pipe_layer = create_pydeck_layers(node_gdf, pipe_gdf)

                # Center map on the average of node coords
                avg_lon = node_gdf.geometry.x.mean()
                avg_lat = node_gdf.geometry.y.mean()
                view_state = pdk.ViewState(latitude=avg_lat, longitude=avg_lon, zoom=12, pitch=0)

                deck_map = pdk.Deck(
                    layers=[pipe_layer, node_layer],
                    initial_view_state=view_state,
                    tooltip={"text": "Node: {node_id}\nPipe: {pipe_id}"}
                )
                st.pydeck_chart(deck_map, use_container_width=True)

            except Exception as e:
                st.error(f"Error building GIS model: {e}")
    else:
        st.info("Upload Node & Pipe CSV, then click 'Build GIS Model' to proceed.")

if __name__ == "__main__":
    main()
