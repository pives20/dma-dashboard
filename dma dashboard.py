import streamlit as st
import wntr
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString
import os
import zipfile
import tempfile

#####################################
# 1. UTILITY & HELPER FUNCTIONS
#####################################

def save_uploaded_file(uploaded_file, directory):
    """
    Saves a Streamlit-uploaded file to the given `directory`,
    returns the full path to the saved file.
    """
    path = os.path.join(directory, uploaded_file.name)
    with open(path, "wb") as f:
        f.write(uploaded_file.read())
    return path

def unzip_file(zip_path, extract_dir):
    """Unzip the file at zip_path into extract_dir."""
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)

def read_epanet_inp(inp_path):
    """Load an EPANET .inp using WNTR, return a WaterNetworkModel."""
    wn = wntr.network.WaterNetworkModel(inp_path)
    return wn

def load_csv_or_excel(file):
    """Load a CSV or Excel file into a pandas DataFrame."""
    if not file:
        return None
    name_lower = file.name.lower()
    if name_lower.endswith(".csv"):
        return pd.read_csv(file)
    elif name_lower.endswith(".xlsx"):
        return pd.read_excel(file)
    return None

def read_shapefile_parts(files, base_name, temp_dir):
    """
    If user uploads separate SHP, DBF, SHX, PRJ, store them under one base name
    so GeoPandas can read them as a single shapefile.
    Returns the path to the .shp file.
    """
    shp_path = None
    for f in files:
        ext = f.name.split(".")[-1].lower()  # shp, dbf, shx, prj
        outpath = os.path.join(temp_dir, f"{base_name}.{ext}")
        with open(outpath, "wb") as out:
            out.write(f.read())
        if ext == "shp":
            shp_path = outpath
    return shp_path

#####################################
# 2. BUILDING A WNTR MODEL FROM GIS
#####################################

def build_wn_from_shapefiles(node_gdf, pipe_gdf):
    """
    Example: create a WaterNetworkModel from two GeoDataFrames:
      - node_gdf with columns [NodeID, Elev, Demand, geometry(Point)]
      - pipe_gdf with columns [PipeID, StartID, EndID, Diameter, geometry(LineString)]
    Adjust to match your real data schema.
    """
    wn = wntr.network.WaterNetworkModel()

    # Add nodes
    for idx, row in node_gdf.iterrows():
        node_id = str(row["NodeID"])
        elev = row.get("Elev", 0.0)
        demand = row.get("Demand", 0.0)
        wn.add_junction(node_id, base_demand=demand, elevation=elev)

        # Store coordinates in WNTR (for reference)
        x, y = row.geometry.x, row.geometry.y
        wn.get_node(node_id).coordinates = (float(x), float(y))

    # Add pipes
    for idx, row in pipe_gdf.iterrows():
        pipe_id   = str(row["PipeID"])
        start_id  = str(row["StartID"])
        end_id    = str(row["EndID"])
        diameter  = row.get("Diameter", 100.0)
        roughness = row.get("Roughness", 100.0)
        length    = row.get("Length", 0.0)

        # If length missing, compute from geometry
        if length <= 0:
            length = row.geometry.length

        wn.add_pipe(
            name=pipe_id,
            start_node_name=start_id,
            end_node_name=end_id,
            length=length,
            diameter=diameter,
            roughness=roughness,
            status='OPEN'
        )

    return wn

#####################################
# 3. STREAMLIT APP
#####################################

def main():
    st.set_page_config(layout="wide")
    st.title("DMA Dashboard – Unified Network Upload & Optional Data")

    # ------ SIDEBAR for optional files ------
    st.sidebar.header("Optional: Historic Leaks & Flow Data")
    leak_file = st.sidebar.file_uploader("Historic Leaks (CSV/XLSX)", type=["csv","xlsx"])
    flow_file = st.sidebar.file_uploader("Measured Flows (CSV/XLSX)", type=["csv","xlsx"])
    # You could also add "Asset Data", "DMA Polygons", etc.

    # ------ MAIN AREA: Upload your network (one tile) ------
    st.subheader("Upload Your Network")
    st.markdown("""
    **Supported files**:  
    - **EPANET .INP**  
    - **Shapefile** (.shp, .dbf, .shx, [optionally .prj])  
    - **GeoJSON**  
    - **CSV**, **TXT** (e.g., node/pipe data, not fully implemented)  
    - **ZIP** (containing shapefiles or .inp)  
    """)

    uploaded_files = st.file_uploader(
        "Drop or select your file(s)",
        accept_multiple_files=True,
        type=["inp","shp","dbf","shx","prj","geojson","csv","txt","zip"]
    )

    # Show optional data even if no network is uploaded
    show_optional_data(leak_file, flow_file)

    if not uploaded_files:
        st.info("Please upload at least one file for the network.")
        return

    temp_dir = tempfile.mkdtemp()
    ext_map = {}
    for uf in uploaded_files:
        ext = uf.name.split(".")[-1].lower()
        ext_map.setdefault(ext, []).append(uf)

    # We'll attempt to parse the network
    wn = None  # WaterNetworkModel
    node_gdf, pipe_gdf = None, None

    # 1) Single .INP
    if len(uploaded_files) == 1 and "inp" in ext_map:
        st.write("Detected EPANET .inp file.")
        inp_path = save_uploaded_file(uploaded_files[0], temp_dir)
        wn = read_epanet_inp(inp_path)

    # 2) Single .geojson
    elif len(uploaded_files) == 1 and "geojson" in ext_map:
        st.write("Detected GeoJSON.")
        geojson_path = save_uploaded_file(uploaded_files[0], temp_dir)
        gdf = gpd.read_file(geojson_path)
        st.write("Loaded GeoDataFrame with", len(gdf), "features.")
        st.dataframe(gdf.head())
        st.info("To build a WNTR model from GeoJSON, you'd typically need separate node & pipe layers or a known schema. Not auto-building here.")

    # 3) ZIP file
    elif len(uploaded_files) == 1 and "zip" in ext_map:
        st.write("Detected a ZIP file. Looking for .inp or .shp inside...")
        zip_path = save_uploaded_file(uploaded_files[0], temp_dir)
        unzip_file(zip_path, temp_dir)

        # scan unzipped for .inp or .shp
        found_inp, found_shp = None, []
        for root, dirs, files in os.walk(temp_dir):
            for f in files:
                if f.lower().endswith(".inp"):
                    found_inp = os.path.join(root, f)
                elif f.lower().endswith(".shp"):
                    found_shp.append(os.path.join(root, f))

        if found_inp:
            st.write("Found an .inp in the ZIP, loading EPANET model.")
            wn = read_epanet_inp(found_inp)
        elif found_shp:
            st.write("Found shapefile(s) in the ZIP. This code doesn't fully auto-detect nodes vs. pipes if there's more than one. We'll just show the first .shp.")
            first_shp = found_shp[0]
            gdf = gpd.read_file(first_shp)
            st.write("Loaded shapefile with", len(gdf), "features.")
            st.dataframe(gdf.head())
        else:
            st.warning("No .inp or .shp found in the ZIP. Possibly other data inside.")
    
    # 4) Shapefile parts (SHP, DBF, SHX, optional PRJ)
    elif "shp" in ext_map and "dbf" in ext_map and "shx" in ext_map:
        # If there's more than one .shp, we might guess one is nodes, one is pipes
        # For demo, let's handle up to 2 shapefiles: node layer + pipe layer
        st.write("Detected Shapefile components.")
        shp_files = ext_map["shp"]
        
        if len(shp_files) == 1:
            # Single shapefile scenario
            st.write("Single shapefile found. Reading as a single layer...")
            # Combine .shp, .dbf, .shx, prj for this layer
            all_parts = shp_files + ext_map["dbf"] + ext_map["shx"]
            if "prj" in ext_map:
                all_parts += ext_map["prj"]

            shp_path = read_shapefile_parts(all_parts, base_name="layer", temp_dir=temp_dir)
            gdf = gpd.read_file(shp_path)
            st.write("Loaded shapefile with", len(gdf), "features.")
            st.dataframe(gdf.head())
            st.info("For a full WN, you might need a second shapefile or a column distinguishing nodes vs. pipes.")
        elif len(shp_files) == 2:
            st.write("Two shapefiles found. Attempting to treat them as 'nodes' & 'pipes'.")
            # We'll guess the first .shp is nodes, second is pipes (or vice versa),
            # or look at the filename to see if it contains "node"/"pipe".
            # Simplified logic here:
            node_file = shp_files[0]
            pipe_file = shp_files[1]
            # Save each set of parts
            # For the node set:
            node_related = [node_file] + ext_map["dbf"] + ext_map["shx"]
            # We'll do a naive approach: just check if the filenames match except extension
            # In real code, you'd separate them carefully or rely on naming conventions
            node_shp_path = read_shapefile_parts(node_related, "nodes", temp_dir)
            pipe_shp_path = None

            # The second .shp we do similarly
            # Actually, let's do a more robust approach: we can't just pass all dbf/shx to node if they're for pipe
            # We'll just read them individually if they have the same base name. 
            # This is complicated to do fully automatically.
            # For demonstration, let's just read them individually:
            pipe_shp_path = save_uploaded_file(pipe_file, temp_dir)  # for now
            # Let’s do a quick read
            node_gdf = gpd.read_file(node_shp_path)
            pipe_gdf = gpd.read_file(pipe_shp_path)
            st.write("Node layer has", len(node_gdf), "features.")
            st.write("Pipe layer has", len(pipe_gdf), "features.")

            # Attempt to build a WN
            st.write("Building WaterNetworkModel from node & pipe shapefiles.")
            try:
                wn = build_wn_from_shapefiles(node_gdf, pipe_gdf)
            except Exception as e:
                st.error(f"Failed to build WN from shapefiles: {e}")
        else:
            st.warning("Found more than 2 .shp files. This demo handles up to 2 only. Please adapt code.")
    
    # 5) CSV or TXT scenario
    elif "csv" in ext_map or "txt" in ext_map:
        st.write("CSV/TXT file(s) found. Displaying them, but not building a WN model.")
        for f in uploaded_files:
            if f.name.lower().endswith((".csv", ".txt")):
                path = save_uploaded_file(f, temp_dir)
                if path.endswith(".csv"):
                    df = pd.read_csv(path)
                else:
                    df = pd.read_table(path)
                st.write(f"**{f.name}**:")
                st.dataframe(df.head())
    else:
        st.warning("Unrecognized combination of files. Please adapt the logic as needed.")

    # If a WaterNetworkModel was built/loaded, let's run a simulation
    if wn:
        st.success("WaterNetworkModel is ready!")
        st.write(f"Junctions: {len(wn.junction_name_list)}, Pipes: {len(wn.pipe_name_list)}")

        with st.spinner("Running EPANET simulation..."):
            try:
                sim = wntr.sim.EpanetSimulator(wn)
                results = sim.run_sim()
                st.success("Simulation complete!")
                st.write("You can now process results (pressure, flow, etc.).")
            except Exception as e:
                st.error(f"Simulation failed: {e}")

def show_optional_data(leak_file, flow_file):
    """Display optional leaks & flow data if provided."""
    if leak_file:
        df_leaks = load_csv_or_excel(leak_file)
        if df_leaks is not None:
            st.subheader("Historic Leaks")
            st.dataframe(df_leaks)

    if flow_file:
        df_flow = load_csv_or_excel(flow_file)
        if df_flow is not None:
            st.subheader("Measured Flow Data")
            st.dataframe(df_flow)


if __name__ == "__main__":
    main()
