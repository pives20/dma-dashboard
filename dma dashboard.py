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

# Ensure column names are stripped of whitespace and lowercased
dma_df.columns = dma_df.columns.str.strip().str.lower()
pipe_network_df.columns = pipe_network_df.columns.str.strip().str.lower()
assets_df.columns = assets_df.columns.str.strip().str.lower()

# Function to estimate pressure based on pipe characteristics
def estimate_pressure(pipe_network_df):
    material_factor = {"pvc": 1.0, "steel": 1.2, "copper": 1.1, "cast iron": 0.9}
    pipe_network_df["pressure"] = pipe_network_df.apply(
        lambda row: (row["diameter (mm)"] * material_factor.get(row["material"].lower(), 1.0)) /
                     (1 + abs(row["latitude"] - (row["latitude"] + row["length (m)"] / 111000))) * 50,
        axis=1
    )
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
valid_pipes = validate_columns(pipe_network_df, ['pipe id', 'dma id', 'length (m)', 'diameter (mm)', 'material', 'latitude', 'longitude', 'pressure'], "Pipe Network")
valid_assets = validate_columns(assets_df, ['asset id', 'asset type', 'latitude', 'longitude'], "Assets Data")

# Function to plot an interactive DMA Map with pressure overlay
def plot_dma_pressure_map():
    if not (valid_dma and valid_pipes and valid_assets):
        st.error("❌ Cannot plot map due to missing columns. Check the errors above.")
        return

    fig = px.scatter_mapbox(
        pipe_network_df, lat='latitude', lon='longitude', color='pressure',
        size_max=10, zoom=13, height=800,
        mapbox_style="carto-darkmatter",
        color_continuous_scale="YlOrRd"
    )

    # Add pipe lines
    for _, row in pipe_network_df.iterrows():
        end_lat = row['latitude'] + row['length (m)'] / 111000
        fig.add_trace(go.Scattermapbox(
            lat=[row['latitude'], end_lat],
            lon=[row['longitude'], row['longitude']],
            mode='lines',
            line=dict(width=2, color='blue'),
            showlegend=False
        ))

    # Show assets
    for _, row in assets_df.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[row['latitude']],
            lon=[row['longitude']],
            mode='markers',
            marker=dict(size=10, symbol='marker', color='cyan' if row['asset type'].lower() == 'valve' else 'red'),
            hoverinfo="none",
            showlegend=False
        ))

    st.plotly_chart(fig, use_container_width=True)

# Streamlit App
st.title("DMA Leakage Reduction AI Dashboard")

# Generate and display the DMA map with estimated pressure overlay
st.write("### DMA Network Map with Estimated Pressure Overlay")
plot_dma_pressure_map()

st.success("Analysis Complete!")
