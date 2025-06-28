import streamlit as st
import pandas as pd
import numpy as np
from pyproj import Transformer
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from io import BytesIO
import tempfile
import zipfile
import os

st.set_page_config(layout="wide")
st.title("🗂️ Composite Data Bor + Dashboard + SHP Overlay")

# ====================================
# 1. Upload File Excel
# ====================================
uploaded_file = st.file_uploader("📤 Upload file Excel eksplorasi (.xlsx)", type=["xlsx"])
if not uploaded_file:
    st.info("Silakan upload file Excel dengan kolom: Prospect, Bukit, BHID, Layer, From, To, XCollar, YCollar, ZCollar, dan unsur.")
    st.stop()

df_raw = pd.read_excel(uploaded_file)

# ====================================
# 2. Cleaning & Composite
# ====================================
unsur = [
    'Ni','Co','Fe2O3','Fe','FeO','SiO2',
    'CaO','MgO','MnO','Cr2O3','Al2O3',
    'P2O5','TiO2','SO3','LOI','MC'
]

if 'Thickness' not in df_raw.columns:
    df_raw['Thickness'] = df_raw['To'] - df_raw['From']

required_cols = ['Prospect','Bukit','BHID','Layer','From','To','Thickness',
                 'XCollar','YCollar','ZCollar'] + unsur
missing = [c for c in required_cols if c not in df_raw.columns]
if missing:
    st.error(f"❌ Kolom hilang: {missing}")
    st.stop()

df = df_raw[required_cols].dropna(subset=['Prospect','Bukit','BHID','Layer','Thickness','XCollar','YCollar'])
df = df[df['Thickness'] > 0]

st.info("🔁 Compositing per Prospect → Bukit → BHID → Layer...")
progress = st.progress(0)
groups = list(df.groupby(['Prospect','Bukit','BHID','Layer']))
comps = []
for i, ((prospect, bukit, bhid, layer), g) in enumerate(groups):
    avg = {
        'Prospect': prospect,
        'Bukit': bukit,
        'BHID': bhid,
        'Layer': layer,
        'From': g['From'].min(),
        'To': g['To'].max(),
        'Thickness': g['Thickness'].sum()
    }
    for u in unsur:
        avg[u] = np.average(g[u], weights=g['Thickness']) if g[u].notna().any() else np.nan
    avg['XCollar'] = g['XCollar'].iat[0]
    avg['YCollar'] = g['YCollar'].iat[0]
    avg['ZCollar'] = g['ZCollar'].iat[0]
    comps.append(avg)
    progress.progress((i+1)/len(groups))
composite = pd.DataFrame(comps)

depth = df.groupby('BHID')['To'].max().rename('Total_Depth')
composite = composite.join(depth, on='BHID')
composite['Percent'] = composite['Thickness'] / composite['Total_Depth'] * 100

# ====================================
# 3. Koordinat ke WGS84
# ====================================
st.info("🌐 Konversi koordinat ke WGS84...")
transformer = Transformer.from_crs("EPSG:32751", "EPSG:4326", always_xy=True)
coords = composite.apply(lambda r: transformer.transform(r['XCollar'], r['YCollar']), axis=1)
composite['Longitude'] = coords.map(lambda x: x[0])
composite['Latitude'] = coords.map(lambda x: x[1])

# ====================================
# 4. Sidebar Filter
# ====================================
st.sidebar.header("🔍 Filter Data")

# Filter berurutan
prospect_opts = sorted(composite['Prospect'].unique())
selected_prospect = st.sidebar.selectbox("🏷️ Prospect", ["All"] + prospect_opts)
df_filter = composite if selected_prospect == "All" else composite[composite['Prospect'] == selected_prospect]

bukit_opts = sorted(df_filter['Bukit'].unique())
selected_bukit = st.sidebar.multiselect("⛰️ Bukit", options=bukit_opts, default=bukit_opts)
df_filter = df_filter[df_filter['Bukit'].isin(selected_bukit)]

bhid_opts = sorted(df_filter['BHID'].unique())
selected_bhids = st.sidebar.multiselect("🔢 BHID", options=bhid_opts, default=bhid_opts)
df_filter = df_filter[df_filter['BHID'].isin(selected_bhids)]

layer_opts = sorted(df_filter['Layer'].astype(str).unique())
selected_layers = st.sidebar.multiselect("📚 Layer", options=layer_opts, default=layer_opts)
df_filter = df_filter[df_filter['Layer'].astype(str).isin(selected_layers)]

# ====================================
# 5. Dashboard Ringkasan
# ====================================
st.markdown("## 📊 Ringkasan Data")
col1, col2, col3, col4 = st.columns(4)
col1.metric("🏷️ Jumlah Prospect", df_filter['Prospect'].nunique())
col2.metric("⛰️ Jumlah Bukit", df_filter['Bukit'].nunique())
col3.metric("🔢 Jumlah BHID", df_filter['BHID'].nunique())
col4.metric("🧪 Jumlah Sampel Awal", df[df['BHID'].isin(df_filter['BHID'])].shape[0])

# ====================================
# 6. Upload Shapefile ZIP
# ====================================
st.markdown("### 📁 Upload Shapefile (.zip)")
shp_zip = st.file_uploader("Upload file .zip yang berisi .shp, .shx, .dbf, dll", type=["zip"])

# ====================================
# 7. Peta
# ====================================
st.markdown("### 🗺️ Peta Bor & Shapefile")
if not df_filter.empty:
    m = folium.Map(
        location=[df_filter['Latitude'].mean(), df_filter['Longitude'].mean()],
        zoom_start=12
    )

    # Tambah titik bor
    for _, r in df_filter.iterrows():
        popup = (
            f"Prospect: {r['Prospect']}<br>"
            f"Bukit: {r['Bukit']}<br>"
            f"BHID: {r['BHID']}<br>"
            f"Layer: {r['Layer']}<br>"
            f"Ni: {r['Ni']:.2f}"
        )
        folium.CircleMarker(
            location=[r['Latitude'], r['Longitude']],
            radius=5,
            color='blue',
            fill=True,
            fill_opacity=0.7,
            popup=popup
        ).add_to(m)

    # Tambah shapefile jika ada
    if shp_zip is not None:
        if shp_zip.name.endswith('.zip'):
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(shp_zip, "r") as zip_ref:
                    zip_ref.extractall(tmpdir)

                shp_files = [f for f in os.listdir(tmpdir) if f.endswith('.shp')]
                if shp_files:
                    shp_path = os.path.join(tmpdir, shp_files[0])
                    shp_gdf = gpd.read_file(shp_path).to_crs(epsg=4326)
                    folium.GeoJson(shp_gdf, name="Shapefile").add_to(m)
                else:
                    st.warning("❗️ File .shp tidak ditemukan di dalam .zip.")
        else:
            st.error("❌ Format harus .zip berisi file .shp, .shx, .dbf, dll.")

    st_folium(m, height=450, use_container_width=True)
else:
    st.warning("Tidak ada data untuk ditampilkan di peta.")

# ====================================
# 8. Tabel Data Composite
# ====================================
st.markdown("### 📋 Tabel Composite")
cols_show = ['Prospect','Bukit','BHID','Layer','From','To','Thickness','Percent'] + unsur
st.dataframe(df_filter[cols_show], use_container_width=True)

# ====================================
# 9. Summary Koordinat + Depth
# ====================================
st.markdown("### 📍 Koordinat & Total Depth")
summary = (
    df_filter[['Prospect','Bukit','BHID','XCollar','YCollar','ZCollar','Total_Depth']]
    .drop_duplicates()
    .sort_values(['Prospect','Bukit','BHID'])
)
st.dataframe(summary, use_container_width=True)

# ====================================
# 10. Download Excel
# ====================================
st.markdown("### 💾 Unduh Hasil")
out = BytesIO()
with pd.ExcelWriter(out, engine='openpyxl') as w:
    df_filter.to_excel(w, sheet_name='Composite', index=False)
    summary.to_excel(w, sheet_name='Summary', index=False)

st.download_button(
    label="⬇️ Download Excel (2 Sheet)",
    data=out.getvalue(),
    file_name="composite_filtered.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
