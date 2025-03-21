import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# Set Streamlit page configuration at the top
st.set_page_config(layout="wide")

# Load data from CSV files
dma_df = pd.read_csv("dma_data.csv")
pipe_network_df = pd.read_csv("pipe_network_data.csv")
assets_df = pd.read_csv("assets_data.csv")

# Ensure column names are stripped of whitespace and converted to lowercase
dma_df.columns = dma_df.columns.str.strip().str.lower()
pipe_network_df.columns = pipe_network_df.columns.str.strip().str.lower()
assets_df.columns = assets_df.columns.str.strip().str.lower()

# Convert latitude and longitude columns to numeric, forcing errors to NaN
numeric_columns = ['latitude', 'longitude', 'latitude start', 'longitude start', 'latitude end', 'longitude end']
for col in numeric_columns:
    if col in pipe_network_df.columns:
        pipe_network_df[col] = pd.to_numeric(pipe_network_df[col], errors='coerce')
    if col in dma_df.columns:
        dma_df[col] = pd.to_numeric(dma_df[col], errors='coerce')
    if col in assets_df.columns:
        assets_df[col] = pd.to_numeric(assets_df[col], errors='coerce')

# Drop rows with NaN values in essential columns
pipe_network_df.dropna(subset=['latitude start', 'longitude start', 'latitude end', 'longitude end'], inplace=True)
dma_df.dropna(subset=['latitude', 'longitude'], inplace=True)
assets_df.dropna(subset=['latitude', 'longitude'], inplace=True)

# Function to estimate pressure based on pipe characteristics
def estimate_pressure(pipe_network_df):
    material_factor = {"pvc": 1.0, "steel": 1.2, "copper": 1.1, "cast iron": 0.9}
    pipe_network_df["pressure"] = pipe_network_df.apply(
        lambda row: (row["diameter (mm)"] * material_factor.get(row["material"].lower(), 1.0)) / 
                     (1 + abs(row["latitude start"] - row["latitude end"])) * 50, axis=1)
    return pipe_network_df

# Estimate pressure data
pipe_network_df = estimate_pressure(pipe_network_df)

# Function to check required columns
def validate_columns(df, required_columns, df_name):
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        st.error(f"❌ Missing columns in {df_name}: {missing_columns}")
        st.write(f"✅ Available columns in {df_name}: {list(df.columns)}")
        return False
    return True

# Validate datasets
valid_dma = validate_columns(dma_df, ['dma id', 'latitude', 'longitude'], "DMA Data")
valid_pipes = validate_columns(pipe_network_df, ['pipe id', 'dma id', 'length (m)', 'diameter (mm)', 'material', 'pressure'], "Pipe Network")
valid_assets = validate_columns(assets_df, ['asset id', 'asset type', 'latitude', 'longitude'], "Assets Data")

# Function to plot an interactive DMA Map with pressure overlay
def plot_dma_pressure_map():
    if not (valid_dma and valid_pipes and valid_assets):
        st.error("❌ Cannot plot map due to missing columns. Check the errors above.")
        return
    
    fig = px.scatter_mapbox(
        pipe_network_df, lat='latitude start', lon='longitude start', color='pressure',
        size_max=10, zoom=12, height=900, width=1600, mapbox_style="carto-darkmatter",
        title="DMA Network Map with Estimated Pressure Overlay", color_continuous_scale="YlOrRd"
    )
    
    # Add pipe network
    for _, row in pipe_network_df.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[row['latitude start'], row['latitude end']],
            lon=[row['longitude start'], row['longitude end']],
            mode='lines',
            line=dict(width=2, color='purple'),
            hoverinfo='none',
            showlegend=False
        ))
    
    # Show assets
    for _, row in assets_df.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[row['latitude']],
            lon=[row['longitude']],
            mode='markers',
            marker=dict(size=10, symbol='marker', color='cyan' if row['asset type'] == 'Valve' else 'red'),
            hoverinfo="none",
            showlegend=False
        ))
    
    # Hide colorbar
    for trace in fig.data:
        if 'marker' in trace and 'color' in trace.marker:
            trace.marker.showscale = False
    
    st.plotly_chart(fig, use_container_width=True)

# Streamlit App
st.title("DMA Leakage Reduction AI Dashboard")

# Generate and display the DMA map with estimated pressure overlay
st.write("### DMA Network Map with Estimated Pressure Overlay")
plot_dma_pressure_map()

st.success("Analysis Complete!")
