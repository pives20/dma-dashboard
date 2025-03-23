import streamlit as st
import wntr
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString
import os
import zipfile
import tempfile

# ---------------------
# 1. HELPER FUNCTIONS
# ---------------------

def save_uploaded_file_to_temp(uploaded_file, temp_dir):
    """
    Saves a Streamlit-uploaded file to a temporary directory.
    Returns the full path to the saved file.
    """
    file_path = os.path.join(temp_dir, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())
    return file_path

def unzip_file(zip_path, extract_to):
    """Unzip the file at zip_path into the folder extract_to."""
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_to)

def read_epanet_inp(inp_path):
    """Load an EPANET .inp using WNTR, return a WaterNetworkModel."""
    wn = wntr.network.WaterNetworkModel(inp_path)
    return wn

def read_geojson(geojson_path):
    """Load a GeoJSON into a GeoDataFrame."""
    return gpd.read_file(geojson_path)

def read_shapefile_parts(files, temp_dir):
    """
    If user uploads separate SHP, DBF, SHX (and maybe PRJ),
    store them in temp_dir with the same basename so gpd can read.
    Returns the path to the .shp.
    """
    # We'll pick a base name "layer", e.g.: layer.shp, layer.shx, layer.dbf, layer.prj
    base = "layer"
    exts = []
    for f in files:
        ext = f.name.split(".")[-1].lower()
        exts.append(ext)

    shp_path = os.path.join(temp_dir, base + ".shp")
    # Save each piece to disk
    for f in files:
        ext = f.name.split(".")[-1].lower()
        outpath = os.path.join(temp_dir, base + f".{ext}")
        with open(outpath, "wb") as out:
            out.write(f.read())

    return shp_path

def build_wn_from_shapefile(node_gdf, pipe_gdf):
    """
    Example building a WaterNetworkModel from two GeoDataFrames:
    one for nodes (junctions), one for pipes (links).
    Adapt column names to your schema.
    """
    wn = wntr.network.WaterNetworkModel()
    # Suppose node_gdf has columns: NodeID, Elev, Demand, geometry(Point)
    for idx, row in node_gdf.iterrows():
        node_id = str(row["NodeID"])
        elev = row.get("Elev", 0.0)
        demand = row.get("Demand", 0.0)
        wn.add_junction(node_id, base_demand=demand, elevation=elev)
        # Store coordinates for reference
        x, y = row.geometry.x, row.geometry.y
        wn.get_node(node_id).coordinates = (float(x), float(y))

    # Suppose pipe_gdf has columns: PipeID, StartID, EndID, Length, Diameter, etc.
    for idx, row in pipe_gdf.iterrows():
        pipe_id   = str(row["PipeID"])
        start_id  = str(row["StartID"])
        end_id    = str(row["EndID"])
        length    = row.get("Length", 0.0)
        diameter  = row.get("Diameter", 100.0)
        roughness = row.get("Roughness", 100.0)

        if length <= 0:
            # derive from geometry length
            length = row.geometry.length

        wn.add_pipe(
            pipe_id,
            start_node_name=start_id,
            end_node_name=end_id,
            length=length,
            diameter=diameter,
            roughness=roughness
        )
    return wn


# ---------------------
# 2. STREAMLIT APP
# ---------------------
def main():
    st.set_page_config(layout="wide")
    st.title("Upload Your Network (GeoJSON, Shapefile, EPANET .INP, CSV/TXT, or ZIP)")

    # Single file uploader that can accept multiple files (e.g., .shp, .dbf, .shx, etc. at once)
    uploaded_files = st.file_uploader(
        label="Upload your network file(s)",
        accept_multiple_files=True,
        type=["geojson","shp","shx","dbf","prj","inp","csv","txt","zip"]
    )

    if not uploaded_files:
        st.info("Please upload at least one file.")
        return

    # Create a temporary directory for processing
    temp_dir = tempfile.mkdtemp()

    # We'll try to detect the scenario:
    # 1) Single file .INP
    # 2) Single file .geojson
    # 3) A set of .shp, .dbf, .shx, etc. (the shapefile approach)
    # 4) A .zip that might contain shapefiles or something else
    # 5) A .csv or .txt that may contain node/pipe data (not fully implemented here)
    
    # Let's group by extension
    ext_map = {}
    for uf in uploaded_files:
        ext = uf.name.split(".")[-1].lower()
        ext_map.setdefault(ext, []).append(uf)

    # Initialize placeholders
    wn = None            # WaterNetworkModel, if we can build one
    node_gdf = None      # Possibly a node layer
    pipe_gdf = None      # Possibly a pipe layer
    other_data = []      # For CSV/TXT or other files

    # Check for single-file cases:
    # 1) If there's exactly 1 file and it's .inp
    if len(uploaded_files) == 1 and "inp" in ext_map:
        inp_file = uploaded_files[0]
        inp_path = save_uploaded_file_to_temp(inp_file, temp_dir)
        st.write("Detected an EPANET .inp file.")
        wn = read_epanet_inp(inp_path)

    # 2) If there's exactly 1 file and it's .geojson
    elif len(uploaded_files) == 1 and "geojson" in ext_map:
        geojson_file = uploaded_files[0]
        geojson_path = save_uploaded_file_to_temp(geojson_file, temp_dir)
        st.write("Detected a GeoJSON file.")
        gdf = gpd.read_file(geojson_path)
        st.write("GeoJSON read into GeoDataFrame with", len(gdf), "features.")
        # For a single-layer approach, you might interpret it as either nodes or pipes
        # or some combined data. Not a complete model. Let's just show it:
        st.dataframe(gdf.head())

    # 3) If there's a .zip
    elif len(uploaded_files) == 1 and "zip" in ext_map:
        zip_file = uploaded_files[0]
        zip_path = save_uploaded_file_to_temp(zip_file, temp_dir)
        st.write("Detected a ZIP file.")
        unzip_file(zip_path, temp_dir)
        # Attempt to find .shp or .inp or .geojson inside the zip
        # Simplify: let's just see if there's an .inp or .shp
        # For a robust approach, we might check all extracted files
        found_inp = None
        found_shp = None
        for root, dirs, files in os.walk(temp_dir):
            for f in files:
                if f.lower().endswith(".inp"):
                    found_inp = os.path.join(root, f)
                elif f.lower().endswith(".shp"):
                    found_shp = os.path.join(root, f)

        if found_inp:
            st.write("Found an .inp inside the ZIP, loading EPANET model.")
            wn = read_epanet_inp(found_inp)
        elif found_shp:
            # Possibly a shapefile. We'll just read it as a single layer.
            st.write("Found a .shp inside the ZIP, trying to load as shapefile.")
            gdf = gpd.read_file(found_shp)
            st.write("Shapefile read with", len(gdf), "features.")
            st.dataframe(gdf.head())
        else:
            st.warning("No .inp or .shp found in the ZIP. Possibly other content.")
    
    # 4) If there's a combination of .shp, .dbf, .shx, ...
    elif "shp" in ext_map and "dbf" in ext_map and "shx" in ext_map:
        st.write("Detected multiple shapefile components.")
        # Save them all. We'll assume they form a single layer or we might have
        # multiple shapefiles if there's more than one .shp.
        # For a more advanced approach, you'd handle node vs. pipe layers, etc.
        # But let's do a single shapefile read for demonstration.

        # Option A: If there's exactly 1 .shp file, we load it as one layer
        # Option B: The user might have 2 .shp files (one for nodes, one for pipes)
        # We'll keep it simple and handle 1 .shp scenario.

        shp_files = ext_map["shp"]
        if len(shp_files) > 1:
            st.error("Multiple .shp files found; code example expects only one shapefile. Adapt as needed!")
            return

        # gather all relevant files
        all_shp_parts = shp_files + ext_map["dbf"] + ext_map["shx"]
        if "prj" in ext_map:
            all_shp_parts += ext_map["prj"]

        shp_path = read_shapefile_parts(all_shp_parts, temp_dir)
        gdf = gpd.read_file(shp_path)
        st.write("Shapefile read with", len(gdf), "features.")
        st.dataframe(gdf.head())
        # Not auto-building a WNTR model unless you define how to interpret columns as nodes/pipes.

    # 5) CSV or TXT
    elif ("csv" in ext_map) or ("txt" in ext_map):
        st.write("Detected CSV/TXT file(s). We'll display them. Building a model would require custom logic.")
        for f in uploaded_files:
            if f.name.lower().endswith((".csv",".txt")):
                path = save_uploaded_file_to_temp(f, temp_dir)
                df = pd.read_csv(path) if f.name.lower().endswith(".csv") else pd.read_table(path)
                st.write(f"**{f.name}**:")
                st.dataframe(df.head())
                other_data.append(df)
    else:
        st.warning("Unrecognized combination of files. Please adapt logic as needed.")

    # If we got a WNTR model, show some basic stats
    if wn:
        st.success("WaterNetworkModel loaded successfully!")
        st.write(f"Number of junctions: {len(wn.junction_name_list)}")
        st.write(f"Number of pipes: {len(wn.pipe_name_list)}")

        # Optionally run simulation
        with st.spinner("Running EPANET simulation..."):
            sim = wntr.sim.EpanetSimulator(wn)
            results = sim.run_sim()
        st.success("Simulation complete!")
        st.write("You can now process results... (pressure, flow, etc.)")

if __name__ == "__main__":
    main()
