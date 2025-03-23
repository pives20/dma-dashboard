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
os.environ["MAPBOX_API_KEY"] = "YOUR_MAPBOX_TOKEN"

#############################
# 2) CUSTOM DARK THEME
#############################
dark_css = """
<style>
.block-container {
    background-color: #1E1E1E !important;
}
.sidebar .sidebar-content {
    background-color: #2F2F2F !important;
    color: white !important;
}
body, .css-145kmo2, .css-12oz5g7, .css-15zrgzn {
    color: #FFFFFF !important;
}
</style>
"""

st.set_page_config(layout="wide")
st.markdown(dark_css, unsafe_allow_html=True)

#############################
# 3) HELPER FUNCTIONS
#############################
def save_uploaded_file(uploaded_file, directory):
    """Save a Streamlit-uploaded file to a local temp directory."""
    file_path = directory + "/" + uploaded_file.name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())
    return file_path

def build_gis_data(node_csv_path, pipe_csv_path):
    """
    Build GeoDataFrames from node & pipe CSVs:
      - Node CSV: NodeID, XCoord, YCoord, elevation
      - Pipe CSV: PipeID, StartID, EndID, flow
    Returns (node_gdf, pipe_gdf).
    """
    df_nodes = pd.read_csv(node_csv_path)
    df_pipes = pd.read_csv(pipe_csv_path)

    # Node GDF
    node_records = []
    for _, row in df_nodes.iterrows():
        node_id = str(row["NodeID"])
        x = float(row["XCoord"])  # LONGITUDE
        y = float(row["YCoord"])  # LATITUDE
        geometry = Point(x, y)

        rec = row.to_dict()
        rec["node_id"] = node_id
        rec["geometry"] = geometry
        node_records.append(rec)

    node_gdf = gpd.GeoDataFrame(node_records, crs="EPSG:4326")

    # Pipe GDF
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

def create_3d_elevation_layer(node_gdf):
    """
    ColumnLayer for nodes, extruded by 'elevation' (m).
    No scenario logic here, because elevation is static.
    """
    data = node_gdf.copy()
    data["lon"] = data.geometry.x
    data["lat"] = data.geometry.y

    # If 'elevation' is not present, set default 0
    if "elevation" not in data:
        data["elevation"] = 0

    max_elev = data["elevation"].max()
    if max_elev <= 0:
        max_elev = 1  # avoid divide-by-zero

    # Scale columns by elevation (2000 = arbitrary scale factor)
    data["height"] = data["elevation"].apply(lambda e: (e / max_elev) * 2000)

    # Color gradient from green (low) to brown (high), just an example
    def elev_to_color(e):
        ratio = e / max_elev
        # green -> brown
        r = 139 + int((205 - 139) * ratio)
        g = 69 + int((133 - 69) * ratio)
        b = 19 + int((63 - 19) * ratio)
        return [r, g, b]

    data["color"] = data["elevation"].apply(elev_to_color)

    elev_layer = pdk.Layer(
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
    return elev_layer

def create_pipe_layer(pipe_gdf, scenario="Baseline"):
    """
    PathLayer for pipes, coloring by 'flow'.
    If scenario == "Leak", we artificially increase flow by 20%.
    """
    data = pipe_gdf.copy()
    if "flow" not in data:
        data["flow"] = 0

    if scenario == "Leak":
        data["flow"] = data["flow"] * 1.2

    max_flow = data["flow"].max()
    if max_flow <= 0:
        max_flow = 1

    def flow_to_color(f):
        ratio = f / max_flow
        # Blue -> Red gradient
        r = int(255 * ratio)
        b = int(255 * (1 - ratio))
        g = 0
        return [r, g, b]

    pipe_records = []
    for _, row in data.iterrows():
        coords = list(row.geometry.coords)
        path = [[float(x), float(y)] for (x, y) in coords]
        c = flow_to_color(row["flow"])
        pipe_records.append({
            "pipe_id": row["pipe_id"],
            "path": path,
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
    st.title("3D Elevation Map + Flow Scenario Toggle (Qatium-Style)")

    # SCENARIO TOGGLE
    st.sidebar.header("Scenario")
    scenario = st.sidebar.selectbox("Pick scenario", ["Baseline", "Leak"])

    # METRICS
    st.sidebar.metric("Network Demand", "120 L/s", "+5%" if scenario=="Leak" else "")
    st.sidebar.metric("Elevation Range", "0-?" )  # We'll display actual range after loading data
    st.sidebar.metric("Pipe Flow Range", "0-?" )

    # UPLOADS
    st.write("#### Node CSV (NodeID, XCoord, YCoord, elevation)")
    node_csv = st.file_uploader("Node CSV", type=["csv"], key="node_csv")

    st.write("#### Pipe CSV (PipeID, StartID, EndID, flow)")
    pipe_csv = st.file_uploader("Pipe CSV", type=["csv"], key="pipe_csv")

    if st.button("Build 3D Map"):
        if not node_csv or not pipe_csv:
            st.error("Please upload both CSV files.")
            return

        tmp_dir = tempfile.mkdtemp()
        node_path = save_uploaded_file(node_csv, tmp_dir)
        pipe_path = save_uploaded_file(pipe_csv, tmp_dir)

        with st.spinner("Building map..."):
            try:
                node_gdf, pipe_gdf = build_gis_data(node_path, pipe_path)

                # Show data
                with st.expander("Node Data"):
                    st.dataframe(node_gdf.drop(columns="geometry").head(10))
                with st.expander("Pipe Data"):
                    st.dataframe(pipe_gdf.drop(columns="geometry").head(10))

                # Update the "Elevation Range" and "Flow Range" metrics
                elev_min = node_gdf["elevation"].min() if "elevation" in node_gdf else 0
                elev_max = node_gdf["elevation"].max() if "elevation" in node_gdf else 0
                st.sidebar.metric("Elevation Range", f"{elev_min}-{elev_max} m")

                flow_min = pipe_gdf["flow"].min() if "flow" in pipe_gdf else 0
                flow_max = pipe_gdf["flow"].max() if "flow" in pipe_gdf else 0
                st.sidebar.metric("Pipe Flow Range", f"{flow_min}-{flow_max} L/s")

                # Create layers
                elev_layer = create_3d_elevation_layer(node_gdf)
                pipe_layer = create_pipe_layer(pipe_gdf, scenario)

                # Center map on average node location
                mean_lon = node_gdf.geometry.x.mean()
                mean_lat = node_gdf.geometry.y.mean()

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
                    layers=[pipe_layer, elev_layer],
                    tooltip={
                        "html": "<b>Elevation:</b> {elevation} m<br/><b>Flow:</b> {flow} L/s<br/><b>Pipe:</b> {pipe_id}",
                        "style": {"color": "white"}
                    },
                )

                st.pydeck_chart(deck_map, use_container_width=True)
                st.success(f"Rendered scenario: {scenario}")

            except Exception as e:
                st.error(f"Error building 3D map: {e}")
    else:
        st.info("Upload Node & Pipe CSV, choose scenario, then click Build 3D Map.")


if __name__ == "__main__":
    main()
