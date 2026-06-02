import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import ee
from datetime import datetime, timedelta
import os

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="Pemetaan Peternakan + Sentinel-2",
    page_icon="🐄",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🐄 Pemetaan Lokasi Peternakan")
st.subheader("Visualisasi + Analisis Citra Satelit Sentinel-2 (Gratis)")

# ==================== GEE INITIALIZATION ====================
def initialize_gee():
    """Initialize Google Earth Engine. 
    Untuk akun baru 2025/2026 biasanya butuh project ID.
    """
    try:
        # Coba tanpa project dulu (personal account)
        ee.Initialize()
        return True
    except Exception:
        try:
            # Kalau gagal, minta user isi project ID (bisa disimpan di secrets)
            project = st.secrets.get("GEE_PROJECT", None)
            if project:
                ee.Initialize(project=project)
                return True
            else:
                st.warning("GEE belum terinisialisasi. Jalankan `earthengine authenticate` di terminal.")
                return False
        except Exception as e:
            st.error(f"Gagal inisialisasi GEE: {e}")
            return False

gee_ready = initialize_gee()

# ==================== DATA LOADING ====================
@st.cache_data
def load_indonesia_sample_data():
    """Load sample data peternakan seluruh Indonesia (lebih lengkap)"""
    try:
        df = pd.read_csv("data_peternakan_indonesia_sample.csv")
        return df
    except FileNotFoundError:
        st.error("File data_peternakan_indonesia_sample.csv tidak ditemukan. Pastikan file berada di folder yang sama dengan app.py")
        return pd.DataFrame()

# ==================== DATA SOURCE SELECTION ====================
st.sidebar.header("📁 Sumber Data Peternakan")

data_source = st.sidebar.radio(
    "Pilih sumber data:",
    options=["Sample Data Indonesia Lengkap", "Upload CSV Sendiri"],
    index=0,
    help="Sample data berisi 180+ titik peternakan tersebar di banyak provinsi"
)

uploaded_file = None
if data_source == "Upload CSV Sendiri":
    uploaded_file = st.sidebar.file_uploader(
        "Upload file CSV lokasi peternakan",
        type=["csv"],
        help="Kolom wajib: nama, latitude, longitude, jenis_ternak, jumlah_ekor"
    )

if data_source == "Sample Data Indonesia Lengkap":
    df = load_indonesia_sample_data()
    if not df.empty:
        st.sidebar.success(f"✅ Menggunakan Sample Data Indonesia ({len(df)} peternakan)")
        st.sidebar.caption("Data tersebar di Jawa, Sumatera, Kalimantan, Sulawesi, NTT & Bali")
elif uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.sidebar.success(f"✅ {len(df)} data peternakan berhasil dimuat dari file")
else:
    st.sidebar.warning("Silakan upload file CSV atau pilih Sample Data")
    st.stop()

# Validasi kolom
required_cols = ["nama", "latitude", "longitude", "jenis_ternak", "jumlah_ekor"]
missing = [col for col in required_cols if col not in df.columns]
if missing:
    st.error(f"Data kurang kolom wajib: {missing}. Pastikan CSV memiliki semua kolom tersebut.")
    st.stop()

# ==================== SIDEBAR STATS ====================
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Ringkasan Data")
st.sidebar.metric("Total Peternakan", len(df))
st.sidebar.metric("Total Ternak", int(df["jumlah_ekor"].sum()))

if "provinsi" in df.columns:
    prov_count = df["provinsi"].value_counts().head(6)
    st.sidebar.write("**Top Provinsi:**")
    for p, c in prov_count.items():
        st.sidebar.write(f"- {p}: {c} peternakan")

jenis_count = df["jenis_ternak"].value_counts()
st.sidebar.write("**Jenis Ternak:**")
for j, c in jenis_count.items():
    st.sidebar.write(f"- {j}: {c} peternakan")

# ==================== MAIN MAP ====================
st.header("🗺️ Peta Interaktif Lokasi Peternakan")

# Warna berdasarkan jenis ternak
color_map = {
    "Sapi": "green",
    "Kambing": "orange",
    "Ayam": "red",
    "Lainnya": "blue"
}

# Center map di rata-rata lokasi atau default Indonesia Barat
center_lat = df["latitude"].mean()
center_lon = df["longitude"].mean()

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=10,
    tiles="OpenStreetMap"
)

# Tambahkan marker (dioptimalkan untuk data banyak)
for idx, row in df.iterrows():
    color = color_map.get(row["jenis_ternak"], "blue")
    popup_html = f"""
    <b>{row['nama']}</b><br>
    Jenis: {row['jenis_ternak']}<br>
    Jumlah: {row['jumlah_ekor']} ekor<br>
    """
    if "provinsi" in df.columns:
        popup_html += f"Provinsi: {row['provinsi']}<br>"
    popup_html += f"Koordinat: {row['latitude']:.4f}, {row['longitude']:.4f}"
    
    folium.CircleMarker(
        location=[row["latitude"], row["longitude"]],
        radius=6,  # radius lebih kecil agar tidak terlalu ramai
        popup=folium.Popup(popup_html, max_width=220),
        color=color,
        fill=True,
        fill_opacity=0.75,
        tooltip=row["nama"]
    ).add_to(m)

# Legend sederhana
legend_html = """
<div style="position: fixed; 
            bottom: 50px; left: 50px; width: 140px; height: 110px; 
            background-color: white; border:2px solid grey; z-index:9999; 
            font-size:13px; padding: 8px; border-radius: 5px;">
<b>Legenda</b><br>
<span style="color:green;">●</span> Sapi<br>
<span style="color:orange;">●</span> Kambing<br>
<span style="color:red;">●</span> Ayam<br>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# Tampilkan peta
st_data = st_folium(m, width=1100, height=520, returned_objects=["last_object_clicked"])

# ==================== ANALISIS SATELIT ====================
st.header("🛰️ Analisis Citra Satelit Sentinel-2")

st.markdown("""
Pilih salah satu peternakan di bawah ini untuk melihat **NDVI terkini** 
(indikator kesehatan vegetasi / pakan hijauan) dalam radius 500 meter dari lokasi.
""")

col1, col2 = st.columns([1, 2])

with col1:
    selected_name = st.selectbox(
        "Pilih Peternakan",
        options=df["nama"].tolist(),
        index=0
    )
    
    selected_row = df[df["nama"] == selected_name].iloc[0]
    st.write(f"**Lokasi:** {selected_row['latitude']:.4f}, {selected_row['longitude']:.4f}")
    st.write(f"**Jenis:** {selected_row['jenis_ternak']} | **Jumlah:** {selected_row['jumlah_ekor']} ekor")

    analyze_btn = st.button("🚀 Analisis Sentinel-2 Sekarang", type="primary", use_container_width=True)

with col2:
    if analyze_btn:
        if not gee_ready:
            st.error("Google Earth Engine belum siap. Ikuti instruksi di README untuk setup.")
        else:
            with st.spinner("Mengambil data Sentinel-2 dari Google Earth Engine..."):
                try:
                    lat = float(selected_row["latitude"])
                    lon = float(selected_row["longitude"])
                    
                    point = ee.Geometry.Point([lon, lat])
                    
                    # Ambil data 30 hari terakhir
                    end_date = ee.Date(datetime.now())
                    start_date = end_date.advance(-30, "day")
                    
                    # Sentinel-2 Surface Reflectance
                    s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                          .filterBounds(point)
                          .filterDate(start_date, end_date)
                          .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
                          .sort("system:time_start", False))
                    
                    if s2.size().getInfo() == 0:
                        st.warning("Tidak ada citra Sentinel-2 yang cukup bersih dalam 30 hari terakhir di lokasi ini.")
                    else:
                        # Ambil image paling baru
                        latest = s2.first()
                        
                        # Hitung NDVI
                        ndvi = latest.normalizedDifference(["B8", "B4"]).rename("NDVI")
                        
                        # Rata-rata dalam buffer 500 meter
                        ndvi_stats = ndvi.reduceRegion(
                            reducer=ee.Reducer.mean(),
                            geometry=point.buffer(500),
                            scale=10,
                            maxPixels=1e9
                        ).getInfo()
                        
                        ndvi_value = ndvi_stats.get("NDVI", None)
                        
                        if ndvi_value is not None:
                            st.success(f"**NDVI Rata-rata (500m buffer):** {ndvi_value:.3f}")
                            
                            # Interpretasi
                            if ndvi_value > 0.65:
                                st.success("✅ Vegetasi sangat sehat — kondisi pakan hijauan kemungkinan sangat baik.")
                            elif ndvi_value > 0.45:
                                st.info("🟡 Vegetasi sedang — pakan cukup, perlu monitoring.")
                            else:
                                st.warning("🔴 Vegetasi rendah — kemungkinan kekeringan atau lahan kurang produktif. Perlu tindakan.")
                            
                            st.caption(f"Data diambil dari citra Sentinel-2 tanggal: {latest.get('system:time_start').getInfo()}")
                        else:
                            st.error("Gagal menghitung NDVI.")
                            
                except Exception as e:
                    st.error(f"Terjadi error saat query GEE: {str(e)}")
                    st.info("Coba jalankan `earthengine authenticate` lagi atau cek koneksi internet.")

# ==================== STATISTIK TAMBAHAN ====================
st.markdown("---")
st.header("📈 Statistik Singkat")

col_stat1, col_stat2 = st.columns(2)

with col_stat1:
    st.subheader("Jumlah Ternak per Jenis")
    st.bar_chart(df.groupby("jenis_ternak")["jumlah_ekor"].sum())

with col_stat2:
    st.subheader("Data Peternakan")
    st.dataframe(
        df[["nama", "jenis_ternak", "jumlah_ekor", "latitude", "longitude"]],
        use_container_width=True,
        hide_index=True
    )

# ==================== FOOTER ====================
st.markdown("---")
st.caption("""
**Catatan:** Sample data berisi 180+ titik peternakan tersebar di berbagai provinsi Indonesia (data sintetis tapi realistis). 
Data satelit diambil secara real-time dari Google Earth Engine (Sentinel-2). 
Untuk data asli, silakan upload CSV sendiri.
""")

st.caption("Dibuat dengan ❤️ menggunakan Streamlit + Folium + Google Earth Engine | Versi 2.0 - Juni 2026 (Data Indonesia Lengkap)")