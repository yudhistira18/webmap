import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
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
# Load GeoData
# ======================
st.title("🗺️ Peta & Tabel Titik Bor Hasil Composite")
gdf = gpd.read_file("composite_bor.geojson")

# Pastikan BHID & Layer string
gdf["BHID"] = gdf["BHID"].astype(str)
gdf["Layer"] = gdf["Layer"].astype(str)

# ======================
# Filter Layer Dropdown
# ======================
available_layers = ["All Layers"] + sorted(gdf["Layer"].unique())
selected_layer = st.selectbox("🔍 Pilih Layer:", options=available_layers)
filtered_gdf = gdf if selected_layer == "All Layers" else gdf[gdf["Layer"] == selected_layer]

# ======================
# Peta Titik Bor
# ======================
st.markdown("### 📍 Peta Titik Bor")
m = folium.Map(
    location=[filtered_gdf.geometry.y.mean(), filtered_gdf.geometry.x.mean()],
    zoom_start=12
)
for _, row in filtered_gdf.iterrows():
    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=6,
        color='red',
        fill=True,
        fill_opacity=0.8,
        popup=f"<b>BHID:</b> {row['BHID']}<br><b>Layer:</b> {row['Layer']}<br><b>Ni:</b> {row['Ni']:.2f}"
    ).add_to(m)
st_data = st_folium(m, use_container_width=True, height=450)

# ======================
# TABEL COMPOSITE
# ======================
st.markdown("### 📋 Tabel Composite")

unsur_cols = [
    'BHID', 'Layer', 'From', 'To', 'Thickness', 'Percent',
    'Ni', 'Fe', 'Co', 'MgO', 'Al2O3', 'SiO2', 'LOI'
]
composite_table = pd.DataFrame(filtered_gdf[unsur_cols]).copy()
composite_table = composite_table.dropna(subset=["BHID", "Layer"])
composite_table["BHID"] = composite_table["BHID"].astype(str)
composite_table["Layer"] = composite_table["Layer"].astype(str)

gb = GridOptionsBuilder.from_dataframe(composite_table)
gb.configure_default_column(sortable=True, resizable=True, floatingFilter=True)
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

st.download_button(
    label="⬇️ Download CSV Filtered",
    data=grid_response["data"].to_csv(index=False).encode(),
    file_name=f"composite_filtered_{selected_layer.lower().replace(' ', '_')}.csv",
    mime="text/csv"
)

# ======================
# TABEL TOTAL DEPTH
# ======================
st.markdown("### 📏 Tabel Total Kedalaman per BHID")

depth_table = gdf[['BHID', 'Total_Depth', 'XCollar', 'YCollar', 'ZCollar']].drop_duplicates()
depth_table = depth_table.dropna(subset=["BHID"])
depth_table["BHID"] = depth_table["BHID"].astype(str)
depth_table = depth_table.sort_values("BHID")

gb_depth = GridOptionsBuilder.from_dataframe(depth_table)
gb_depth.configure_default_column(sortable=True, resizable=True, floatingFilter=True)
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

