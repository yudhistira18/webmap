import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from io import BytesIO
from pyproj import Transformer

st.set_page_config(layout="wide")
st.title("🗂️ Composite Data Bor + Koordinat UTM ke WGS84")

unsur = [
    'Ni', 'Co', 'Fe2O3', 'Fe', 'FeO', 'SiO2', 'CaO', 'MgO', 'MnO',
    'Cr2O3', 'Al2O3', 'P2O5', 'TiO2', 'SO3', 'LOI', 'Total Oksida ', 'MC'
]

layer_mapping = {'TP': 100, 'L': 200, 'LO': 250, 'S': 300, 'BR': 400}

uploaded_file = st.file_uploader("Upload file Excel bor (.xlsx)", type=["xlsx"])
if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)

    if 'Thickness' not in df.columns and 'From' in df.columns and 'To' in df.columns:
        df['Thickness'] = df['To'] - df['From']

    required_cols = ['BHID', 'From', 'To', 'Layer', 'Thickness', 'X', 'Y', 'XCollar', 'YCollar', 'ZCollar'] + unsur
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        st.error(f"File tidak memiliki kolom berikut: {missing_cols}")
        st.stop()

    df = df[required_cols].copy()
    df = df.dropna(subset=['BHID', 'Layer', 'Thickness', 'X', 'Y'])
    df = df[df['Thickness'] > 0]

    # Spinner & progress bar saat compositing
    with st.spinner("⏳ Sedang memproses composite per BHID dan Layer..."):
        progress = st.progress(0, text="Memulai komposit data...")

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

        groups = df.groupby(['BHID', 'Layer'])
        total_groups = len(groups)
        composite_rows = []

        for i, ((bhid, layer), group) in enumerate(groups):
            result = weighted_avg(group)
            composite_rows.append([bhid, layer] + list(result))
            progress.progress((i + 1) / total_groups, text=f"Proses {i+1}/{total_groups} — BHID: {bhid}, Layer: {layer}")

        composite = pd.DataFrame(composite_rows)
        composite.columns = ['BHID', 'Layer'] + list(weighted_avg(df.iloc[0:1]).index)

    progress.empty()
    st.success("✅ Proses compositing selesai!")

    # Tambah info lanjutan
    composite['Layer_Code'] = composite['Layer'].map(layer_mapping)
    composite['Layer_Code'] = composite['Layer_Code'].fillna(pd.to_numeric(composite['Layer'], errors='coerce'))

    depth = df.groupby('BHID')['To'].max().reset_index()
    depth.columns = ['BHID', 'Total_Depth']
    composite = composite.merge(depth, on='BHID', how='left')
    composite['Percent'] = (composite['Thickness'] / composite['Total_Depth']) * 100
    composite['Organic_Limonite'] = composite['Layer_Code'].apply(lambda x: 'LO' if x == 250 else '')

    # Konversi koordinat UTM 51S → WGS84
    transformer = Transformer.from_crs("EPSG:32751", "EPSG:4326", always_xy=True)
    lon_lat = composite.apply(lambda row: transformer.transform(row["XCollar"], row["YCollar"]), axis=1)
    composite["Longitude"] = lon_lat.apply(lambda x: x[0])
    composite["Latitude"] = lon_lat.apply(lambda x: x[1])

    # Urutkan kolom
    cols_order = ['BHID', 'XCollar', 'YCollar', 'ZCollar', 'Longitude', 'Latitude'] + \
                 [col for col in composite.columns if col not in ['BHID', 'XCollar', 'YCollar', 'ZCollar', 'Longitude', 'Latitude', 'Organic_Limonite']] + ['Organic_Limonite']
    composite = composite[cols_order]

    st.markdown("### 📋 Tabel Composite")
    st.dataframe(composite, use_container_width=True)

    # Peta
    st.markdown("### 🗺️ Peta Titik Bor")
    if not composite.empty:
        m = folium.Map(
            location=[composite['Latitude'].mean(), composite['Longitude'].mean()],
            zoom_start=12
        )
        for _, row in composite.iterrows():
            popup = (
                f"<b>BHID:</b> {row['BHID']}<br>"
                f"<b>Layer:</b> {row['Layer']}<br>"
                f"<b>Ni:</b> {row['Ni']:.2f}<br>"
                f"<b>Thickness:</b> {row['Thickness']:.2f} m<br>"
                f"<b>Percent:</b> {row['Percent']:.2f} %"
            )
            folium.CircleMarker(
                location=[row['Latitude'], row['Longitude']],
                radius=6,
                color='green',
                fill=True,
                fill_opacity=0.7,
                popup=popup
            ).add_to(m)

        st_folium(m, height=450, use_container_width=True)

    # Tombol download
    st.markdown("### 💾 Download Hasil")
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        composite.to_excel(writer, sheet_name='Layer_Composite', index=False)
        depth.to_excel(writer, sheet_name='Total_Depth', index=False)
    st.download_button(
        label="⬇️ Download Excel",
        data=output.getvalue(),
        file_name="composite_with_coords.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Silakan upload file Excel terlebih dahulu.")
