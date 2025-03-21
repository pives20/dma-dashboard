import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# Set seed for reproducibility
np.random.seed(42)

# Define DMA boundaries
num_pipes = 500
num_dmas = 20
latitude_center, longitude_center = 50.3763, -4.1438

# Generate DMA Polygon Coordinates (Bounding Boxes)
dma_bounds = []
for i in range(num_dmas):
    lat_start = latitude_center + np.random.rand() * 0.04 - 0.02
    lon_start = longitude_center + np.random.rand() * 0.04 - 0.02
    lat_end = lat_start + np.random.rand() * 0.01
    lon_end = lon_start + np.random.rand() * 0.01
    dma_bounds.append({'DMA ID': f'DMA{i:02}', 'lat_min': lat_start, 'lon_min': lon_start, 'lat_max': lat_end, 'lon_max': lon_end})

dma_df = pd.DataFrame(dma_bounds)

# Generate Pipe Network assigned to random DMAs
pipe_network_data = []
for i in range(num_pipes):
    dma = dma_df.sample(1).iloc[0]  # Assign pipe to a DMA
    lat_start = np.random.uniform(dma['lat_min'], dma['lat_max'])
    lon_start = np.random.uniform(dma['lon_min'], dma['lon_max'])
    lat_end = lat_start + np.random.uniform(-0.002, 0.002)
    lon_end = lon_start + np.random.uniform(-0.002, 0.002)
    pipe_network_data.append({'Pipe ID': f'P{str(i).zfill(3)}', 'Latitude Start': lat_start, 'Longitude Start': lon_start, 'Latitude End': lat_end, 'Longitude End': lon_end})

pipe_network_df = pd.DataFrame(pipe_network_data)

# Generate Pressure Data assigned to pipes
pressure_data = []
for _, pipe in pipe_network_df.iterrows():
    pressure_data.append({'Latitude': (pipe['Latitude Start'] + pipe['Latitude End']) / 2,
                          'Longitude': (pipe['Longitude Start'] + pipe['Longitude End']) / 2,
                          'Pressure': np.random.randint(40, 60)})
pressure_df = pd.DataFrame(pressure_data)

# Generate Assets assigned to DMAs
assets_data = []
for i in range(100):
    dma = dma_df.sample(1).iloc[0]  # Assign asset to a DMA
    assets_data.append({'Latitude': np.random.uniform(dma['lat_min'], dma['lat_max']),
                        'Longitude': np.random.uniform(dma['lon_min'], dma['lon_max']),
                        'Asset Type': np.random.choice(['Valve', 'Hydrant']),
                        'Asset ID': f'A{str(i).zfill(3)}',
                        'Status': np.random.choice(['Open', 'Closed']),
                        'Diameter': np.random.choice([100, 150, 200, 250])})

assets_df = pd.DataFrame(assets_data)

# Function to plot an interactive DMA Map with pressure overlay
def plot_dma_pressure_map():
    fig = go.Figure()

    # Plot DMA Polygons
    for _, dma in dma_df.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[dma['lat_min'], dma['lat_max'], dma['lat_max'], dma['lat_min'], dma['lat_min']],
            lon=[dma['lon_min'], dma['lon_min'], dma['lon_max'], dma['lon_max'], dma['lon_min']],
            fill="toself",
            line=dict(width=1, color="yellow"),
            opacity=0.3,
            name=f"{dma['DMA ID']}"
        ))

    # Add Pipe Network
    for _, row in pipe_network_df.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[row['Latitude Start'], row['Latitude End']],
            lon=[row['Longitude Start'], row['Longitude End']],
            mode='lines',
            line=dict(width=1.5, color='blue'),
            name=f"Pipe {row['Pipe ID']}"
        ))

    # Add Pressure Data
    fig.add_trace(go.Scattermapbox(
        lat=pressure_df['Latitude'],
        lon=pressure_df['Longitude'],
        mode='markers',
        marker=dict(size=5, color=pressure_df['Pressure'], colorscale='YlOrRd', showscale=True),
        text=pressure_df['Pressure'],
        name="Pressure Levels"
    ))

    # Add Assets
    for _, row in assets_df.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[row['Latitude']],
            lon=[row['Longitude']],
            mode='markers',
            marker=dict(size=8, symbol='circle', c
