import streamlit as st
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Point
import folium
from streamlit_folium import st_folium
from st_aggrid import AgGrid, GridOptionsBuilder

st.set_page_config(layout="wide")
st.title("🧪 Komposit & Visualisasi Eksplorasi")

uploaded_file = st.file_uploader("📁 Upload file Excel eksplorasi (sheet: data mentah)", type=["xlsx"])
if not uploaded_file:
    st.info("Silakan upload file Excel mentah hasil eksplorasi.")
    st.stop()

progress = st.progress(0, text="🚀 Memulai...")

# STEP 1: Baca data
progress.progress(10, text="📖 Membaca Excel...")
df = pd.read_excel(uploaded_file)

unsur = [
    'Ni', 'Co', 'Fe2O3', 'Fe', 'FeO', 'SiO2', 'CaO', 'MgO', 'MnO',
    'Cr2O3', 'Al2O3', 'P2O5', 'TiO2', 'SO3', 'LOI', 'Total Oksida ', 'MC'
]

cols = ['BHID', 'From', 'To', 'Layer', 'Thickness', 'X', 'Y',
        'XCollar', 'YCollar', 'ZCollar'] + unsur
df = df[cols].copy()
df = df.dropna(subset=['BHID', 'Layer', 'Thickness', 'X', 'Y'])
df = df[df['Thickness'] > 0]

# STEP 2: Compositing
progress.progress(30, text="🔁 Compositing per BHID dan Layer...")

def weighted_avg(group):
    result = {
        'From': group['From'].min(),
        'To': group['To'].max(),
        'Thickness': group['Thickness'].sum()
    }
    for u in unsur:
        if group[u].notna().any():
            result[u] = np.average(group[u], weights=group['Thickness'])
        else:
            result[u] = np.nan
    result['X'] = group['X'].iloc[0]
    result['Y'] = group['Y'].iloc[0]
    result['XCollar'] = group['XCollar'].iloc[0]
    result['YCollar'] = group['YCollar'].iloc[0]
    result['ZCollar'] = group['ZCollar'].iloc[0]
    return pd.Series(result)

composite_df = df.groupby(['BHID', 'Layer']).apply(weighted_avg).reset_index()

# STEP 3: Layer mapping & percent
progress.progress(50, text="📏 Hitung Total Depth dan Persentase...")

layer_mapping = {'TP': 100, 'L': 200, 'LO': 250, 'S': 300, 'BR': 400}
composite_df['Layer_Code'] = composite_df['Layer'].map(layer_mapping)
composite_df['Layer_Code'] = composite_df['Layer_Code'].fillna(
    pd.to_numeric(composite_df['Layer'], errors='coerce'))

depth_df = df.groupby('BHID')['To'].max().reset_index()
depth_df.columns = ['BHID', 'Total_Depth']
composite_df = composite_df.merge(depth_df, on='BHID', how='left')
composite_df['Percent'] = (composite_df['Thickness'] / composite_df['Total_Depth']) * 100
composite_df['Organic_Limonite'] = composite_df['Layer_Code'].apply(lambda x: 'LO' if x == 250 else '')

# STEP 4: Konversi ke WGS84
progress.progress(70, text="🌍 Konversi Koordinat UTM ke WGS84...")

geo_df = gpd.GeoDataFrame(
    composite_df,
    geometry=gpd.points_from_xy(composite_df["XCollar"], composite_df["YCollar"]),
    crs="EPSG:32751"
)
geo_df = geo_df.to_crs("EPSG:4326")
composite_df["Longitude"] = geo_df.geometry.x
composite_df["Latitude"] = geo_df.geometry.y
composite_df["geometry"] = geo_df.geometry

# STEP 5: Filter Layer dan BHID
progress.progress(85, text="📌 Menyusun Tampilan...")

available_layers = ["All Layers"] + sorted(composite_df["Layer"].astype(str).unique())
selected_layer = st.selectbox("🔍 Pilih Layer:", available_layers)
layer_filtered = composite_df if selected_layer == "All Layers" else composite_df[composite_df["Layer"] == selected_layer]
available_bhids = sorted(layer_filtered["BHID"].astype(str).unique())
selected_bhids = st.multiselect("✅ Pilih BHID:", available_bhids)
filtered_df = layer_filtered if not selected_bhids else layer_filtered[layer_filtered["BHID"].isin(selected_bhids)]

# STEP 6: Peta
st.markdown("### 🗺️ Peta Titik Bor")
if not filtered_df.empty:
    m = folium.Map(location=[filtered_df["Latitude"].mean(), filtered_df["Longitude"].mean()], zoom_start=12)
    for _, row in filtered_df.iterrows():
        popup = f"<b>BHID:</b> {row['BHID']}<br><b>Layer:</b> {row['Layer']}<br><b>Ni:</b> {row.get('Ni', 0):.2f}"
        folium.CircleMarker(location=[row['Latitude'], row['Longitude']], radius=5, color='red', fill=True, fill_opacity=0.8, popup=popup).add_to(m)
    st_folium(m, use_container_width=True, height=450)
else:
    st.warning("Tidak ada data yang cocok untuk ditampilkan di peta.")

# STEP 7: Tabel Composite
st.markdown("### 📋 Tabel Composite")
unsur_cols = ['BHID', 'Layer', 'From', 'To', 'Thickness', 'Percent', 'Ni', 'Fe', 'Co', 'MgO', 'Al2O3', 'SiO2', 'LOI']
composite_table = filtered_df[unsur_cols].copy()
gb = GridOptionsBuilder.from_dataframe(composite_table)
gb.configure_default_column(sortable=True, resizable=True, floatingFilter=True)
gb.configure_pagination()
AgGrid(composite_table, gridOptions=gb.build(), theme="streamlit", height=400, fit_columns_on_grid_load=True)

st.download_button("⬇️ Download CSV (Filtered)", composite_table.to_csv(index=False).encode(), "composite_filtered.csv", "text/csv")

# STEP 8: Tabel Total Kedalaman
st.markdown("### 📏 Tabel Total Depth")
depth_filtered = depth_df[depth_df["BHID"].isin(filtered_df["BHID"].unique())].copy()
gb2 = GridOptionsBuilder.from_dataframe(depth_filtered)
gb2.configure_default_column(sortable=True, resizable=True, floatingFilter=True)
gb2.configure_pagination()
AgGrid(depth_filtered, gridOptions=gb2.build(), theme="streamlit", height=300, fit_columns_on_grid_load=True)

# STEP 9: Tabel Koordinat Collar
st.markdown("### 📍 Tabel Koordinat Collar (UTM) + Kedalaman")
coord_table = filtered_df[['BHID', 'XCollar', 'YCollar', 'ZCollar']].drop_duplicates()
coord_table = coord_table.merge(depth_df, on='BHID', how='left')
gb3 = GridOptionsBuilder.from_dataframe(coord_table)
gb3.configure_default_column(sortable=True, resizable=True, floatingFilter=True)
gb3.configure_pagination()
AgGrid(coord_table, gridOptions=gb3.build(), theme="streamlit", height=300, fit_columns_on_grid_load=True)

progress.progress(100, text="✅ Selesai! Aplikasi siap digunakan.")
