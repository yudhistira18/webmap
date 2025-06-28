import streamlit as st
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import folium
from streamlit_folium import st_folium
from io import BytesIO
import tempfile

# ========== Konfigurasi ==========
st.set_page_config(layout="wide")
st.title("🛠️ Composite Data Bor + Clean Excel + Koordinat + Peta")

unsur = [
    'Ni', 'Co', 'Fe2O3', 'Fe', 'FeO', 'SiO2', 'CaO', 'MgO', 'MnO',
    'Cr2O3', 'Al2O3', 'P2O5', 'TiO2', 'SO3', 'LOI', 'Total Oksida ', 'MC'
]
layer_mapping = {'TP': 100, 'L': 200, 'LO': 250, 'S': 300, 'BR': 400}

# ========== Upload File ==========
uploaded_file = st.file_uploader("📤 Upload file Excel bor (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(uploaded_file.read())
        temp_path = tmp.name

    # ========== STEP 1: CLEAN EXCEL ==========
    st.subheader("🧼 Step 1: Membersihkan Formatting Excel")
    progress1 = st.progress(0, text="📄 Membaca dan membersihkan file Excel...")
    raw_excel = pd.read_excel(temp_path, sheet_name=None)

    cleaned_buffer = BytesIO()
    wb = Workbook()
    wb.remove(wb.active)

    sheet_count = len(raw_excel)
    for i, (sheet_name, df) in enumerate(raw_excel.items()):
        ws = wb.create_sheet(title=sheet_name)
        for row in dataframe_to_rows(df, index=False, header=True):
            ws.append(row)
        progress1.progress((i + 1) / sheet_count, text=f"🧹 Membersihkan sheet: {sheet_name}")

    wb.save(cleaned_buffer)
    cleaned_buffer.seek(0)
    progress1.empty()
    st.success("✅ File berhasil dibersihkan dari formatting dan extension.")

    # ========== STEP 2: LOAD DAN VALIDASI ==========
    df = pd.read_excel(cleaned_buffer, sheet_name=0)

    if 'Thickness' not in df.columns and 'From' in df.columns and 'To' in df.columns:
        df['Thickness'] = df['To'] - df['From']

    required_cols = ['BHID', 'From', 'To', 'Layer', 'Thickness', 'X', 'Y',
                     'XCollar', 'YCollar', 'ZCollar'] + unsur
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        st.error(f"❌ Kolom berikut tidak ditemukan: {missing}")
        st.stop()

    df = df[required_cols].copy()
    df = df.dropna(subset=['BHID', 'Layer', 'Thickness', 'X', 'Y'])
    df = df[df['Thickness'] > 0]

    # ========== STEP 3: COMPOSITING ==========
    st.subheader("🔁 Step 2: Compositing per BHID + Layer")
    progress2 = st.progress(0, text="🔄 Proses composite...")

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

    composite_rows = []
    grouped = df.groupby(['BHID', 'Layer'])
    for i, ((bhid, layer), group) in enumerate(grouped):
        composite_rows.append([bhid, layer] + list(weighted_avg(group)))
        progress2.progress((i + 1) / len(grouped), text=f"⛏️ Composite: {bhid} - {layer}")
    progress2.empty()

    composite = pd.DataFrame(composite_rows)
    composite.columns = ['BHID', 'Layer'] + list(weighted_avg(df.iloc[0:1]).index)

    composite['Layer_Code'] = composite['Layer'].map(layer_mapping)
    composite['Layer_Code'] = composite['Layer_Code'].fillna(pd.to_numeric(composite['Layer'], errors='coerce'))

    depth = df.groupby('BHID')['To'].max().reset_index()
    depth.columns = ['BHID', 'Total_Depth']
    composite = composite.merge(depth, on='BHID', how='left')
    composite['Percent'] = (composite['Thickness'] / composite['Total_Depth']) * 100
    composite['Organic_Limonite'] = composite['Layer_Code'].apply(lambda x: 'LO' if x == 250 else '')

    # ========== STEP 4: KONVERSI KOORDINAT ==========
    st.subheader("📍 Step 3: Konversi Koordinat UTM 51S → WGS84")
    geo_df = gpd.GeoDataFrame(
        composite,
        geometry=gpd.points_from_xy(composite['XCollar'], composite['YCollar']),
        crs='EPSG:32751'
    )
    geo_df = geo_df.to_crs('EPSG:4326')
    composite['Longitude'] = geo_df.geometry.x
    composite['Latitude'] = geo_df.geometry.y

    # ========== STEP 5: TABEL & PETA ==========
    st.subheader("📋 Tabel Hasil Composite")
    st.dataframe(composite, use_container_width=True)

    st.subheader("🗺️ Peta Titik Bor")
    if not composite.empty:
        m = folium.Map(
            location=[composite['Latitude'].mean(), composite['Longitude'].mean()],
            zoom_start=12
        )
        for _, row in composite.iterrows():
            folium.CircleMarker(
                location=[row['Latitude'], row['Longitude']],
                radius=5,
                color='blue',
                fill=True,
                fill_opacity=0.7,
                popup=folium.Popup(
                    f"<b>BHID:</b> {row['BHID']}<br><b>Layer:</b> {row['Layer']}<br><b>Ni:</b> {row['Ni']:.2f}",
                    max_width=300
                )
            ).add_to(m)
        st_folium(m, height=400, use_container_width=True)

    # ========== STEP 6: UNDUH HASIL ==========
    st.subheader("💾 Unduh Excel (Semua Sheet)")
    summary_table = composite[['BHID', 'XCollar', 'YCollar', 'ZCollar', 'Total_Depth']].drop_duplicates()
    summary_table = summary_table.sort_values(by='BHID')

    out_buffer = BytesIO()
    with pd.ExcelWriter(out_buffer, engine='openpyxl') as writer:
        composite.to_excel(writer, sheet_name='Layer_Composite', index=False)
        depth.to_excel(writer, sheet_name='Total_Depth', index=False)
        summary_table.to_excel(writer, sheet_name='Koordinat_Collar', index=False)

    st.download_button(
        label="⬇️ Download Excel (Composite + Semua Sheet)",
        data=out_buffer.getvalue(),
        file_name="composite_output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # ========== STEP 7: TABEL KOORDINAT COLLAR ==========
    st.subheader("📏 Tabel Koordinat Collar (UTM) + Total Kedalaman")
    st.dataframe(summary_table, use_container_width=True)

else:
    st.info("Silakan upload file Excel terlebih dahulu.")
