import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Load data from CSV files
dma_df = pd.read_csv("dma_data.csv")
pipe_network_df = pd.read_csv("pipe_network.csv")
pressure_df = pd.read_csv("pressure_data.csv")
assets_df = pd.read_csv("assets_data.csv")

# Ensure column names are formatted correctly
def clean_column_names(df):
    df.columns = df.columns.str.replace(r'\s+', ' ', regex=True).str.strip()
    return df

dma_df = clean_column_names(dma_df)
pipe_network_df = clean_column_names(pipe_network_df)
pressure_df = clean_column_names(pressure_df)
assets_df = clean_column_names(assets_df)

# Debug: Print actual column names to check formatting issues
st.write("### Debug: Checking Column Names in Data Files")
st.write("#### DMA Data Columns:", list(dma_df.columns))
st.write("#### Pipe Network Data Columns:", list(pipe_network_df.columns))
st.write("#### Pressure Data Columns:", list(pressure_df.columns))
st.write("#### Assets Data Columns:", list(assets_df.columns))

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
    
    for _, row in pipe_network_df.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[row['Latitude Start'], row['Latitude End']],
            lon=[row['Longitude Start'], row['Longitude End']],
            mode='lines',
            line=dict(width=2, color='blue'),
            name=f"Pipe {row['Pipe ID']} (DMA {row['DMA_ID']})"
        ))
    
    fig.add_trace(go.Scattermapbox(
        lat=pressure_df['Latitude'],
        lon=pressure_df['Longitude'],
        mode='markers',
        marker=dict(size=5, color=pressure_df['Pressure'], colorscale='YlOrRd', showscale=True),
        text=pressure_df['Pressure'],
        name="Pressure Levels"
    ))
    
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

st.title("DMA Leakage Reduction AI Dashboard")
st.write("### DMA Network Map with Pressure Overlay")
plot_dma_pressure_map()
st.success("Analysis Complete!")
