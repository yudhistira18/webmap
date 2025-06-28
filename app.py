import streamlit as st
import pandas as pd
import numpy as np
from pyproj import Transformer
import folium
from streamlit_folium import st_folium
from io import BytesIO

st.set_page_config(layout="wide")
st.title("🗂️ Composite Data Bor + Dashboard Ringkasan")

# ====================================
# 1. Upload & Read Excel
# ====================================
uploaded_file = st.file_uploader(
    "📤 Upload file Excel (.xlsx) hasil eksplorasi",
    type=["xlsx"]
)
if not uploaded_file:
    st.info("Silakan upload file Excel dengan kolom From, To, BHID, XCollar, YCollar, ZCollar, dan unsur.")
    st.stop()

df = pd.read_excel(uploaded_file)

# ====================================
# 2. Prepare & Composite
# ====================================
unsur = [
    'Ni','Co','Fe2O3','Fe','FeO','SiO2',
    'CaO','MgO','MnO','Cr2O3','Al2O3',
    'P2O5','TiO2','SO3','LOI','MC'
]

# Hitung Thickness jika belum ada
if 'Thickness' not in df.columns:
    df['Thickness'] = df['To'] - df['From']

required = ['BHID','From','To','Layer','Thickness',
            'XCollar','YCollar','ZCollar'] + unsur

missing = [c for c in required if c not in df.columns]
if missing:
    st.error(f"❌ Kolom hilang: {missing}")
    st.stop()

df = (
    df[required]
    .dropna(subset=['BHID','Layer','Thickness','XCollar','YCollar'])
    .query("Thickness > 0")
)

progress = st.progress(0, text="🔁 Compositing per BHID & Layer...")
groups = list(df.groupby(['BHID','Layer']))
comps = []
for i, ((bhid, layer), g) in enumerate(groups):
    avg = {
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

# Total depth & percent
depth = df.groupby('BHID')['To'].max().rename('Total_Depth')
composite = composite.join(depth, on='BHID')
composite['Percent'] = composite['Thickness'] / composite['Total_Depth'] * 100

st.success("✅ Compositing selesai!")

# ====================================
# 3. Konversi Koordinat
# ====================================
st.info("🌐 Konversi koordinat UTM zone 51S → WGS84")
transformer = Transformer.from_crs("EPSG:32751","EPSG:4326",always_xy=True)
coords = composite.apply(
    lambda r: transformer.transform(r['XCollar'], r['YCollar']),
    axis=1
)
composite['Longitude'] = coords.map(lambda x: x[0])
composite['Latitude']  = coords.map(lambda x: x[1])

# ====================================
# 4. Dashboard Ringkasan
# ====================================
st.markdown("## 📊 Dashboard Ringkasan")
col1, col2 = st.columns(2)
col1.metric("🔢 Unique BHID", composite['BHID'].nunique())
col2.metric("📦 Total Samples", len(df))

# ====================================
# 5. Filter Layer & BHID
# ====================================
available_layers = ["All Layers"] + sorted(composite["Layer"].astype(str).unique())
selected_layer = st.selectbox("🔍 Pilih Layer:", available_layers)
layer_filtered = composite if selected_layer=="All Layers" else composite[composite["Layer"]==selected_layer]

available_bhids = sorted(layer_filtered["BHID"].astype(str).unique())
selected_bhids = st.multiselect("✅ Pilih BHID:", available_bhids)
filtered = layer_filtered if not selected_bhids else layer_filtered[layer_filtered["BHID"].isin(selected_bhids)]

# ====================================
# 6. Peta Titik Bor
# ====================================
st.markdown("### 🗺️ Peta Titik Bor")
if not filtered.empty:
    m = folium.Map(
        location=[filtered["Latitude"].mean(), filtered["Longitude"].mean()],
        zoom_start=12
    )
    for _, r in filtered.iterrows():
        folium.CircleMarker(
            [r['Latitude'], r['Longitude']],
            radius=5, color='blue',
            fill=True, fill_opacity=0.7,
            popup=f"BHID: {r['BHID']}<br>Layer: {r['Layer']}<br>Ni: {r['Ni']:.2f}"
        ).add_to(m)
    st_folium(m, height=400, use_container_width=True)
else:
    st.warning("Tidak ada data untuk peta.")

# ====================================
# 7. Tabel Composite
# ====================================
st.markdown("### 📋 Tabel Composite")
cols_show = ['BHID','Layer','From','To','Thickness','Percent'] + unsur
st.dataframe(filtered[cols_show], use_container_width=True)

# ====================================
# 8. Tabel Ringkasan (Coord + Depth)
# ====================================
st.markdown("### 📍 Koordinat Collar UTM & Total Depth")
summary = (
    composite[['BHID','XCollar','YCollar','ZCollar','Total_Depth']]
    .drop_duplicates()
    .sort_values('BHID')
)
st.dataframe(summary, use_container_width=True)

# ====================================
# 9. Download Excel (2 sheets)
# ====================================
st.markdown("### 💾 Unduh Hasil")
out = BytesIO()
with pd.ExcelWriter(out, engine='openpyxl') as w:
    composite.to_excel(w, sheet_name='Composite', index=False)
    summary.to_excel(w, sheet_name='Summary', index=False)

st.download_button(
    label="⬇️ Download Excel (2 sheets)",
    data=out.getvalue(),
    file_name="composite_and_summary.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
