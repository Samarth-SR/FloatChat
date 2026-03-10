import streamlit as st
import folium
from streamlit_folium import st_folium

def render_map(map_data):
    lat = map_data.get("lat", 0)
    lon = map_data.get("lon", 0)
    zoom = map_data.get("zoom", 10)

    st.subheader("Map Location")
    m = folium.Map(location=[lat, lon], zoom_start=zoom)
    folium.Marker([lat, lon], tooltip="Location").add_to(m)
    st_folium(m, width=700, height=500)
