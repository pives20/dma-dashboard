import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# Set page config
st.set_page_config(layout="wide")

# Load CSV files
pipe_network_df = pd.read_csv("pipe_network_data.csv")
dma_df = pd.read_csv("dma_data.csv")
assets_df = pd.read_csv("assets_data.csv")

# Standardize column names
pipe_network_df.columns = pipe_network_df.columns.str.strip().str.lower()
dma_df.columns = dma_df.columns.str.strip().str.lower()
assets_df.columns = assets_df.columns.str.strip().str.lower()

# Estimate pressure based on diameter, material and slope (lat diff)
def estimate_pressure(df):
    material_factor = {"pvc": 1.0, "steel": 1.2, "copper": 1.1, "cast iron": 0.9}
    df["pressure"] = df.apply(
        lambda row: (
            row["diameter (mm)"] * material_factor.get(row["material"].lower(), 1.0)
        ) / (1 + abs(row["latitude_start"] - row["latitude_end"])) * 50,
        axis=1
    )
    return df

# Apply pressure estimation
pipe_network_df = estimate_pressure(pipe_network_df)

# Drop rows with missing coordinates
pipe_network_df.dropna(subset=["latitude_start", "longitude_start", "latitude_end", "longitude_end"], inplace=True)

# Streamlit title
st.title("DMA Leakage Reduction AI Dashboard")
st.write("### DMA Network Map with Estimated Pressure Overlay")

# Plotting function
def plot_dma_pressure_map():
    fig = go.Figure()

    # Add pipe segments
    for _, row in pipe_network_df.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[row['latitude_start'], row['latitude_end']],
            lon=[row['longitude_start'], row['longitude_end']],
            mode='lines',
            line=dict(width=2, color='purple'),
            hoverinfo='text',
            text=f"Pipe {row['pipe_id']} (DMA {row['dma_id']})\nPressure: {row['pressure']:.1f} psi",
            showlegend=False
        ))

    # Add pressure markers at start nodes
    fig.add_trace(go.Scattermapbox(
        lat=pipe_network_df['latitude_start'],
        lon=pipe_network_df['longitude_start'],
        mode='markers',
        marker=dict(size=6, color=pipe_network_df['pressure'], colorscale='YlOrRd', showscale=False),
        hoverinfo='skip',
        name="Estimated Pressure"
    ))

    # Add DMA points
    fig.add_trace(go.Scattermapbox(
        lat=dma_df['latitude'],
        lon=dma_df['longitude'],
        mode='markers',
        marker=dict(size=8, color='green'),
        text="DMA",
        showlegend=False
    ))

    # Add asset markers
    for _, row in assets_df.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[row['latitude']],
            lon=[row['longitude']],
            mode='markers',
            marker=dict(size=9, color='cyan' if row['asset type'].lower() == 'valve' else 'red'),
            text=row['asset type'],
            hoverinfo="text",
            showlegend=False
        ))

    fig.update_layout(
        mapbox_style="carto-darkmatter",
        mapbox_zoom=13,
        mapbox_center={"lat": dma_df['latitude'].mean(), "lon": dma_df['longitude'].mean()},
        margin={"r":0,"t":0,"l":0,"b":0},
        height=850
    )

    st.plotly_chart(fig, use_container_width=True)

# Plot the map
plot_dma_pressure_map()

st.success("Analysis Complete!")
