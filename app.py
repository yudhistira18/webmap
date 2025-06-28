import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import folium_static

st.set_page_config(layout="wide")
st.title("Peta & Tabel Titik Bor Hasil Composite")

# Load GeoJSON
gdf = gpd.read_file("composite_bor.geojson")

# Dropdown filter layer
available_layers = sorted(gdf['Layer'].unique().tolist())
selected_layer = st.selectbox("Pilih Layer yang ingin ditampilkan:", options=available_layers)

# Filter data berdasarkan pilihan layer
filtered_gdf = gdf[gdf['Layer'] == selected_layer]

# Buat peta folium
m = folium.Map(location=[filtered_gdf.geometry.y.mean(), filtered_gdf.geometry.x.mean()], zoom_start=12)

for _, row in filtered_gdf.iterrows():
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

# =========================================
# TAMPILKAN TABEL COMPOSITE PER LAYER
# =========================================

st.subheader("📋 Tabel Data Composite - Layer: " + selected_layer)

# Kolom penting unsur dan info
unsur_cols = [
    'BHID', 'Layer', 'From', 'To', 'Thickness', 'Percent',
    'Ni', 'Co', 'Fe', 'Fe2O3', 'FeO', 'SiO2', 'MgO', 'Al2O3'
]

composite_table = pd.DataFrame(filtered_gdf[unsur_cols])
st.dataframe(composite_table.style.format(precision=2), use_container_width=True)

# =========================================
# TABEL TOTAL DEPTH PER BHID
# =========================================

st.subheader("📏 Total Depth per BHID")
total_depth_table = gdf[['BHID', 'Total_Depth', 'XCollar', 'YCollar', 'ZCollar']].drop_duplicates()
st.dataframe(total_depth_table.sort_values('BHID'), use_container_width=True)
