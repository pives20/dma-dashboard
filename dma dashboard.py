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

# Load shapefile from uploaded files
def load_shapefile(files):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            for file in files:
                with open(os.path.join(tmpdir, file.name), "wb") as f:
                    f.write(file.read())
            shp_path = [f.name for f in files if f.name.endswith(".shp")]
            if not shp_path:
                st.sidebar.error("No .shp file found.")
                return None
            shp_full_path = os.path.join(tmpdir, shp_path[0])
            gdf = gpd.read_file(shp_full_path)
            if gdf.empty:
                st.sidebar.warning("Shapefile loaded, but it's empty.")
            else:
                st.sidebar.success(f"Loaded shapefile with {len(gdf)} records.")
            return gdf
    except Exception as e:
        st.sidebar.error(f"Failed to load shapefile: {e}")
        return None

# Upload interface for CSV or shapefile
def load_layer(name, geom_type="Point"):
    st.sidebar.markdown(f"### {name}")
    shapefiles = st.sidebar.file_uploader(f"Upload {name} Shapefile Set", type=["shp", "shx", "dbf", "prj"], accept_multiple_files=True, key=f"{name}_shp")
    csv = st.sidebar.file_uploader(f"Or upload {name} CSV", type="csv", key=f"{name}_csv")

    gdf = None
    if shapefiles:
        gdf = load_shapefile(shapefiles)
        if gdf is not None and geom_type == "Line" and not gdf.geom_type.isin(["LineString", "MultiLineString"]).any():
            st.sidebar.error(f"{name} must contain Line geometry.")
            return None
        if gdf is not None and geom_type == "Point" and not gdf.geom_type.isin(["Point"]).any():
            st.sidebar.error(f"{name} must contain Point geometry.")
            return None
    elif csv:
        try:
            df = pd.read_csv(csv)
            if "XCoord" in df.columns and "YCoord" in df.columns:
                gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.XCoord, df.YCoord), crs="EPSG:27700").to_crs("EPSG:4326")
            else:
                st.sidebar.error("CSV must contain 'XCoord' and 'YCoord' columns.")
        except Exception as e:
            st.sidebar.error(f"Error loading CSV: {e}")
    return gdf

# Create layers
def create_pipe_layer(pipe_gdf, criticality_on):
    current_year = datetime.now().year

    def color(row):
        try:
            age = current_year - int(row["Age"])
        except:
            age = 0
        if not criticality_on:
            return [0, 255, 255]
        if age > 50 or row.get("Material", "").lower() == "cast iron":
            return [255, 0, 0]
        elif age > 30:
            return [255, 165, 0]
        return [0, 255, 0]

    features = []
    for _, row in pipe_gdf.iterrows():
        coords = list(row.geometry.coords)
        features.append({
            "path": coords,
            "pipe_id": row.get("PipeID", ""),
            "Material": row.get("Material", "Unknown"),
            "Age": row.get("Age", "Unknown"),
            "color": color(row)
        })

    return pdk.Layer(
        "PathLayer",
        features,
        get_path="path",
        get_color="color",
        width_min_pixels=4,
        pickable=True
    )

def create_point_layer(gdf, color, radius):
    gdf["lon"] = gdf.geometry.x
    gdf["lat"] = gdf.geometry.y
    return pdk.Layer(
        "ScatterplotLayer",
        data=gdf,
        get_position=["lon", "lat"],
        get_fill_color=color,
        get_radius=radius,
        pickable=True
    )

# Main app
st.title("💧 DMA Dashboard — Pipes with Shapefile Support")

criticality_on = st.sidebar.checkbox("Show Pipe Criticality", value=True)

node_gdf = load_layer("Nodes")
pipe_gdf = load_layer("Pipes", geom_type="Line")
asset_gdf = load_layer("Assets")
leak_gdf = load_layer("Leaks")

if st.button("Render Map"):
    if node_gdf is None or pipe_gdf is None:
        st.error("Please upload at least Nodes and Pipes.")
    else:
        layers = [create_pipe_layer(pipe_gdf, criticality_on)]
        if asset_gdf is not None:
            layers.append(create_point_layer(asset_gdf, [0, 200, 255], 30))
        if leak_gdf is not None:
            layers.append(create_point_layer(leak_gdf, [255, 0, 0], 20))

        view = pdk.ViewState(
            latitude=node_gdf.geometry.y.mean(),
            longitude=node_gdf.geometry.x.mean(),
            zoom=13,
            pitch=45
        )

        st.pydeck_chart(pdk.Deck(
            map_style="mapbox://styles/mapbox/dark-v10",
            initial_view_state=view,
            layers=layers,
            tooltip={
                "html": "<b>Pipe ID:</b> {pipe_id}<br><b>Material:</b> {Material}<br><b>Age:</b> {Age}",
                "style": {"color": "white"}
            }
        ))
