import streamlit as st
import pandas as pd
import numpy as np
from pyproj import Transformer
import folium
from streamlit_folium import st_folium
from io import BytesIO

st.set_page_config(layout="wide")
st.title("🗂️ Composite Data Bor ")

# ====================================
# 1. Upload & Read Excel
# ====================================
uploaded_file = st.file_uploader(
    "📤 Upload file Excel (.xlsx) hasil eksplorasi (pastikan tidak ada conditional formatting!)",
    type=["xlsx"]
)
if not uploaded_file:
    st.info("Silakan upload file Excel dengan kolom Prospect, From, To, BHID, XCollar, YCollar, ZCollar, dan unsur.")
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

required = ['Prospect','BHID','From','To','Layer','Thickness',
            'XCollar','YCollar','ZCollar'] + unsur

missing = [c for c in required if c not in df.columns]
if missing:
    st.error(f"❌ Kolom hilang: {missing}")
    st.stop()

df = (
    df[required]
    .dropna(subset=['Prospect','BHID','Layer','Thickness','XCollar','YCollar'])
    .query("Thickness > 0")
)

# ====================================
# 3. Compositing per BHID & Layer
# ====================================
st.info("🔁 Mulai compositing per Prospect → BHID → Layer...")
progress = st.progress(0)
groups = list(df.groupby(['Prospect','BHID','Layer']))
comps = []
for i, ((prospect, bhid, layer), g) in enumerate(groups):
    avg = {
        'Prospect': prospect,
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
# 4. Konversi Koordinat
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
# 5. Dashboard Ringkasan
# ====================================
st.markdown("## 📊 Dashboard Ringkasan")
col1, col2, col3 = st.columns(3)
col1.metric("🔢 Unique Prospect", composite['Prospect'].nunique())
col2.metric("🔢 Unique BHID", composite['BHID'].nunique())
col3.metric("📦 Total Samples", len(df))

# ====================================
# 6. Filter Prospect, Layer & BHID
# ====================================
# Prospect filter
available_prospects = ["All Prospects"] + sorted(composite['Prospect'].unique())
selected_prospect = st.selectbox("🏷️ Filter Prospect:", available_prospects)
df_p = composite if selected_prospect=="All Prospects" else composite[composite['Prospect']==selected_prospect]

# Layer filter
available_layers = ["All Layers"] + sorted(df_p["Layer"].astype(str).unique())
selected_layer = st.selectbox("🔍 Filter Layer:", available_layers)
df_pl = df_p if selected_layer=="All Layers" else df_p[df_p["Layer"]==selected_layer]

# BHID filter
available_bhids = sorted(df_pl["BHID"].astype(str).unique())
selected_bhids = st.multiselect("✅ Filter BHID:", available_bhids)
filtered = df_pl if not selected_bhids else df_pl[df_pl["BHID"].isin(selected_bhids)]

# ====================================
# 7. Peta Titik Bor
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
            popup=(
                f"Prospect: {r['Prospect']}<br>"
                f"BHID: {r['BHID']}<br>"
                f"Layer: {r['Layer']}<br>"
                f"Ni: {r['Ni']:.2f}"
            )
        ).add_to(m)
    st_folium(m, height=400, use_container_width=True)
else:
    st.warning("Tidak ada data untuk peta.")

# ====================================
# 8. Tabel Composite
# ====================================
st.markdown("### 📋 Tabel Composite")
cols_show = ['Prospect','BHID','Layer','From','To','Thickness','Percent'] + unsur
st.dataframe(filtered[cols_show], use_container_width=True)

# ====================================
# 9. Tabel Ringkasan (Coord + Depth)
# ====================================
st.markdown("### 📍 Koordinat Collar UTM & Total Depth")
summary = (
    composite[['Prospect','BHID','XCollar','YCollar','ZCollar','Total_Depth']]
    .drop_duplicates()
    .sort_values(['Prospect','BHID'])
)
st.dataframe(summary, use_container_width=True)

# ====================================
# 10. Download Excel (2 sheets)
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
