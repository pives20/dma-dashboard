import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# Generate Mock Data for Large DMA Visualization
num_pipes = 200
num_dmas = 10

# Generate random coordinates around a center point
np.random.seed(42)
latitude_center, longitude_center = 50.3763, -4.1438
pipe_network_data = {
    'Latitude Start': latitude_center + np.random.rand(num_pipes) * 0.02 - 0.01,
    'Longitude Start': longitude_center + np.random.rand(num_pipes) * 0.02 - 0.01,
    'Latitude End': latitude_center + np.random.rand(num_pipes) * 0.02 - 0.01,
    'Longitude End': longitude_center + np.random.rand(num_pipes) * 0.02 - 0.01,
    'Pipe ID': [f'P{str(i).zfill(3)}' for i in range(num_pipes)]
}
pipe_network_df = pd.DataFrame(pipe_network_data)

# Generate DMA Polygons
dma_data = {
    'Latitude': latitude_center + np.random.rand(num_dmas) * 0.02 - 0.01,
    'Longitude': longitude_center + np.random.rand(num_dmas) * 0.02 - 0.01,
    'Age (years)': np.random.randint(5, 25, num_dmas),
    'DMA ID': [f'DMA{str(i).zfill(2)}' for i in range(num_dmas)]
}
dma_df = pd.DataFrame(dma_data)

# Generate Pressure Data
pressure_data = {
    'Latitude': latitude_center + np.random.rand(num_pipes) * 0.02 - 0.01,
    'Longitude': longitude_center + np.random.rand(num_pipes) * 0.02 - 0.01,
    'Pressure': np.random.randint(40, 60, num_pipes)
}
pressure_df = pd.DataFrame(pressure_data)

# Generate Assets Data
assets_data = {
    'Latitude': latitude_center + np.random.rand(20) * 0.02 - 0.01,
    'Longitude': longitude_center + np.random.rand(20) * 0.02 - 0.01,
    'Asset Type': np.random.choice(['Valve', 'Hydrant'], 20),
    'Asset ID': [f'A{str(i).zfill(3)}' for i in range(20)],
    'Status': np.random.choice(['Open', 'Closed', 'Available'], 20),
    'Diameter': np.random.choice([100, 150, 200, 250], 20)
}
assets_df = pd.DataFrame(assets_data)

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
