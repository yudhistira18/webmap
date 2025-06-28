import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
import numpy as np
from scipy.interpolate import griddata
from PIL import Image
from folium.raster_layers import ImageOverlay
from st_aggrid import AgGrid, GridOptionsBuilder

st.set_page_config(layout="wide")
PASSWORD = "Geomin2025"

# ======================
# Login
# ======================
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def login():
    pwd = st.text_input("Masukkan password:", type="password")
    if st.button("Login"):
        if pwd == PASSWORD:
            st.session_state.authenticated = True
            st.success("Login berhasil!")
        else:
            st.error("Password salah.")

if not st.session_state.authenticated:
    login()
    st.stop()

# ======================
# Load Data
# ======================
st.title("🗺️ Peta & Tabel Titik Bor Hasil Composite")
gdf = gpd.read_file("composite_bor.geojson")

# Pastikan kolom bertipe string
gdf["BHID"] = gdf["BHID"].astype(str)
gdf["Layer"] = gdf["Layer"].astype(str)

# Filter dropdown layer
available_layers = ["All Layers"] + sorted(gdf['Layer'].unique().tolist())
selected_layer = st.selectbox("🔍 Pilih Layer:", options=available_layers)

filtered_gdf = gdf.copy() if selected_layer == "All Layers" else gdf[gdf['Layer'] == selected_layer]

# ======================
# Isograde Ni Interpolasi
# ======================
st.markdown("### 🌀 Isograde Ni (Interpolasi)")

x, y, z = filtered_gdf.geometry.x.values, filtered_gdf.geometry.y.values, filtered_gdf['Ni'].values
overlay_image, bounds = None, None

if selected_layer != "All Layers" and len(z) >= 3:
    xi = np.linspace(x.min(), x.max(), 200)
    yi = np.linspace(y.min(), y.max(), 200)
    xi, yi = np.meshgrid(xi, yi)
    zi = griddata((x, y), z, (xi, yi), method='linear')

    def classify(values):
        c = np.full(values.shape, 0)
        c[(values >= 0.9) & (values < 1.1)] = 1
        c[(values >= 1.1) & (values < 1.6)] = 2
        c[values >= 1.6] = 3
        return c

    class_map = classify(zi)
    colors = {
        0: (160,160,160,150), 1: (189,228,141,150),
        2: (123,210,140,150), 3: (34,139,34,150)
    }
    rgba = np.zeros((class_map.shape[0], class_map.shape[1], 4), dtype=np.uint8)
    for cls, col in colors.items():
        rgba[class_map == cls] = col

    img = Image.fromarray(rgba, mode='RGBA')
    img.save("isograde_overlay.png")
    overlay_image, bounds = img, [[yi.min(), xi.min()], [yi.max(), xi.max()]]
elif selected_layer != "All Layers":
    st.warning("⚠️ Tidak cukup titik untuk interpolasi isograde.")

# ======================
# PETA
# ======================
st.markdown("### 📍 Peta Titik Bor + Isograde")
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
        radius=6, color='red', fill=True, fill_opacity=0.8, popup=popup
    ).add_to(m)

if overlay_image and bounds:
    ImageOverlay(image="isograde_overlay.png", bounds=bounds, opacity=0.6, name="Isograde Ni").add_to(m)

folium.LayerControl().add_to(m)
st_folium(m, use_container_width=True, height=500)

# ======================
# TABEL COMPOSITE
# ======================
st.markdown(f"### 📋 Tabel Composite - Layer: {selected_layer if selected_layer != 'All Layers' else 'Semua'}")

unsur_cols = [
    'BHID', 'Layer', 'From', 'To', 'Thickness', 'Percent',
    'Ni', 'Fe', 'Co', 'MgO', 'Al2O3', 'SiO2', 'LOI'
]

composite_table = pd.DataFrame(filtered_gdf[unsur_cols])
composite_table["BHID"] = composite_table["BHID"].astype(str)
composite_table["Layer"] = composite_table["Layer"].astype(str)

gb = GridOptionsBuilder.from_dataframe(composite_table)
gb.configure_default_column(
    sortable=True,
    resizable=True,
    floatingFilter=True
)
gb.configure_column("BHID", filter="agSetColumnFilter")
gb.configure_column("Layer", filter="agSetColumnFilter")
gb.configure_pagination(paginationAutoPageSize=True)
grid_options = gb.build()

grid_response = AgGrid(
    composite_table,
    gridOptions=grid_options,
    enable_enterprise_modules=False,
    fit_columns_on_grid_load=True,
    theme="streamlit",
    height=400,
    editable=False
)

file_layer_name = selected_layer.lower().replace(" ", "_")
st.download_button(
    label="⬇️ Download CSV Filtered",
    data=grid_response["data"].to_csv(index=False).encode(),
    file_name=f"filtered_composite_{file_layer_name}.csv",
    mime='text/csv'
)

# ======================
# TABEL TOTAL DEPTH
# ======================
st.markdown("### 📏 Tabel Total Depth per BHID")

depth_table = gdf[['BHID', 'Total_Depth', 'XCollar', 'YCollar', 'ZCollar']].drop_duplicates()
depth_table["BHID"] = depth_table["BHID"].astype(str)
depth_table = depth_table.sort_values('BHID')

gb_depth = GridOptionsBuilder.from_dataframe(depth_table)
gb_depth.configure_default_column(
    sortable=True,
    resizable=True,
    floatingFilter=True
)
gb_depth.configure_column("BHID", filter="agSetColumnFilter")
gb_depth.configure_pagination(paginationAutoPageSize=True)
depth_options = gb_depth.build()

AgGrid(
    depth_table,
    gridOptions=depth_options,
    enable_enterprise_modules=False,
    fit_columns_on_grid_load=True,
    theme="streamlit",
    height=350,
    editable=False
)
