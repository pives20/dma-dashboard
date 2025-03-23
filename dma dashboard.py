import streamlit as st
import wntr
import geopandas as gpd
import pandas as pd
import pydeck as pdk
import tempfile
import zipfile
import os
from shapely.geometry import Point, LineString

############################################
# 1) UTILITY FUNCTIONS
############################################

def unzip_and_get_shp(zip_file) -> str:
    """
    Extracts a zipfile (uploaded via Streamlit) to a temp folder,
    returns the path to the .shp file.
    Assumes there's exactly one .shp inside the zip.
    """
    tdir = tempfile.mkdtemp()
    with zipfile.ZipFile(zip_file, "r") as z:
        z.extractall(tdir)
    # Find the first .shp file in the temp folder
    shp_path = None
    for root, dirs, files in os.walk(tdir):
        for f in files:
            if f.lower().endswith(".shp"):
                shp_path = os.path.join(root, f)
                break
    return shp_path

def build_model_from_gis(nodes_shp: str, pipes_shp: str) -> wntr.network.WaterNetworkModel:
    """
    Reads node and pipe shapefiles (paths to .shp),
    creates a WaterNetworkModel in memory.
    Assumes certain columns:
      - node_gdf: NodeID, Elev, Demand, geometry(Point)
      - pipe_gdf: PipeID, StartID, EndID, Length, Diameter, Roughness, geometry(LineString)
    """
    wn = wntr.network.WaterNetworkModel()

    # 1. Load node shapefile
    node_gdf = gpd.read_file(nodes_shp)
    # For each node
    for idx, row in node_gdf.iterrows():
        node_id = str(row["NodeID"])
        elev = row.get("Elev", 0.0)
        demand = row.get("Demand", 0.0)
        wn.add_junction(name=node_id, base_demand=demand, elevation=elev)
        # Store coordinates for reference (won't affect hydraulic calcs)
        x, y = row.geometry.x, row.geometry.y
        wn.get_node(node_id).coordinates = (float(x), float(y))

    # 2. Load pipe shapefile
    pipe_gdf = gpd.read_file(pipes_shp)
    for idx, row in pipe_gdf.iterrows():
        pipe_id   = str(row["PipeID"])
        start_id  = str(row["StartID"])
        end_id    = str(row["EndID"])
        length    = row.get("Length", 0.0)
        diameter  = row.get("Diameter", 100.0)
        roughness = row.get("Roughness", 100.0)

        # If no length in attribute, compute from geometry (in shapefile units)
        if (not length) or (length <= 0):
            length = row.geometry.length

        wn.add_pipe(
            name=pipe_id,
            start_node_name=start_id,
            end_node_name=end_id,
            length=length,
            diameter=diameter,
            roughness=roughness,
            minor_loss=0.0,
            status='OPEN'
        )

    return wn

def run_epanet_simulation(wn: wntr.network.WaterNetworkModel):
    """
    Runs an EPANET simulation via WNTR,
    returns final time-step results as dicts (pressures, flows, etc.).
    """
    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim()

    # Extract final time
    last_time = results.node["pressure"].index[-1]
    pressures = results.node["pressure"].loc[last_time].to_dict()
    demands   = results.node["demand"].loc[last_time].to_dict()
    flows     = results.link["flowrate"].loc[last_time].to_dict()
    velocity  = results.link["velocity"].loc[last_time].to_dict()

    return {
        "pressures": pressures,
        "demands":   demands,
        "flows":     flows,
        "velocity":  velocity
    }

def build_geodataframes(wn, results_dict):
    """
    Convert WNTR model + results into GeoDataFrames (nodes, links).
    We'll rely on the coordinates we stored in wn.get_node(node_id).coordinates.
    """
    node_data = []
    for node_name, node_obj in wn.nodes():
        x, y = node_obj.coordinates
        pressure = results_dict["pressures"].get(node_name, 0.0)
        demand   = results_dict["demands"].get(node_name, 0.0)
        node_data.append({
            "node_id":   node_name,
            "pressure":  pressure,
            "demand":    demand,
            "geometry":  Point(x, y),
        })
    node_gdf = gpd.GeoDataFrame(node_data, crs="EPSG:4326")

    link_data = []
    for link_name, link_obj in wn.links():
        start_node = wn.get_node(link_obj.start_node_name)
        end_node   = wn.get_node(link_obj.end_node_name)
        x1, y1 = start_node.coordinates
        x2, y2 = end_node.coordinates
        link_data.append({
            "link_id":   link_name,
            "flow":      results_dict["flows"].get(link_name, 0.0),
            "velocity":  results_dict["velocity"].get(link_name, 0.0),
            "geometry":  LineString([(x1, y1), (x2, y2)]),
        })
    link_gdf = gpd.GeoDataFrame(link_data, crs="EPSG:4326")

    return node_gdf, link_gdf

def create_map_layers(node_gdf, link_gdf):
    """
    Create Pydeck layers for a quick interactive map.
    """
    node_df = node_gdf.copy()
    node_df["lon"] = node_df.geometry.x
    node_df["lat"] = node_df.geometry.y

    link_records = []
    for idx, row in link_gdf.iterrows():
        coords = list(row.geometry.coords)
        link_coords = [[float(x), float(y)] for (x, y) in coords]
        link_records.append({
            "link_id":   row["link_id"],
            "flow":      row["flow"],
            "velocity":  row["velocity"],
            "path":      link_coords
        })
    link_df = pd.DataFrame(link_records)

    node_layer = pdk.Layer(
        "ScatterplotLayer",
        data=node_df,
        get_position=["lon", "lat"],
        get_radius=50,
        get_fill_color=[0, 100, 255],
        pickable=True,
    )
    link_layer = pdk.Layer(
        "PathLayer",
        data=link_df,
        get_path="path",
        get_color=[200, 30, 0],
        width_scale=1,
        width_min_pixels=2,
        get_width=5,
        pickable=True,
    )
    return node_layer, link_layer

@st.cache_data
def load_user_data(file):
    """
    Load CSV or Excel into a pandas DataFrame.
    Adjust to your column naming conventions as needed.
    """
    file_name = file.name.lower()
    if file_name.endswith(".csv"):
        df = pd.read_csv(file)
    elif file_name.endswith(".xlsx"):
        df = pd.read_excel(file)
    else:
        df = pd.DataFrame()
    return df


############################################
# 2) STREAMLIT APP
############################################

def main():
    st.set_page_config(layout="wide")
    st.title("DMA Dashboard Using Shapefiles Instead of .inp")

    # 1. File Uploads in Sidebar
    with st.sidebar:
        st.header("Upload Shapefiles (Zipped)")
        node_zip = st.file_uploader("Node Shapefile (ZIPPED)", type=["zip"], key="node_zip")
        pipe_zip = st.file_uploader("Pipe Shapefile (ZIPPED)", type=["zip"], key="pipe_zip")

        st.markdown("---")
        st.header("Upload Supplemental Data (Optional)")
        leak_file = st.file_uploader("Historic Leaks CSV/XLSX", type=["csv","xlsx"], key="leaks")
        dma_file  = st.file_uploader("DMA/Asset Data CSV/XLSX", type=["csv","xlsx"], key="dma")
        flow_file = st.file_uploader("Measured Flows CSV/XLSX", type=["csv","xlsx"], key="flows")

    # 2. Check if user uploaded both node & pipe shapefile zips
    if not node_zip or not pipe_zip:
        st.info("Please upload both Node and Pipe shapefiles (as .zip).")
        return

    # 3. Extract shapefiles & build water network model
    with st.spinner("Building water network from GIS..."):
        node_shp = unzip_and_get_shp(node_zip)
        pipe_shp = unzip_and_get_shp(pipe_zip)
        if not node_shp or not pipe_shp:
            st.error("Could not find .shp inside the uploaded zip(s). Make sure they contain .shp, .dbf, etc.")
            return
        wn = build_model_from_gis(node_shp, pipe_shp)

    # 4. Run EPANET simulation
    with st.spinner("Running hydraulic simulation..."):
        results_dict = run_epanet_simulation(wn)

    # 5. Build geodataframes
    node_gdf, link_gdf = build_geodataframes(wn, results_dict)

    # 6. Supplemental data (leaks, dma, flows)
    df_leaks = load_user_data(leak_file) if leak_file else None
    df_dma   = load_user_data(dma_file)  if dma_file  else None
    df_flow  = load_user_data(flow_file) if flow_file else None

    # 7. Display some summary stats
    st.subheader("Simulation Summary")
    col1, col2, col3 = st.columns(3)
    avg_pressure = node_gdf["pressure"].mean()
    total_demand = node_gdf["demand"].sum()
    avg_flow     = link_gdf["flow"].mean()
    col1.metric("Avg Pressure (m)", f"{avg_pressure:.2f}")
    col2.metric("Total Demand (L/s)", f"{total_demand:.2f}")
    col3.metric("Avg Flow (L/s)", f"{avg_flow:.2f}")

    # 8. Display map
    node_layer, link_layer = create_map_layers(node_gdf, link_gdf)
    avg_lon = node_gdf.geometry.x.mean()
    avg_lat = node_gdf.geometry.y.mean()
    view_state = pdk.ViewState(latitude=avg_lat, longitude=avg_lon, zoom=13, pitch=0)
    deck_map = pdk.Deck(layers=[link_layer, node_layer], initial_view_state=view_state)
    st.pydeck_chart(deck_map, use_container_width=True)

    # 9. Show supplemental data
    if df_leaks is not None:
        st.subheader("Historic Leak Data")
        st.dataframe(df_leaks)
    if df_dma is not None:
        st.subheader("DMA / Asset Data")
        st.dataframe(df_dma)
    if df_flow is not None:
        st.subheader("Measured vs. Expected Flows")
        st.dataframe(df_flow)

    # 10. Node / Link Data
    with st.expander("Node Data"):
        st.dataframe(node_gdf.drop(columns="geometry"))
    with st.expander("Link Data"):
        st.dataframe(link_gdf.drop(columns="geometry"))


if __name__ == "__main__":
    main()
