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
    file_path = os.path.join(directory, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())
    return file_path

def build_wn_from_csv(node_csv_path, pipe_csv_path):
    """
    Build a WaterNetworkModel from two CSVs: one for nodes, one for pipes.
    
    Required columns (by default):
      - Node CSV: [NodeID, Elev, Demand, (optional XCoord, YCoord)]
      - Pipe CSV: [PipeID, StartID, EndID, (optional Length, Diameter, Roughness)]
    
    If your CSV column names differ, update them here or rename your CSV columns.
    """
    df_nodes = pd.read_csv(node_csv_path)
    df_pipes = pd.read_csv(pipe_csv_path)

    wn = wntr.network.WaterNetworkModel()

    # 1) Create nodes (junctions)
    for idx, row in df_nodes.iterrows():
        # Must have "NodeID" in your CSV
        node_id = str(row["NodeID"])  
        elev    = row.get("Elev", 0.0)
        demand  = row.get("Demand", 0.0)

        # Add the junction
        wn.add_junction(name=node_id, base_demand=demand, elevation=elev)

        # If we have coordinates, store them in wntr
        x_coord = row.get("XCoord", None)
        y_coord = row.get("YCoord", None)
        if x_coord is not None and y_coord is not None:
            wn.get_node(node_id).coordinates = (float(x_coord), float(y_coord))

    # 2) Create pipes
    for idx, row in df_pipes.iterrows():
        # Must have "PipeID", "StartID", "EndID"
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
            length=length,
            diameter=diameter,
            roughness=roughness
        )

    return wn

def load_leak_data(file):
    """Load a CSV or Excel with historic leaks data."""
    if not file:
        return None
    lower_name = file.name.lower()
    if lower_name.endswith(".csv"):
        return pd.read_csv(file)
    elif lower_name.endswith(".xlsx"):
        return pd.read_excel(file)
    else:
        return None

###############################
# 2) STREAMLIT APP
###############################

def main():
    st.set_page_config(layout="wide")
    st.title("DMA Dashboard – Build Model from CSV + Historic Leaks in Sidebar")

    # --------- SIDEBAR FOR HISTORIC LEAKS ---------
    st.sidebar.header("Optional: Historic Leaks")
    leak_file = st.sidebar.file_uploader("Upload CSV/XLSX with leak records", type=["csv","xlsx"])

    st.write("## Upload Node & Pipe CSV to Build the Model")
    st.markdown("""
    **Requirements**:
    - **Node CSV** must have columns: `NodeID`, `Elev`, `Demand` (plus optional `XCoord`, `YCoord`).  
    - **Pipe CSV** must have columns: `PipeID`, `StartID`, `EndID` (plus optional `Length`, `Diameter`, `Roughness`).  
    """)

    uploaded_files = st.file_uploader(
        "Select your CSV files for nodes & pipes (you can upload them together or one at a time).",
        accept_multiple_files=True,
        type=["csv"]
    )

    temp_dir = tempfile.mkdtemp()

    # We'll keep track of whether we found node_csv and pipe_csv
    node_csv_path = None
    pipe_csv_path = None

    if uploaded_files:
        # Save them locally
        for uf in uploaded_files:
            saved_path = save_uploaded_file(uf, temp_dir)
            # We'll do naive name detection: "node" in the filename => node CSV, "pipe" => pipe CSV
            fname_lower = uf.name.lower()
            if "node" in fname_lower:
                node_csv_path = saved_path
            elif "pipe" in fname_lower:
                pipe_csv_path = saved_path

        # If we have both, build the WN
        if node_csv_path and pipe_csv_path:
            st.success(f"Found node CSV: {os.path.basename(node_csv_path)} and pipe CSV: {os.path.basename(pipe_csv_path)}")
            with st.spinner("Building the water network model from CSV..."):
                try:
                    wn = build_wn_from_csv(node_csv_path, pipe_csv_path)
                    st.success("Model built successfully!")
                    st.write(f"Junctions: {len(wn.junction_name_list)}, Pipes: {len(wn.pipe_name_list)}")

                    # Optionally run the simulation
                    with st.spinner("Running EPANET simulation..."):
                        sim = wntr.sim.EpanetSimulator(wn)
                        results = sim.run_sim()
                    st.success("Simulation complete!")

                except KeyError as e:
                    st.error(f"Missing required column: {e}")
                except Exception as e:
                    st.error(f"Failed to build or simulate the model: {e}")
        else:
            # Not enough info to build a model, so let's just display them
            st.warning("We didn't detect both node & pipe CSVs. Displaying the uploaded files below:")
            for uf in uploaded_files:
                file_path = os.path.join(temp_dir, uf.name)
                df = pd.read_csv(file_path)
                st.write(f"**{uf.name}**:")
                st.dataframe(df.head())

    else:
        st.info("No CSV uploaded yet.")

    # --------- SHOW LEAK DATA ---------
    st.write("## Historic Leaks (Optional)")
    if leak_file:
        df_leaks = load_leak_data(leak_file)
        if df_leaks is not None:
            st.write("### Historic Leak Records")
            st.dataframe(df_leaks)
        else:
            st.error("Invalid leak file format (must be CSV or XLSX).")
    else:
        st.info("No leak data uploaded.")

if __name__ == "__main__":
    main()
