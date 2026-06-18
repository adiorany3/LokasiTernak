# Dashboard Peternakan Indonesia

Aplikasi Streamlit untuk pemetaan data peternakan Indonesia, visualisasi populasi ternak, dan analisis NDVI Sentinel-2 menggunakan Google Earth Engine.

## Isi ZIP

- `app.py` — kode aplikasi utama.
- `requirements.txt` — dependency Python.
- `data_peternakan_indonesia_bps_2024.csv` — data bawaan agregat provinsi.
- `contoh_format_upload_peternakan.csv` — contoh CSV terbaik untuk upload data kandang nyata.
- `.streamlit/config.toml` — konfigurasi light theme agar tulisan/legend terbaca.
- `.streamlit/secrets_TEMPLATE.toml` — template Secrets, jangan isi private key asli di GitHub.

## Cara Menjalankan Lokal

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Format CSV Upload

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

Contoh sudah tersedia di `contoh_format_upload_peternakan.csv`.

## Setting Google Earth Engine di Streamlit Cloud

1. Buat Google Cloud Project.
2. Enable Earth Engine API.
3. Register project untuk Google Earth Engine.
4. Buat Service Account.
5. Download JSON key.
6. Paste ke Streamlit Cloud `Manage app -> Settings -> Secrets` menggunakan format pada `.streamlit/secrets_TEMPLATE.toml`.
7. Reboot app.

## Catatan Keamanan

Jangan upload `secrets.toml` berisi private key asli ke GitHub.
Jika private key pernah tersebar, revoke/hapus key lama dan buat JSON key baru.
