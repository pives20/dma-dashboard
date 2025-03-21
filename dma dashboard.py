import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Load data from CSV files
dma_df = pd.read_csv("dma_data.csv")
pipe_network_df = pd.read_csv("pipe_network_data.csv")
pressure_df = pd.read_csv("pressure_data.csv")
assets_df = pd.read_csv("assets_data.csv")

# Function to plot an interactive DMA Map with pressure overlay
def plot_dma_pressure_map():
    fig = px.scatter_mapbox(
        dma_df, lat='Latitude', lon='Longitude', color='Age (years)',
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
            line=dict(width=1.5, color='blue'),
            name=f"Pipe {row['Pipe ID']}"
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
            marker=dict(size=8, symbol='marker', color='cyan' if row['Asset Type'] == 'Valve' else 'red'),
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
