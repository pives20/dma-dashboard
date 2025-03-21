import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# List of required files with expected names
required_files = [
    "dma dashboard.py",
    "Pipe_Network.csv",
    "Assets_Data.csv",
    "requirements.txt",
    "dma_data.csv",
    "Pressure_Data.csv"
]

# Get files in the directory
available_files = os.listdir()
st.write("### Available Files:", available_files)

# Check for missing files
missing_files = [file for file in required_files if file not in available_files]
if missing_files:
    st.error(f"❌ Missing required files: {missing_files}")
    st.stop()

# Load data from available CSV files
dma_df = pd.read_csv("dma_data.csv")
pipe_network_df = pd.read_csv("Pipe_Network.csv")
pressure_df = pd.read_csv("Pressure_Data.csv")
assets_df = pd.read_csv("Assets_Data.csv")

# Ensure column names are stripped of whitespace
dma_df.columns = dma_df.columns.str.strip()
pipe_network_df.columns = pipe_network_df.columns.str.strip()
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
valid_pipes = validate_columns(pipe_network_df, ['Pipe ID', 'Latitude Start', 'Longitude Start', 'Latitude End', 'Longitude End', 'DMA_ID'], "Pipe Network")
valid_pressure = validate_columns(pressure_df, ['DMA ID', 'Pressure', 'Latitude', 'Longitude'], "Pressure Data")
valid_assets = validate_columns(assets_df, ['Asset ID', 'Asset Type', 'Latitude', 'Longitude'], "Assets Data")

# Function to plot an interactive DMA Map with pressure overlay
def plot_dma_pressure_map():
    if not (valid_dma and valid_pipes and valid_pressure and valid_assets):
        st.error("❌ Cannot plot map due to missing columns. Check the errors above.")
        return
    
    fig = px.scatter_mapbox(
        dma_df, lat='Latitude', lon='Longitude', color='DMA ID',
        size_max=10, zoom=12, height=600,
        mapbox_style="carto-darkmatter",
        title="DMA Network Map with Pressure Overlay",
        color_continuous_scale="YlOrRd"
    )
    
    # Add pipe network
    for _, row in pipe_network_df.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[row['Latitude Start'], row['Latitude End']],
            lon=[row['Longitude Start'], row['Longitude End']],
            mode='lines',
            line=dict(width=2, color='blue'),
            name=f"Pipe {row['Pipe ID']} (DMA {row['DMA_ID']})"
        ))
    
    # Add pressure data
    fig.add_trace(go.Scattermapbox(
        lat=pressure_df['Latitude'],
        lon=pressure_df['Longitude'],
        mode='markers',
        marker=dict(size=5, color=pressure_df['Pressure'], colorscale='YlOrRd', showscale=True),
        text=pressure_df['Pressure'],
        name="Pressure Levels"
    ))
    
    # Show assets
    for _, row in assets_df.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[row['Latitude']],
            lon=[row['Longitude']],
            mode='markers',
            marker=dict(size=8, symbol='circle', color='cyan' if row['Asset Type'] == 'Valve' else 'red'),
            text=row['Asset ID'],
            hoverinfo="text",
            name=row['Asset Type']
        ))
    
    st.plotly_chart(fig, use_container_width=True)

# Streamlit App
st.title("DMA Leakage Reduction AI Dashboard")

# Generate and display the DMA map with pressure overlay
st.write("### DMA Network Map with Pressure Overlay")
plot_dma_pressure_map()

st.success("Analysis Complete!")
