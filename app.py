import streamlit as st
import pandas as pd
import numpy as np
from pyproj import Transformer
import folium
from folium.plugins import ScaleControl
from streamlit_folium import st_folium
from io import BytesIO

st.set_page_config(layout="wide")
st.title("🗂️ Composite Data Bor + Dashboard + Filter Dinamis + Peta GIS")

# ====================================
# 1. Upload & Read Excel
# ====================================
uploaded_file = st.file_uploader("\U0001F4C4 Upload file Excel (.xlsx) hasil eksplorasi", type=["xlsx"])
if not uploaded_file:
    st.info("Silakan upload file Excel dengan kolom Prospect, Bukit, BHID, Layer, From, To, XCollar, YCollar, ZCollar, dan unsur.")
    st.stop()

df_raw = pd.read_excel(uploaded_file)

# ====================================
# 2. Prepare & Composite
# ====================================
unsur = ['Ni','Co','Fe2O3','Fe','FeO','SiO2','CaO','MgO','MnO','Cr2O3','Al2O3','P2O5','TiO2','SO3','LOI','MC']

if 'Thickness' not in df_raw.columns:
    df_raw['Thickness'] = df_raw['To'] - df_raw['From']

required = ['Prospect','Bukit','BHID','Layer','From','To','Thickness','XCollar','YCollar','ZCollar'] + unsur
missing = [c for c in required if c not in df_raw.columns]
if missing:
    st.error(f"\u274C Kolom hilang: {missing}")
    st.stop()

df = (
    df_raw[required]
    .dropna(subset=['Prospect','Bukit','BHID','Layer','Thickness','XCollar','YCollar'])
    .query("Thickness > 0")
)

# Compositing per Prospect → Bukit → BHID → Layer
st.info("\U0001F501 Mulai compositing per Prospect → Bukit → BHID → Layer...")
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

# ====================================
# 3. Konversi Koordinat UTM→WGS84
# ====================================
st.info("\U0001F310 Konversi koordinat UTM zone 51S → WGS84")
transformer = Transformer.from_crs("EPSG:32751","EPSG:4326",always_xy=True)
coords = composite.apply(lambda r: transformer.transform(r['XCollar'], r['YCollar']), axis=1)
composite['Longitude'] = coords.map(lambda x: x[0])
composite['Latitude']  = coords.map(lambda x: x[1])

# ====================================
# 4. Filter Dinamis
# ====================================
st.sidebar.header("\U0001F50D Filter Data")
prospect_opts = sorted(composite['Prospect'].unique())
selected_prospect = st.sidebar.selectbox("\U0001F3F7️ Prospect", ["All"] + prospect_opts)
df_filter = composite if selected_prospect == "All" else composite[composite['Prospect'] == selected_prospect]

bukit_opts = sorted(df_filter['Bukit'].unique())
selected_bukit = st.sidebar.multiselect("\u26f0\ufe0f Bukit", options=bukit_opts, default=bukit_opts)
df_filter = df_filter[df_filter['Bukit'].isin(selected_bukit)]

bhid_opts = sorted(df_filter['BHID'].unique())
selected_bhids = st.sidebar.multiselect("\U0001F522 BHID", options=bhid_opts, default=bhid_opts)
df_filter = df_filter[df_filter['BHID'].isin(selected_bhids)]

layer_opts = sorted(df_filter['Layer'].astype(str).unique())
selected_layers = st.sidebar.multiselect("\U0001F4DA Layer", options=layer_opts, default=layer_opts)
df_filter = df_filter[df_filter['Layer'].astype(str).isin(selected_layers)]

# ====================================
# 5. Dashboard Ringkasan
# ====================================
st.markdown("## \U0001F4CA Dashboard Ringkasan")
col1, col2, col3, col4 = st.columns(4)
col1.metric("\U0001F3F7️ Jumlah Prospect", df_filter['Prospect'].nunique())
col2.metric("\u26f0\ufe0f Jumlah Bukit", df_filter['Bukit'].nunique())
col3.metric("\U0001F522 Jumlah BHID", df_filter['BHID'].nunique())
col4.metric("\U0001F9EA Jumlah Sampel (row awal)", df[df['BHID'].isin(df_filter['BHID'])].shape[0])

# ====================================
# 6. Peta Titik Bor dengan Legend, Scale, North
# ====================================
st.markdown("### \U0001F5FA️ Peta Titik Bor")
if not df_filter.empty:
    m = folium.Map(location=[df_filter["Latitude"].mean(), df_filter["Longitude"].mean()], zoom_start=12)

    # CircleMarker
    for _, r in df_filter.iterrows():
        folium.CircleMarker(
            [r['Latitude'], r['Longitude']],
            radius=5, color='blue', fill=True, fill_opacity=0.7,
            popup=f"Prospect: {r['Prospect']}<br>Bukit: {r['Bukit']}<br>BHID: {r['BHID']}<br>Layer: {r['Layer']}<br>Ni: {r['Ni']:.2f}"
        ).add_to(m)

    # Scale
    m.add_child(ScaleControl(position='bottomleft'))

    # North Arrow
    north_arrow_url = "https://upload.wikimedia.org/wikipedia/commons/e/ed/North_arrow.svg"
    folium.raster_layers.ImageOverlay(
        image=north_arrow_url,
        bounds=[[df_filter["Latitude"].max(), df_filter["Longitude"].min()],
                [df_filter["Latitude"].max()+0.01, df_filter["Longitude"].min()+0.01]],
        opacity=1, interactive=False
    ).add_to(m)

    st_folium(m, height=450, use_container_width=True)
else:
    st.warning("Tidak ada data untuk peta.")

# ====================================
# 7. Tabel Composite
# ====================================
st.markdown("### \U0001F4CB Tabel Composite")
cols_show = ['Prospect','Bukit','BHID','Layer','From','To','Thickness','Percent'] + unsur
st.dataframe(df_filter[cols_show], use_container_width=True)

# ====================================
# 8. Tabel Summary Koordinat & Total Depth
# ====================================
st.markdown("### \U0001F4CD Tabel Summary Koordinat & Total Depth")
summary = (
    df_filter[['Prospect','Bukit','BHID','XCollar','YCollar','ZCollar','Total_Depth']]
    .drop_duplicates()
    .sort_values(['Prospect','Bukit','BHID'])
)
st.dataframe(summary, use_container_width=True)

# ====================================
# 9. Download Excel
# ====================================
st.markdown("### \U0001F4BE Unduh Excel (2 Sheet)")
out = BytesIO()
with pd.ExcelWriter(out, engine='openpyxl') as w:
    df_filter.to_excel(w, sheet_name='Composite', index=False)
    summary.to_excel(w, sheet_name='Summary', index=False)

st.download_button(
    label="\u2B07\ufe0f Download Excel",
    data=out.getvalue(),
    file_name="composite_filtered.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
