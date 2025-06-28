import streamlit as st
import pandas as pd
import numpy as np
from pyproj import Transformer
import folium
from streamlit_folium import st_folium
from io import BytesIO

st.set_page_config(layout="wide")
st.title("🗂️ Composite Data Bor + Dashboard + Filter Multiselect")

# ================================
# 1. Upload & Read Excel
# ================================
uploaded_file = st.file_uploader("📤 Upload file Excel (.xlsx)", type=["xlsx"])
if not uploaded_file:
    st.info("Silakan upload file Excel dengan kolom Prospect, Bukit, BHID, Layer, From, To, XCollar, YCollar, ZCollar, dan unsur.")
    st.stop()

df = pd.read_excel(uploaded_file)

# ================================
# 2. Prepare & Composite
# ================================
unsur = [
    'Ni','Co','Fe2O3','Fe','FeO','SiO2',
    'CaO','MgO','MnO','Cr2O3','Al2O3',
    'P2O5','TiO2','SO3','LOI','MC'
]

if 'Thickness' not in df.columns:
    df['Thickness'] = df['To'] - df['From']

required = ['Prospect','Bukit','BHID','Layer','From','To','Thickness',
            'XCollar','YCollar','ZCollar'] + unsur
missing = [c for c in required if c not in df.columns]
if missing:
    st.error(f"❌ Kolom hilang: {missing}")
    st.stop()

df = (
    df[required]
    .dropna(subset=['Prospect','Bukit','BHID','Layer','Thickness','XCollar','YCollar'])
    .query("Thickness > 0")
)

# Compositing
st.info("🔁 Mulai compositing per Prospect → Bukit → BHID → Layer...")
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

# Total depth & percent
depth = df.groupby('BHID')['To'].max().rename('Total_Depth')
composite = composite.join(depth, on='BHID')
composite['Percent'] = composite['Thickness'] / composite['Total_Depth'] * 100
st.success("✅ Compositing selesai!")

# ================================
# 3. Konversi Koordinat
# ================================
st.info("🌐 Konversi koordinat UTM 51S → WGS84")
transformer = Transformer.from_crs("EPSG:32751", "EPSG:4326", always_xy=True)
coords = composite.apply(lambda r: transformer.transform(r['XCollar'], r['YCollar']), axis=1)
composite['Longitude'] = coords.map(lambda x: x[0])
composite['Latitude']  = coords.map(lambda x: x[1])

# ================================
# 4. Filter Interface (Multiselect)
# ================================
st.markdown("## 🎛️ Filter Data (Multiselect)")

df_filter = composite.copy()

# Filter Prospect
prospects = ["All Prospects"] + sorted(df_filter['Prospect'].unique())
sel_prospect = st.selectbox("🏷️ Filter Prospect:", prospects)
if sel_prospect != "All Prospects":
    df_filter = df_filter[df_filter['Prospect'] == sel_prospect]

# Filter Bukit
bukit_options = sorted(df_filter['Bukit'].unique())
sel_bukit = st.multiselect("⛰️ Filter Bukit:", options=bukit_options, default=bukit_options)
if sel_bukit:
    df_filter = df_filter[df_filter['Bukit'].isin(sel_bukit)]

# Filter BHID
bhid_options = sorted(df_filter['BHID'].unique())
sel_bhid = st.multiselect("🔢 Filter BHID:", options=bhid_options, default=bhid_options)
if sel_bhid:
    df_filter = df_filter[df_filter['BHID'].isin(sel_bhid)]

# Filter Layer
layer_options = sorted(df_filter['Layer'].astype(str).unique())
sel_layer = st.multiselect("📚 Filter Layer:", options=layer_options, default=layer_options)
if sel_layer:
    df_filter = df_filter[df_filter['Layer'].astype(str).isin(sel_layer)]

# ================================
# 5. Dashboard Ringkasan
# ================================
st.markdown("## 📊 Dashboard Ringkasan")

# Hitung berdasarkan filter dari df_filter (composite) dan df (original)
filtered_bhids = df_filter['BHID'].unique()
df_sample_filtered = df[df['BHID'].isin(filtered_bhids)]

col1, col2 = st.columns(2)
col1.metric("🔢 Jumlah BHID", len(filtered_bhids))
col2.metric("🧪 Jumlah Sampel", len(df_sample_filtered))

# ================================
# 6. Peta
# ================================
st.markdown("### 🗺️ Peta Titik Bor")
if not df_filter.empty:
    m = folium.Map(
        location=[df_filter["Latitude"].mean(), df_filter["Longitude"].mean()],
        zoom_start=12
    )
    for _, r in df_filter.iterrows():
        folium.CircleMarker(
            [r['Latitude'], r['Longitude']],
            radius=5, color='blue',
            fill=True, fill_opacity=0.7,
            popup=(f"Prospect: {r['Prospect']}<br>"
                   f"Bukit: {r['Bukit']}<br>"
                   f"BHID: {r['BHID']}<br>"
                   f"Layer: {r['Layer']}<br>"
                   f"Ni: {r['Ni']:.2f}")
        ).add_to(m)
    st_folium(m, height=400, use_container_width=True)
else:
    st.warning("Tidak ada data untuk ditampilkan di peta.")

# ================================
# 7. Tabel Composite
# ================================
st.markdown("### 📋 Tabel Composite")
cols_show = ['Prospect','Bukit','BHID','Layer','From','To','Thickness','Percent'] + unsur
st.dataframe(df_filter[cols_show], use_container_width=True)

# ================================
# 8. Tabel Summary: Koordinat & Depth
# ================================
st.markdown("### 📍 Koordinat Collar UTM & Total Depth")
summary = (
    composite[['Prospect','Bukit','BHID','XCollar','YCollar','ZCollar','Total_Depth']]
    .drop_duplicates()
    .sort_values(['Prospect','Bukit','BHID'])
)
summary_filtered = summary[summary['BHID'].isin(filtered_bhids)]
st.dataframe(summary_filtered, use_container_width=True)

# ================================
# 9. Download Excel
# ================================
st.markdown("### 💾 Unduh Hasil")
out = BytesIO()
with pd.ExcelWriter(out, engine='openpyxl') as writer:
    df_filter.to_excel(writer, sheet_name='Composite', index=False)
    summary_filtered.to_excel(writer, sheet_name='Summary', index=False)

st.download_button(
    label="⬇️ Download Excel (2 sheets)",
    data=out.getvalue(),
    file_name="filtered_composite_and_summary.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
