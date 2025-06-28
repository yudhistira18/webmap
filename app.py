import streamlit as st
import pandas as pd
import numpy as np
from pyproj import Transformer
import folium
from streamlit_folium import st_folium
from io import BytesIO

st.set_page_config(layout="wide")
st.title("🗂️ Composite Data Bor + Dashboard + Filter Lengkap")

# ======================
# 1. Upload Excel
# ======================
uploaded_file = st.file_uploader("📤 Upload file Excel (.xlsx)", type=["xlsx"])
if not uploaded_file:
    st.info("Silakan upload file Excel dengan kolom Prospect, Bukit, BHID, Layer, From, To, XCollar, YCollar, ZCollar, dan unsur.")
    st.stop()

df = pd.read_excel(uploaded_file)

# ======================
# 2. Cleaning & Composite
# ======================
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

# Backup untuk menghitung jumlah sampel asli
original_df = df.copy()

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

depth = df.groupby('BHID')['To'].max().rename('Total_Depth')
composite = composite.join(depth, on='BHID')
composite['Percent'] = composite['Thickness'] / composite['Total_Depth'] * 100

# ======================
# 3. Koordinat WGS84
# ======================
st.info("🌐 Konversi koordinat UTM zone 51S → WGS84")
transformer = Transformer.from_crs("EPSG:32751", "EPSG:4326", always_xy=True)
coords = composite.apply(lambda r: transformer.transform(r['XCollar'], r['YCollar']), axis=1)
composite['Longitude'] = coords.map(lambda x: x[0])
composite['Latitude'] = coords.map(lambda x: x[1])

# ======================
# 4. Filter Prospek → Bukit → BHID → Layer
# ======================
st.header("🎛️ Filter Data")

df_filter = composite.copy()

# Filter Prospect
available_prospects = sorted(df_filter['Prospect'].unique())
selected_prospect = st.selectbox("🏷️ Filter Prospect", ["All"] + available_prospects)
if selected_prospect != "All":
    df_filter = df_filter[df_filter['Prospect'] == selected_prospect]

# Filter Bukit
all_bukit = sorted(df_filter['Bukit'].unique())
select_all_bukit = st.checkbox("✅ Pilih semua Bukit", value=True)
selected_bukit = st.multiselect("⛰️ Filter Bukit", all_bukit, default=all_bukit if select_all_bukit else [])
if selected_bukit:
    df_filter = df_filter[df_filter['Bukit'].isin(selected_bukit)]

# Filter BHID
all_bhids = sorted(df_filter['BHID'].unique())
select_all_bhid = st.checkbox("✅ Pilih semua BHID", value=True)
selected_bhids = st.multiselect("🔢 Filter BHID", all_bhids, default=all_bhids if select_all_bhid else [])
if selected_bhids:
    df_filter = df_filter[df_filter['BHID'].isin(selected_bhids)]

# Filter Layer
all_layers = sorted(df_filter['Layer'].astype(str).unique())
select_all_layer = st.checkbox("✅ Pilih semua Layer", value=True)
selected_layers = st.multiselect("🪨 Filter Layer", all_layers, default=all_layers if select_all_layer else [])
if selected_layers:
    df_filter = df_filter[df_filter['Layer'].astype(str).isin(selected_layers)]

# ======================
# 5. Dashboard
# ======================
st.markdown("## 📊 Dashboard Ringkasan (berdasarkan filter)")
col1, col2 = st.columns(2)
col1.metric("🔢 Jumlah BHID (unik)", df_filter['BHID'].nunique())

# Jumlah sampel dari original_df, disesuaikan filter BHID
filtered_bhid = df_filter['BHID'].unique()
sample_count = original_df[original_df['BHID'].isin(filtered_bhid)].shape[0]
col2.metric("🧪 Jumlah Sampel", sample_count)

# ======================
# 6. Peta Titik Bor
# ======================
st.markdown("## 🗺️ Peta Titik Bor")
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
            popup=(
                f"Prospect: {r['Prospect']}<br>"
                f"Bukit: {r['Bukit']}<br>"
                f"BHID: {r['BHID']}<br>"
                f"Layer: {r['Layer']}<br>"
                f"Ni: {r['Ni']:.2f}"
            )
        ).add_to(m)
    st_folium(m, height=450, use_container_width=True)
else:
    st.warning("⚠️ Tidak ada data untuk ditampilkan di peta.")

# ======================
# 7. Tabel Composite
# ======================
st.markdown("## 📋 Tabel Composite (Terfilter)")
cols_show = ['Prospect','Bukit','BHID','Layer','From','To','Thickness','Percent'] + unsur
st.dataframe(df_filter[cols_show], use_container_width=True)

# ======================
# 8. Tabel Summary (Koordinat dan Total Depth)
# ======================
st.markdown("## 📍 Tabel Summary Koordinat & Total Depth")
summary = (
    composite[['Prospect','Bukit','BHID','XCollar','YCollar','ZCollar','Total_Depth']]
    .drop_duplicates()
    .sort_values(['Prospect','Bukit','BHID'])
)
st.dataframe(summary, use_container_width=True)

# ======================
# 9. Download Excel
# ======================
st.markdown("## 💾 Unduh Excel")
out = BytesIO()
with pd.ExcelWriter(out, engine='openpyxl') as w:
    composite.to_excel(w, sheet_name='Composite', index=False)
    summary.to_excel(w, sheet_name='Summary', index=False)

st.download_button(
    label="⬇️ Download Excel (2 sheet)",
    data=out.getvalue(),
    file_name="composite_summary.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
