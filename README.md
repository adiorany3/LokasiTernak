# Dashboard Peternakan Indonesia + NDVI Sentinel-2

Aplikasi web Streamlit untuk memetakan data peternakan Indonesia, menampilkan statistik populasi ternak, dan menganalisis NDVI Sentinel-2 menggunakan Google Earth Engine.

## Perubahan Versi Revisi

- Data bawaan diganti dari data sintetis menjadi data agregat provinsi berbasis tabel BPS 2024.
- Ditambahkan keterangan bahwa titik peta BPS adalah koordinat representatif ibu kota provinsi, bukan lokasi kandang individu.
- Ditambahkan filter provinsi dan jenis ternak.
- Tampilan peta diperbaiki dengan radius marker proporsional terhadap jumlah populasi.
- Emblem/menu/footer bawaan Streamlit disembunyikan dengan CSS.
- Footer custom ditambahkan: `Developed by Marcus Thorne`.
- Catatan sumber data BPS ditampilkan di aplikasi.

## File Utama

- `app.py` — aplikasi Streamlit versi revisi.
- `data_peternakan_indonesia_bps_2024.csv` — data bawaan agregat BPS 2024.
- `requirements.txt` — dependency Python.

## Cara Menjalankan

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Setup Google Earth Engine

Fitur peta dan statistik tetap berjalan tanpa Google Earth Engine. Untuk fitur NDVI, lakukan autentikasi:

```bash
earthengine authenticate
```

Jika akun membutuhkan Google Cloud Project, tambahkan `GEE_PROJECT` ke Streamlit Secrets.

## Format CSV Upload

Kolom wajib:

```csv
nama,latitude,longitude,jenis_ternak,jumlah_ekor
```

Kolom opsional:

```csv
provinsi,tahun,sumber,jenis_data,keterangan
```

## Catatan Data

Data bawaan adalah data agregat provinsi. Karena BPS tidak menyajikan koordinat kandang individu pada tabel tersebut, koordinat yang digunakan adalah titik representatif ibu kota provinsi untuk visualisasi peta. Untuk analisis kondisi peternakan nyata, upload CSV berisi koordinat kandang atau lahan pakan yang aktual.

Sumber utama: Badan Pusat Statistik (BPS), tabel **Populasi Ternak Menurut Provinsi dan Jenis Ternak (ekor), 2024** dan publikasi **Peternakan Dalam Angka 2025**.
