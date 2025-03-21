import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, r2_score
import io
import base64
from io import BytesIO
from fpdf import FPDF
import time

# Load Data from backend storage
@st.cache_data
def load_backend_data():
    dma_df = pd.read_csv("dma_data.csv")
    pipe_network_df = pd.read_csv("pipe_network.csv")
    pressure_df = pd.read_csv("pressure_data.csv")
    assets_df = pd.read_csv("assets_data.csv")
    return dma_df, pipe_network_df, pressure_df, assets_df

# Load all backend data
dma_df, pipe_network_df, pressure_df, assets_df = load_backend_data()

# Function to generate a Pressure Heatmap with Time-Based Animation
def plot_pressure_time_animation(pressure_df):
    if pressure_df is not None:
        pressure_df['Timestamp'] = pd.to_datetime(pressure_df['Timestamp'])
        fig = px.scatter_mapbox(
            pressure_df, lat='Latitude', lon='Longitude', color='Pressure', size_max=10,
            animation_frame=pressure_df['Timestamp'].astype(str),
            mapbox_style="carto-darkmatter",
            title="Pressure Variation Over Time",
            color_continuous_scale=["yellow", "orange", "red"]
        )
        st.plotly_chart(fig)
    else:
        st.write("Pressure animation cannot be generated due to missing data.")

# Function to plot an interactive DMA Map with hexagonal bins, pressure overlay, and advanced asset visualization
def plot_dma_pressure_map(dma_df, pipe_network_df, pressure_df, assets_df):
    if dma_df is not None:
        fig = px.hexbin_mapbox(
            dma_df, lat='Latitude', lon='Longitude', color='Age (years)',
            zoom=12, height=600, size_max=20, opacity=0.7,
            title="DMA Network Map with Pressure Overlay",
            color_continuous_scale="YlOrRd"
        )
        fig.update_layout(mapbox_style="carto-darkmatter")
        
        # Add pipe network if available
        if pipe_network_df is not None:
            for _, row in pipe_network_df.iterrows():
                fig.add_trace(go.Scattermapbox(
                    lat=[row['Latitude Start'], row['Latitude End']],
                    lon=[row['Longitude Start'], row['Longitude End']],
                    mode='lines',
                    line=dict(width=2, color='blue'),
                    name=f"Pipe {row['Pipe ID']}"
                ))
        
        # Add pressure data if available
        if pressure_df is not None:
            fig.add_trace(go.Scattermapbox(
                lat=pressure_df['Latitude'],
                lon=pressure_df['Longitude'],
                mode='markers',
                marker=dict(size=8, color=pressure_df['Pressure'], colorscale='YlOrRd', showscale=True),
                text=pressure_df['Pressure'],
                name="Pressure Levels"
            ))
        
        # Show assets with interactive click events
        if assets_df is not None:
            asset_types = assets_df['Asset Type'].unique().tolist()
            selected_assets = st.multiselect("Select Asset Types to Display:", asset_types, default=asset_types)
            filtered_assets = assets_df[assets_df['Asset Type'].isin(selected_assets)]
            
            for asset_type in selected_assets:
                asset_subset = filtered_assets[filtered_assets['Asset Type'] == asset_type]
                fig.add_trace(go.Scattermapbox(
                    lat=asset_subset['Latitude'],
                    lon=asset_subset['Longitude'],
                    mode='markers',
                    marker=dict(
                        size=12,
                        symbol='marker',
                        color='cyan' if asset_type == 'Valve' else 'red' if asset_type == 'Hydrant' else 'purple'
                    ),
                    text=asset_subset['Asset ID'],
                    customdata=asset_subset[['Asset ID', 'Status', 'Diameter']],
                    hovertemplate="<b>%{customdata[0]}</b><br>Status: %{customdata[1]}<br>Diameter: %{customdata[2]} mm<extra></extra>",
                    name=asset_type
                ))
        
        st.plotly_chart(fig)
        
        # Control valves interactively
        selected_valve = st.selectbox("Select a Valve to Control:", filtered_assets[filtered_assets['Asset Type'] == 'Valve']['Asset ID'].unique() if 'Valve' in selected_assets else [])
        if selected_valve:
            valve_status = st.radio("Valve Status:", ['Open', 'Closed'])
            st.write(f"Valve {selected_valve} is now {valve_status}.")
    else:
        st.write("No DMA data available for mapping.")

# Streamlit App
st.title("DMA Leakage Reduction AI Dashboard")

# Generate and display the DMA map with pressure overlay
st.write("### DMA Network Map with Pressure Overlay")
plot_dma_pressure_map(dma_df, pipe_network_df, pressure_df, assets_df)

# Generate and display the pressure heatmap with time-based animation
st.write("### Pressure Variation Over Time")
plot_pressure_time_animation(pressure_df)

st.success("Analysis Complete!")

