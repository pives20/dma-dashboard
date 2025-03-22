import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Set Streamlit page configuration
st.set_page_config(layout="wide")

# Load and clean data from CSV files
pipe_network_df = pd.read_csv("pipe_network_data.csv")
dma_df = pd.read_csv("dma_data.csv")
assets_df = pd.read_csv("assets_data.csv")

# Clean column names immediately
pipe_network_df.columns = pipe_network_df.columns.str.strip().str.lower()
dma_df.columns = dma_df.columns.str.strip().str.lower()
assets_df.columns = assets_df.columns.str.strip().str.lower()

# Debug column names
st.write("✅ Pipe network columns:", pipe_network_df.columns.tolist())

# Function to estimate pressure based on pipe characteristics
def estimate_pressure(df):
    material_factor = {"pvc": 1.0, "steel": 1.2, "copper": 1.1, "cast iron": 0.9}
    df["pressure"] = df.apply(
        lambda row: row["diameter (mm)"] * material_factor.get(row["material"].lower(), 1.0),
        axis=1
    )
    return df

# Estimate pressure
pipe_network_df = estimate_pressure(pipe_network_df)

# Drop any rows without lat/lon to avoid plotting issues
pipe_network_df.dropna(subset=['latitude', 'longitude'], inplace=True)

# Function to validate required columns

def validate_columns(df, required_columns, df_name):
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        st.error(f"❌ Missing columns in {df_name}: {missing_columns}")
        st.write(f"✅ Available columns in {df_name}: {list(df.columns)}")
        return False
    return True

valid_dma = validate_columns(dma_df, ['latitude', 'longitude'], "DMA Data")
valid_pipes = validate_columns(pipe_network_df, ['latitude', 'longitude', 'diameter (mm)', 'material', 'pressure'], "Pipe Network")
valid_assets = validate_columns(assets_df, ['latitude', 'longitude', 'asset type'], "Assets Data")

# Function to plot interactive map
def plot_dma_pressure_map():
    if not (valid_dma and valid_pipes and valid_assets):
        st.error("❌ Cannot plot map due to missing columns. Check the errors above.")
        return

    fig = px.scatter_mapbox(
        pipe_network_df,
        lat='latitude', lon='longitude',
        color='pressure',
        color_continuous_scale='YlOrRd',
        zoom=12, height=900, mapbox_style="carto-darkmatter"
    )

    # Add assets
    for _, row in assets_df.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[row['latitude']],
            lon=[row['longitude']],
            mode='markers',
            marker=dict(size=10, symbol='marker', color='cyan' if row['asset type'].lower() == 'valve' else 'red'),
            showlegend=False,
            hoverinfo="text",
            text=row['asset type']
        ))

    st.plotly_chart(fig, use_container_width=True)

# Page title and map
st.title("DMA Leakage Reduction AI Dashboard")
st.write("### DMA Network Map with Estimated Pressure Overlay")
plot_dma_pressure_map()
st.success("Analysis Complete!")
