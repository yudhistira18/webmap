import streamlit as st
import pandas as pd
import numpy as np
from pyproj import Transformer
import folium
from streamlit_folium import st_folium
from io import BytesIO
import plotly.express as px

st.set_page_config(layout="wide")
st.title("🗂️ Composite Data Bor")

# Styling: compact layout
st.markdown("""
<style>
.block-container {
    padding-top: 1rem;
    padding-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

# Upload
uploaded_file = st.file_uploader("📤 Upload file Excel (.xlsx)", type=["xlsx"])
if not uploaded_file:
    st.info("Silakan upload file Excel yang berisi kolom: Prospect, Bukit, BHID, Layer, From, To, XCollar, YCollar, ZCollar, dan unsur.")
    st.stop()

df_raw = pd.read_excel(uploaded_file)

# Setup
unsur = ['Ni','Co','Fe2O3','Fe','FeO','SiO2','CaO','MgO','MnO','Cr2O3','Al2O3','P2O5','TiO2','SO3','LOI','MC']
if 'Thickness' not in df_raw.columns:
    df_raw['Thickness'] = df_raw['To'] - df_raw['From']

required = ['Prospect','Bukit','BHID','Layer','From','To','Thickness','XCollar','YCollar','ZCollar'] + unsur
missing = [c for c in required if c not in df_raw.columns]
if missing:
    st.error(f"❌ Kolom hilang: {missing}")
    st.stop()

df_clean = (
    df_raw[required]
    .dropna(subset=['Prospect','Bukit','BHID','Layer','Thickness','XCollar','YCollar'])
    .query("Thickness > 0")
)

sample_count = df_clean.groupby('BHID').size().reset_index(name='Sample_Count')

# Komposit
st.info("🔁 Komposit per Prospect → Bukit → BHID → Layer...")
progress = st.progress(0)
result = []
groups = list(df_clean.groupby(['Prospect','Bukit','BHID','Layer']))
for i, ((prospect, bukit, bhid, layer), g) in enumerate(groups):
    row = {
        'Prospect': prospect,
        'Bukit': bukit,
        'BHID': bhid,
        'Layer': layer,
        'From': g['From'].min(),
        'To': g['To'].max(),
        'Layer Thickness': g['Thickness'].sum(),
        'XCollar': g['XCollar'].iat[0],
        'YCollar': g['YCollar'].iat[0],
        'ZCollar': g['ZCollar'].iat[0]
    }
    for u in unsur:
        row[u] = np.average(g[u], weights=g['Thickness']) if g[u].notna().any() else np.nan
    result.append(row)
    progress.progress((i+1)/len(groups))
composite = pd.DataFrame(result)

# Info tambahan
composite = composite.merge(df_clean.groupby('BHID')['To'].max().rename('Total_Depth'), on='BHID')
composite = composite.merge(sample_count, on='BHID', how='left')
composite['Percent'] = (composite['Layer Thickness'] / composite['Total_Depth']) * 100

# Konversi koordinat
transformer = Transformer.from_crs("EPSG:32751", "EPSG:4326", always_xy=True)
lonlat = composite.apply(lambda row: transformer.transform(row['XCollar'], row['YCollar']), axis=1)
composite['Longitude'] = lonlat.map(lambda x: x[0])
composite['Latitude'] = lonlat.map(lambda x: x[1])

# Filter Sidebar
st.sidebar.header("🔍 Filter Data")
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

# 7 + 8. Ringkasan & Peta Lebar Layar
st.markdown("## 📊 Ringkasan & 🗺️ Peta")

col1, col2 = st.columns([1, 4])  # col1 kecil, col2 besar

with col1:
    st.markdown("#### 📋 Info Ringkas")
    st.metric("🏷️ Prospect", df_filter['Prospect'].nunique())
    st.metric("⛰️ Bukit", df_filter['Bukit'].nunique())
    st.metric("🔢 BHID", df_filter['BHID'].nunique())
    st.metric("🧪 Sampel Awal", df_clean[df_clean['BHID'].isin(df_filter['BHID'])].shape[0])

with col2:
    st.markdown("#### 📍 Peta Titik Bor")
    if not df_filter.empty:
        m = folium.Map(location=[df_filter['Latitude'].mean(), df_filter['Longitude'].mean()], zoom_start=12)
        for _, r in df_filter.iterrows():
            folium.CircleMarker(
                [r['Latitude'], r['Longitude']],
                radius=5, color='blue', fill=True, fill_opacity=0.7,
                popup=(f"Prospect: {r['Prospect']}<br>"
                       f"Bukit: {r['Bukit']}<br>"
                       f"BHID: {r['BHID']}<br>"
                       f"Layer: {r['Layer']}<br>"
                       f"Ni: {r['Ni']:.2f}")
            ).add_to(m)
        st_folium(m, height=500, use_container_width=True)
    else:
        st.warning("Tidak ada data ditampilkan pada peta.")


# Checkbox untuk menampilkan data asli
st.markdown("### 📋 Tabel Data")
show_original = st.checkbox("Tampilkan data asli (belum dikomposit)", value=False)

composite_cols = ['Prospect','Bukit','BHID','Layer','From','To','Layer Thickness','Total_Depth'] + unsur
original_cols = [col for col in composite_cols if col in df_clean.columns]

if show_original:
    original_filtered = df_clean[df_clean['BHID'].isin(df_filter['BHID']) & df_clean['Layer'].astype(str).isin(selected_layers)]
    st.dataframe(original_filtered[original_cols], use_container_width=True)
else:
    st.dataframe(df_filter[composite_cols], use_container_width=True)

# Tabel koordinat
st.markdown("### 📍 Koordinat Collar dan Total Depth")
summary = df_filter[['Prospect','Bukit','BHID','XCollar','YCollar','ZCollar','Total_Depth']].drop_duplicates()
st.dataframe(summary, use_container_width=True)

# Download
st.markdown("### 💾 Unduh Hasil")
out = BytesIO()
with pd.ExcelWriter(out, engine='openpyxl') as writer:
    df_filter.to_excel(writer, sheet_name='Composite', index=False)
    summary.to_excel(writer, sheet_name='Summary', index=False)
st.download_button(
    label="⬇️ Download Excel (2 Sheet)",
    data=out.getvalue(),
    file_name="composite_filtered.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# Ternary Plot
st.markdown("### 🔺 Ternary Plot (SiO₂ - MgO - FeO) berdasarkan Layer")

ternary_data = df_clean.dropna(subset=['SiO2', 'MgO', 'FeO', 'Layer']).copy()
ternary_data['Layer'] = ternary_data['Layer'].astype(int)

color_map = {
    100: 'gray',    # Top Soil
    200: 'red',     # Limonit
    250: 'black',   # Limonit Organik
    300: 'green',   # Saprolit
    400: 'blue',    # Bedrock
}
label_map = {
    100: "Top Soil",
    200: "Limonit",
    250: "Limonit Organik",
    300: "Saprolit",
    400: "Bedrock"
}
ternary_data['Color'] = ternary_data['Layer'].map(color_map)
ternary_data['Layer_Label'] = ternary_data['Layer'].map(label_map)

fig = px.scatter_ternary(
    ternary_data,
    a='SiO2', b='MgO', c='FeO',
    color='Layer_Label',
    color_discrete_map={v: color_map[k] for k, v in label_map.items()},
    hover_name='BHID',
    size_max=8
)
fig.update_layout(title='Ternary Plot SiO₂ - MgO - FeO berdasarkan Layer')
st.plotly_chart(fig, use_container_width=True)
