import streamlit as st
import pandas as pd
import numpy as np
from pyproj import Transformer
import folium
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("🗂️ Composite Data Bor + Konversi Koordinat (PyProj)")

# ====================================
# 1. Upload & Read Excel
# ====================================
uploaded_file = st.file_uploader("📤 Upload file Excel (.xlsx) hasil eksplorasi", type=["xlsx"])
if not uploaded_file:
    st.info("Silakan upload file Excel dengan kolom From, To, BHID, XCollar, YCollar, ZCollar, dan unsur.")
    st.stop()

df = pd.read_excel(uploaded_file)

# ====================================
# 2. Prepare & Composite
# ====================================
unsur = ['Ni','Co','Fe2O3','Fe','FeO','SiO2','CaO','MgO','MnO','Cr2O3','Al2O3','P2O5','TiO2','SO3','LOI','MC']
# Pastikan Thickness
if 'Thickness' not in df:
    df['Thickness'] = df['To'] - df['From']

required = ['BHID','From','To','Layer','Thickness','XCollar','YCollar','ZCollar'] + unsur
missing = [c for c in required if c not in df.columns]
if missing:
    st.error(f"❌ Kolom hilang: {missing}")
    st.stop()

df = df[required].dropna(subset=['BHID','Layer','Thickness','XCollar','YCollar']).query("Thickness>0")

st.info("🔁 Mulai compositing per BHID & Layer...")
progress = st.progress(0)
groups = list(df.groupby(['BHID','Layer']))
comps = []
for i, ((bhid, layer), g) in enumerate(groups):
    avg = {'From':g['From'].min(),'To':g['To'].max(),'Thickness':g['Thickness'].sum()}
    for u in unsur:
        avg[u] = np.average(g[u], weights=g['Thickness']) if g[u].notna().any() else np.nan
    avg['XCollar']=g['XCollar'].iat[0]
    avg['YCollar']=g['YCollar'].iat[0]
    avg['ZCollar']=g['ZCollar'].iat[0]
    avg['BHID'],avg['Layer']=bhid,layer
    comps.append(avg)
    progress.progress((i+1)/len(groups))
composite = pd.DataFrame(comps)

# Total depth & percent
depth = df.groupby('BHID')['To'].max().rename('Total_Depth')
composite = composite.join(depth, on='BHID')
composite['Percent'] = composite['Thickness']/composite['Total_Depth']*100

st.success("✅ Compositing selesai!")

# ====================================
# 3. Konversi Koordinat UTM→WGS84
# ====================================
st.info("🌐 Konversi koordinat UTM zone 51S → WGS84")
transformer = Transformer.from_crs("EPSG:32751","EPSG:4326",always_xy=True)
coords = composite.apply(lambda r: transformer.transform(r['XCollar'],r['YCollar']),axis=1)
composite['Longitude'] = coords.map(lambda x:x[0])
composite['Latitude']  = coords.map(lambda x:x[1])

# ====================================
# 4. Map & Tables
# ====================================
# Map
st.markdown("### 🗺️ Peta Titik Bor")
m = folium.Map(location=[composite['Latitude'].mean(),composite['Longitude'].mean()],zoom_start=12)
for _,r in composite.iterrows():
    folium.CircleMarker(
        [r['Latitude'],r['Longitude']],
        radius=5, color='blue', fill=True, fill_opacity=0.7,
        popup=f"BHID: {r['BHID']}<br>Layer: {r['Layer']}<br>Ni: {r['Ni']:.2f}"
    ).add_to(m)
st_folium(m, height=400, use_container_width=True)

# Composite table
st.markdown("### 📋 Tabel Composite")
st.dataframe(composite[['BHID','Layer','From','To','Thickness','Percent']+unsur], use_container_width=True)

# Total depth table
st.markdown("### 📏 Tabel Total Depth")
st.dataframe(depth.reset_index(), use_container_width=True)

# Collar coords + depth
st.markdown("### 📍 Koordinat Collar UTM & Total Depth")
coord_tab = composite[['BHID','XCollar','YCollar','ZCollar','Total_Depth']].drop_duplicates()
st.dataframe(coord_tab, use_container_width=True)

# Download Excel
out = BytesIO()
with pd.ExcelWriter(out, engine='openpyxl') as w:
    composite.to_excel(w, sheet_name='Composite', index=False)
    depth.reset_index().to_excel(w, sheet_name='Total_Depth', index=False)
    coord_tab.to_excel(w, sheet_name='Coords', index=False)
st.download_button("⬇️ Download Excel (3 sheets)", out.getvalue(),
                   "composite_full.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
