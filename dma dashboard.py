import streamlit as st
import wntr
import pandas as pd
import os
import tempfile

###############################
# 1) HELPER FUNCTIONS
###############################

def save_uploaded_file(uploaded_file, directory):
    """
    Saves a Streamlit-uploaded file to `directory`,
    returns the full path to the saved file.
    """
    path = os.path.join(directory, uploaded_file.name)
    with open(path, "wb") as f:
        f.write(uploaded_file.read())
    return path

def build_wn_from_csv(node_csv_path, pipe_csv_path):
    """
    Build a WaterNetworkModel from two CSVs: one for nodes, one for pipes.
    
    We assume NodeData.csv has columns:
      - NodeID (str)
      - NodeType (str) -> e.g. "Meter", "Junction", "Tank", "Reservoir"
      - Elev (float) -> for normal junctions or the elevation of a tank
      - Demand (float) -> only relevant for "Junction"
      - BaseHead (float) -> used if NodeType is "Meter" or "Reservoir"
      - (optional) XCoord, YCoord for location

    PipeData.csv has columns:
      - PipeID (str)
      - StartID (str)
      - EndID (str)
      - Length (float)
      - Diameter (float)
      - Roughness (float)
    """
    df_nodes = pd.read_csv(node_csv_path)
    df_pipes = pd.read_csv(pipe_csv_path)

    wn = wntr.network.WaterNetworkModel()

    # Track if we found at least one reservoir or meter node
    found_reservoir = False

    # 1) Create nodes
    for idx, row in df_nodes.iterrows():
        node_id   = str(row["NodeID"])
        node_type = str(row.get("NodeType", "Junction")).lower()  # default "junction"
        elev      = row.get("Elev", 0.0)
        demand    = row.get("Demand", 0.0)

        if node_type == "meter" or node_type == "reservoir":
            # We'll treat the meter as a reservoir node in EPANET
            base_head = row.get("BaseHead", 50.0)  # default if none
            wn.add_reservoir(
                name=node_id,
                base_head=float(base_head)
            )
            found_reservoir = True

        elif node_type == "tank":
            # If you want tanks, you can parse other columns like init_level, min_level, etc.
            # For example:
            init_level = row.get("InitLevel", 5.0)
            min_level  = row.get("MinLevel", 0.0)
            max_level  = row.get("MaxLevel", 10.0)
            wn.add_tank(
                name=node_id,
                elevation=float(elev),
                init_level=float(init_level),
                min_level=float(min_level),
                max_level=float(max_level)
            )
            found_reservoir = True  # tank also counts as a boundary
        else:
            # Normal junction
            wn.add_junction(
                name=node_id,
                base_demand=float(demand),
                elevation=float(elev)
            )

        # Optionally store coordinates
        x_coord = row.get("XCoord", None)
        y_coord = row.get("YCoord", None)
        if pd.notnull(x_coord) and pd.notnull(y_coord):
            wn.get_node(node_id).coordinates = (float(x_coord), float(y_coord))

    # 2) Create pipes
    for idx, row in df_pipes.iterrows():
        pipe_id   = str(row["PipeID"])
        start_id  = str(row["StartID"])
        end_id    = str(row["EndID"])
        length    = row.get("Length", 0.0)
        diameter  = row.get("Diameter", 100.0)
        roughness = row.get("Roughness", 100.0)

        wn.add_pipe(
            name=pipe_id,
            start_node_name=start_id,
            end_node_name=end_id,
            length=float(length),
            diameter=float(diameter),
            roughness=float(roughness)
        )

    # If no reservoir or meter node was found, we can either
    # fail or add a dummy reservoir automatically. For now, let's add a dummy:
    if not found_reservoir:
        st.warning("No Meter or Reservoir node found in node CSV. Adding a dummy reservoir 'R0'.")
        wn.add_reservoir("R0", base_head=50.0)
        # connect it to the first node if there's at least one
        if len(wn.node_name_list) > 1:
            some_node = wn.node_name_list[1]
            wn.add_pipe("R0_pipe", "R0", some_node, length=10, diameter=100, roughness=100)

    return wn

###############################
# 2) STREAMLIT APP
###############################

def main():
    st.set_page_config(layout="wide")
    st.title("DMA Model with Main Meter as Reservoir")

    st.write("""
    ### Instructions:
    1. Upload **NodeData.csv** (must contain a row for your meter with `NodeType='Meter'` and `BaseHead` if known).
    2. Upload **PipeData.csv** referencing that meter NodeID in `StartID` or `EndID`.
    3. Click build to see results.
    If no `Meter` or `Reservoir` node is found, we'll add a dummy reservoir automatically.
    """)

    # File upload for node & pipe CSV
    node_csv = st.file_uploader("Upload Node CSV (required)", type=["csv"], key="node_csv")
    pipe_csv = st.file_uploader("Upload Pipe CSV (required)", type=["csv"], key="pipe_csv")

    if st.button("Build & Simulate"):
        if not node_csv or not pipe_csv:
            st.error("Please upload both Node CSV and Pipe CSV.")
            return

        temp_dir = tempfile.mkdtemp()
        node_path = save_uploaded_file(node_csv, temp_dir)
        pipe_path = save_uploaded_file(pipe_csv, temp_dir)

        with st.spinner("Building EPANET model..."):
            try:
                wn = build_wn_from_csv(node_path, pipe_path)
                st.success("Model built successfully!")
                st.write(f"Nodes: {len(wn.node_name_list)}, Links: {len(wn.link_name_list)}")

                # Run simulation
                st.write("Running EPANET simulation...")
                sim = wntr.sim.EpanetSimulator(wn)
                results = sim.run_sim()
                st.success("Simulation complete!")
            except Exception as e:
                st.error(f"Failed to build or simulate model: {e}")
    else:
        st.info("Upload Node & Pipe CSV, then click 'Build & Simulate'.")


if __name__ == "__main__":
    main()
