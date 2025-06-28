import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
import io
import branca.colormap as cm

st.set_page_config(layout="wide")

# ======================
# Password sederhana
# ======================
PASSWORD = "Geomin2025"  # ganti dengan password kamu

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
# Load data setelah login
# ======================
st.title("🗺️ Peta & Tabel Titik Bor Hasil Composite")

# Load GeoJSON hasil export dari GEE
gdf = gpd.read_file("composite_bor.geojson")

# Dropdown filter berdasarkan layer
available_layers = sorted(gdf['Layer'].unique().tolist())
selected_layer = st.selectbox("🔍 Pilih Layer:", options=available_layers)

# Filter berdasarkan layer
filtered_gdf = gdf[gdf['Layer'] == selected_layer]

# =======================
# Tambahan Filter Ni Grade
# =======================
st.markdown("### 🎚️ Filter Kadar Nikel (Ni)")
min_ni = float(filtered_gdf['Ni'].min())
max_ni = float(filtered_gdf['Ni'].max())
ni_threshold = st.slider(
    "Tampilkan hanya titik dengan Ni ≥ ...", 
    min_value=round(min_ni, 2), 
    max_value=round(max_ni, 2), 
    value=1.8, step=0.05
)

# Terapkan filter Ni
filtered_gdf = filtered_gdf[filtered_gdf['Ni'] >= ni_threshold]

# =======================
# Peta folium
# =======================
m = folium.Map(
    location=[filtered_gdf.geometry.y.mean(), filtered_gdf.geometry.x.mean()],
    zoom_start=12
)

# Colormap berdasarkan Ni
colormap = cm.linear.YlOrRd_09.scale(min_ni, max_ni)
colormap.caption = 'Kadar Ni'

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
        color=colormap(row['Ni']),
        fill=True,
        fill_opacity=0.8,
        popup=popup
    ).add_to(m)

m.add_child(colormap)

# Tampilkan peta di Streamlit
st_data = st_folium(m, use_container_width=True)

# =======================
# TABEL COMPOSITE PER LAYER
# =======================
st.subheader(f"📋 Tabel Data Composite - Layer: {selected_layer} (Ni ≥ {ni_threshold})")

unsur_cols = [
    'BHID', 'Layer', 'From', 'To', 'Thickness', 'Percent',
    'Ni', 'Fe', 'Co', 'MgO', 'Al2O3', 'SiO2', 'LOI'
]

composite_table = pd.DataFrame(filtered_gdf[unsur_cols])
st.dataframe(composite_table.style.format(precision=2), use_container_width=True)

# Tombol download CSV
csv_buffer = io.StringIO()
composite_table.to_csv(csv_buffer, index=False)
csv_bytes = csv_buffer.getvalue().encode()

st.download_button(
    label="⬇️ Download CSV Data Composite",
    data=csv_bytes,
    file_name=f"composite_layer_{selected_layer}_Ni{ni_threshold}.csv",
    mime='text/csv'
)

# =======================
# TABEL TOTAL DEPTH
# =======================
st.subheader("📏 Total Depth per BHID")
depth_table = gdf[['BHID', 'Total_Depth', 'XCollar', 'YCollar', 'ZCollar']].drop_duplicates()
st.dataframe(depth_table.sort_values('BHID'), use_container_width=True)
