# 🐄 Pemetaan Lokasi Peternakan + Analisis Citra Satelit Sentinel-2

Aplikasi web interaktif berbasis **Streamlit** untuk:
- Memetakan lokasi peternakan
- Visualisasi data di peta interaktif
- Analisis kesehatan vegetasi (NDVI) menggunakan **citra satelit Sentinel-2** secara gratis via Google Earth Engine

Cocok untuk mahasiswa, Dinas Peternakan, atau monitoring peternakan skala kecil-menengah.

## ✨ Fitur Utama

- Upload data peternakan via CSV
- Peta interaktif dengan marker lokasi (folium)
- Popup detail + filter sederhana
- **Analisis Sentinel-2 real-time**: Hitung NDVI rata-rata dalam radius 500m dari kandang (indikator kesehatan pakan hijauan)
- Sample data Indonesia (sekitar Bogor & Bekasi)
- Dashboard statistik dasar
- Siap dikembangkan lebih lanjut (buffer analysis, time-series, export laporan)

## 📦 Instalasi & Menjalankan

### 1. Clone / Download
Download folder ini atau clone repo.

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Setup Google Earth Engine (WAJIB untuk fitur satelit)
1. Buat akun gratis di [Google Earth Engine](https://earthengine.google.com/)
2. Buat Google Cloud Project baru (atau pakai existing)
3. Aktifkan **Earth Engine API** di project tersebut
4. Jalankan di terminal:
   ```bash
   earthengine authenticate
   ```
   Ikuti instruksi browser untuk login & authorize.

   **Catatan 2026**: Beberapa akun baru butuh `ee.Initialize(project='nama-project-mu')`. Lihat di app.py bagian `ee.Initialize()`.

### 4. Jalankan aplikasi
```bash
streamlit run app.py
```

Buka browser di `http://localhost:8501`

## 📋 Format File CSV

Kolom **wajib**:
- `nama` → Nama peternakan/kandang
- `latitude` → Koordinat lintang (decimal degrees)
- `longitude` → Koordinat bujur
- `jenis_ternak` → Sapi / Kambing / Ayam / dll
- `jumlah_ekor` → Jumlah ternak

Contoh baris:
```
nama,latitude,longitude,jenis_ternak,jumlah_ekor
Peternakan Sapi Cijeruk,-6.597,106.797,Sapi,45
Kandang Kambing Parung,-6.421,106.712,Kambing,120
```

Aplikasi sudah include **sample data** Indonesia kalau tidak upload CSV.

## 🚀 Cara Pakai

1. Buka app → lihat peta dengan sample data
2. Upload CSV sendiri via sidebar (akan ganti sample)
3. Pilih nama peternakan di dropdown
4. Klik tombol **"Analisis Sentinel-2 Sekarang"**
5. Lihat nilai NDVI + interpretasi otomatis

**Interpretasi NDVI cepat:**
- > 0.6  → Vegetasi sangat sehat (pakan bagus)
- 0.4 - 0.6 → Sedang
- < 0.4  → Perlu perhatian (kekeringan / lahan kurang hijau)

## 🌍 Data Satelit yang Dipakai

- **Sentinel-2 SR Harmonized** (resolusi 10m)
- Filter: 30 hari terakhir + cloud < 20%
- NDVI = (NIR - Red) / (NIR + Red) → band B8 & B4
- Diambil rata-rata dalam buffer 500 meter

Semua data **gratis** dan open.

## 📌 Catatan Penting & Troubleshooting

- **Error "Earth Engine client library not initialized"**:
  - Jalankan `earthengine authenticate` lagi
  - Atau tambahkan `ee.Initialize(project="nama-project")` di app.py

- **Query lambat / timeout**: Normal untuk pertama kali. GEE butuh waktu inisialisasi.

- **Deploy ke Streamlit Cloud**:
  - Push ke GitHub
  - Di Streamlit Cloud → Settings → Secrets, tambahkan:
    ```
    EARTHENGINE_TOKEN = "isi token dari earthengine authenticate --token"
    ```
  - Modifikasi app.py untuk baca dari `st.secrets`

- Untuk fitur lebih advanced (time-series NDVI, multi-buffer, klasifikasi lahan) bisa pakai `leafmap` atau `geemap` nanti.

## 🔧 Pengembangan Selanjutnya (Saran)

- Tambah time-series NDVI 1 tahun
- Buffer analysis + luas lahan hijau
- Integrasi data desa/kabupaten Indonesia (Ina-Geoportal)
- Notifikasi jika NDVI turun drastis
- Multi-user + database (PostgreSQL)
- Export laporan PDF otomatis

---

**Dibuat oleh Rex buat Boss** — siap dikustomisasi lebih lanjut.  
Kalau butuh tambahan fitur, perbaikan, atau versi dengan `leafmap` yang lebih powerful, bilang aja.

Selamat monitoring peternakannya! 🐮🌿