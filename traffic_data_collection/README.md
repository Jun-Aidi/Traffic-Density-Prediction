# 🚦 Tutorial: Traffic Density Detection

Sistem deteksi keramaian jalan secara *real-time* menggunakan **YOLOv8** dan stream CCTV publik.

---

## 📋 Daftar Isi

1. [Prasyarat](#1-prasyarat)
2. [Struktur Proyek](#2-struktur-proyek)
3. [Instalasi (Pertama Kali)](#3-instalasi-pertama-kali)
4. [Menjalankan Aplikasi](#4-menjalankan-aplikasi)
5. [Memahami Output Program](#5-memahami-output-program)
6. [Menghentikan Program](#6-menghentikan-program)
7. [Troubleshooting](#7-troubleshooting)
8. [Konfigurasi Lanjutan](#8-konfigurasi-lanjutan)

---

## 1. Prasyarat

Pastikan software berikut sudah terinstall di komputer Anda **sebelum** memulai.

### ✅ Python 3.8 atau lebih baru

Cek versi Python:
```bash
python --version
```

Jika belum ada, download di: https://www.python.org/downloads/  
> ⚠️ **Penting:** Saat instalasi, centang opsi **"Add Python to PATH"**

---

### ✅ FFmpeg

Program ini **wajib** ada karena digunakan untuk membaca stream CCTV (format HLS/m3u8).

**Cara install FFmpeg di Windows:**

1. Download dari: https://www.gyan.dev/ffmpeg/builds/ (pilih `ffmpeg-release-essentials.zip`)
2. Ekstrak ke folder, misal: `C:\ffmpeg`
3. Tambahkan `C:\ffmpeg\bin` ke **System PATH**:
   - Buka **Start Menu** → cari **"Environment Variables"**
   - Klik **"Edit the system environment variables"**
   - Klik **"Environment Variables..."**
   - Di bagian **"System variables"**, pilih **"Path"** → klik **"Edit"**
   - Klik **"New"** → masukkan `C:\ffmpeg\bin`
   - Klik **OK** di semua jendela

**Verifikasi instalasi FFmpeg:**
```bash
ffmpeg -version
```

---

### ✅ Koneksi Internet

Proyek ini mengambil stream langsung dari CCTV publik:
```
https://cctv.balitower.co.id/Gelora-017-700470_3/tracks-v1/index.m3u8
```
Pastikan koneksi internet stabil.

---

## 2. Struktur Proyek

```
IOT/
├── detect_traffic.py   # 🎯 Script utama — deteksi kendaraan dengan YOLOv8
├── aa.py               # 🎥 Script sederhana — hanya tampilkan stream CCTV (tanpa AI)
├── setup.bat           # ⚙️  Script setup otomatis (buat venv + install library)
├── run.bat             # ▶️  Script jalankan program utama
├── yolov8n.pt          # 🤖 Model YOLOv8 Nano (sudah tersedia)
└── venv/               # 📦 Virtual environment Python (dibuat saat setup)
```

---

## 3. Instalasi (Pertama Kali)

> Langkah ini hanya dilakukan **sekali saja** saat pertama kali menjalankan proyek.

### Cara A: Otomatis via `setup.bat` ⭐ (Direkomendasikan)

1. Buka **File Explorer**, navigasi ke folder proyek:
   ```
   C:\Users\Fahrezi\Documents\KULIAH\Semester 6\PBL\IOT\
   ```

2. **Double-click** file `setup.bat`

3. Tunggu prosesnya selesai. Script akan:
   - ✅ Membuat virtual environment (`venv/`)
   - ✅ Meng-upgrade `pip`
   - ✅ Menginstall library: `numpy`, `opencv-python`, `ultralytics`

4. Setelah muncul pesan **"Setup selesai!"**, tekan sembarang tombol untuk menutup.

---

### Cara B: Manual via Command Prompt / PowerShell

Buka **Command Prompt** atau **PowerShell**, lalu jalankan perintah berikut satu per satu:

```bash
# 1. Masuk ke folder proyek
cd "C:\Users\Fahrezi\Documents\KULIAH\Semester 6\PBL\IOT"

# 2. Buat virtual environment
python -m venv venv

# 3. Aktifkan virtual environment
venv\Scripts\activate

# 4. Install library yang dibutuhkan
pip install --upgrade pip
pip install numpy opencv-python ultralytics
```

---

## 4. Menjalankan Aplikasi

### Cara A: Otomatis via `run.bat` ⭐ (Direkomendasikan)

1. **Double-click** file `run.bat` di folder proyek
2. Program akan otomatis mengaktifkan `venv` dan menjalankan `detect_traffic.py`

---

### Cara B: Manual via Command Prompt

```bash
# 1. Masuk ke folder proyek
cd "C:\Users\Fahrezi\Documents\KULIAH\Semester 6\PBL\IOT"

# 2. Aktifkan virtual environment
venv\Scripts\activate

# 3. Jalankan program utama
python detect_traffic.py
```

---

### Script Alternatif: `aa.py` (Stream Tanpa AI)

Jika hanya ingin melihat stream CCTV **tanpa** deteksi kendaraan (lebih ringan):

```bash
# Pastikan venv sudah aktif
venv\Scripts\activate
python aa.py
```

---

## 5. Memahami Output Program

Saat program berjalan, Anda akan melihat:

### Di Console (Terminal)
```
Loading YOLO model (yolov8n.pt)...
Model loaded.
Buffering... (menunggu 30 frame)
Stream aktif | 20 fps | Resolusi: 1664x1248
Deteksi setiap 3 frame | Confidence: 0.35
Tekan Q untuk keluar
```

### Di Jendela Video

| Elemen | Keterangan |
|--------|-----------|
| **Status: SEPI / NORMAL / RAMAI / PADAT** | Level keramaian lalu lintas saat ini |
| **Kendaraan: N** | Jumlah kendaraan yang terdeteksi |
| **Mobil:2  Motor:5  Bus:1** | Rincian per jenis kendaraan |
| **FPS & Buffer** | Performa stream (pojok kanan atas) |
| **Bar warna** | Indikator visual tingkat keramaian |
| **Bounding box** | Kotak di setiap kendaraan yang terdeteksi |

### Level Keramaian

| Level | Jumlah Kendaraan | Warna Indikator |
|-------|-----------------|-----------------|
| 🟢 **SEPI** | 0 – 5 | Hijau |
| 🟡 **NORMAL** | 6 – 15 | Kuning |
| 🟠 **RAMAI** | 16 – 30 | Oranye |
| 🔴 **PADAT** | > 30 | Merah |

---

## 6. Menghentikan Program

Tekan tombol **`Q`** pada jendela video yang terbuka untuk keluar.

Setelah keluar, terminal akan menampilkan ringkasan:
```
Stream ditutup.
Status terakhir: NORMAL (12 kendaraan)
FPS terakhir: 19.8
```

---

## 7. Troubleshooting

### ❌ `python` tidak ditemukan
**Penyebab:** Python belum terinstall atau tidak ada di PATH.  
**Solusi:** Install Python dari https://www.python.org/downloads/ dan centang **"Add to PATH"**.

---

### ❌ `ffmpeg` tidak ditemukan / stream tidak muncul
**Penyebab:** FFmpeg belum terinstall atau tidak ada di PATH.  
**Solusi:** Ikuti panduan instalasi FFmpeg di bagian [Prasyarat](#-ffmpeg).

```bash
# Cek apakah ffmpeg sudah bisa diakses
ffmpeg -version
```

---

### ❌ `ModuleNotFoundError: No module named 'cv2'` atau `ultralytics`
**Penyebab:** Library belum terinstall atau venv belum diaktifkan.  
**Solusi:**
```bash
venv\Scripts\activate
pip install numpy opencv-python ultralytics
```

---

### ❌ Jendela video tidak muncul / langsung tutup
**Penyebab:** Stream CCTV tidak bisa diakses (URL mungkin berubah atau koneksi lambat).  
**Solusi:**
- Pastikan koneksi internet aktif
- Coba buka URL stream di browser atau VLC:  
  `https://cctv.balitower.co.id/Gelora-017-700470_3/tracks-v1/index.m3u8`

---

### ❌ Program berjalan lambat / FPS rendah
**Penyebab:** Spesifikasi komputer terbatas.  
**Solusi:** Edit `detect_traffic.py` dan ubah nilai `DETECT_EVERY`:
```python
DETECT_EVERY = 5   # Deteksi setiap 5 frame (lebih hemat, default: 3)
```

---

## 8. Konfigurasi Lanjutan

Anda dapat mengubah parameter di bagian **KONFIGURASI** dalam file `detect_traffic.py`:

```python
# URL stream CCTV (bisa diganti dengan CCTV lain yang mendukung HLS)
URL = "https://cctv.balitower.co.id/Gelora-017-700470_3/tracks-v1/index.m3u8"

# Resolusi output
PIPE_W = 1664   # Lebar frame
PIPE_H = 1248   # Tinggi frame

# Target FPS tampilan
DISPLAY_FPS = 20

# Konfigurasi YOLOv8
YOLO_MODEL   = "yolov8n.pt"   # Model: yolov8n (nano), yolov8s (small), dst.
CONFIDENCE   = 0.35           # Threshold kepercayaan deteksi (0.0 – 1.0)
DETECT_EVERY = 3              # Jalankan AI setiap N frame

# Threshold level keramaian
DENSITY_THRESHOLDS = [
    (5,   "SEPI",   ...),   # 0-5 kendaraan
    (15,  "NORMAL", ...),   # 6-15 kendaraan
    (30,  "RAMAI",  ...),   # 16-30 kendaraan
    (999, "PADAT",  ...),   # >30 kendaraan
]
```

---

## 📌 Ringkasan Cepat

```
Pertama kali  →  double-click setup.bat
Jalankan      →  double-click run.bat
Keluar        →  tekan Q pada jendela video
```

---

*Dibuat untuk proyek PBL IoT — Semester 6*
