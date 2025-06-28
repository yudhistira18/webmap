import streamlit as st
import pandas as pd
import numpy as np
from pyproj import Transformer
import folium
from streamlit_folium import st_folium
from io import BytesIO

st.set_page_config(layout="wide")
st.title("🗂️ Composite Data Bor + Dashboard + Filter")

# 1. Upload Excel
uploaded_file = st.file_uploader("📤 Upload file Excel (.xlsx) hasil eksplorasi", type=["xlsx"])
if not uploaded_file:
    st.info("Silakan upload file Excel dengan kolom Prospect, Bukit, BHID, Layer, From, To, XCollar, YCollar, ZCollar, dan unsur.")
    st.stop()

df = pd.read_excel(uploaded_file)

# 2. Persiapan data
unsur = ['Ni','Co','Fe2O3','Fe','FeO','SiO2','CaO','MgO','MnO','Cr2O3','Al2O3','P2O5','TiO2','SO3','LOI','MC']
if 'Thickness' not in df.columns:
    df['Thickness'] = df['To'] - df['From']

required_cols = ['Prospect','Bukit','BHID','Layer','From','To','Thickness','XCollar','YCollar','ZCollar'] + unsur
missing_cols = [col for col in required_cols if col not in df.columns]
if missing_cols:
    st.error(f"❌ Kolom hilang: {missing_cols}")
    st.stop()

df = df[required_cols].dropna(subset=['Prospect','Bukit','BHID','Layer','XCollar','YCollar'])
df = df[df['Thickness'] > 0]

sample_count = df.groupby('BHID').size().reset_index(name='Sample_Count')

# 3. Komposit
st.info("🔁 Mulai proses komposit...")
progress = st.progress(0)
grouped = list(df.groupby(['Prospect','Bukit','BHID','Layer']))
result = []
for i, ((prospect, bukit, bhid, layer), g) in enumerate(grouped):
    row = {
        'Prospect': prospect,
        'Bukit': bukit,
        'BHID': bhid,
        'Layer': layer,
        'From': g['From'].min(),
        'To': g['To'].max(),
        'Thickness': g['Thickness'].sum(),
        'XCollar': g['XCollar'].iloc[0],
        'YCollar': g['YCollar'].iloc[0],
        'ZCollar': g['ZCollar'].iloc[0]
    }
    for u in unsur:
        row[u] = np.average(g[u], weights=g['Thickness']) if g[u].notna().any() else np.nan
    result.append(row)
    progress.progress((i+1)/len(grouped))
composite = pd.DataFrame(result)
composite = composite.merge(df.groupby('BHID')['To'].max().rename('Total_Depth'), on='BHID', how='left')
composite = composite.merge(sample_count, on='BHID', how='left')
composite['Percent'] = (composite['Thickness'] / composite['Total_Depth']) * 100

# 4. Konversi Koordinat
transformer = Transformer.from_crs("EPSG:32751", "EPSG:4326", always_xy=True)
lonlat = composite.apply(lambda row: transformer.transform(row['XCollar'], row['YCollar']), axis=1)
composite['Longitude'] = lonlat.map(lambda x: x[0])
composite['Latitude'] = lonlat.map(lambda x: x[1])

# 5. Filter Sidebar
st.markdown("### 🎛️ Filter Data")
col1, col2, col3, col4 = st.columns(4)

prospects = sorted(composite['Prospect'].unique())
selected_prospect = col1.selectbox("🏷️ Prospect", ["All"] + prospects)

bukit_all = sorted(composite['Bukit'].unique())
selected_bukit = col2.multiselect("⛰️ Bukit", bukit_all, default=bukit_all)

bhid_all = sorted(composite['BHID'].unique())
selected_bhid = col3.multiselect("🔢 BHID", bhid_all, default=bhid_all)

layer_all = sorted(composite['Layer'].astype(str).unique())
selected_layer = col4.multiselect("📚 Layer", layer_all, default=layer_all)

filtered = composite.copy()
if selected_prospect != "All":
    filtered = filtered[filtered['Prospect'] == selected_prospect]
filtered = filtered[
    filtered['Bukit'].isin(selected_bukit) &
    filtered['BHID'].isin(selected_bhid) &
    filtered['Layer'].astype(str).isin(selected_layer)
]

# 6. Dashboard
st.markdown("## 📊 Ringkasan Data")
d1, d2, d3, d4 = st.columns(4)
d1.metric("🔢 Jumlah BHID", filtered['BHID'].nunique())
d2.metric("📌 Jumlah Sampel", df[df['BHID'].isin(filtered['BHID'])].shape[0])
d3.metric("🏷️ Jumlah Prospect", filtered['Prospect'].nunique())
d4.metric("⛰️ Jumlah Bukit", filtered['Bukit'].nunique())

# 7. Peta
st.markdown("### 🗺️ Peta Titik Bor")
if not filtered.empty:
    m = folium.Map(location=[filtered['Latitude'].mean(), filtered['Longitude'].mean()], zoom_start=12)
    for _, r in filtered.iterrows():
        folium.CircleMarker(
            [r['Latitude'], r['Longitude']],
            radius=5, color='blue', fill=True, fill_opacity=0.7,
            popup=(f"Prospect: {r['Prospect']}<br>"
                   f"Bukit: {r['Bukit']}<br>"
                   f"BHID: {r['BHID']}<br>"
                   f"Layer: {r['Layer']}<br>"
                   f"Ni: {r['Ni']:.2f}")
        ).add_to(m)
    st_folium(m, height=400, use_container_width=True)
else:
    st.warning("Tidak ada data untuk ditampilkan di peta.")

# 8. Tabel Composite
st.markdown("### 📋 Tabel Composite")
cols_show = ['Prospect','Bukit','BHID','Layer','From','To','Thickness','Percent'] + unsur
st.dataframe(filtered[cols_show], use_container_width=True)

# 9. Tabel Ringkasan Koordinat & Total Depth
st.markdown("### 📍 Koordinat Collar UTM & Total Depth")
summary = filtered[['Prospect','Bukit','BHID','XCollar','YCollar','ZCollar','Total_Depth']].drop_duplicates()
st.dataframe(summary, use_container_width=True)

# 10. Download Excel
st.markdown("### 💾 Unduh Hasil")
out = BytesIO()
with pd.ExcelWriter(out, engine='openpyxl') as writer:
    filtered.to_excel(writer, sheet_name='Composite', index=False)
    summary.to_excel(writer, sheet_name='Summary', index=False)

st.download_button(
    "⬇️ Download Excel (2 Sheets)",
    data=out.getvalue(),
    file_name="composite_output.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
