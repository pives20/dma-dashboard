import streamlit as st
import wntr
import geopandas as gpd
import pandas as pd
import pydeck as pdk
from shapely.geometry import Point, LineString
import os

############################################
# 1) HELPER FUNCTIONS & DATA MODELING
############################################

@st.cache_data
def load_epanet_model(inp_text: str):
    """Loads an EPANET model from raw text (the .inp file contents)."""
    temp_inp_path = "temp_network.inp"
    with open(temp_inp_path, "w") as f:
        f.write(inp_text)
    wn = wntr.network.WaterNetworkModel(temp_inp_path)
    if os.path.exists(temp_inp_path):
        os.remove(temp_inp_path)
    return wn

def run_simulation(wn: wntr.network.WaterNetworkModel):
    """
    Run a hydraulic simulation on the given WaterNetworkModel,
    returning final time-step results as dictionaries.
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
    Convert the WNTR model + results into GeoDataFrames (nodes, links).
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
    Create Pydeck layers for interactive mapping.
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

############################################
# 2) STREAMLIT APP
############################################

def main():
    st.set_page_config(layout="wide")
    st.title("DMA Dashboard (EPANET + Historic Leak Data + Assets)")

    with st.sidebar:
        st.header("Upload EPANET .inp File")
        epanet_file = st.file_uploader("EPANET .inp", type=["inp"])

        st.header("Upload DMA / Asset Data")
        st.markdown("**Historic Leak Data:** (optional)")
        leak_file = st.file_uploader("CSV/Excel with historic leaks", type=["csv", "xlsx"], key="leaks")

        st.markdown("**DMA Details / Assets:** (optional)")
        dma_file = st.file_uploader("CSV/Excel with DMA assets/pipes", type=["csv", "xlsx"], key="dma")

        st.markdown("**Measured vs. Expected Flows:** (optional)")
        flow_file = st.file_uploader("CSV/Excel with measured flows", type=["csv", "xlsx"], key="flows")

    if not epanet_file:
        st.info("Please upload an EPANET .inp file.")
        return

    # 1) Load the EPANET model
    with st.spinner("Loading EPANET model..."):
        inp_text = epanet_file.read().decode("utf-8")
        wn = load_epanet_model(inp_text)

    # 2) Run the simulation
    with st.spinner("Running simulation..."):
        results_dict = run_simulation(wn)

    # 3) Build geodataframes for nodes & links
    node_gdf, link_gdf = build_geodataframes(wn, results_dict)

    # 4) Additional Data: Historic Leaks, DMA/Asset, Flow Comparisons
    #    We'll store them in session_state or local variables just to show in the dashboard
    if leak_file:
        with st.spinner("Loading historic leak data..."):
            df_leaks = load_user_data(leak_file)
    else:
        df_leaks = None

    if dma_file:
        with st.spinner("Loading DMA asset data..."):
            df_dma = load_user_data(dma_file)
    else:
        df_dma = None

    if flow_file:
        with st.spinner("Loading measured flow data..."):
            df_flow = load_user_data(flow_file)
    else:
        df_flow = None

    # 5) Display Key Results / Summaries
    st.subheader("Simulation Summary")
    col1, col2, col3 = st.columns(3)
    avg_pressure = node_gdf["pressure"].mean()
    total_demand = node_gdf["demand"].sum()
    avg_flow     = link_gdf["flow"].mean()
    col1.metric("Avg Pressure (m)", f"{avg_pressure:.2f}")
    col2.metric("Total Demand (L/s)", f"{total_demand:.2f}")
    col3.metric("Avg Flow (L/s)", f"{avg_flow:.2f}")

    # 6) Visualize the network with Pydeck
    node_layer, link_layer = create_map_layers(node_gdf, link_gdf)
    avg_lon = node_gdf.geometry.x.mean()
    avg_lat = node_gdf.geometry.y.mean()
    view_state = pdk.ViewState(latitude=avg_lat, longitude=avg_lon, zoom=13, pitch=0)
    deck_map = pdk.Deck(layers=[link_layer, node_layer], initial_view_state=view_state)
    st.pydeck_chart(deck_map, use_container_width=True)

    # 7) Display user data (Historic leaks, DMA assets, etc.)
    if df_leaks is not None:
        st.subheader("Historic Leak Data")
        st.dataframe(df_leaks)

    if df_dma is not None:
        st.subheader("DMA Asset Details")
        st.dataframe(df_dma)

    if df_flow is not None:
        st.subheader("Measured vs. Expected Flow Data")
        st.dataframe(df_flow)
        # Potentially compare df_flow with your node/link_gdf to highlight mismatches

    # 8) Show raw node/link data
    with st.expander("Node Data"):
        st.dataframe(node_gdf.drop(columns="geometry"))
    with st.expander("Link Data"):
        st.dataframe(link_gdf.drop(columns="geometry"))


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


if __name__ == "__main__":
    main()
