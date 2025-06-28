import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from st_aggrid import AgGrid, GridOptionsBuilder
from io import BytesIO

st.set_page_config(layout="wide")
st.title("🗂️ Upload & Compositing Data Bor tanpa geopandas")

unsur = [
    'Ni', 'Co', 'Fe2O3', 'Fe', 'FeO', 'SiO2', 'CaO', 'MgO', 'MnO',
    'Cr2O3', 'Al2O3', 'P2O5', 'TiO2', 'SO3', 'LOI', 'Total Oksida ', 'MC'
]

layer_mapping = {'TP': 100, 'L': 200, 'LO': 250, 'S': 300, 'BR': 400}

uploaded_file = st.file_uploader("Upload file Excel bor (.xlsx)", type=["xlsx"])
if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)

    # Hitung Thickness kalau belum ada
    if 'Thickness' not in df.columns:
        if ('To' in df.columns) and ('From' in df.columns):
            df['Thickness'] = df['To'] - df['From']
        else:
            st.error("Kolom 'Thickness' tidak ditemukan, dan kolom 'From' atau 'To' juga tidak lengkap.")
            st.stop()

    required_cols = ['BHID', 'From', 'To', 'Layer', 'Thickness', 'X', 'Y', 'XCollar', 'YCollar', 'ZCollar'] + unsur
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        st.error(f"File tidak memiliki kolom berikut: {missing_cols}")
        st.stop()

    df = df[required_cols].copy()
    df = df.dropna(subset=['BHID', 'Layer', 'Thickness', 'X', 'Y'])
    df = df[df['Thickness'] > 0]

    # Compositing weighted average
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

    composite = df.groupby(['BHID', 'Layer']).apply(weighted_avg).reset_index()

    # Mapping Layer_Code
    composite['Layer_Code'] = composite['Layer'].map(layer_mapping)
    composite['Layer_Code'] = composite['Layer_Code'].fillna(pd.to_numeric(composite['Layer'], errors='coerce'))

    # Total Depth per BHID
    depth = df.groupby('BHID')['To'].max().reset_index()
    depth.columns = ['BHID', 'Total_Depth']
    composite = composite.merge(depth, on='BHID', how='left')
    composite['Percent'] = (composite['Thickness'] / composite['Total_Depth']) * 100

    composite['Organic_Limonite'] = composite['Layer_Code'].apply(lambda x: 'LO' if x == 250 else '')

    # Reorder columns, pastikan Organic_Limonite paling kanan
    cols_order = ['BHID', 'XCollar', 'YCollar', 'ZCollar'] + \
                 [col for col in composite.columns if col not in ['BHID', 'XCollar', 'YCollar', 'ZCollar', 'Organic_Limonite']] + ['Organic_Limonite']
    composite = composite[cols_order]

    # Tampilkan tabel compositing
    st.markdown("### 📋 Hasil Compositing per BHID & Layer")
    gb = GridOptionsBuilder.from_dataframe(composite)
    gb.configure_default_column(sortable=True, resizable=True, floatingFilter=True)
    gb.configure_pagination(paginationAutoPageSize=True)
    grid_options = gb.build()

    AgGrid(
        composite,
        gridOptions=grid_options,
        enable_enterprise_modules=False,
        fit_columns_on_grid_load=True,
        theme="streamlit",
        height=400,
        editable=False
    )

    # Buat peta Folium tanpa geopandas
    st.markdown("### 🗺️ Peta Titik Compositing")
    if not composite.empty:
        m = folium.Map(
            location=[composite['Y'].mean(), composite['X'].mean()],
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
                location=[row['Y'], row['X']],
                radius=6,
                color='blue',
                fill=True,
                fill_opacity=0.7,
                popup=popup
            ).add_to(m)

        st_folium(m, height=450, use_container_width=True)
    else:
        st.info("Tidak ada data titik untuk ditampilkan di peta.")

    # Tombol download hasil compositing excel
    st.markdown("### 💾 Download Hasil Compositing")
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        composite.to_excel(writer, sheet_name='Layer_Composite', index=False)
        depth.to_excel(writer, sheet_name='Total_Depth', index=False)
    processed_data = output.getvalue()

    st.download_button(
        label="⬇️ Download Excel Compositing",
        data=processed_data,
        file_name="composite_bhid_layer.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Silakan upload file Excel bor untuk memulai compositing.")
