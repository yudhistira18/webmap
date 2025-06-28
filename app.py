import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import folium_static

st.set_page_config(layout="wide")
st.title("Peta Titik Bor Hasil Composite")

# Load GeoJSON
gdf = gpd.read_file("composite_bor.geojson")

# Buat peta folium
m = folium.Map(location=[gdf.geometry.y.mean(), gdf.geometry.x.mean()], zoom_start=12)

# Tambahkan titik ke peta
for _, row in gdf.iterrows():
    popup = (
        f"<b>BHID:</b> {row['BHID']}<br>"
        f"<b>Layer:</b> {row['Layer']}<br>"
        f"<b>Ni:</b> {row['Ni']:.2f}<br>"
    )
    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=6,
        color='red',
        fill=True,
        fill_opacity=0.8,
        popup=popup
    ).add_to(m)

folium_static(m)
