import streamlit as st
import pydeck as pdk

pdk.settings.mapbox_api_key = "pk.eyJ1IjoicGl2ZXMiLCJhIjoiY204bGVweHY5MTFnZDJscXluOTJ1OHI5OCJ9.3BHtAPkRsjGbwgNykec4VA"

st.title("Quick Map Test")

# Dummy coordinates
lat, lon = -19.118, 146.85

view_state = pdk.ViewState(
    latitude=lat,
    longitude=lon,
    zoom=12,
    pitch=45
)

layer = pdk.Layer(
    "ScatterplotLayer",
    data=[{"position": [lon, lat]}],
    get_position="position",
    get_color=[255, 0, 0],
    get_radius=100,
)

r = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    map_style="mapbox://styles/mapbox/dark-v10",
)

st.pydeck_chart(r)
