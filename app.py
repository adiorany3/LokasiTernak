import json
import math
from datetime import datetime
from pathlib import Path

import ee
import folium
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_folium import st_folium


# ============================================================
# KONFIGURASI DASAR
# ============================================================
APP_TITLE = "Dashboard Peternakan Indonesia"
DEVELOPER_NAME = "Galuh Adi Insani"

DEFAULT_DATA_FILE = "data_peternakan_indonesia_bps_2024.csv"

BPS_TABLE_URL = (
    "https://www.bps.go.id/id/statistics-table/3/"
    "UzJWaVUxZHdWVGxwU1hSd1UxTXZlbmRITjA1Q2R6MDkjMw%3D%3D/"
    "populasi-ternak-menurut-provinsi-dan-jenis-ternak--ekor---2024.html?year=2024"
)


# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🐄",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# HIDE STREAMLIT BRANDING + CUSTOM STYLE
# ============================================================
def hide_streamlit_branding():
    st.markdown(
        """
        <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}

            [data-testid="stToolbar"] {
                visibility: hidden !important;
                height: 0%;
                position: fixed;
            }

            [data-testid="stDecoration"] {
                display: none !important;
            }

            [data-testid="stStatusWidget"] {
                visibility: hidden !important;
            }

            [data-testid="stHeader"] {
                display: none !important;
            }

            .stDeployButton {
                display: none !important;
            }

            .viewerBadge_container__1QSob,
            .viewerBadge_link__1S137,
            .viewerBadge_text__1JaDK {
                display: none !important;
            }

            .block-container {
                padding-top: 1.5rem;
                padding-bottom: 5rem;
            }

            .custom-footer {
                position: fixed;
                left: 0;
                bottom: 0;
                width: 100%;
                background: rgba(255, 255, 255, 0.96);
                border-top: 1px solid #e5e7eb;
                text-align: center;
                padding: 10px 12px;
                font-size: 13px;
                color: #475569;
                z-index: 999999;
            }

            .source-note {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                padding: 0.85rem 1rem;
                border-radius: 0.7rem;
                color: #334155;
                margin-bottom: 1rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


hide_streamlit_branding()


# ============================================================
# HEADER
# ============================================================
st.title("🐄 Dashboard Peternakan Indonesia")
st.subheader("Data agregat resmi + pemetaan interaktif + analisis NDVI Sentinel-2")

st.markdown(
    """
    <div class="source-note">
    <b>Status data:</b> data bawaan aplikasi menggunakan
    <b>data agregat provinsi BPS 2024</b> untuk populasi sapi perah dan sapi potong.
    Titik pada peta adalah <b>koordinat representatif ibu kota provinsi</b>,
    bukan titik kandang individu. Untuk analisis kandang nyata, gunakan menu
    <b>Upload CSV Sendiri</b> berisi koordinat peternakan asli.
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# GOOGLE EARTH ENGINE
# ============================================================
def safe_secret_get(key, default=None):
    """Ambil secret dengan aman."""
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def normalize_private_key(private_key):
    """
    Membersihkan private key dari Streamlit Secrets.

    Mendukung:
    1. Private key multiline TOML asli.
    2. Private key JSON yang masih memakai \\n.
    """
    private_key = str(private_key)
    private_key = private_key.replace("\\n", "\n")
    private_key = private_key.strip()

    private_key = private_key.replace(
        "-----BEGIN PRIVATE KEY-----\n\n",
        "-----BEGIN PRIVATE KEY-----\n",
    )
    private_key = private_key.replace(
        "\n\n-----END PRIVATE KEY-----",
        "\n-----END PRIVATE KEY-----",
    )

    return private_key


def read_gee_project():
    """Ambil GEE_PROJECT dari Streamlit Secrets."""
    project = safe_secret_get("GEE_PROJECT", None)
    if project:
        return str(project).strip()
    return None


def read_service_account_info():
    """
    Membaca Service Account dari Streamlit Secrets.

    Format yang didukung:

    GEE_PROJECT = "project-id"

    [gcp_service_account]
    type = "service_account"
    project_id = "project-id"
    private_key_id = "..."
    private_key = \"\"\"-----BEGIN PRIVATE KEY-----
    ...
    -----END PRIVATE KEY-----\"\"\"
    client_email = "..."
    client_id = "..."
    token_uri = "https://oauth2.googleapis.com/token"

    Atau:

    GEE_SERVICE_ACCOUNT_JSON = "{...json penuh...}"
    """
    try:
        if "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])

        elif "GEE_SERVICE_ACCOUNT_JSON" in st.secrets:
            raw_json = st.secrets["GEE_SERVICE_ACCOUNT_JSON"]
            info = json.loads(raw_json)

        else:
            st.session_state["gee_init_error"] = (
                "Secrets belum menemukan [gcp_service_account] atau GEE_SERVICE_ACCOUNT_JSON."
            )
            return None

        if "private_key" in info and info["private_key"]:
            info["private_key"] = normalize_private_key(info["private_key"])

        return info

    except Exception as e:
        st.session_state["gee_init_error"] = (
            f"Secrets terbaca, tetapi format service account salah: {e}"
        )
        return None


def initialize_gee():
    """
    Inisialisasi Google Earth Engine.

    Streamlit Cloud:
    - Pakai Service Account dari Streamlit Secrets.

    Lokal:
    - Fallback ke earthengine authenticate jika tidak ada Service Account.
    """
    project = read_gee_project()
    service_account_info = read_service_account_info()

    try:
        if service_account_info:
            required_keys = [
                "type",
                "project_id",
                "private_key_id",
                "private_key",
                "client_email",
                "client_id",
                "token_uri",
            ]

            missing_keys = [
                key for key in required_keys
                if not service_account_info.get(key)
            ]

            if missing_keys:
                raise ValueError(
                    f"Secrets service account kurang field: {missing_keys}"
                )

            private_key = service_account_info["private_key"]

            if not private_key.startswith("-----BEGIN PRIVATE KEY-----"):
                raise ValueError(
                    "Format private_key salah. Private key harus diawali "
                    "-----BEGIN PRIVATE KEY-----"
                )

            if not private_key.strip().endswith("-----END PRIVATE KEY-----"):
                raise ValueError(
                    "Format private_key salah. Private key harus diakhiri "
                    "-----END PRIVATE KEY-----"
                )

            credentials = ee.ServiceAccountCredentials(
                service_account_info["client_email"],
                key_data=json.dumps(service_account_info),
            )

            ee.Initialize(
                credentials=credentials,
                project=project or service_account_info.get("project_id"),
            )

            # Tes ringan agar error API/permission langsung kelihatan.
            ee.Number(1).getInfo()

            st.session_state["gee_init_mode"] = "Service Account Streamlit Secrets"
            st.session_state["gee_init_error"] = ""
            return True

        # Fallback lokal/laptop.
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()

        ee.Number(1).getInfo()

        st.session_state["gee_init_mode"] = "Credential lokal/default"
        st.session_state["gee_init_error"] = ""
        return True

    except Exception as e:
        st.session_state["gee_init_mode"] = "Belum aktif"
        st.session_state["gee_init_error"] = str(e)
        return False


gee_ready = initialize_gee()


# ============================================================
# SIDEBAR: STATUS GEE + DEBUG
# ============================================================
with st.sidebar.expander("Status Google Earth Engine", expanded=not gee_ready):
    if gee_ready:
        st.success(f"GEE aktif via {st.session_state.get('gee_init_mode', '-')}")
    else:
        st.warning("GEE belum aktif di Streamlit Cloud.")
        st.caption(
            "Pastikan Service Account sudah dimasukkan ke Streamlit Secrets, "
            "Earth Engine API aktif, project sudah terdaftar Earth Engine, "
            "role IAM benar, lalu Reboot app."
        )

        detail = st.session_state.get("gee_init_error", "")
        if detail:
            st.code(detail, language="text")


with st.sidebar.expander("DEBUG Secrets", expanded=False):
    try:
        st.write("GEE_PROJECT ada:", "GEE_PROJECT" in st.secrets)
        st.write("gcp_service_account ada:", "gcp_service_account" in st.secrets)
        st.write("GEE_SERVICE_ACCOUNT_JSON ada:", "GEE_SERVICE_ACCOUNT_JSON" in st.secrets)

        if "gcp_service_account" in st.secrets:
            sa = dict(st.secrets["gcp_service_account"])
            pk = str(sa.get("private_key", ""))
            pk_normalized = normalize_private_key(pk) if pk else ""

            st.write("client_email ada:", bool(sa.get("client_email")))
            st.write("private_key ada:", bool(pk))
            st.write("project_id:", sa.get("project_id", "-"))
            st.write(
                "private_key mulai benar:",
                pk_normalized.startswith("-----BEGIN PRIVATE KEY-----"),
            )
            st.write(
                "private_key selesai benar:",
                pk_normalized.strip().endswith("-----END PRIVATE KEY-----"),
            )
            st.write("client_email:", sa.get("client_email", "-"))

    except Exception as e:
        st.code(str(e), language="text")


# ============================================================
# LOAD DATA
# ============================================================
@st.cache_data(show_spinner=False)
def load_default_data():
    """Memuat CSV data BPS bawaan."""
    data_path = Path(DEFAULT_DATA_FILE)

    if not data_path.exists():
        data_path = Path(__file__).resolve().parent / DEFAULT_DATA_FILE

    try:
        return pd.read_csv(data_path)
    except FileNotFoundError:
        st.error(
            f"File {DEFAULT_DATA_FILE} tidak ditemukan. "
            "Pastikan file CSV berada satu folder dengan app.py."
        )
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Gagal membaca file data: {e}")
        return pd.DataFrame()


def clean_and_validate_data(df):
    """Validasi dan pembersihan data."""
    required_cols = [
        "nama",
        "latitude",
        "longitude",
        "jenis_ternak",
        "jumlah_ekor",
    ]

    missing = [col for col in required_cols if col not in df.columns]

    if missing:
        st.error(f"Data kurang kolom wajib: {missing}")
        st.stop()

    cleaned = df.copy()

    cleaned["latitude"] = pd.to_numeric(cleaned["latitude"], errors="coerce")
    cleaned["longitude"] = pd.to_numeric(cleaned["longitude"], errors="coerce")
    cleaned["jumlah_ekor"] = (
        pd.to_numeric(cleaned["jumlah_ekor"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    cleaned = cleaned.dropna(subset=["latitude", "longitude"])

    if cleaned.empty:
        st.error("Data tidak memiliki koordinat valid.")
        st.stop()

    return cleaned


# ============================================================
# SIDEBAR: SUMBER DATA
# ============================================================
st.sidebar.header("📁 Sumber Data")

data_source = st.sidebar.radio(
    "Pilih sumber data:",
    options=[
        "Data Resmi BPS 2024 (Agregat Provinsi)",
        "Upload CSV Sendiri",
    ],
    index=0,
)

uploaded_file = None

if data_source == "Upload CSV Sendiri":
    uploaded_file = st.sidebar.file_uploader(
        "Upload file CSV lokasi peternakan",
        type=["csv"],
        help=(
            "Kolom wajib: nama, latitude, longitude, jenis_ternak, jumlah_ekor. "
            "Kolom opsional: provinsi, tahun, sumber."
        ),
    )

if data_source == "Data Resmi BPS 2024 (Agregat Provinsi)":
    df = load_default_data()

    if not df.empty:
        st.sidebar.success(f"✅ {len(df)} baris data agregat BPS dimuat")
        st.sidebar.caption("Satuan: ekor. Titik peta: ibu kota provinsi.")

elif uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.sidebar.success(f"✅ {len(df)} baris data berhasil dimuat")

else:
    st.sidebar.warning("Upload CSV terlebih dahulu atau gunakan data BPS bawaan.")
    st.stop()


df = clean_and_validate_data(df)


# ============================================================
# FILTER DATA
# ============================================================
st.sidebar.markdown("---")
st.sidebar.subheader("🔎 Filter")

if "provinsi" in df.columns:
    provinsi_options = sorted(df["provinsi"].dropna().unique().tolist())
    selected_provinsi = st.sidebar.multiselect(
        "Provinsi",
        provinsi_options,
        default=provinsi_options,
    )
else:
    selected_provinsi = []

jenis_options = sorted(df["jenis_ternak"].dropna().unique().tolist())
selected_jenis = st.sidebar.multiselect(
    "Jenis ternak",
    jenis_options,
    default=jenis_options,
)

filtered_df = df.copy()

if "provinsi" in filtered_df.columns and selected_provinsi:
    filtered_df = filtered_df[filtered_df["provinsi"].isin(selected_provinsi)]

if selected_jenis:
    filtered_df = filtered_df[filtered_df["jenis_ternak"].isin(selected_jenis)]

if filtered_df.empty:
    st.warning("Tidak ada data sesuai filter.")
    st.stop()


# ============================================================
# SIDEBAR: RINGKASAN
# ============================================================
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Ringkasan")

st.sidebar.metric("Baris Data", len(filtered_df))
st.sidebar.metric(
    "Total Populasi",
    f"{int(filtered_df['jumlah_ekor'].sum()):,}".replace(",", "."),
)

if "provinsi" in filtered_df.columns:
    st.sidebar.metric("Jumlah Provinsi", filtered_df["provinsi"].nunique())

jenis_count = (
    filtered_df.groupby("jenis_ternak")["jumlah_ekor"]
    .sum()
    .sort_values(ascending=False)
)

st.sidebar.write("**Populasi per Jenis:**")

for jenis, total in jenis_count.items():
    st.sidebar.write(f"- {jenis}: {int(total):,} ekor".replace(",", "."))


# ============================================================
# PETA
# ============================================================
st.header("🗺️ Peta Interaktif Populasi Ternak")

color_map = {
    "Sapi Perah": "blue",
    "Sapi Potong": "green",
    "Sapi": "green",
    "Kerbau": "purple",
    "Kambing": "orange",
    "Domba": "cadetblue",
    "Ayam": "red",
    "Ayam Buras": "red",
    "Ayam Ras Pedaging": "darkred",
    "Ayam Ras Petelur": "pink",
    "Itik": "lightblue",
    "Lainnya": "gray",
}


def marker_radius(value):
    """Radius marker agar data besar tidak menutupi peta."""
    return max(5, min(18, 3 + math.log10(max(int(value), 1)) * 2.2))


center_lat = filtered_df["latitude"].mean()
center_lon = filtered_df["longitude"].mean()

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=5,
    tiles="OpenStreetMap",
)

folium.TileLayer("CartoDB positron", name="CartoDB Positron").add_to(m)
folium.TileLayer("CartoDB dark_matter", name="CartoDB Dark").add_to(m)

for _, row in filtered_df.iterrows():
    jenis = str(row["jenis_ternak"])
    color = color_map.get(jenis, "gray")
    jumlah = int(row["jumlah_ekor"])

    popup_html = f"""
    <b>{row['nama']}</b><br>
    Jenis ternak: {jenis}<br>
    Jumlah populasi: {jumlah:,} ekor<br>
    """.replace(",", ".")

    if "provinsi" in filtered_df.columns:
        popup_html += f"Provinsi: {row.get('provinsi', '-')}<br>"

    if "tahun" in filtered_df.columns:
        popup_html += f"Tahun: {row.get('tahun', '-')}<br>"

    if "sumber" in filtered_df.columns:
        popup_html += f"Sumber: {row.get('sumber', '-')}<br>"

    if "jenis_data" in filtered_df.columns:
        popup_html += f"Jenis data: {row.get('jenis_data', '-')}<br>"

    popup_html += f"Koordinat: {row['latitude']:.4f}, {row['longitude']:.4f}"

    folium.CircleMarker(
        location=[row["latitude"], row["longitude"]],
        radius=marker_radius(jumlah),
        popup=folium.Popup(popup_html, max_width=340),
        color=color,
        fill=True,
        fill_opacity=0.72,
        tooltip=f"{row['nama']} - {jumlah:,} ekor".replace(",", "."),
    ).add_to(m)


legend_items = ""

for jenis in selected_jenis:
    legend_items += (
        f"<span style='color:{color_map.get(jenis, 'gray')};'>●</span> "
        f"{jenis}<br>"
    )

legend_html = f"""
<div style="position: fixed; bottom: 72px; left: 50px; min-width: 175px;
            background-color: white; border: 1px solid #CBD5E1; z-index: 9999;
            font-size: 13px; padding: 10px; border-radius: 8px;
            box-shadow: 0 3px 14px rgba(0,0,0,.12);">
<b>Legenda</b><br>{legend_items}
</div>
"""

m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl().add_to(m)

try:
    # Versi baru Streamlit menyarankan width="stretch".
    st_folium(
        m,
        height=540,
        width="stretch",
        returned_objects=["last_object_clicked"],
        key="peta_peternakan_indonesia",
    )

except TypeError:
    # Fallback jika streamlit-folium belum mendukung width="stretch".
    try:
        st_folium(
            m,
            height=540,
            use_container_width=True,
            returned_objects=["last_object_clicked"],
            key="peta_peternakan_indonesia_fallback_container",
        )
    except TypeError:
        st_folium(
            m,
            width=1200,
            height=540,
            returned_objects=["last_object_clicked"],
            key="peta_peternakan_indonesia_fallback_width",
        )

except Exception as map_error:
    st.warning(f"Komponen streamlit-folium gagal dimuat: {map_error}")
    components.html(m.get_root().render(), height=560, scrolling=False)


# ============================================================
# ANALISIS SENTINEL-2
# ============================================================
st.header("🛰️ Analisis NDVI Sentinel-2")

st.info(
    "NDVI cocok untuk melihat kondisi vegetasi/hijauan. "
    "Untuk data BPS agregat, hasil NDVI hanya membaca area representatif provinsi. "
    "Agar analisis benar-benar kondisi peternakan, upload CSV berisi koordinat kandang/lahan pakan yang aktual."
)

col1, col2 = st.columns([1, 2])

with col1:
    selected_name = st.selectbox(
        "Pilih data lokasi",
        options=filtered_df["nama"].tolist(),
        index=0,
    )

    selected_row = filtered_df[filtered_df["nama"] == selected_name].iloc[0]

    st.write(
        f"**Koordinat:** "
        f"{selected_row['latitude']:.4f}, {selected_row['longitude']:.4f}"
    )
    st.write(f"**Jenis:** {selected_row['jenis_ternak']}")
    st.write(
        f"**Jumlah:** "
        f"{int(selected_row['jumlah_ekor']):,} ekor".replace(",", ".")
    )

    if "provinsi" in filtered_df.columns:
        st.write(f"**Provinsi:** {selected_row.get('provinsi', '-')}")

    try:
        analyze_btn = st.button(
            "🚀 Analisis NDVI",
            type="primary",
            width="stretch",
        )
    except TypeError:
        analyze_btn = st.button(
            "🚀 Analisis NDVI",
            type="primary",
            use_container_width=True,
        )

with col2:
    if analyze_btn:
        if not gee_ready:
            st.error(
                "Google Earth Engine belum siap di Streamlit Cloud. "
                "Cek sidebar bagian Status Google Earth Engine dan DEBUG Secrets."
            )

        else:
            with st.spinner("Mengambil citra Sentinel-2 terbaru yang bebas awan..."):
                try:
                    lat = float(selected_row["latitude"])
                    lon = float(selected_row["longitude"])

                    point = ee.Geometry.Point([lon, lat])

                    end_date = ee.Date(datetime.now())
                    start_date = end_date.advance(-30, "day")

                    s2 = (
                        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                        .filterBounds(point)
                        .filterDate(start_date, end_date)
                        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
                        .sort("system:time_start", False)
                    )

                    image_count = s2.size().getInfo()

                    if image_count == 0:
                        st.warning(
                            "Tidak ada citra Sentinel-2 dengan awan < 20% "
                            "dalam 30 hari terakhir untuk lokasi ini."
                        )

                    else:
                        latest = s2.first()

                        ndvi = latest.normalizedDifference(["B8", "B4"]).rename("NDVI")

                        ndvi_stats = ndvi.reduceRegion(
                            reducer=ee.Reducer.mean(),
                            geometry=point.buffer(500),
                            scale=10,
                            maxPixels=1e9,
                        ).getInfo()

                        ndvi_value = ndvi_stats.get("NDVI")

                        image_date = (
                            ee.Date(latest.get("system:time_start"))
                            .format("YYYY-MM-dd")
                            .getInfo()
                        )

                        if ndvi_value is None:
                            st.error("Gagal menghitung NDVI untuk lokasi ini.")

                        else:
                            st.metric(
                                "NDVI rata-rata radius 500 m",
                                f"{ndvi_value:.3f}",
                            )

                            st.caption(f"Tanggal citra Sentinel-2: {image_date}")

                            if ndvi_value > 0.65:
                                st.success(
                                    "Vegetasi sangat sehat. "
                                    "Potensi hijauan/pakan di sekitar titik cukup baik."
                                )

                            elif ndvi_value > 0.45:
                                st.info(
                                    "Vegetasi sedang. "
                                    "Ketersediaan hijauan perlu dipantau berkala."
                                )

                            elif ndvi_value > 0.25:
                                st.warning(
                                    "Vegetasi rendah. "
                                    "Ada indikasi area kurang hijau atau tertekan kekeringan."
                                )

                            else:
                                st.error(
                                    "Vegetasi sangat rendah. "
                                    "Area kemungkinan dominan lahan terbuka/bangunan/air atau hijauan minim."
                                )

                except Exception as e:
                    st.error(f"Terjadi error saat mengambil data GEE: {e}")


# ============================================================
# STATISTIK
# ============================================================
st.markdown("---")
st.header("📈 Statistik Populasi")

col_stat1, col_stat2 = st.columns(2)

with col_stat1:
    st.subheader("Populasi per Jenis Ternak")

    chart_df = (
        filtered_df.groupby("jenis_ternak", as_index=True)["jumlah_ekor"]
        .sum()
        .sort_values(ascending=False)
    )

    st.bar_chart(chart_df)

with col_stat2:
    st.subheader("Populasi per Provinsi")

    if "provinsi" in filtered_df.columns:
        prov_chart = (
            filtered_df.groupby("provinsi", as_index=True)["jumlah_ekor"]
            .sum()
            .sort_values(ascending=False)
        )

        st.bar_chart(prov_chart)

    else:
        st.write("Kolom provinsi tidak tersedia pada data upload.")


st.subheader("📋 Tabel Data")

display_cols = [
    col for col in [
        "nama",
        "provinsi",
        "jenis_ternak",
        "jumlah_ekor",
        "tahun",
        "jenis_data",
        "latitude",
        "longitude",
        "sumber",
        "keterangan",
    ]
    if col in filtered_df.columns
]

try:
    st.dataframe(
        filtered_df[display_cols],
        width="stretch",
        hide_index=True,
    )
except TypeError:
    st.dataframe(
        filtered_df[display_cols],
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# CATATAN SUMBER & FOOTER
# ============================================================
st.markdown("---")

st.caption(
    "Sumber data bawaan: BPS, tabel Populasi Ternak Menurut Provinsi dan Jenis Ternak (ekor), 2024. "
    "Sebagian baris data dikurasi dari tabel resmi BPS untuk kebutuhan demo aplikasi. "
    "Untuk data lengkap seluruh provinsi/jenis ternak, unduh tabel BPS atau gunakan API BPS dengan key resmi."
)

st.link_button("Buka Tabel BPS", BPS_TABLE_URL)

st.markdown(
    f'<div class="custom-footer">Developed by {DEVELOPER_NAME}</div>',
    unsafe_allow_html=True,
)
