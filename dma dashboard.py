import os
import tempfile
import streamlit as st
import pandas as pd
import geopandas as gpd
import pydeck as pdk
from shapely.geometry import LineString
from datetime import datetime

st.set_page_config(layout="wide")
os.environ["MAPBOX_API_KEY"] = "your-mapbox-token-here"  # Replace with your token

# Utility to load shapefiles
def load_shapefile(files):
    with tempfile.TemporaryDirectory() as tmpdir:
        for file in files:
            with open(os.path.join(tmpdir, file.name), "wb") as f:
                f.write(file.read())
        shp_path = [f.name for f in files if f.name.endswith(".shp")][0]
        return gpd.read_file(os.path.join(tmpdir, shp_path))

# Load file for nodes/pipes/assets/leaks
def load_layer(name):
    st.sidebar.markdown(f"### {name}")
    shapefiles = st.sidebar.file_uploader(f"Upload {name} Shapefile Set", type=["shp", "shx", "dbf", "prj", "cpg", "qmd"], accept_multiple_files=True, key=f"{name}_shp")
    csv = st.sidebar.file_uploader(f"Or upload {name} CSV", type="csv", key=f"{name}_csv")

    gdf = None
    if shapefiles:
        try:
            gdf = load_shapefile(shapefiles)
            st.sidebar.success(f"{name} shapefile loaded.")
        except Exception as e:
            st.sidebar.error(f"Failed to load {name} shapefile: {e}")
    elif csv:
        try:
            df = pd.read_csv(csv)
            if name == "Nodes":
                gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.XCoord, df.YCoord), crs="EPSG:27700").to_crs("EPSG:4326")
            elif name == "Leaks":
                gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.XCoord, df.YCoord), crs="EPSG:27700").to_crs("EPSG:4326")
            elif name == "Assets":
                gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.XCoord, df.YCoord), crs="EPSG:27700").to_crs("EPSG:4326")
            elif name == "Pipes":
                # Build pipes from CSV StartID/EndID
                return "CSV_PIPE"  # signal to handle in custom logic
            st.sidebar.success(f"{name} CSV loaded.")
        except Exception as e:
            st.sidebar.error(f"Failed to load {name} CSV: {e}")
    return gdf

# Create pipe GeoDataFrame from CSV
def build_pipe_gdf_from_csv(df_pipes, node_gdf):
    node_map = {str(row.NodeID): row for _, row in node_gdf.iterrows()}
    current_year = datetime.now().year
    records = []

    for _, row in df_pipes.iterrows():
        start = node_map.get(str(row["StartID"]))
        end = node_map.get(str(row["EndID"]))
        if start is not None and end is not None:
            try:
                year_laid = int(row["Age"])
                age = current_year - year_laid
            except:
                continue
            records.append({
                "pipe_id": row["PipeID"],
                "geometry": LineString([start.geometry, end.geometry]),
                "Age": age,
                "Material": row.get("Material", "Unknown")
            })

    return gpd.GeoDataFrame(records, crs="EPSG:4326")

# Create map layers
def create_pipe_layer(pipe_gdf, criticality_on):
    def get_color(row):
        if not criticality_on:
            return [0, 255, 255]
        if row["Age"] > 50 or row["Material"].lower() == "cast iron":
            return [255, 0, 0]
        elif row["Age"] > 30:
            return [255, 165, 0]
        return [0, 255, 0]

    return pdk.Layer(
        "PathLayer",
        [{
            "path": list(row.geometry.coords),
            "pipe_id": row["pipe_id"],
            "Material": row["Material"],
            "Age": row["Age"],
            "color": get_color(row)
        } for _, row in pipe_gdf.iterrows()],
        get_path="path",
        get_color="color",
        width_min_pixels=4,
        pickable=True
    )

def create_asset_layer(asset_gdf):
    asset_gdf["lon"] = asset_gdf.geometry.x
    asset_gdf["lat"] = asset_gdf.geometry.y
    return pdk.Layer(
        "ScatterplotLayer",
        data=asset_gdf,
        get_position=["lon", "lat"],
        get_fill_color=[0, 200, 255],
        get_radius=30,
        pickable=True
    )

def create_leak_layer(leak_gdf):
    leak_gdf["lon"] = leak_gdf.geometry.x
    leak_gdf["lat"] = leak_gdf.geometry.y
    return pdk.Layer(
        "ScatterplotLayer",
        data=leak_gdf,
        get_position=["lon", "lat"],
        get_fill_color=[255, 0, 0],
        get_radius=20,
        pickable=True
    )

# Main App
st.title("💧 DMA Dashboard with Shapefile + CSV Upload Support")

criticality_on = st.sidebar.checkbox("Show Pipe Criticality", value=True)

node_gdf = load_layer("Nodes")
pipe_source = load_layer("Pipes")
asset_gdf = load_layer("Assets")
leak_gdf = load_layer("Leaks")

pipe_gdf = None
if pipe_source == "CSV_PIPE":
    if node_gdf:
        pipe_csv = st.sidebar.file_uploader("Upload Pipe CSV (for StartID/EndID method)", type="csv", key="pipe_logic_csv")
        if pipe_csv:
            df_pipes = pd.read_csv(pipe_csv)
            pipe_gdf = build_pipe_gdf_from_csv(df_pipes, node_gdf)
else:
    pipe_gdf = pipe_source

if st.button("Render Map"):
    if node_gdf is None or pipe_gdf is None:
        st.error("Please upload at least Nodes and Pipes.")
    else:
        layers = [create_pipe_layer(pipe_gdf, criticality_on)]
        if asset_gdf is not None:
            layers.append(create_asset_layer(asset_gdf))
        if leak_gdf is not None:
            layers.append(create_leak_layer(leak_gdf))

        view_state = pdk.ViewState(
            latitude=node_gdf.geometry.y.mean(),
            longitude=node_gdf.geometry.x.mean(),
            zoom=13,
            pitch=45
        )

        deck = pdk.Deck(
            map_style="mapbox://styles/mapbox/dark-v10",
            initial_view_state=view_state,
            layers=layers,
            tooltip={
                "html": """
                <b>Pipe ID:</b> {pipe_id}<br>
                <b>Material:</b> {Material}<br>
                <b>Age:</b> {Age} years<br>
                <b>Leak Type:</b> {LeakType}
                """,
                "style": {"color": "white"}
            }
        )

        st.pydeck_chart(deck, use_container_width=True)
