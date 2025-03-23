import streamlit as st
import wntr
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString
import os
import zipfile
import tempfile

#################################
# 1) HELPER FUNCTIONS
#################################

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

def read_shapefile_parts(files, temp_dir):
    """
    If user uploads separate SHP, DBF, SHX (and maybe PRJ),
    store them in temp_dir with the same basename so gpd can read.
    Returns the path to the .shp.
    """
    base = "layer"
    shp_path = None
    for f in files:
        ext = f.name.split(".")[-1].lower()
        outpath = os.path.join(temp_dir, f"{base}.{ext}")
        with open(outpath, "wb") as out:
            out.write(f.read())
        if ext == "shp":
            shp_path = outpath
    return shp_path

def load_csv_or_excel(upload):
    """Load an uploaded CSV or Excel file into a DataFrame."""
    if not upload:
        return None
    ext = upload.name.lower()
    if ext.endswith(".csv"):
        return pd.read_csv(upload)
    elif ext.endswith(".xlsx"):
        return pd.read_excel(upload)
    else:
        return None

##################
# WNTR BUILDING  #
##################

def build_wn_from_gdfs(node_gdf, pipe_gdf):
    """
    Example building a WaterNetworkModel from two GeoDataFrames.
    Adjust column names to your schema (NodeID, Elev, Demand, etc.).
    """
    wn = wntr.network.WaterNetworkModel()

    # Suppose node_gdf has columns: NodeID, Elev, Demand, geometry(Point)
    for idx, row in node_gdf.iterrows():
        node_id = str(row["NodeID"])
        elev = row.get("Elev", 0.0)
        demand = row.
