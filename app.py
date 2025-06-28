import streamlit as st
import pandas as pd
import numpy as np
from pyproj import Transformer
import folium
from streamlit_folium import st_folium
from io import BytesIO

st.set_page_config(layout="wide")
st.title("🗂️ Composite Data Bor + Dashboard + Filter")

# =======================
# 1. Upload & Load
# =======================
uploaded_file = st.file_uploader("📤 Upload file Excel (.xlsx)", type=["xlsx"])
if not uploaded_file:
    st.info("Silakan upload file dengan kolom: Prospect, Bukit, BHID, Layer, From, To, XCollar, YCollar, ZCollar, dan unsur.")
    st.stop()

df = pd.read_excel(uploaded_file)

# =======================
# 2. Persiapan Kolom
# =======================
unsur = ['Ni','Co','Fe2O3','Fe','FeO','SiO2','CaO','MgO','MnO','Cr2O3','Al2O3','P2O5','TiO2','SO3','LOI','MC']
if 'Thickness' not in df.columns:
    df['Thickness'] = df['To'] - df['From']

required_cols = ['Prospect','Bukit','BHID','Layer','From','To','Thickness','XCollar','YCollar','ZCollar'] + unsur
missing_cols = [c for c in required_cols if c not in df.columns]
if missing_cols:
    st.error(f"❌ Kolom hilang: {missing_cols}")
    st.stop()

df = df[required_cols].dropna(subset=['Prospect','Bukit','BHID','Layer','Thickness','XCollar','YCollar'])
df = df[df['Thickness'] > 0]

# =======================
# 3. Compositing
# =======================
st.info("🔁 Sedang mengolah composite data...")
progress = st.progress(0)
groups = list(df.groupby(['Prospect','Bukit','BHID','Layer']))
comps = []
for i, ((prospect, bukit, bhid, layer), g) in enumerate(groups):
    comp = {
        'Prospect': prospect,
        'Bukit': bukit,
        'BHID': bhid,
        'Layer': layer,
        'From': g['From'].min(),
        'To': g['To'].max(),
        'Thickness': g['Thickness'].sum()
    }
    for u in unsur:
        comp[u] = np.average(g[u], weights=g['Thickness']) if g[u].notna().any() else np.nan
    comp['XCollar'] = g['XCollar'].iat[0]
    comp['YCollar'] = g['YCollar'].iat[0]
    comp['ZCollar'] = g['ZCollar'].iat[0]
    comps.append(comp)
    progress.progress((i+1)/len(groups))
composite = pd.DataFrame(comps)

# Total depth dan persentase
depth = df.groupby('BHID')['To'].max().rename('Total_Depth')
composite = composite.join(depth, on='BHID')
composite['Percent'] = composite['Thickness'] / composite['Total_Depth'] * 100

# =======================
# 4. Koordinat WGS84
# =======================
transformer = Transformer.from_crs("EPSG:32751","EPSG:4326",always_xy=True)
lon_lat = composite.apply(lambda r: transformer.transform(r['XCollar'], r['YCollar']), axis=1)
composite['Longitude'] = lon_lat.map(lambda x: x[0])
composite['Latitude']  = lon_lat.map(lambda x: x[1])

# =======================
# 5. Filter
# =======================
st.markdown("### 🎛️ Filter Data")
c1, c2, c3, c4 = st.columns(4)

# Prospect
prospects = sorted(composite['Prospect'].unique())
selected_prospect = c1.selectbox("🏷️ Prospect", ["All"] + prospects)
filtered = composite if selected_prospect == "All" else composite[composite['Prospect'] == selected_prospect]

# Bukit
bukit_list = sorted(filtered['Bukit'].unique())
all_bukit = c2.multiselect("⛰️ Bukit", options=bukit_list, default=bukit_list)
filtered = filtered[filtered['Bukit'].isin(all_bukit)]

# BHID
bhid_list = sorted(filtered['BHID'].unique())
all_bhid = c3.multiselect("🔢 BHID", options=bhid_list, default=bhid_list)
filtered = filtered[filtered['BHID'].isin(all_bhid)]

# Layer
layer_list = sorted(filtered['Layer'].astype(str).unique())
all_layer = c4.multiselect("📚 Layer", options=layer_list, default=layer_list)
filtered = filtered[filtered['Layer'].astype(str).isin(all_layer)]

# =======================
# 6. Dashboard Ringkasan
# =======================
st.markdown("### 📊 Ringkasan Data (berdasarkan filter)")
col1, col2 = st.columns(2)
col1.metric("🔢 Jumlah BHID", filtered['BHID'].nunique())
col2.metric("📦 Jumlah Sampel (baris awal)", df[df['BHID'].isin(filtered['BHID'])].shape[0])

# =======================
# 7. Peta
# =======================
with st.container():
    st.markdown("### 🗺️ Peta Titik Bor")
    if not filtered.empty:
        m = folium.Map(location=[filtered["Latitude"].mean(), filtered["Longitude"].mean()], zoom_start=12)
        for _, r in filtered.iterrows():
            folium.CircleMarker(
                location=[r["Latitude"], r["Longitude"]],
                radius=5,
                color="blue",
                fill=True,
                fill_opacity=0.7,
                popup=f"{r['BHID']}<br>{r['Layer']}<br>Ni: {r['Ni']:.2f}"
            ).add_to(m)
        st_folium(m, height=400, use_container_width=True)
    else:
        st.warning("Tidak ada data untuk ditampilkan di peta.")

# =======================
# 8. Tabel Composite
# =======================
with st.container():
    st.markdown("### 📋 Tabel Composite")
    show_cols = ['Prospect','Bukit','BHID','Layer','From','To','Thickness','Percent'] + unsur
    st.dataframe(filtered[show_cols], use_container_width=True)

# =======================
# 9. Tabel Summary
# =======================
with st.container():
    st.markdown("### 📍 Tabel Koordinat & Total Depth")
    summary = (
        filtered[['Prospect','Bukit','BHID','XCollar','YCollar','ZCollar','Total_Depth']]
        .drop_duplicates()
        .sort_values(['Prospect','Bukit','BHID'])
    )
    st.dataframe(summary, use_container_width=True)

# =======================
# 10. Download
# =======================
st.markdown("### 💾 Unduh Excel")
out = BytesIO()
with pd.ExcelWriter(out, engine='openpyxl') as writer:
    composite.to_excel(writer, sheet_name='Composite', index=False)
    summary.to_excel(writer, sheet_name='Summary', index=False)

st.download_button(
    label="⬇️ Download Excel",
    data=out.getvalue(),
    file_name="composite_summary.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
