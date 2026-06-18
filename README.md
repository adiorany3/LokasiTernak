# Dashboard Peternakan Indonesia — Versi Insight Peternak

Aplikasi Streamlit untuk pemetaan data peternakan, analisis kondisi hijauan/pakan berbasis NDVI Sentinel-2, tren NDVI 90 hari, kepadatan ternak per hektare, dan rekomendasi otomatis untuk peternak.

## Isi ZIP

- `app.py` — kode aplikasi final.
- `requirements.txt` — dependency Python.
- `data_peternakan_indonesia_bps_2024.csv` — data bawaan agregat provinsi.
- `contoh_format_upload_peternakan.csv` — contoh upload CSV.
- `contoh_format_upload_peternakan.xlsx` — contoh upload XLSX.
- `.streamlit/config.toml` — paksa light theme agar legend dan teks terbaca.
- `.streamlit/secrets_TEMPLATE.toml` — template Secrets. Jangan isi private key asli di GitHub.

## Fitur Utama

1. Upload data `.csv` dan `.xlsx`.
2. Peta interaktif lokasi peternakan.
3. Marker warna berdasarkan jenis ternak.
4. Legend peta dipaksa terang agar mudah terbaca.
5. Analisis NDVI Sentinel-2 radius 100–2000 meter.
6. Tren NDVI 90 hari.
7. Skor kondisi hijauan/pakan.
8. Rekomendasi otomatis untuk peternak.
9. Kepadatan ternak per hektare jika ada kolom `luas_lahan_ha`.
10. Download laporan ringkas CSV.

## Cara Menjalankan Lokal

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Format Upload Terbaik

Kolom wajib:

- `nama`
- `latitude`
- `longitude`
- `jenis_ternak`
- `jumlah_ekor`

Kolom rekomendasi:

- `provinsi`
- `kabupaten_kota`
- `kecamatan`
- `desa`
- `alamat`
- `luas_lahan_ha`
- `sistem_pemeliharaan`
- `sumber_pakan`
- `tahun`
- `sumber`
- `keterangan`

## Catatan Penting

- `jumlah_ekor` sebaiknya angka polos, contoh `2500`.
- `latitude` dan `longitude` harus angka desimal, contoh `-6.704512` dan `106.821345`.
- Untuk NDVI, gunakan koordinat kandang/lahan hijauan/pakan aktual.
- Jika memakai data BPS bawaan, titik hanyalah representatif ibu kota provinsi.

## Streamlit Cloud + Google Earth Engine

1. Buat Google Cloud Project.
2. Enable Earth Engine API.
3. Register project untuk Google Earth Engine.
4. Buat Service Account.
5. Download JSON key.
6. Masukkan credential ke `Streamlit Cloud -> Manage app -> Settings -> Secrets`.
7. Gunakan format pada `.streamlit/secrets_TEMPLATE.toml`.
8. Reboot app.

## Keamanan

Jangan upload `secrets.toml` yang berisi private key asli ke GitHub.
Jika private key pernah tersebar, revoke/hapus key lama dan buat key JSON baru.
