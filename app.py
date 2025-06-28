import streamlit as st
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Point
import folium
from streamlit_folium import st_folium
from st_aggrid import AgGrid, GridOptionsBuilder

st.set_page_config(layout="wide")
st.title("📤 Upload & Visualisasi Composite Data")

# =====================
# 1. Upload Excel File
# =====================
uploaded_file = st.file_uploader("Unggah file Excel composite kamu (.xlsx)", type=["xlsx"])

if uploaded_file:
    # =============================
    # 2. Baca Sheet 'Layer_Composite'
    # =============================
    df = pd.read_excel(uploaded_file, sheet_name='Layer_Composite')
    df = df.fillna(0)

    # Pastikan kolom penting tersedia
    if not all(col in df.columns for col in ['BHID', 'Layer', 'From', 'To', 'XCollar', 'YCollar']):
        st.error("Kolom penting tidak ditemukan. Pastikan sheet bernama 'Layer_Composite' dan kolomnya lengkap.")
        st.stop()

    # =============================
    # 3. Tambahkan Layer_Code dan Organic_Limonite
    # =============================
    layer_mapping = {'TP': 100, 'L': 200, 'LO': 250, 'S': 300, 'BR': 400}
    df['Layer_Code'] = df['Layer'].map(layer_mapping)
    df['Layer_Code'] = df['Layer_Code'].fillna(pd.to_numeric(df['Layer'], errors='coerce'))
    df['Organic_Limonite'] = df['Layer_Code'].apply(lambda x: 'LO' if x == 250 else '')

    # =============================
    # 4. Hitung Total_Depth & Percent
    # =============================
    total_depth = df.groupby('BHID')['To'].max().reset_index().rename(columns={'To': 'Total_Depth'})
    df = df.merge(total_depth, on='BHID', how='left')
    df['Percent'] = (df['Thickness'] / df['Total_Depth']) * 100

    # =============================
    # 5. Konversi Koordinat UTM → WGS84
    # =============================
    gdf = df.copy()
    gdf['geometry'] = gdf.apply(lambda row: Point(row['XCollar'], row['YCollar']), axis=1)
    gdf = gpd.GeoDataFrame(gdf, geometry='geometry', crs='EPSG:32751')
    gdf = gdf.to_crs('EPSG:4326')
    gdf['Latitude'] = gdf.geometry.y
    gdf['Longitude'] = gdf.geometry.x

    # =============================
    # 6. Dropdown Layer & BHID
    # =============================
    gdf["BHID"] = gdf["BHID"].astype(str)
    gdf["Layer"] = gdf["Layer"].astype(str)

    selected_layer = st.selectbox("🔍 Pilih Layer:", options=["All Layers"] + sorted(gdf["Layer"].unique()))
    layer_filtered = gdf if selected_layer == "All Layers" else gdf[gdf["Layer"] == selected_layer]

    selected_bhids = st.multiselect("✅ Pilih BHID:", options=sorted(layer_filtered["BHID"].unique()))
    if not selected_bhids:
        filtered_gdf = layer_filtered.copy()
    else:
        filtered_gdf = layer_filtered[layer_filtered["BHID"].isin(selected_bhids)]

    # =============================
    # 7. Peta Titik Bor
    # =============================
    st.markdown("### 🌍 Peta Lokasi Titik Bor")
    m = folium.Map(location=[filtered_gdf.Latitude.mean(), filtered_gdf.Longitude.mean()], zoom_start=12)

    for _, row in filtered_gdf.iterrows():
        popup = (
            f"<b>BHID:</b> {row['BHID']}<br>"
            f"<b>Layer:</b> {row['Layer']}<br>"
            f"<b>Ni:</b> {row['Ni']:.2f}<br>"
            f"<b>Fe:</b> {row['Fe']:.2f}"
        )
        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=6,
            color='green',
            fill=True,
            fill_opacity=0.8,
            popup=popup
        ).add_to(m)

    st_folium(m, use_container_width=True, height=450)

    # =============================
    # 8. Tabel Composite
    # =============================
    st.markdown("### 📋 Tabel Data Composite")

    display_cols = [
        'BHID', 'Layer', 'From', 'To', 'Thickness', 'Percent',
        'Ni', 'Fe', 'Co', 'MgO', 'Al2O3', 'SiO2', 'LOI', 'Organic_Limonite'
    ]

    table_df = filtered_gdf[display_cols].copy()

    gb = GridOptionsBuilder.from_dataframe(table_df)
    gb.configure_default_column(sortable=True, resizable=True, floatingFilter=True)
    gb.configure_pagination()
    grid_options = gb.build()

    AgGrid(
        table_df,
        gridOptions=grid_options,
        enable_enterprise_modules=False,
        theme="streamlit",
        height=400,
    )

    # =============================
    # 9. Tombol Download GeoJSON
    # =============================
    geo_out = filtered_gdf[['BHID', 'Layer', 'Ni', 'Fe', 'geometry']]
    geo_out = gpd.GeoDataFrame(geo_out, geometry='geometry', crs='EPSG:4326')
    geojson_bytes = geo_out.to_json().encode('utf-8')

    st.download_button("⬇️ Download GeoJSON", data=geojson_bytes, file_name="composite.geojson", mime="application/geo+json")
