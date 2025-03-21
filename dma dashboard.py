import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from shapely.geometry import Polygon, Point
import geopandas as gpd

# Set Streamlit page configuration at the top
st.set_page_config(layout="wide")

# Load data from CSV files
dma_df = pd.read_csv("dma_data.csv")
pipe_network_df = pd.read_csv("pipe_network_data.csv")
assets_df = pd.read_csv("assets_data.csv")

# Ensure column names are stripped of whitespace
dma_df.columns = dma_df.columns.str.strip().str.lower()
pipe_network_df.columns = pipe_network_df.columns.str.strip().str.lower()
assets_df.columns = assets_df.columns.str.strip().str.lower()

# Convert DMAs into polygons
def create_dma_polygons(dma_df):
    dma_polygons = {}
    for dma_id in dma_df["dma id"].unique():
        dma_points = dma_df[dma_df["dma id"] == dma_id][["latitude", "longitude"]].values
        if len(dma_points) > 2:
            dma_polygons[dma_id] = Polygon(dma_points)
    return dma_polygons

dma_polygons = create_dma_polygons(dma_df)

# Assign pipes and assets to DMAs
pipe_network_df["dma id"] = pipe_network_df.apply(lambda row: next((dma_id for dma_id, poly in dma_polygons.items() if poly.contains(Point(row["latitude"], row["longitude"]))), None), axis=1)
assets_df["dma id"] = assets_df.apply(lambda row: next((dma_id for dma_id, poly in dma_polygons.items() if poly.contains(Point(row["latitude"], row["longitude"]))), None), axis=1)

# Function to estimate pressure based on pipe characteristics
def estimate_pressure(pipe_network_df):
    material_factor = {"PVC": 1.0, "Steel": 1.2, "Copper": 1.1, "Cast Iron": 0.9}
    pipe_network_df["pressure"] = pipe_network_df.apply(
        lambda row: (row["diameter (mm)"] * material_factor.get(row["material"], 1.0)) / 100, axis=1)
    return pipe_network_df

# Estimate pressure data
pipe_network_df = estimate_pressure(pipe_network_df)

# Function to plot an interactive DMA Map with pressure overlay
def plot_dma_pressure_map():
    fig = go.Figure()
    
    # Add DMA Polygons
    for dma_id, polygon in dma_polygons.items():
        x, y = polygon.exterior.xy
        fig.add_trace(go.Scattermapbox(
            lat=list(x), lon=list(y),
            mode='lines', fill='toself',
            fillcolor='rgba(0, 150, 255, 0.2)',
            line=dict(width=1, color='blue'),
            name=f"DMA {dma_id}"
        ))
    
    # Add pipe network
    for _, row in pipe_network_df.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[row['latitude'], row['latitude'] + row['length (m)'] / 111000],
            lon=[row['longitude'], row['longitude']],
            mode='lines',
            line=dict(width=2, color='blue'),
            name=f"Pipe {row['pipe id']}"
        ))
    
    # Add assets
    for _, row in assets_df.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[row['latitude']], lon=[row['longitude']],
            mode='markers',
            marker=dict(size=10, color='red' if row['asset type'] == 'Hydrant' else 'cyan'),
            name=row['asset type']
        ))
    
    # Configure map layout
    fig.update_layout(
        mapbox=dict(
            style='carto-darkmatter',
            zoom=13,
            center=dict(lat=dma_df['latitude'].mean(), lon=dma_df['longitude'].mean())
        ),
        showlegend=False,
        height=800,
        margin=dict(l=0, r=0, t=0, b=0)
    )
    
    st.plotly_chart(fig, use_container_width=True)

# Streamlit App
st.title("DMA Leakage Reduction AI Dashboard")

# Generate and display the DMA map with estimated pressure overlay
st.write("### DMA Network Map with Estimated Pressure Overlay")
plot_dma_pressure_map()

st.success("Analysis Complete!")
