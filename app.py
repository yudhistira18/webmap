import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
import io
from scipy.interpolate import griddata
import numpy as np
import matplotlib.pyplot as plt

st.set_page_config(layout="wide")

# ======================
# Password sederhana
# ======================
PASSWORD = "Geomin2025"

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def login():
    pwd = st.text_input("Masukkan password untuk mengakses aplikasi:", type="password")
    if st.button("Login"):
        if pwd == PASSWORD:
            st.session_state.authenticated = True
            st.success("Login berhasil!")
        else:
            st.error("Password salah, coba lagi.")

if not st.session_state.authenticated:
    login()
    st.stop()

# ======================
# App utama
# ======================
st.title("🗺️ Peta & Tabel Titik Bor Hasil Composite")

# Load GeoJSON
gdf = gpd.read_file("composite_bor.geojson")

# Dropdown layer
available_layers = sorted(gdf['Layer'].unique().tolist())
selected_layer = st.selectbox("🔍 Pilih Layer:", options=available_layers)

# Filter berdasarkan layer
filtered_gdf = gdf[gdf['Layer'] == selected_layer]

# =======================
# PETA ISOGRADE Ni
# =======================
st.subheader("🌀 Peta Isograde (Interpolasi Ni)")

x = filtered_gdf.geometry.x.values
y = filtered_gdf.geometry.y.values
z = filtered_gdf['Ni'].values

if len(z) >= 3:
    xi = np.linspace(x.min(), x.max(), 100)
    yi = np.linspace(y.min(), y.max(), 100)
    xi, yi = np.meshgrid(xi, yi)
    zi = griddata((x, y), z, (xi, yi), method='linear')

    fig, ax = plt.subplots(figsize=(8, 6))
    contour = ax.contourf(xi, yi, zi, levels=15, cmap='YlOrRd')
    scatter = ax.scatter(x, y, c='black', s=10, label='Titik Bor')
    ax.set_title(f'Isograde Ni - Layer {selected_layer}')
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.legend()
    fig.colorbar(contour, ax=ax, label='Kadar Ni (%)')

    st.pyplot(fig)
else:
    st.warning("⚠️ Tidak cukup titik (min. 3) untuk interpolasi isograde.")

# =======================
# PETA FOLIUM TITIK BOR
# =======================
st.subheader("📍 Peta Titik Bor")
m = folium.Map(
    location=[filtered_gdf.geometry.y.mean(), filtered_gdf.geometry.x.mean()],
    zoom_start=12
)

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

st_data = st_folium(m, use_container_width=True)

# =======================
# TABEL COMPOSITE
# =======================
st.subheader(f"📋 Tabel Data Composite - Layer: {selected_layer}")
unsur_cols = [
    'BHID', 'Layer', 'From', 'To', 'Thickness', 'Percent',
    'Ni', 'Fe', 'Co', 'MgO', 'Al2O3', 'SiO2', 'LOI'
]
composite_table = pd.DataFrame(filtered_gdf[unsur_cols])
st.dataframe(composite_table.style.format(precision=2), use_container_width=True)

# Tombol Download CSV
csv_buffer = io.StringIO()
composite_table.to_csv(csv_buffer, index=False)
st.download_button(
    label="⬇️ Download CSV",
    data=csv_buffer.getvalue().encode(),
    file_name=f"composite_layer_{selected_layer}.csv",
    mime='text/csv'
)

# =======================
# TABEL TOTAL DEPTH
# =======================
st.subheader("📏 Total Depth per BHID")
depth_table = gdf[['BHID', 'Total_Depth', 'XCollar', 'YCollar', 'ZCollar']].drop_duplicates()
st.dataframe(depth_table.sort_values('BHID'), use_container_width=True)
