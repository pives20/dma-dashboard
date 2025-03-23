import streamlit as st
import wntr
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString
import os
import zipfile
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

def unzip_file(zip_path, extract_dir):
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)

def read_epanet_inp(inp_path):
    """Load an EPANET .inp using WNTR, return a WaterNetworkModel."""
    return wntr.network.WaterNetworkModel(inp_path)

def load_csv(filepath):
    """Load a CSV into a pandas DataFrame."""
    return pd.read_csv(filepath)

def build_wn_from_csv(node_csv_path, pipe_csv_path):
    """
    Example: create a WaterNetworkModel from two CSV files:
      - node_csv with columns [NodeID, Elev, Demand, XCoord, YCoord]
      - pipe_csv with columns [PipeID, StartID, EndID, Length, Diameter, etc.]
    Adjust column names to match your data.
    """
    df_nodes = pd.read_csv(node_csv_path)
    df_pipes = pd.read_csv(pipe_csv_path)

    wn = wntr.network.WaterNetworkModel()

    # 1) Create nodes
    for idx, row in df_nodes.iterrows():
        node_id = str(row["NodeID"])
        elev    = row.get("Elev", 0.0)
        demand  = row.get("Demand", 0.0)
        wn.add_junction(node_id, base_demand=demand, elevation=elev)
        # Optional: store coords in WNTR for reference
        x_coord = row.get("XCoord", None)
        y_coord = row.get("YCoord", None)
        if x_coord is not None and y_coord is not None:
            wn.get_node(node_id).coordinates = (float(x_coord), float(y_coord))

    # 2) Create pipes
    for idx, row in df_pipes.iterrows():
        pipe_id   = str(row["PipeID"])
        start_id  = str(row["StartID"])
        end_id    = str(row["EndID"])
        length    = row.get("Length", 0.0)
        diameter  = row.get("Diameter", 100.0)
        roughness = row.get("Roughness", 100.0)
        # If length not provided, there's no geometry to compute from CSV. 
        # So we rely on the CSV's "Length" column if you have it.
        wn.add_pipe(
            name=pipe_id,
            start_node_name=start_id,
            end_node_name=end_id,
            length=length,
            diameter=diameter,
            roughness=roughness
        )
    return wn

def read_shapefile_parts(files, base_name, temp_dir):
    """
    If user uploads separate SHP, DBF, SHX, etc., store them under one base_name 
    so we can read them as a single shapefile with GeoPandas.
    Returns the path to the .shp file.
    """
    shp_path = None
    for f in files:
        ext = f.name.split(".")[-1].lower()
        outpath = os.path.join(temp_dir, f"{base_name}.{ext}")
        with open(outpath, "wb") as out:
            out.write(f.read())
        if ext == "shp":
            shp_path = outpath
    return shp_path

def build_wn_from_shapefiles(node_gdf, pipe_gdf):
    """
    Create a WaterNetworkModel from two GeoDataFrames:
      - node_gdf (with NodeID, Elev, Demand, geometry(Point))
      - pipe_gdf (with PipeID, StartID, EndID, Diameter, geometry(LineString))
    Adjust for your real columns as needed.
    """
    wn = wntr.network.WaterNetworkModel()
    # Nodes
    for idx, row in node_gdf.iterrows():
        node_id = str(row["NodeID"])
        elev    = row.get("Elev", 0.0)
        demand  = row.get("Demand", 0.0)
        wn.add_junction(node_id, base_demand=demand, elevation=elev)
        x, y = row.geometry.x, row.geometry.y
        wn.get_node(node_id).coordinates = (float(x), float(y))

    # Pipes
    for idx, row in pipe_gdf.iterrows():
        pipe_id   = str(row["PipeID"])
        start_id  = str(row["StartID"])
        end_id    = str(row["EndID"])
        diameter  = row.get("Diameter", 100.0)
        roughness = row.get("Roughness", 100.0)
        length    = row.get("Length", 0.0)
        if length <= 0:
            length = row.geometry.length
        wn.add_pipe(
            name=pipe_id,
            start_node_name=start_id,
            end_node_name=end_id,
            length=length,
            diameter=diameter,
            roughness=roughness
        )
    return wn


#################################
# 2) STREAMLIT APP
#################################

def main():
    st.set_page_config(layout="wide")
    st.title("DMA Dashboard: CSV, Shapefile, or EPANET for Building Models")

    st.write("""
    **Upload your water network** in **any** of the following formats:
    - **EPANET .inp** (single file)
    - **Shapefile** (.shp + .dbf + .shx, optionally .prj) 
      - either 1 shapefile or 2 shapefiles (nodes + pipes)
    - **CSV** 
      - either 2 CSVs: one for nodes, one for pipes (to build a model),
      - or single CSV just for display.
    - **ZIP** containing .inp or .shp
    """)

    uploaded_files = st.file_uploader(
        "Upload your files here:",
        accept_multiple_files=True,
        type=["inp","shp","dbf","shx","prj","csv","zip","geojson","txt"]
    )

    if not uploaded_files:
        st.info("Please upload at least one file.")
        return

    # Create a temp directory
    temp_dir = tempfile.mkdtemp()

    # Group files by extension
    ext_map = {}
    for uf in uploaded_files:
        ext = uf.name.split(".")[-1].lower()
        ext_map.setdefault(ext, []).append(uf)

    wn = None  # WaterNetworkModel if we can build it
    # We'll handle the same logic as before but add a new CSV scenario

    # 1) Single EPANET .inp
    if len(uploaded_files) == 1 and "inp" in ext_map:
        st.write("Detected single EPANET .inp file.")
        inp_path = save_uploaded_file(uploaded_files[0], temp_dir)
        wn = read_epanet_inp(inp_path)

    # 2) CSV-based scenario
    elif "csv" in ext_map:
        # Possibly we have multiple CSV files. We'll see if we can find a node CSV and pipe CSV
        st.write("Detected CSV file(s). Attempting to see if we have Node & Pipe CSV to build a model.")
        # Let’s define a naive approach: 
        #   - We look for exactly 2 CSVs named something containing 'node' and 'pipe' (case-insensitive).
        csv_files = ext_map["csv"]
        node_csv_path = None
        pipe_csv_path = None

        # Save all CSVs to disk
        saved_paths = []
        for f in csv_files:
            fpath = save_uploaded_file(f, temp_dir)
            saved_paths.append(fpath)

        # Attempt to find a "node" CSV and "pipe" CSV by name or partial match
        for p in saved_paths:
            fname_lower = os.path.basename(p).lower()
            if "node" in fname_lower:
                node_csv_path = p
            elif "pipe" in fname_lower:
                pipe_csv_path = p

        if node_csv_path and pipe_csv_path:
            st.write(f"Found a node CSV: {os.path.basename(node_csv_path)}")
            st.write(f"Found a pipe CSV: {os.path.basename(pipe_csv_path)}")
            with st.spinner("Building WNTR model from CSV..."):
                try:
                    wn = build_wn_from_csv(node_csv_path, pipe_csv_path)
                    st.success("Model built successfully from CSV!")
                except Exception as e:
                    st.error(f"Failed to build model from CSV: {e}")
        else:
            # If we don't have a matching pair, we just display them
            st.info("Could not find matching node & pipe CSV files. Displaying them instead.")
            for p in saved_paths:
                df = pd.read_csv(p)
                st.write(f"**{os.path.basename(p)}** (no model built):")
                st.dataframe(df.head())

    # 3) ZIP file
    elif len(uploaded_files) == 1 and "zip" in ext_map:
        zip_file = uploaded_files[0]
        zip_path = save_uploaded_file(zip_file, temp_dir)
        st.write("Detected a ZIP file. Checking contents for .inp or .shp.")
        unzip_file(zip_path, temp_dir)
        found_inp, found_shp = None, None
        for root, dirs, files in os.walk(temp_dir):
            for f in files:
                if f.lower().endswith(".inp"):
                    found_inp = os.path.join(root, f)
                elif f.lower().endswith(".shp"):
                    found_shp = os.path.join(root, f)
        if found_inp:
            st.write("Found .inp inside ZIP, loading EPANET model.")
            wn = read_epanet_inp(found_inp)
        elif found_shp:
            st.write("Found a shapefile in the ZIP. This example won't fully parse 2 shapefiles automatically. We'll just load the first.")
            gdf = gpd.read_file(found_shp)
            st.write("Shapefile read, displaying head:")
            st.dataframe(gdf.head())
            st.info("For a complete model, you'd typically need separate node & pipe shapefiles or a single .inp.")
        else:
            st.warning("No .inp or .shp found in ZIP. Possibly other data, but we can't build a model.")

    # 4) Shapefile scenario
    elif "shp" in ext_map and "dbf" in ext_map and "shx" in ext_map:
        st.write("Detected Shapefile parts.")
        # Could be 1 or 2 shapefiles. 
        # If 2, we attempt node vs. pipe logic. Otherwise we just display one layer.
        shp_files = ext_map["shp"]
        if len(shp_files) == 1:
            st.write("Single shapefile scenario, reading it as one layer.")
            all_parts = shp_files + ext_map["dbf"] + ext_map["shx"]
            if "prj" in ext_map:
                all_parts += ext_map["prj"]
            shp_path = read_shapefile_parts(all_parts, "layer", temp_dir)
            gdf = gpd.read_file(shp_path)
            st.write("Shapefile loaded, here's the head:")
            st.dataframe(gdf.head())
            st.info("For a full WNTR model, we might need separate Node & Pipe shapefiles or a known schema.")
        elif len(shp_files) == 2:
            st.write("Two shapefiles found, attempting Node & Pipe approach.")
            # This is a simplistic approach, not fully robust. 
            # We'll guess the first is node, second is pipe, or look for 'node'/'pipe' in the filename.
            # Then read them both, call build_wn_from_shapefiles(node_gdf, pipe_gdf).
            # (Omitted here for brevity - same logic as earlier examples.)
            st.warning("Implement your two-shapefile logic here if needed.")
        else:
            st.warning("More than 2 shapefiles found. This example code won't parse them automatically.")
    # 5) If none of the above match
    else:
        st.warning("Unrecognized combination of files. Displaying them if CSV/TXT, or ignoring if unknown.")
        for f in uploaded_files:
            path = save_uploaded_file(f, temp_dir)
            if path.lower().endswith((".csv",".txt")):
                df = pd.read_csv(path) if path.endswith(".csv") else pd.read_table(path)
                st.write(f"**{os.path.basename(path)}**:")
                st.dataframe(df.head())

    # If we have a WN, let's attempt a simulation
    if wn:
        st.success("WaterNetworkModel is ready!")
        st.write(f"Junctions: {len(wn.junction_name_list)}, Pipes: {len(wn.pipe_name_list)}")

        with st.spinner("Running EPANET simulation..."):
            try:
                sim = wntr.sim.EpanetSimulator(wn)
                results = sim.run_sim()
                st.success("Simulation complete!")
                st.write("Now you can process results or visualize pressures/flows.")
            except Exception as e:
                st.error(f"Simulation error: {e}")

if __name__ == "__main__":
    main()
