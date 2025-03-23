import os
import streamlit as st
import pandas as pd
import geopandas as gpd
import pydeck as pdk
import tempfile
from shapely.geometry import Point, LineString

#############################
# 1) SETUP MAPBOX TOKEN
#############################
os.environ["MAPBOX_API_KEY"] = "pk.eyJ1IjoicGl2ZXMiLCJhIjoiY204bGVweHY5MTFnZDJscXluOTJ1OHI5OCJ9.3BHtAPkRsjGbwgNykec4VA"

#############################
# 2) CUSTOM DARK THEME
#############################
dark_css = """
<style>
.block-container {
    background-color: #1E1E1E !important;
}
.sidebar .sidebar-content {
    background-color: #2F2F2F !important;
    color: white !important;
}
body, .css-145kmo2, .css-12oz5g7, .css-15zrgzn {
    color: #FFFFFF !important;
}
</style>
"""

st.set_page_config(layout="wide")
st.markdown(dark_css, unsafe_allow_html=True)

#############################
# 3) HELPER FUNCTIONS
#############################
def save_uploaded_file(uploaded_file, directory):
    file_path = directory + "/" + uploaded_file.name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())
    return file_path

def convert_to_latlon(df, x_col="XCoord", y_col="YCoord"):
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[x_col], df[y_col]), crs="EPSG:27700")
    gdf = gdf.to_crs("EPSG:4326")
    gdf["lon"] = gdf.geometry.x
    gdf["lat"] = gdf.geometry.y
    return gdf

def build_gis_data(node_csv_path, pipe_csv_path):
    df_nodes = pd.read_csv(node_csv_path)
    df_pipes = pd.read_csv(pipe_csv_path)

    node_gdf = convert_to_latlon(df_nodes)

    node_map = {str(r["NodeID"]): r.geometry for _, r in node_gdf.iterrows()}
    pipe_records = []
    for _, row in df_pipes.iterrows():
        start_geom = node_map.get(str(row["StartID"]))
        end_geom = node_map.get(str(row["EndID"]))
        if start_geom and end_geom:
            line = LineString([start_geom.coords[0], end_geom.coords[0]])
            row_dict = row.to_dict()
            row_dict["geometry"] = line
            pipe_records.append(row_dict)

    pipe_gdf = gpd.GeoDataFrame(pipe_records, crs="EPSG:4326")
    return node_gdf, pipe_gdf

def create_3d_elevation_layer(node_gdf):
    data = node_gdf.copy()
    data["elevation"] = data.get("Elevation_m", 0)
    data["height"] = (data["elevation"] / max(data["elevation"].max(), 1)) * 2000

    def elev_to_color(e):
        ratio = e / max(data["elevation"].max(), 1)
        r = 139 + int((205 - 139) * ratio)
        g = 69 + int((133 - 69) * ratio)
        b = 19 + int((63 - 19) * ratio)
        return [r, g, b]

    data["color"] = data["elevation"].apply(elev_to_color)

    return pdk.Layer(
        "ColumnLayer",
        data=data,
        get_position=["lon", "lat"],
        get_elevation="height",
        elevation_scale=1,
        radius=30,
        get_fill_color="color",
        pickable=True,
        extruded=True
    )

def create_pipe_layer(pipe_gdf, scenario="Baseline"):
    data = pipe_gdf.copy()
    if "flow" not in data:
        data["flow"] = 0
    if scenario == "Leak":
        data["flow"] *= 1.2

    max_flow = max(data["flow"].max(), 1)

    def flow_to_color(f):
        ratio = f / max_flow
        return [int(255 * ratio), 0, int(255 * (1 - ratio))]

    paths = []
    for _, row in data.iterrows():
        coords = list(row.geometry.coords)
        path = [[x, y] for x, y in coords]
        paths.append({"path": path, "color": flow_to_color(row["flow"])})

    return pdk.Layer(
        "PathLayer",
        data=paths,
        get_path="path",
        get_color="color",
        width_min_pixels=2,
        get_width=5,
        pickable=True
    )

#############################
# 4) STREAMLIT APP
#############################
def main():
    st.title("3D Elevation Map + Flow Scenario Toggle (Qatium-Style)")
    scenario = st.sidebar.selectbox("Scenario", ["Baseline", "Leak"])

    st.sidebar.metric("Network Demand", "120 L/s", "+5%" if scenario == "Leak" else "")
    st.sidebar.metric("Elevation Range", "0-?")
    st.sidebar.metric("Pipe Flow Range", "0-?")

    node_csv = st.file_uploader("Upload Node CSV", type="csv")
    pipe_csv = st.file_uploader("Upload Pipe CSV", type="csv")

    if st.button("Build 3D Map"):
        if not node_csv or not pipe_csv:
            st.error("Please upload both CSV files.")
            return

        tmp_dir = tempfile.mkdtemp()
        node_path = save_uploaded_file(node_csv, tmp_dir)
        pipe_path = save_uploaded_file(pipe_csv, tmp_dir)

        try:
            node_gdf, pipe_gdf = build_gis_data(node_path, pipe_path)

            elev_min = node_gdf["elevation"].min()
            elev_max = node_gdf["elevation"].max()
            st.sidebar.metric("Elevation Range", f"{elev_min}-{elev_max} m")

            flow_min = pipe_gdf["flow"].min() if "flow" in pipe_gdf else 0
            flow_max = pipe_gdf["flow"].max() if "flow" in pipe_gdf else 0
            st.sidebar.metric("Pipe Flow Range", f"{flow_min}-{flow_max} L/s")

            elev_layer = create_3d_elevation_layer(node_gdf)
            pipe_layer = create_pipe_layer(pipe_gdf, scenario)

            view_state = pdk.ViewState(
                longitude=node_gdf["lon"].mean(),
                latitude=node_gdf["lat"].mean(),
                zoom=13,
                pitch=45,
                bearing=30
            )

            deck_map = pdk.Deck(
                map_style="mapbox://styles/mapbox/dark-v10",
                initial_view_state=view_state,
                layers=[pipe_layer, elev_layer],
                tooltip={
                    "html": "<b>Elevation:</b> {elevation} m<br/><b>Flow:</b> {flow} L/s",
                    "style": {"color": "white"}
                },
            )

            st.pydeck_chart(deck_map, use_container_width=True)
            st.success(f"Rendered scenario: {scenario}")

        except Exception as e:
            st.error(f"Error building 3D map: {e}")

if __name__ == "__main__":
    main()
