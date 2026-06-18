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
10. Download laporan ringkas XLSX.

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


## Laporan XLSX

Tombol laporan pada aplikasi sekarang hanya menghasilkan file `.xlsx`. Workbook laporan berisi sheet `Laporan Ringkas`, `Tren NDVI 90 Hari`, dan `Rekomendasi`.

## Insight Awam yang Ditambahkan

Versi ini menambahkan:
- Kesimpulan otomatis dalam bahasa sederhana.
- Skor Kondisi Peternakan 0–100.
- Status lampu warna: hijau, kuning, oranye, merah.
- Risiko kekurangan pakan.
- Estimasi kebutuhan pakan harian.
- Prioritas tindakan hari ini.
- Catatan validasi titik koordinat agar peternak tidak salah membaca NDVI.
- Laporan XLSX yang memuat skor, risiko, estimasi pakan, kesimpulan awam, tren NDVI, dan rekomendasi.


## Catatan Luas Lahan

Pada contoh file `contoh_format_upload_peternakan.xlsx`, sheet `Petunjuk` sudah ditambahkan catatan: **Tambahkan `luas_lahan_ha` pada CSV/XLSX untuk insight lebih baik**. Kolom ini dipakai aplikasi untuk menghitung kepadatan ternak per hektare.

## Modul Profil Lingkungan & Kesuburan Lahan

Versi ini menambahkan analisis:
- Elevasi / ketinggian tempat dari SRTM.
- Kemiringan lahan dari turunan data elevasi.
- Curah hujan 30 dan 90 hari dari CHIRPS.
- Estimasi pH tanah dari OpenLandMap.
- Estimasi karbon organik tanah dari OpenLandMap.
- Skor lingkungan 0–100.
- Rekomendasi lingkungan untuk peternak awam.
- Download laporan lingkungan dalam format XLSX.

Catatan penting: data tanah, elevasi, dan curah hujan pada aplikasi bersifat estimasi awal dari satelit/model global. Untuk mendapatkan data yang lebih akurat, peternak tetap perlu melakukan pengecekan langsung di lapangan dan uji tanah bila diperlukan.

## Modul Gas & Emisi Peternakan

Versi ini menambahkan:
- Profil CH₄ atmosfer dari Sentinel-5P/TROPOMI.
- Profil CO atmosfer dari Sentinel-5P/TROPOMI.
- Profil NO₂ atmosfer dari Sentinel-5P/TROPOMI.
- Estimasi emisi CH₄ dari ternak berdasarkan jenis dan jumlah ternak.
- Estimasi N₂O dari pengelolaan kotoran ternak secara sederhana.
- Estimasi CO₂e per tahun.
- Rekomendasi pengurangan emisi dan gas untuk peternak awam.
- Download laporan Gas & Emisi dalam format XLSX.

Catatan penting: data gas satelit adalah indikasi atmosfer wilayah luas, bukan pengukuran langsung dari kandang. Estimasi emisi ternak bersifat pendekatan awal. Untuk data yang paling akurat, lakukan pengukuran langsung memakai sensor gas, audit emisi, atau pengecekan lapangan.
