import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
import io
import numpy as np
from scipy.interpolate import griddata
import matplotlib.pyplot as plt
from PIL import Image
from folium.raster_layers import ImageOverlay

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
# Interpolasi dan Buat Overlay Gambar Isograde
# =======================
st.subheader("🌀 Isograde Ni (Interaktif di Peta)")

x = filtered_gdf.geometry.x.values
y = filtered_gdf.geometry.y.values
z = filtered_gdf['Ni'].values

overlay_image = None
bounds = None

if len(z) >= 3:
    xi = np.linspace(x.min(), x.max(), 200)
    yi = np.linspace(y.min(), y.max(), 200)
    xi, yi = np.meshgrid(xi, yi)
    zi = griddata((x, y), z, (xi, yi), method='linear')

    def classify_isograde(values):
        classes = np.full(values.shape, 0)
        classes[(values >= 0.9) & (values < 1.1)] = 1
        classes[(values >= 1.1) & (values < 1.6)] = 2
        classes[(values >= 1.6)] = 3
        return classes

    class_map = classify_isograde(zi)

    # Warna kelas:
    colors = {
        0: (160, 160, 160, 150),   # abu-abu < 0.9
        1: (189, 228, 141, 150),   # kuning kehijauan
        2: (123, 210, 140, 150),   # hijau muda
        3: (34, 139, 34, 150),     # hijau pekat
    }

    rgba_img = np.zeros((class_map.shape[0], class_map.shape[1], 4), dtype=np.uint8)
    for cls, color in colors.items():
        rgba_img[class_map == cls] = color

    img = Image.fromarray(rgba_img, mode='RGBA')
    img.save("isograde_overlay.png")
    overlay_image = img
    bounds = [[yi.min(), xi.min()], [yi.max(), xi.max()]]
else:
    st.warning("⚠️ Tidak cukup titik untuk interpolasi isograde.")

# =======================
# PETA FOLIUM TITIK BOR + OVERLAY
# =======================
st.subheader("📍 Peta Titik Bor dan Isograde")

m = folium.Map(
    location=[filtered_gdf.geometry.y.mean(), filtered_gdf.geometry.x.mean()],
    zoom_start=12
)

# Tambahkan titik bor
for _, row in filtered_gdf.iterrows():
    popup = (
        f"<b>BHID:</b> {row['BHID']}<br>"
        f"<b>Layer:</b> {row['Layer']}<br>"
