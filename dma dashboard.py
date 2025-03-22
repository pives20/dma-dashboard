import streamlit as st
import wntr
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString
import pydeck as pdk
import os

#######################################
# 1. Load the Network & Utility Funcs #
#######################################

@st.cache_data
def load_network_model(inp_text: str):
    """
    Load the EPANET model from the raw `.inp` text (once),
    return a WaterNetworkModel object.
    """
    temp_inp_path = "temp_network.inp"
    with open(temp_inp_path, "w") as f:
        f.write(inp_text)

    wn = wntr.network.WaterNetworkModel(temp_inp_path)
    if os.path.exists(temp_inp_path):
        os.remove(temp_inp_path)
    return wn

def close_valves_and_run_sim(wn_original, valves_to_close):
    """
    1) Copy the original network.
    2) Close the selected valves (or pipes if you prefer).
    3) Run a hydraulic simulation.
    4) Return a dictionary of final pressures, demands, etc.
    """
    # 1. Copy the model so we don't overwrite the original
    wn_copy = wn_original.clone()

    # 2. Close selected valves
    # In EPANET/wntr, a valve is also a 'Link' object. Setting status to 'Closed' isolates it.
    for v_name in valves_to_close:
        if v_name in wn_copy.links:
            link_obj = wn_copy.get_link(v_name)
            # EPANET link status options: OPEN, CLOSED, CV (check valve), etc.
            link_obj.status = wntr.network.LinkStatus.Closed

    # 3. Run simulation
    sim = wntr.sim.EpanetSimulator(wn_copy)
    results = sim.run_sim()

    # 4. Extract final time-step results
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


def build_geodataframes(wn, results_dict, pressure_threshold=1.0):
    """
    Create GeoDataFrames for nodes and links based on final simulation results.
    Mark nodes as 'is_disconnected' if their pressure < pressure_threshold.
    """
    node_data = []
    for node_name, node_obj in wn.nodes():
        x, y = node_obj.coordinates
        pressure = results_dict["pressures"].get(node_name, 0.0)
        demand   = results_dict["demands"].get(node_name, 0.0)
        
        # Mark disconnected if pressure is below threshold
        is_disc = (pressure < pressure_threshold)

        # If you track how many properties each node represents, 
        # you could store that in the .inp or add it as a custom attribute
        # For now, let's just store demand as a proxy
        node_data.append({
            "node_id": node_name,
            "geometry": Point(x, y),
            "pressure": pressure,
            "demand":   demand,
            "is_disconnected": is_disc
        })
    node_gdf = gpd.GeoDataFrame(node_data, crs="EPSG:4326")

    link_data = []
    for link_name, link_obj in wn.links():
        start_node = wn.get_node(link_obj.start_node_name)
        end_node   = wn.get_node(link_obj.end_node_name)
        x1, y1 = start_node.coordinates
        x2, y2 = end_node.coordinates

        flow = results_dict["flows"].get(link_name, 0.0)
        vel  = results_dict["velocity"].get(link_name, 0.0)
        
        link_data.append({
            "link_id": link_name,
            "geometry": LineString([(x1, y1), (x2, y2)]),
            "flow": flow,
            "velocity": vel,
            "status": str(link_obj.status)  # 'Open' or 'Closed'
        })
    link_gdf = gpd.GeoDataFrame(link_data, crs="EPSG:4326")

    return node_gdf, link_gdf


def create_pydeck_layers(node_gdf, link_gdf):
    """
    Generate Pydeck layers for nodes & links, coloring disconnected nodes in red.
    """
    node_df = node_gdf.copy()
    node_df["lon"] = node_df.geometry.x
    node_df["lat"] = node_df.geometry.y

    # Color nodes: if disconnected -> red, else scaled by pressure
    def node_color(row):
        if row["is_disconnected"]:
            return [255, 0, 0]  # Red
        else:
            # e.g. greenish color based on pressure
            # scale pressure 0-10 -> 0-255, just as example
            press = row["pressure"]
            max_press = 50.0
            scaled = min(press / max_press, 1.0)
            return [0, int(255 * scaled), 50]

    node_df["color"] = node_df.apply(node_color, axis=1)

    # Convert link geometry to path
    link_records = []
    for idx, row in link_gdf.iterrows():
        coords = list(row.geometry.coords)
        link_coords = [[float(x), float(y)] for (x, y) in coords]
        link_records.append({
            "link_id": row["link_id"],
            "status": row["status"],
            "flow": row["flow"],
            "velocity": row["velocity"],
            "path": link_coords
        })
    link_df = pd.DataFrame(link_records)

    # Color links: closed -> gray, open -> blue
    def link_color(row):
        if row["status"] == "LinkStatus.Closed":
            return [100, 100, 100]
        else:
            return [0, 100, 255]

    link_df["color"] = link_df.apply(link_color, axis=1)

    node_layer = pdk.Layer(
        "ScatterplotLayer",
        data=node_df,
        pickable=True,
        get_position=["lon", "lat"],
        get_radius=40,
        get_fill_color="color",
        tooltip=True,
    )

    link_layer = pdk.Layer(
        "PathLayer",
        data=link_df,
        pickable=True,
        get_path="path",
        get_color="color",
        width_scale=2,
        width_min_pixels=2,
        get_width=5,
        tooltip=True,
    )

    return node_layer, link_layer


########################
# 2. Streamlit UI App  #
########################

def main():
    st.set_page_config(layout="wide")
    st.title("Valve Closure & Disconnected Properties Demo")

    with st.sidebar:
        st.header("1) Upload EPANET .inp")
        uploaded_file = st.file_uploader("Upload .inp", type=["inp"])
        st.write("---")

    if not uploaded_file:
        st.info("Upload an EPANET file to begin.")
        return

    # Load the network once
    inp_text = uploaded_file.read().decode("utf-8")
    wn_original = load_network_model(inp_text)
    
    # Identify valves/links in the network 
    # (some models might label 'VALVE' vs 'PIPE'. In EPANET, valves are special link types.)
    valve_names = []
    for link_name, link in wn_original.links():
        if link.link_type in ['PRV','PSV','PBV','FCV','TCV','GPV']:  
            valve_names.append(link_name)
        # Or if you want to treat certain pipes as valves, or do user-defined categories

    with st.sidebar:
        st.header("2) Select valves to close")
        # If no official valves in the model, show all links
        if not valve_names:
            st.warning("No official valves found. Showing all links instead.")
            valve_names = list(wn_original.links.keys())
        valves_to_close = st.multiselect("Close these valves:", valve_names, default=[])

        st.write("---")
        st.header("3) Pressure threshold for 'disconnected'")
        threshold = st.slider("Min Pressure to be considered 'served' (m)", 0.1, 5.0, 1.0, 0.1)

    # Now we run the simulation with chosen valves closed
    results_dict = close_valves_and_run_sim(wn_original, valves_to_close)

    # Build GDFs
    node_gdf, link_gdf = build_geodataframes(wn_original, results_dict, pressure_threshold=threshold)

    # Count how many are disconnected
    disconnected_nodes = node_gdf[node_gdf["is_disconnected"]]
    num_disconnected = len(disconnected_nodes)
    total_nodes = len(node_gdf)

    # Sum up demands in disconnected nodes as a measure of how many "properties" are cut off
    # If you have a custom attribute, you'd sum that instead
    total_demand_disc = disconnected_nodes["demand"].sum()
    total_demand_all = node_gdf["demand"].sum()

    # Metrics up top
    col1, col2, col3 = st.columns(3)
    col1.metric("Disconnected Nodes", f"{num_disconnected}/{total_nodes}")
    col2.metric("Disconnected Demand (L/s)", f"{total_demand_disc:.2f}")
    col3.metric("Valves Closed", f"{len(valves_to_close)}")

    st.write("Selected valves closed:", valves_to_close if valves_to_close else "None")

    # 3. Show the map
    node_layer, link_layer = create_pydeck_layers(node_gdf, link_gdf)
    
    avg_lon = node_gdf.geometry.x.mean()
    avg_lat = node_gdf.geometry.y.mean()
    view_state = pdk.ViewState(
        latitude=avg_lat,
        longitude=avg_lon,
        zoom=13,
        pitch=0
    )

    deck_map = pdk.Deck(
        layers=[link_layer, node_layer],
        initial_view_state=view_state,
        tooltip={"html": "<b>{node_id}</b> | Pressure: {pressure}", "style": {"color": "white"}},
    )

    st.pydeck_chart(deck_map, use_container_width=True)

    # 4. Show data tables
    with st.expander("Node Table"):
        st.write(node_gdf.drop(columns="geometry"))
    with st.expander("Link Table"):
        st.write(link_gdf.drop(columns="geometry"))


if __name__ == "__main__":
    main()
