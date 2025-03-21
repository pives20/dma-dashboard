import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go

# Load CSV Data
dma_df = pd.read_csv("dma_data.csv")
pressure_df = pd.read_csv("Pressure_Data.csv")
assets_df = pd.read_csv("Assets_Data.csv")

# Load Shapefile Data
try:
    dma_boundaries = gpd.read_file("dma_boundaries.shp")  # DMA Boundaries
    pipe_network = gpd.read_file("pipe_network.shp")  # Pipe Network
except Exception as e:
    st.error(f"Error loading shapefiles: {e}")
    dma_boundaries = None
    pipe_network = None

# Ensure column names are stripped of whitespace
dma_df.columns = dma_df.columns.str.strip()
pressure_df.columns = pressure_df.columns.str.strip()
assets_df.columns = assets_df.columns.str.strip()

# Function to check required columns
def validate_columns(df, required_columns, df_name):
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        st.error(f"❌ Missing columns in {df_name}: {missing_columns}")
        st.write(f"✅ Available columns in {df_name}: {list(df.columns)}")
        return False
    return True

# Validate all datasets
valid_dma = validate_columns(dma_df, ['DMA ID', 'Latitude', 'Longitude'], "DMA Data")
valid_pressure = validate_columns(pressure_df, ['DMA ID', 'Pressure', 'Latitude', 'Longitude'], "Pressure Data")
valid_assets = validate_columns(assets_df, ['Asset ID', 'Asset Type', 'Latitude', 'Longitude'], "Assets Data")

# Function to plot an interactive DMA Map with pressure overlay and SHP layers
def plot_dma_pressure_map():
    if not (valid_dma and valid_pressure and valid_assets):
        st.error("❌ Cannot plot map due to missing columns. Check the errors above.")
        return
    
    fig = px.density_mapbox(
        pressure_df, lat='Latitude', lon='Longitude', z='Pressure',
        radius=25, zoom=12, height=600, mapbox_style="carto-darkmatter",
        title="DMA Network Map with Pressure Overlay", color_continuous_scale="YlOrRd"
    )
    
    # Add DMA boundaries (Polygons)
    if dma_boundaries is not None:
        for _, row in dma_boundaries.iterrows():
            geo_json = row["geometry"].__geo_interface__
            fig.add_trace(go.Scattermapbox(
                lon=[point[0] for point in geo_json['coordinates'][0]],
                lat=[point[1] for point in geo_json['coordinates'][0]],
                mode="lines",
                line=dict(width=2, color="yellow"),
                name=f"DMA {row['DMA_ID']}"
            ))

    # Add Pipe Network (Lines)
    if pipe_network is not None:
        for _, row in pipe_network.iterrows():
            geo_json = row["geometry"].__geo_interface__
            fig.add_trace(go.Scattermapbox(
                lon=[point[0] for point in geo_json['coordinates']],
                lat=[point[1] for point in geo_json['coordinates']],
                mode="lines",
                line=dict(width=2, color="blue"),
                name=f"Pipe {row['Pipe_ID']}"
            ))

    # Show assets (Valves, Hydrants)
    for _, row in assets_df.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[row['Latitude']],
            lon=[row['Longitude']],
            mode='markers',
            marker=dict(size=10, symbol='marker', color='cyan' if row['Asset Type'] == 'Valve' else 'red'),
            text=row['Asset Type'],
            hoverinfo="text",
            name=row['Asset Type']
        ))
    
    st.plotly_chart(fig, use_container_width=True)

# Streamlit App
st.title("DMA Leakage Reduction AI Dashboard")

# Generate and display the DMA map with pressure overlay and shapefiles
st.write("### DMA Network Map with Pressure Overlay")
plot_dma_pressure_map()

st.success("Analysis Complete!")
