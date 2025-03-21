import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Sample Mock Data for DMA Visualization
dma_data = {
    'Latitude': [50.3763, 50.3772, 50.3785],
    'Longitude': [-4.1438, -4.1425, -4.1412],
    'Age (years)': [10, 15, 8]
}
dma_df = pd.DataFrame(dma_data)

pipe_network_data = {
    'Latitude Start': [50.3760, 50.3770],
    'Longitude Start': [-4.1440, -4.1430],
    'Latitude End': [50.3775, 50.3780],
    'Longitude End': [-4.1420, -4.1410],
    'Pipe ID': ['P001', 'P002']
}
pipe_network_df = pd.DataFrame(pipe_network_data)

pressure_data = {
    'Latitude': [50.3765, 50.3775, 50.3782],
    'Longitude': [-4.1435, -4.1422, -4.1410],
    'Pressure': [50, 48, 52]
}
pressure_df = pd.DataFrame(pressure_data)

assets_data = {
    'Latitude': [50.3768, 50.3779],
    'Longitude': [-4.1433, -4.1421],
    'Asset Type': ['Valve', 'Hydrant'],
    'Asset ID': ['V001', 'H001'],
    'Status': ['Open', 'Available'],
    'Diameter': [150, 200]
}
assets_df = pd.DataFrame(assets_data)

# Function to plot an interactive DMA Map with pressure overlay
def plot_dma_pressure_map():
    fig = px.density_mapbox(
        dma_df, lat='Latitude', lon='Longitude', z='Age (years)',
        radius=15, zoom=12, height=600,
        mapbox_style="carto-darkmatter",
        title="DMA Network Map with Pressure Overlay",
        color_continuous_scale="YlOrRd"
    )
    
    # Add pipe network if available
    for _, row in pipe_network_df.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[row['Latitude Start'], row['Latitude End']],
            lon=[row['Longitude Start'], row['Longitude End']],
            mode='lines',
            line=dict(width=2, color='blue'),
            name=f"Pipe {row['Pipe ID']}"
        ))
    
    # Add pressure data
    fig.add_trace(go.Scattermapbox(
        lat=pressure_df['Latitude'],
        lon=pressure_df['Longitude'],
        mode='markers',
        marker=dict(size=8, color=pressure_df['Pressure'], colorscale='YlOrRd', showscale=True),
        text=pressure_df['Pressure'],
        name="Pressure Levels"
    ))
    
    # Show assets with interactive click events
    for _, row in assets_df.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[row['Latitude']],
            lon=[row['Longitude']],
            mode='markers',
            marker=dict(
                size=12,
                symbol='marker',
                color='cyan' if row['Asset Type'] == 'Valve' else 'red'
            ),
            text=row['Asset ID'],
            hoverinfo="text",
            name=row['Asset Type']
        ))
    
    st.plotly_chart(fig)

# Streamlit App
st.title("DMA Leakage Reduction AI Dashboard")

# Generate and display the DMA map with pressure overlay
st.write("### DMA Network Map with Pressure Overlay")
plot_dma_pressure_map()

st.success("Analysis Complete!")
