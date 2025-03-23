import streamlit as st
import pydeck as pdk
import pandas as pd

# Mapbox Token
pdk.settings.mapbox_api_key = "pk.eyJ1IjoicGl2ZXMiLCJhIjoiY204bGVweHY5MTFnZDJscXluOTJ1OHI5OCJ9.3BHtAPkRsjGbwgNykec4VA"

# Simple test data
df = pd.DataFrame({
    'lat': [-19.1127],
    'lon': [146.854]
})

# View
view = pdk.ViewState(
    latitude=df["lat"][0],
    longitude=df["lon"][0],
    zoom=14,
    pitch=40
)

# Layer
layer = pdk.Layer(
    "ScatterplotLayer",
    data=df,
    get_position='[lon, lat]',
    get_color='[200, 30, 0, 160]',
    get_radius=50
)

# Deck
r = pdk.Deck(
    layers=[layer],
    initial_view_state=view,
    map_style="mapbox://styles/mapbox/dark-v10",
    tooltip={"text": "Test Point"},
)

st.pydeck_chart(r)
