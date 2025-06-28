import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium  # gunakan st_folium (recommended)

st.set_page_config(layout="wide")
st.title("🗺️ Peta & Tabel Titik Bor Hasil Composite")

# Load GeoJSON hasil export dari GEE
gdf = gpd.read_file("composite_bor.geojson")

# Dropdown filter berdasarkan layer
available_layers = sorted(gdf['Layer'].unique().tolist())
selected_layer = st.selectbox("🔍 Pilih Layer:", options=available_layers)

# Filter data berdasarkan layer yang dipilih
filtered_gdf = gdf[gdf['Layer'] == selected_layer]

# Peta folium
m = folium.Map(
    location=[filtered_gdf.geometry.y.mean(), filtered_gdf.geometry.x.mean()],
    zoom_start=12
)

# Tambahkan marker ke peta
for _, row in filtered_gdf.iterrows():
    popup = (
        f"<b>BHID:</b> {row['BHID']}<br>"
        f"<b>Layer:</b> {row['Layer']}<br>"
        f"<b>Ni:</b> {row['Ni']:.2f}<br>"
        f"<b>Fe:</b> {row['Fe']:.2f}"
    )
    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=6,
        color='red',
        fill=True,
        fill_opacity=0.8,
        popup=popup
    ).add_to(m)

# Tampilkan peta di Streamlit
st_data = st_folium(m, use_container_width=True)

# =======================
# TABEL COMPOSITE PER LAYER
# =======================
st.subheader(f"📋 Tabel Data Composite - Layer: {selected_layer}")

unsur_cols = [
    'BHID', 'Layer', 'From', 'To', 'Thickness', 'Percent',
    'Ni', 'Fe', 'Co', 'MgO', 'Al2O3', 'SiO2', 'LOI'
]

composite_table = pd.DataFrame(filtered_gdf[unsur_cols])
st.dataframe(composite_table.style.format(precision=2), use_container_width=True)

# =======================
# TABEL TOTAL DEPTH
# =======================
st.subheader("📏 Total Depth per BHID")
depth_table = gdf[['BHID', 'Total_Depth', 'XCollar', 'YCollar', 'ZCollar']].drop_duplicates()
st.dataframe(depth_table.sort_values('BHID'), use_container_width=True)

