import json
import math
import re
from datetime import datetime, timedelta
from io import BytesIO
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
# STYLE: LIGHT THEME + LEGEND TERBACA + HIDE STREAMLIT BRANDING
# ============================================================
def apply_custom_style():
    st.markdown(
        """
        <style>
            :root {
                --background-color: #ffffff !important;
                --secondary-background-color: #f8fafc !important;
                --text-color: #111827 !important;
                --primary-color: #16a34a !important;
            }

            html, body, .stApp {
                background-color: #ffffff !important;
                color: #111827 !important;
            }

            section[data-testid="stSidebar"] {
                background-color: #f8fafc !important;
                color: #111827 !important;
            }

            section[data-testid="stSidebar"] * {
                color: #111827 !important;
            }

            div[data-testid="stMarkdownContainer"],
            h1, h2, h3, h4, h5, h6, p, span, label {
                color: #111827 !important;
            }

            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}

            [data-testid="stToolbar"] {
                visibility: hidden !important;
                height: 0%;
                position: fixed;
            }

            [data-testid="stDecoration"],
            [data-testid="stHeader"] {
                display: none !important;
            }

            [data-testid="stStatusWidget"] {
                visibility: hidden !important;
            }

            .stDeployButton,
            .viewerBadge_container__1QSob,
            .viewerBadge_link__1S137,
            .viewerBadge_text__1JaDK {
                display: none !important;
            }

            .block-container {
                padding-top: 1.5rem;
                padding-bottom: 5rem;
            }

            .source-note {
                background: #f8fafc !important;
                border: 1px solid #e2e8f0 !important;
                padding: 0.85rem 1rem;
                border-radius: 0.7rem;
                color: #111827 !important;
                margin-bottom: 1rem;
            }

            .insight-card {
                background: #ffffff !important;
                border: 1px solid #e2e8f0 !important;
                border-radius: 14px;
                padding: 1rem;
                margin-bottom: 0.75rem;
                box-shadow: 0 1px 8px rgba(15, 23, 42, 0.06);
                color: #111827 !important;
            }

            .insight-title {
                font-size: 15px;
                font-weight: 800;
                color: #0f172a !important;
                margin-bottom: 0.35rem;
            }

            .custom-footer {
                position: fixed;
                left: 0;
                bottom: 0;
                width: 100%;
                background: rgba(255, 255, 255, 0.98) !important;
                border-top: 1px solid #e5e7eb;
                text-align: center;
                padding: 10px 12px;
                font-size: 13px;
                font-weight: 600;
                color: #111827 !important;
                z-index: 999999;
            }

            input, textarea, select {
                color: #111827 !important;
                background-color: #ffffff !important;
            }

            div[data-baseweb="select"] * {
                color: #111827 !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


apply_custom_style()


# ============================================================
# HELPER UI
# ============================================================
def full_width_button(label, **kwargs):
    """Kompatibel untuk Streamlit lama dan baru."""
    try:
        return st.button(label, width="stretch", **kwargs)
    except TypeError:
        return st.button(label, use_container_width=True, **kwargs)


def show_metric_card(title, value, note=""):
    st.markdown(
        f"""
        <div class="insight-card">
            <div class="insight-title">{title}</div>
            <div style="font-size: 24px; font-weight: 900; color:#0f172a !important;">{value}</div>
            <div style="font-size: 13px; color:#475569 !important;">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# HEADER
# ============================================================
st.title("🐄 Dashboard Peternakan Indonesia")
st.subheader("Pemetaan peternakan, kondisi hijauan, dan rekomendasi tindakan berbasis NDVI Sentinel-2")

st.markdown(
    """
    <div class="source-note">
    <b>Status data:</b> data bawaan aplikasi menggunakan <b>data agregat provinsi BPS 2024</b>.
    Titik pada peta bawaan adalah <b>koordinat representatif ibu kota provinsi</b>, bukan titik kandang individu.
    Untuk insight yang benar-benar sesuai kondisi peternakan, gunakan menu <b>Upload CSV/XLSX Sendiri</b>
    berisi koordinat kandang atau lahan hijauan/pakan aktual.
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# GOOGLE EARTH ENGINE
# ============================================================
def safe_secret_get(key, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def normalize_private_key(private_key):
    private_key = str(private_key)
    private_key = private_key.replace("\\n", "\n")
    private_key = private_key.strip()
    private_key = private_key.replace("-----BEGIN PRIVATE KEY-----\n\n", "-----BEGIN PRIVATE KEY-----\n")
    private_key = private_key.replace("\n\n-----END PRIVATE KEY-----", "\n-----END PRIVATE KEY-----")
    return private_key


def read_gee_project():
    project = safe_secret_get("GEE_PROJECT", None)
    return str(project).strip() if project else None


def read_service_account_info():
    try:
        if "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
        elif "GEE_SERVICE_ACCOUNT_JSON" in st.secrets:
            info = json.loads(st.secrets["GEE_SERVICE_ACCOUNT_JSON"])
        else:
            st.session_state["gee_init_error"] = "Secrets belum menemukan service account."
            return None

        if "private_key" in info and info["private_key"]:
            info["private_key"] = normalize_private_key(info["private_key"])

        return info
    except Exception as e:
        st.session_state["gee_init_error"] = f"Format Secrets service account salah: {e}"
        return None


def initialize_gee():
    project = read_gee_project()
    service_account_info = read_service_account_info()

    try:
        if service_account_info:
            required_keys = [
                "type", "project_id", "private_key_id", "private_key",
                "client_email", "client_id", "token_uri",
            ]
            missing_keys = [key for key in required_keys if not service_account_info.get(key)]
            if missing_keys:
                raise ValueError(f"Secrets service account kurang field: {missing_keys}")

            private_key = service_account_info["private_key"]
            if not private_key.startswith("-----BEGIN PRIVATE KEY-----"):
                raise ValueError("Format private_key salah: harus diawali -----BEGIN PRIVATE KEY-----")
            if not private_key.strip().endswith("-----END PRIVATE KEY-----"):
                raise ValueError("Format private_key salah: harus diakhiri -----END PRIVATE KEY-----")

            credentials = ee.ServiceAccountCredentials(
                service_account_info["client_email"],
                key_data=json.dumps(service_account_info),
            )

            ee.Initialize(
                credentials=credentials,
                project=project or service_account_info.get("project_id"),
            )
            ee.Number(1).getInfo()

            st.session_state["gee_init_mode"] = "aktif"
            st.session_state["gee_init_error"] = ""
            return True

        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()

        ee.Number(1).getInfo()
        st.session_state["gee_init_mode"] = "aktif"
        st.session_state["gee_init_error"] = ""
        return True

    except Exception as e:
        st.session_state["gee_init_mode"] = "belum aktif"
        st.session_state["gee_init_error"] = str(e)
        return False


gee_ready = initialize_gee()

with st.sidebar.expander("Status Satelit", expanded=not gee_ready):
    if gee_ready:
        st.success("Satelit aktif")
        st.caption("Analisis NDVI Sentinel-2 siap digunakan.")
    else:
        st.warning("Satelit belum aktif")
        st.caption("Peta dan data tetap bisa digunakan. NDVI membutuhkan Google Earth Engine.")
        with st.expander("Detail teknis", expanded=False):
            st.code(st.session_state.get("gee_init_error", "Tidak ada detail error."), language="text")


# ============================================================
# DATA LOADING
# ============================================================
@st.cache_data(show_spinner=False)
def load_default_data():
    data_path = Path(DEFAULT_DATA_FILE)
    if not data_path.exists():
        data_path = Path(__file__).resolve().parent / DEFAULT_DATA_FILE

    try:
        return pd.read_csv(data_path)
    except FileNotFoundError:
        st.error(f"File {DEFAULT_DATA_FILE} tidak ditemukan. Pastikan file CSV berada satu folder dengan app.py.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Gagal membaca file data: {e}")
        return pd.DataFrame()


def read_uploaded_peternakan_file(uploaded_file):
    """Membaca upload CSV atau XLSX."""
    filename = uploaded_file.name.lower()
    try:
        if filename.endswith(".csv"):
            return pd.read_csv(uploaded_file)
        if filename.endswith(".xlsx"):
            return pd.read_excel(uploaded_file, sheet_name=0)
        st.error("Format file tidak didukung. Gunakan CSV atau XLSX.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Gagal membaca file upload: {e}")
        return pd.DataFrame()


def parse_count(value):
    """Jumlah ekor: angka bulat. Hapus pemisah ribuan kalau ada."""
    if pd.isna(value):
        return 0
    if isinstance(value, str):
        value = value.strip().replace(" ", "")
        # Anggap titik/koma sebagai pemisah ribuan untuk kolom jumlah.
        value = value.replace(".", "").replace(",", "")
    try:
        return int(float(value))
    except Exception:
        return 0


def parse_decimal(value):
    """Angka desimal seperti luas lahan. Mendukung koma desimal."""
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip().replace(" ", "").replace(",", ".")
    try:
        return float(value)
    except Exception:
        return None


def clean_and_validate_data(df):
    required_cols = ["nama", "latitude", "longitude", "jenis_ternak", "jumlah_ekor"]
    missing = [col for col in required_cols if col not in df.columns]

    if missing:
        st.error(f"Data kurang kolom wajib: {missing}")
        st.stop()

    cleaned = df.copy()

    cleaned["latitude"] = cleaned["latitude"].apply(parse_decimal)
    cleaned["longitude"] = cleaned["longitude"].apply(parse_decimal)
    cleaned["jumlah_ekor"] = cleaned["jumlah_ekor"].apply(parse_count)

    if "luas_lahan_ha" in cleaned.columns:
        cleaned["luas_lahan_ha"] = cleaned["luas_lahan_ha"].apply(parse_decimal)

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
    options=["Data Resmi BPS 2024 (Agregat Provinsi)", "Upload CSV/XLSX Sendiri"],
    index=0,
)

uploaded_file = None

if data_source == "Upload CSV/XLSX Sendiri":
    uploaded_file = st.sidebar.file_uploader(
        "Upload file CSV/XLSX lokasi peternakan",
        type=["csv", "xlsx"],
        help=(
            "Kolom wajib: nama, latitude, longitude, jenis_ternak, jumlah_ekor. "
            "Kolom opsional: provinsi, kabupaten_kota, kecamatan, desa, alamat, luas_lahan_ha, tahun, sumber."
        ),
    )

if data_source == "Data Resmi BPS 2024 (Agregat Provinsi)":
    df = load_default_data()
    if not df.empty:
        st.sidebar.success(f"✅ {len(df)} baris data agregat dimuat")
        st.sidebar.caption("Satuan: ekor. Titik peta: ibu kota provinsi.")
elif uploaded_file is not None:
    df = read_uploaded_peternakan_file(uploaded_file)
    st.sidebar.success(f"✅ {len(df)} baris data dimuat dari {uploaded_file.name}")
else:
    st.sidebar.warning("Upload CSV/XLSX terlebih dahulu atau gunakan data BPS bawaan.")
    st.stop()

df = clean_and_validate_data(df)


# ============================================================
# FILTER DATA
# ============================================================
st.sidebar.markdown("---")
st.sidebar.subheader("🔎 Filter")

if "provinsi" in df.columns:
    provinsi_options = sorted(df["provinsi"].dropna().unique().tolist())
    selected_provinsi = st.sidebar.multiselect("Provinsi", provinsi_options, default=provinsi_options)
else:
    selected_provinsi = []

jenis_options = sorted(df["jenis_ternak"].dropna().unique().tolist())
selected_jenis = st.sidebar.multiselect("Jenis ternak", jenis_options, default=jenis_options)

filtered_df = df.copy()

if "provinsi" in filtered_df.columns and selected_provinsi:
    filtered_df = filtered_df[filtered_df["provinsi"].isin(selected_provinsi)]

if selected_jenis:
    filtered_df = filtered_df[filtered_df["jenis_ternak"].isin(selected_jenis)]

if filtered_df.empty:
    st.warning("Tidak ada data sesuai filter.")
    st.stop()


# ============================================================
# HELPER INSIGHT
# ============================================================
def classify_ndvi(ndvi_value):
    if ndvi_value is None:
        return "Tidak tersedia", "Data NDVI belum tersedia.", "gray", [
            "Coba perluas periode pencarian citra atau cek kembali koordinat lokasi."
        ]

    if ndvi_value > 0.65:
        return "Hijauan sangat baik", "Vegetasi sangat sehat.", "green", [
            "Pertahankan pola pemeliharaan lahan hijauan.",
            "Lakukan monitoring ulang 7–14 hari ke depan.",
            "Manfaatkan kondisi baik ini untuk menyiapkan stok pakan cadangan."
        ]
    if ndvi_value > 0.45:
        return "Hijauan cukup", "Vegetasi sedang dan masih mendukung.", "blue", [
            "Pantau ketersediaan hijauan secara berkala.",
            "Mulai siapkan pakan tambahan bila jumlah ternak tinggi.",
            "Periksa area yang mulai mengering di sekitar kandang/lahan pakan."
        ]
    if ndvi_value > 0.25:
        return "Hijauan rendah", "Vegetasi kurang optimal.", "orange", [
            "Tambahkan pakan dari luar lahan atau stok pakan kering.",
            "Periksa ketersediaan air dan kondisi lahan pakan.",
            "Prioritaskan lahan hijauan yang masih produktif untuk ternak utama."
        ]

    return "Hijauan sangat rendah", "Vegetasi minim atau lahan dominan terbuka/bangunan/air.", "red", [
        "Segera siapkan pakan tambahan minimal untuk 7 hari.",
        "Cek kemungkinan kekeringan, lahan terbuka, atau kesalahan titik koordinat.",
        "Jika koordinat berada di kandang tertutup, gunakan koordinat lahan hijauan/pakan."
    ]


def density_insight(jenis_ternak, jumlah_ekor, luas_lahan_ha):
    if luas_lahan_ha is None or luas_lahan_ha <= 0:
        return None, "Luas lahan belum tersedia", [
            "Tambahkan kolom luas_lahan_ha agar aplikasi dapat menilai kepadatan ternak."
        ]

    density = jumlah_ekor / luas_lahan_ha
    jenis_lower = str(jenis_ternak).lower()

    if "ayam" in jenis_lower or "itik" in jenis_lower:
        if density <= 1000:
            status = "Kepadatan rendah-sedang"
            recs = ["Kepadatan unggas masih relatif terkendali menurut input luas lahan."]
        elif density <= 5000:
            status = "Kepadatan tinggi"
            recs = ["Periksa ventilasi, air minum, sanitasi, dan manajemen pakan lebih rutin."]
        else:
            status = "Kepadatan sangat tinggi"
            recs = ["Prioritaskan sanitasi kandang, ventilasi, dan kontrol penyakit."]
    elif any(x in jenis_lower for x in ["kambing", "domba"]):
        if density <= 25:
            status = "Kepadatan rendah-sedang"
            recs = ["Kepadatan ternak relatif aman menurut input luas lahan."]
        elif density <= 75:
            status = "Kepadatan tinggi"
            recs = ["Tambahkan sumber hijauan/pakan dari luar lahan bila NDVI menurun."]
        else:
            status = "Kepadatan sangat tinggi"
            recs = ["Risiko tekanan pakan meningkat. Siapkan pakan tambahan dan evaluasi kapasitas kandang."]
    else:
        if density <= 5:
            status = "Kepadatan rendah-sedang"
            recs = ["Kepadatan sapi/ternak besar relatif aman menurut input luas lahan."]
        elif density <= 20:
            status = "Kepadatan tinggi"
            recs = ["Pantau hijauan dan air minum karena kebutuhan pakan cukup besar."]
        else:
            status = "Kepadatan sangat tinggi"
            recs = ["Risiko kekurangan hijauan tinggi. Tambahkan stok pakan dan evaluasi daya dukung lahan."]

    return density, status, recs



def calculate_trend_change(trend_df):
    """Menghitung perubahan NDVI dari awal ke akhir periode 90 hari."""
    if trend_df is None or trend_df.empty or "ndvi" not in trend_df.columns:
        return None

    valid = trend_df["ndvi"].dropna()
    if len(valid) < 2:
        return None

    first = float(valid.iloc[0])
    last = float(valid.iloc[-1])

    if first == 0:
        return None

    return ((last - first) / abs(first)) * 100


def estimate_feed_requirement(jenis_ternak, jumlah_ekor):
    """
    Estimasi kebutuhan pakan harian sederhana.
    Angka ini bersifat pendekatan umum agar peternak awam memahami skala kebutuhan pakan.
    """
    jenis = str(jenis_ternak).lower()
    jumlah = int(jumlah_ekor)

    if "sapi perah" in jenis:
        min_kg, max_kg, satuan = 30, 40, "kg hijauan/ekor/hari"
    elif "sapi" in jenis or "kerbau" in jenis:
        min_kg, max_kg, satuan = 25, 35, "kg hijauan/ekor/hari"
    elif "kambing" in jenis or "domba" in jenis:
        min_kg, max_kg, satuan = 3, 5, "kg hijauan/ekor/hari"
    elif "ayam" in jenis or "itik" in jenis:
        # Pakan unggas lebih relevan dihitung gram pakan jadi per hari.
        min_kg, max_kg, satuan = 0.08, 0.12, "kg pakan/ekor/hari"
    else:
        min_kg, max_kg, satuan = 2, 5, "kg pakan/ekor/hari"

    total_min = jumlah * min_kg
    total_max = jumlah * max_kg

    return {
        "min_per_ekor": min_kg,
        "max_per_ekor": max_kg,
        "total_min": total_min,
        "total_max": total_max,
        "satuan": satuan,
        "teks": f"±{total_min:,.0f}–{total_max:,.0f} kg/hari".replace(",", "."),
    }


def calculate_peternakan_score(ndvi_value, trend_change, density_status):
    """
    Skor 0–100 agar peternak awam mudah membaca kondisi.
    Bobot:
    - NDVI/kondisi hijauan: 50%
    - Tren NDVI 90 hari: 25%
    - Kepadatan ternak: 25%
    """
    if ndvi_value is None:
        ndvi_score = 50
    elif ndvi_value > 0.65:
        ndvi_score = 92
    elif ndvi_value > 0.45:
        ndvi_score = 75
    elif ndvi_value > 0.25:
        ndvi_score = 50
    else:
        ndvi_score = 25

    if trend_change is None:
        trend_score = 60
    elif trend_change > 10:
        trend_score = 85
    elif trend_change >= -10:
        trend_score = 70
    elif trend_change >= -25:
        trend_score = 45
    else:
        trend_score = 25

    density_text = str(density_status).lower()
    if "belum tersedia" in density_text:
        density_score = 60
    elif "rendah" in density_text or "sedang" in density_text:
        density_score = 85
    elif "sangat tinggi" in density_text:
        density_score = 30
    elif "tinggi" in density_text:
        density_score = 55
    else:
        density_score = 60

    score = round((ndvi_score * 0.50) + (trend_score * 0.25) + (density_score * 0.25))

    if score >= 80:
        lampu = "🟢"
        label = "Sangat Baik"
        risiko = "Rendah"
        arti = "Kondisi hijauan dan kepadatan relatif mendukung."
    elif score >= 60:
        lampu = "🟡"
        label = "Baik / Perlu Dipantau"
        risiko = "Sedang"
        arti = "Kondisi masih cukup baik, tetapi tetap perlu monitoring."
    elif score >= 40:
        lampu = "🟠"
        label = "Perlu Perhatian"
        risiko = "Cukup Tinggi"
        arti = "Ada tanda kondisi pakan/hijauan atau kepadatan mulai perlu diwaspadai."
    else:
        lampu = "🔴"
        label = "Risiko Tinggi"
        risiko = "Tinggi"
        arti = "Perlu tindakan cepat agar kebutuhan pakan dan kondisi ternak tetap aman."

    return {
        "score": score,
        "lampu": lampu,
        "label": label,
        "risiko": risiko,
        "arti": arti,
        "ndvi_score": ndvi_score,
        "trend_score": trend_score,
        "density_score": density_score,
    }


def explain_ndvi_simple(ndvi_value):
    """Penjelasan NDVI dalam bahasa awam."""
    if ndvi_value is None:
        return "Nilai NDVI belum tersedia. Aplikasi belum bisa membaca kondisi hijauan dari citra satelit pada periode ini."
    if ndvi_value > 0.65:
        return "Angka NDVI menunjukkan rumput atau vegetasi di sekitar lokasi tampak sangat hijau dan sehat."
    if ndvi_value > 0.45:
        return "Angka NDVI menunjukkan hijauan masih cukup, tetapi tetap perlu dipantau agar tidak menurun."
    if ndvi_value > 0.25:
        return "Angka NDVI menunjukkan hijauan mulai rendah. Rumput bisa kurang lebat, mulai kering, atau area sekitar bercampur bangunan/lahan terbuka."
    return "Angka NDVI sangat rendah. Kemungkinan area sekitar titik kurang hijau, kering, dominan bangunan/jalan/air, atau koordinat tidak tepat di lahan hijauan."


def build_simple_summary(row, ndvi_value, trend_change, score_info, density_status, feed_info):
    """Kesimpulan singkat yang mudah dipahami peternak."""
    nama = row.get("nama", "Lokasi")
    jenis = row.get("jenis_ternak", "ternak")
    jumlah = int(row.get("jumlah_ekor", 0))

    if trend_change is None:
        trend_text = "tren 90 hari belum cukup terbaca"
    elif trend_change < -10:
        trend_text = f"tren hijauan menurun sekitar {abs(trend_change):.1f}% dalam 90 hari"
    elif trend_change > 10:
        trend_text = f"tren hijauan membaik sekitar {trend_change:.1f}% dalam 90 hari"
    else:
        trend_text = "tren hijauan relatif stabil dalam 90 hari"

    return (
        f"{score_info['lampu']} Kondisi di {nama} berada pada kategori **{score_info['label']}** "
        f"dengan skor **{score_info['score']}/100**. "
        f"Data menunjukkan {explain_ndvi_simple(ndvi_value)} "
        f"Selain itu, {trend_text}. "
        f"Dengan jumlah {jumlah:,} ekor {jenis}, estimasi kebutuhan pakan harian sekitar "
        f"**{feed_info['teks']}**. Status kepadatan: **{density_status}**."
    ).replace(",", ".")


def build_daily_priority_actions(score_info, ndvi_value, trend_change, density_status):
    """Prioritas tindakan praktis untuk hari ini."""
    actions = []

    if score_info["risiko"] in ["Tinggi", "Cukup Tinggi"]:
        actions.append("Cek stok pakan hari ini dan siapkan pakan cadangan minimal 7 hari.")
    else:
        actions.append("Cek stok pakan dan pastikan cukup untuk beberapa hari ke depan.")

    actions.append("Pastikan air minum ternak tersedia dan bersih.")

    if ndvi_value is None:
        actions.append("Cek ulang koordinat dan coba analisis lagi dengan periode/awan yang lebih longgar.")
    elif ndvi_value <= 0.45:
        actions.append("Periksa kondisi rumput/lahan hijauan di sekitar kandang karena hijauan mulai rendah.")
    else:
        actions.append("Pertahankan area hijauan yang masih baik dan lakukan monitoring berkala.")

    if trend_change is not None and trend_change < -10:
        actions.append("Karena tren hijauan menurun, mulai tambah sumber pakan dari luar lahan.")

    if "sangat tinggi" in str(density_status).lower() or "tinggi" in str(density_status).lower():
        actions.append("Evaluasi kepadatan kandang/lahan karena kebutuhan pakan dan sanitasi meningkat.")

    actions.append("Catat perubahan kondisi ternak: nafsu makan, minum, aktivitas, dan gejala sakit.")

    return actions


def coordinate_validation_note(ndvi_value):
    """Peringatan agar peternak tidak salah tafsir jika titik berada di bangunan/jalan."""
    if ndvi_value is None or ndvi_value <= 0.25:
        return (
            "Catatan koordinat: jika lokasi sebenarnya memiliki rumput/hijauan tetapi NDVI sangat rendah, "
            "pastikan titik koordinat tidak berada tepat di atap kandang, jalan, bangunan, sungai, atau area kosong. "
            "Untuk analisis pakan, titik terbaik adalah lahan hijauan/pakan."
        )
    return (
        "Catatan koordinat: untuk hasil lebih akurat, gunakan titik kandang terbuka atau lahan hijauan/pakan, "
        "bukan kantor desa atau titik administratif."
    )


def build_recommendation_report(row, ndvi_value=None, trend_df=None, score_info=None, feed_info=None, density=None, density_status=None, kesimpulan_awam=None):
    status, desc, _, ndvi_recs = classify_ndvi(ndvi_value)

    luas = row.get("luas_lahan_ha", None) if "luas_lahan_ha" in row.index else None

    if density is None or density_status is None:
        density, density_status, density_recs = density_insight(
            row.get("jenis_ternak", "-"),
            int(row.get("jumlah_ekor", 0)),
            luas,
        )
    else:
        _, _, density_recs = density_insight(
            row.get("jenis_ternak", "-"),
            int(row.get("jumlah_ekor", 0)),
            luas,
        )

    trend_change = calculate_trend_change(trend_df)

    if feed_info is None:
        feed_info = estimate_feed_requirement(row.get("jenis_ternak", "-"), int(row.get("jumlah_ekor", 0)))

    if score_info is None:
        score_info = calculate_peternakan_score(ndvi_value, trend_change, density_status)

    if kesimpulan_awam is None:
        kesimpulan_awam = build_simple_summary(row, ndvi_value, trend_change, score_info, density_status, feed_info)

    report = {
        "tanggal_analisis": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "nama": row.get("nama", "-"),
        "jenis_ternak": row.get("jenis_ternak", "-"),
        "jumlah_ekor": int(row.get("jumlah_ekor", 0)),
        "latitude": row.get("latitude", None),
        "longitude": row.get("longitude", None),
        "ndvi": ndvi_value,
        "status_hijauan": status,
        "keterangan_hijauan": desc,
        "perubahan_ndvi_90_hari_persen": trend_change,
        "skor_kondisi_peternakan": score_info["score"],
        "status_lampu": f"{score_info['lampu']} {score_info['label']}",
        "risiko_kekurangan_pakan": score_info["risiko"],
        "estimasi_pakan_min_kg_hari": feed_info["total_min"],
        "estimasi_pakan_max_kg_hari": feed_info["total_max"],
        "estimasi_pakan_teks": feed_info["teks"],
        "kepadatan_ekor_per_ha": density,
        "status_kepadatan": density_status,
        "kesimpulan_awam": kesimpulan_awam,
        "catatan_koordinat": coordinate_validation_note(ndvi_value),
        "rekomendasi": " | ".join(ndvi_recs + density_recs),
    }

    return pd.DataFrame([report])


def safe_filename(text):
    """Membersihkan nama file agar aman untuk download."""
    text = str(text).strip().replace(" ", "_")
    text = re.sub(r"[^A-Za-z0-9_\\-]", "", text)
    return text or "laporan_peternakan"


def create_xlsx_report_bytes(report_df, trend_df=None, rekomendasi=None):
    """
    Membuat laporan ringkas format XLSX dalam memory.
    Sheet:
    1. Laporan Ringkas
    2. Tren NDVI 90 Hari
    3. Rekomendasi
    """
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        report_df.to_excel(writer, index=False, sheet_name="Laporan Ringkas")

        if trend_df is not None and not trend_df.empty:
            trend_df.to_excel(writer, index=False, sheet_name="Tren NDVI 90 Hari")

        if rekomendasi:
            rec_df = pd.DataFrame({
                "No": list(range(1, len(rekomendasi) + 1)),
                "Rekomendasi": rekomendasi,
            })
            rec_df.to_excel(writer, index=False, sheet_name="Rekomendasi")

        workbook = writer.book

        for sheet_name in workbook.sheetnames:
            ws = workbook[sheet_name]
            ws.freeze_panes = "A2"

            for cell in ws[1]:
                cell.font = cell.font.copy(bold=True, color="FFFFFF")
                cell.fill = cell.fill.copy(fill_type="solid", fgColor="16A34A")
                cell.alignment = cell.alignment.copy(horizontal="center", vertical="center", wrap_text=True)

            for column_cells in ws.columns:
                max_length = 0
                col_letter = column_cells[0].column_letter
                for cell in column_cells:
                    value = "" if cell.value is None else str(cell.value)
                    max_length = max(max_length, len(value))
                    cell.alignment = cell.alignment.copy(vertical="top", wrap_text=True)

                adjusted_width = min(max(max_length + 2, 12), 42)
                ws.column_dimensions[col_letter].width = adjusted_width

    output.seek(0)
    return output.getvalue()


def get_ndvi_mean(point, start_date, end_date, cloud_threshold=30, buffer_meter=500):
    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(point)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_threshold))
        .sort("system:time_start", False)
    )

    count = s2.size().getInfo()
    if count == 0:
        return None, 0

    ndvi_img = s2.median().normalizedDifference(["B8", "B4"]).rename("NDVI")
    stats = ndvi_img.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=point.buffer(buffer_meter),
        scale=10,
        maxPixels=1e9,
    ).getInfo()

    return stats.get("NDVI"), count


def get_ndvi_trend_90_days(point, cloud_threshold=30, buffer_meter=500):
    today = datetime.now()
    records = []

    # 6 periode x 15 hari = 90 hari
    for i in range(6, 0, -1):
        start_dt = today - timedelta(days=i * 15)
        end_dt = today - timedelta(days=(i - 1) * 15)

        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")
        label = f"{start_dt.strftime('%d %b')} - {end_dt.strftime('%d %b')}"

        try:
            ndvi, count = get_ndvi_mean(point, start_str, end_str, cloud_threshold, buffer_meter)
        except Exception:
            ndvi, count = None, 0

        records.append({
            "periode": label,
            "tanggal_mulai": start_str,
            "tanggal_selesai": end_str,
            "ndvi": ndvi,
            "jumlah_citra": count,
        })

    return pd.DataFrame(records)


# ============================================================
# RINGKASAN ATAS
# ============================================================
total_populasi = int(filtered_df["jumlah_ekor"].sum())
total_lokasi = len(filtered_df)
total_jenis = filtered_df["jenis_ternak"].nunique()
total_provinsi = filtered_df["provinsi"].nunique() if "provinsi" in filtered_df.columns else "-"

metric_cols = st.columns(4)
with metric_cols[0]:
    st.metric("Lokasi/Data", f"{total_lokasi:,}".replace(",", "."))
with metric_cols[1]:
    st.metric("Total Populasi", f"{total_populasi:,}".replace(",", "."))
with metric_cols[2]:
    st.metric("Jenis Ternak", total_jenis)
with metric_cols[3]:
    st.metric("Provinsi", total_provinsi)


# ============================================================
# SIDEBAR: RINGKASAN
# ============================================================
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Ringkasan")
st.sidebar.metric("Baris Data", total_lokasi)
st.sidebar.metric("Total Populasi", f"{total_populasi:,}".replace(",", "."))

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
    "Sapi Perah": "#2563eb",
    "Sapi Potong": "#16a34a",
    "Sapi": "#16a34a",
    "Kerbau": "#7c3aed",
    "Kambing": "#f97316",
    "Domba": "#0891b2",
    "Ayam": "#dc2626",
    "Ayam Buras": "#dc2626",
    "Ayam Ras Pedaging": "#991b1b",
    "Ayam Ras Petelur": "#ec4899",
    "Itik": "#38bdf8",
    "Lainnya": "#64748b",
}


def marker_radius(value):
    return max(5, min(18, 3 + math.log10(max(int(value), 1)) * 2.2))


center_lat = filtered_df["latitude"].mean()
center_lon = filtered_df["longitude"].mean()

m = folium.Map(location=[center_lat, center_lon], zoom_start=5, tiles="OpenStreetMap")
folium.TileLayer("CartoDB positron", name="CartoDB Positron").add_to(m)
folium.TileLayer("CartoDB dark_matter", name="CartoDB Dark").add_to(m)

for _, row in filtered_df.iterrows():
    jenis = str(row["jenis_ternak"])
    color = color_map.get(jenis, "#64748b")
    jumlah = int(row["jumlah_ekor"])

    popup_html = f"""
    <div style="font-family: Arial, sans-serif; color:#111827;">
        <b>{row['nama']}</b><br>
        Jenis ternak: {jenis}<br>
        Jumlah populasi: {jumlah:,} ekor<br>
    """.replace(",", ".")

    for col in ["provinsi", "kabupaten_kota", "kecamatan", "desa", "tahun", "sumber"]:
        if col in filtered_df.columns:
            popup_html += f"{col.replace('_', ' ').title()}: {row.get(col, '-')}<br>"

    if "luas_lahan_ha" in filtered_df.columns and pd.notna(row.get("luas_lahan_ha", None)):
        popup_html += f"Luas lahan: {row.get('luas_lahan_ha', '-')} ha<br>"

    popup_html += f"Koordinat: {row['latitude']:.4f}, {row['longitude']:.4f}</div>"

    folium.CircleMarker(
        location=[row["latitude"], row["longitude"]],
        radius=marker_radius(jumlah),
        popup=folium.Popup(popup_html, max_width=360),
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.72,
        tooltip=f"{row['nama']} - {jumlah:,} ekor".replace(",", "."),
    ).add_to(m)


legend_items = ""
for jenis in selected_jenis:
    warna = color_map.get(jenis, "#64748b")
    legend_items += f"""
    <div style="display:flex;align-items:center;gap:8px;margin:4px 0;color:#111827!important;font-weight:700;white-space:nowrap;">
        <span style="color:{warna}!important;font-size:20px;line-height:1;font-weight:900;text-shadow:0 0 1px #000000;">●</span>
        <span style="color:#111827!important;font-size:14px;font-weight:700;">{jenis}</span>
    </div>
    """

legend_html = f"""
<div style="
    position: fixed; bottom: 72px; left: 50px; min-width: 210px; max-width: 300px;
    max-height: 260px; overflow-y: auto; background: #ffffff !important;
    color: #111827 !important; border: 2px solid #334155; z-index: 999999;
    font-family: Arial, sans-serif; font-size: 14px; line-height: 1.45;
    padding: 12px 14px; border-radius: 12px; box-shadow: 0 6px 22px rgba(0,0,0,.35);
">
    <div style="color:#111827!important;font-size:16px;font-weight:900;margin-bottom:8px;border-bottom:1px solid #cbd5e1;padding-bottom:5px;">
        Legenda
    </div>
    {legend_items}
</div>
"""

m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl().add_to(m)

try:
    st_folium(m, height=540, width="stretch", returned_objects=["last_object_clicked"], key="peta_peternakan_indonesia")
except TypeError:
    try:
        st_folium(m, height=540, use_container_width=True, returned_objects=["last_object_clicked"], key="peta_peternakan_indonesia_fallback_container")
    except TypeError:
        st_folium(m, width=1200, height=540, returned_objects=["last_object_clicked"], key="peta_peternakan_indonesia_fallback_width")
except Exception as map_error:
    st.warning(f"Komponen streamlit-folium gagal dimuat: {map_error}")
    components.html(m.get_root().render(), height=560, scrolling=False)


# ============================================================
# INSIGHT OPERASIONAL
# ============================================================
st.header("🔍 Insight Peternakan")

selected_name = st.selectbox("Pilih lokasi/data untuk dianalisis", options=filtered_df["nama"].tolist(), index=0)
selected_row = filtered_df[filtered_df["nama"] == selected_name].iloc[0]

col_info, col_rekom = st.columns([1, 1])

with col_info:
    st.subheader("Profil Lokasi")
    st.write(f"**Nama:** {selected_row.get('nama', '-')}")
    st.write(f"**Jenis ternak:** {selected_row.get('jenis_ternak', '-')}")
    st.write(f"**Jumlah:** {int(selected_row.get('jumlah_ekor', 0)):,} ekor".replace(",", "."))
    st.write(f"**Koordinat:** {selected_row.get('latitude', 0):.5f}, {selected_row.get('longitude', 0):.5f}")

    if "provinsi" in filtered_df.columns:
        st.write(f"**Provinsi:** {selected_row.get('provinsi', '-')}")
    if "luas_lahan_ha" in filtered_df.columns and pd.notna(selected_row.get("luas_lahan_ha", None)):
        st.write(f"**Luas lahan:** {selected_row.get('luas_lahan_ha')} ha")

with col_rekom:
    st.subheader("Kepadatan Ternak")
    luas_lahan = selected_row.get("luas_lahan_ha", None) if "luas_lahan_ha" in selected_row.index else None
    density, density_status, density_recs = density_insight(
        selected_row.get("jenis_ternak", "-"),
        int(selected_row.get("jumlah_ekor", 0)),
        luas_lahan,
    )

    if density is None:
        show_metric_card("Status Kepadatan", density_status, "Tambahkan luas_lahan_ha pada CSV/XLSX untuk insight lebih baik.")
    else:
        show_metric_card("Kepadatan", f"{density:.2f} ekor/ha", density_status)
        for rec in density_recs:
            st.write(f"• {rec}")


# ============================================================
# ANALISIS SENTINEL-2 + REKOMENDASI
# ============================================================
st.header("🛰️ Analisis Hijauan/Pakan Berbasis NDVI Sentinel-2")

st.info(
    "NDVI membantu membaca kondisi vegetasi/hijauan sekitar titik lokasi. "
    "Untuk hasil paling akurat, gunakan koordinat kandang terbuka atau lahan hijauan/pakan, bukan kantor/desa."
)

cloud_threshold = st.slider("Batas maksimal awan citra Sentinel-2 (%)", min_value=10, max_value=80, value=30, step=5)
buffer_meter = st.slider("Radius analisis sekitar titik (meter)", min_value=100, max_value=2000, value=500, step=100)

run_ndvi = full_width_button("🚀 Analisis NDVI + Tren 90 Hari", type="primary")

if run_ndvi:
    if not gee_ready:
        st.error("Status satelit belum aktif. Aktifkan Google Earth Engine agar analisis NDVI dapat berjalan.")
    else:
        with st.spinner("Mengambil dan menganalisis citra Sentinel-2..."):
            try:
                lat = float(selected_row["latitude"])
                lon = float(selected_row["longitude"])
                point = ee.Geometry.Point([lon, lat])

                today = datetime.now()
                latest_start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
                latest_end = today.strftime("%Y-%m-%d")

                ndvi_value, image_count = get_ndvi_mean(point, latest_start, latest_end, cloud_threshold, buffer_meter)
                trend_df = get_ndvi_trend_90_days(point, cloud_threshold, buffer_meter)

                status, desc, color, ndvi_recs = classify_ndvi(ndvi_value)
                trend_change = calculate_trend_change(trend_df)
                feed_info = estimate_feed_requirement(
                    selected_row.get("jenis_ternak", "-"),
                    int(selected_row.get("jumlah_ekor", 0)),
                )
                score_info = calculate_peternakan_score(ndvi_value, trend_change, density_status)
                kesimpulan_awam = build_simple_summary(
                    selected_row,
                    ndvi_value,
                    trend_change,
                    score_info,
                    density_status,
                    feed_info,
                )
                priority_actions = build_daily_priority_actions(
                    score_info,
                    ndvi_value,
                    trend_change,
                    density_status,
                )
                coord_note = coordinate_validation_note(ndvi_value)

                report_df = build_recommendation_report(
                    selected_row,
                    ndvi_value,
                    trend_df,
                    score_info=score_info,
                    feed_info=feed_info,
                    density=density,
                    density_status=density_status,
                    kesimpulan_awam=kesimpulan_awam,
                )

                st.subheader("Kesimpulan Mudah Dipahami")
                st.markdown(kesimpulan_awam)

                insight_cols = st.columns(4)
                with insight_cols[0]:
                    st.metric("Skor Kondisi", f"{score_info['score']}/100", score_info["label"])
                with insight_cols[1]:
                    st.metric("Status", f"{score_info['lampu']} {score_info['label']}")
                with insight_cols[2]:
                    st.metric("Risiko Pakan", score_info["risiko"])
                with insight_cols[3]:
                    st.metric("Estimasi Pakan", feed_info["teks"])

                with st.expander("Arti hasil pengamatan untuk peternak awam", expanded=True):
                    st.write(f"**Arti NDVI:** {explain_ndvi_simple(ndvi_value)}")
                    if trend_change is None:
                        st.write("**Tren 90 hari:** belum cukup data untuk menyimpulkan perubahan.")
                    elif trend_change < -10:
                        st.write(f"**Tren 90 hari:** menurun sekitar {abs(trend_change):.1f}%. Ketersediaan hijauan perlu diwaspadai.")
                    elif trend_change > 10:
                        st.write(f"**Tren 90 hari:** naik sekitar {trend_change:.1f}%. Kondisi hijauan cenderung membaik.")
                    else:
                        st.write(f"**Tren 90 hari:** relatif stabil, perubahan sekitar {trend_change:.1f}%.")
                    st.write(f"**Kebutuhan pakan:** {feed_info['teks']} untuk {int(selected_row.get('jumlah_ekor', 0)):,} ekor.".replace(",", "."))
                    st.info(coord_note)

                st.subheader("Prioritas Tindakan Hari Ini")
                for i, action in enumerate(priority_actions, start=1):
                    st.write(f"{i}. {action}")

                st.subheader("Hasil Kondisi Hijauan")
                if ndvi_value is None:
                    st.warning("NDVI belum tersedia untuk lokasi dan periode ini.")
                else:
                    st.metric("NDVI rata-rata 30 hari terakhir", f"{ndvi_value:.3f}", help="Rata-rata NDVI pada radius analisis.")
                    st.write(f"**Status:** {status}")
                    st.write(f"**Keterangan:** {desc}")
                    st.caption(f"Jumlah citra Sentinel-2 yang dipakai: {image_count}")

                st.subheader("Tren NDVI 90 Hari")
                if trend_df["ndvi"].notna().sum() == 0:
                    st.warning("Tren NDVI belum tersedia. Coba naikkan batas awan atau cek koordinat.")
                else:
                    chart_df = trend_df.set_index("periode")[["ndvi"]]
                    st.line_chart(chart_df)
                    st.dataframe(trend_df, width="stretch", hide_index=True)

                    valid = trend_df["ndvi"].dropna()
                    if len(valid) >= 2:
                        first = valid.iloc[0]
                        last = valid.iloc[-1]
                        change = ((last - first) / abs(first)) * 100 if first != 0 else 0
                        if change < -10:
                            st.warning(f"NDVI turun sekitar {change:.1f}% selama 90 hari. Ada indikasi penurunan hijauan.")
                        elif change > 10:
                            st.success(f"NDVI naik sekitar {change:.1f}% selama 90 hari. Kondisi hijauan cenderung membaik.")
                        else:
                            st.info(f"Perubahan NDVI sekitar {change:.1f}%. Kondisi hijauan relatif stabil.")

                st.subheader("Rekomendasi Otomatis untuk Peternak")
                combined_recs = priority_actions + ndvi_recs + density_recs
                for i, rec in enumerate(combined_recs, start=1):
                    st.write(f"{i}. {rec}")

                xlsx_data = create_xlsx_report_bytes(
                    report_df=report_df,
                    trend_df=trend_df,
                    rekomendasi=combined_recs,
                )

                st.download_button(
                    "⬇️ Download Laporan Ringkas XLSX",
                    data=xlsx_data,
                    file_name=f"laporan_peternakan_{safe_filename(selected_name)}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            except Exception as e:
                st.error(f"Terjadi error saat analisis NDVI: {e}")


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
        "nama", "provinsi", "kabupaten_kota", "kecamatan", "desa", "alamat",
        "jenis_ternak", "jumlah_ekor", "luas_lahan_ha", "tahun", "jenis_data",
        "latitude", "longitude", "sumber", "keterangan",
    ]
    if col in filtered_df.columns
]

try:
    st.dataframe(filtered_df[display_cols], width="stretch", hide_index=True)
except TypeError:
    st.dataframe(filtered_df[display_cols], use_container_width=True, hide_index=True)


# ============================================================
# CATATAN SUMBER & FOOTER
# ============================================================
st.markdown("---")

st.caption(
    "Sumber data bawaan: BPS, tabel Populasi Ternak Menurut Provinsi dan Jenis Ternak (ekor), 2024. "
    "Analisis NDVI memakai Sentinel-2 melalui Google Earth Engine. "
    "Untuk hasil operasional, gunakan koordinat kandang atau lahan hijauan/pakan aktual."
)

st.link_button("Buka Tabel BPS", BPS_TABLE_URL)

st.markdown(
    f'<div class="custom-footer">Developed by {DEVELOPER_NAME}</div>',
    unsafe_allow_html=True,
)
