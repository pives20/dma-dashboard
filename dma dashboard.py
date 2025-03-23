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
# Replace with your actual token or read from environment/secrets
os.environ["MAPBOX_API_KEY"] = "YOUR_MAPBOX_TOKEN"

#############################
# 2) CUSTOM CSS FOR DARK UI
#############################
custom_css = """
<style>
/* Dark background for entire app */
.block-container {
    background-color: #1E1E1E !important;
}
.sidebar .sidebar-content {
    background-color: #2F2F2F !important;
    color: white !important;
}
.reportview-container .main .block-container {
    color: #FFFFFF !important;
}
/* Make text white */
body, .css-145kmo2, .css-12oz5g7, .css-15zrgzn {
    color: #FFFFFF !important;
}
</style>
"""

st.set_page_config(layout="wide")
st.markdown(custom_css, unsafe_allow_html=True)

#############################
# 3) HELPER FUNCTIONS
#############################
def save_uploaded_file(uploaded_file, directory):
    """Save Streamlit-uploaded file to a local temp directory."""
    file_path = directory + "/" + uploaded_file.name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())
    return file_path

def build_gis_data(node_csv_path, pipe_csv_path):
    """
    Build GeoDataFrames for nodes & pipes:
    - Node CSV: [NodeID, XCoord, YCoord, pressure, ...]
    - Pipe CSV: [PipeID, StartID, EndID, flow, ...]
    Returns (node_gdf, pipe_gdf).
    """
    df_nodes = pd.read_csv(node_csv_path)
    df_pipes = pd.read_csv(pipe_csv_path)

    # Create node GeoDataFrame
    node_records = []
    for idx, row in df_nodes.iterrows():
        node_id = str(row["NodeID"])
        x = float(row["XCoord"])  # LONGITUDE
        y = float(row["YCoord"])  # LATITUDE
        geometry = Point(x, y)

        rec = row.to_dict()
        rec["node_id"] = node_id
        rec["geometry"] = geometry
        node_records.append(rec)

    node_gdf = gpd.GeoDataFrame(node_records, crs="EPSG:4326")

    # Create pipe GeoDataFrame
    node_map = { r["node_id"]: r.geometry for _, r in node_gdf.iterrows() }
    pipe_records = []
    for idx, row in df_pipes.iterrows():
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

def create_3d_node_layer(node_gdf, scenario="Baseline"):
    """
    Example 3D ColumnLayer for nodes, extruded by 'pressure'.
    If scenario == "Leak", we might reduce pressure artificially.
    """
    data = node_gdf.copy()
    
    # Scenario logic: if "Leak" scenario, reduce pressure by 20% as a simple example
    if scenario == "Leak":
        data["pressure"] = data["pressure"] * 0.8
    
    # Decide a max pressure to scale columns
    max_pressure = data["pressure"].max() if "pressure" in data else 1
    if max_pressure <= 0: max_pressure = 1

    data["lon"] = data.geometry.x
    data["lat"] = data.geometry.y

    # Elevation: scale pressure to some 3D height
    data["height"] = data["pressure"].apply(lambda p: (p / max_pressure) * 1000)

    # Color columns by pressure ratio
    def pressure_to_color(p):
        ratio = p / max_pressure
        # Purple -> Yellow gradient as an example
        r = 103 + int((253 - 103) * ratio)
        g = 0 + int((184 - 0) * ratio)
        b = 31 + int((99 - 31) * ratio)
        return [r, g, b]

    data["color"] = data["pressure"].apply(pressure_to_color)

    node_layer = pdk.Layer(
        "ColumnLayer",
        data=data,
        get_position=["lon", "lat"],
        get_elevation="height",
        elevation_scale=1,
        radius=30,
        get_fill_color="color",
        pickable=True,
        extruded=True
    )
    return node_layer

def create_pipe_layer(pipe_gdf, scenario="Baseline"):
    """
    PathLayer for pipes, colored by flow.
    If scenario == "Leak", maybe flow is higher, etc.
    """
    data = pipe_gdf.copy()

    # Example: If "Leak" scenario, we add 20% to flow
    if scenario == "Leak":
        data["flow"] = data["flow"] * 1.2

    max_flow = data["flow"].max() if "flow" in data else 1
    if max_flow <= 0: max_flow = 1

    # Color by flow ratio
    def flow_to_color(f):
        ratio = f / max_flow
        # Blue -> Red gradient
        r = int(255 * ratio)
        g = 0
        b = int(255 * (1 - ratio))
        return [r, g, b]

    pipe_records = []
    for idx, row in data.iterrows():
        coords = list(row.geometry.coords)
        path = [[float(x), float(y)] for (x, y) in coords]
        c = flow_to_color(row["flow"])
        pipe_records.append({
            "pipe_id": row["pipe_id"],
            "path": path,
            "start": row["StartID"],
            "end": row["EndID"],
            "color": c
        })

    pipe_layer = pdk.Layer(
        "PathLayer",
        data=pipe_records,
        get_path="path",
        get_color="color",
        width_min_pixels=2,
        get_width=5,
        pickable=True
    )
    return pipe_layer

#############################
# 4) STREAMLIT APP
#############################
def main():
    st.title("Qatium-Style 3D DMA Map Demo")

    # ---- SIDEBAR for scenario toggles
    st.sidebar.header("Scenario Selection")
    scenario = st.sidebar.selectbox("Choose scenario:", ["Baseline", "Leak"])
    
    st.sidebar.header("Metrics (Example)")
    st.sidebar.metric("Network Demand", "120 L/s", "+5%" if scenario=="Leak" else "0%")
    st.sidebar.metric("Active Leaks", "0" if scenario=="Baseline" else "1")
    st.sidebar.metric("Service Pressure", "50 m", "-10 m" if scenario=="Leak" else "0 m")

    # ---- MAIN FILE UPLOAD
    st.write("**Upload Node CSV** (with columns: NodeID, XCoord, YCoord, pressure)")
    node_csv = st.file_uploader("Node CSV", type=["csv"], key="node_csv")

    st.write("**Upload Pipe CSV** (with columns: PipeID, StartID, EndID, flow)")
    pipe_csv = st.file_uploader("Pipe CSV", type=["csv"], key="pipe_csv")

    if st.button("Build 3D Map"):
        if not node_csv or not pipe_csv:
            st.error("Please upload both CSVs first.")
            return

        tmp_dir = tempfile.mkdtemp()
        node_path = save_uploaded_file(node_csv, tmp_dir)
        pipe_path = save_uploaded_file(pipe_csv, tmp_dir)

        with st.spinner("Building 3D map..."):
            try:
                node_gdf, pipe_gdf = build_gis_data(node_path, pipe_path)

                # Optional: show data in expanders
                with st.expander("Node Data"):
                    st.dataframe(node_gdf.drop(columns="geometry").head(10))
                with st.expander("Pipe Data"):
                    st.dataframe(pipe_gdf.drop(columns="geometry").head(10))

                # Create the Pydeck layers (3D nodes + pipes)
                node_layer = create_3d_node_layer(node_gdf, scenario)
                pipe_layer = create_pipe_layer(pipe_gdf, scenario)

                # Center the map
                mean_lon = node_gdf.geometry.x.mean()
                mean_lat = node_gdf.geometry.y.mean()

                view_state = pdk.ViewState(
                    longitude=mean_lon,
                    latitude=mean_lat,
                    zoom=13,
                    pitch=45,   # tilt the camera for 3D
                    bearing=30  # rotate for a nicer angle
                )

                # Combine layers
                deck_map = pdk.Deck(
                    map_style="mapbox://styles/mapbox/dark-v10",
                    initial_view_state=view_state,
                    layers=[pipe_layer, node_layer],
                    tooltip={
                        "html": "<b>Node:</b> {node_id} <br/><b>Pipe:</b> {pipe_id}",
                        "style": {"color": "white"}
                    },
                )

                st.pydeck_chart(deck_map, use_container_width=True)
                st.success(f"Rendered scenario: {scenario}")
                st.info("Scroll/pinch to zoom, drag to pan, tilt for a Qatium-like 3D feel.")

            except Exception as e:
                st.error(f"Error building 3D map: {e}")
    else:
        st.info("Upload Node & Pipe CSV, pick scenario, then click 'Build 3D Map'.")


if __name__ == "__main__":
    main()
