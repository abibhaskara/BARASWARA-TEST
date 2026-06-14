# BARASWARA — Privacy-as-a-Service REST API

> Sistem proteksi data privasi berbasis **Differential Privacy** dengan antarmuka Human-in-the-Loop (HITL) untuk anonimisasi berkas CSV secara matematis.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-green)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16-black)](https://nextjs.org)
[![Status](https://img.shields.io/badge/Status-Prototype%20v0.3.0-yellow)]()

---

## Daftar Isi

1. [Fitur Utama](#fitur-utama)
2. [Arsitektur Sistem](#arsitektur-sistem)
3. [Prasyarat](#prasyarat)
4. [Instalasi](#instalasi)
   - [Backend (FastAPI)](#2-backend-fastapi)
   - [Frontend (Next.js)](#3-frontend-nextjs)
5. [Menjalankan Aplikasi](#menjalankan-aplikasi)
6. [Penggunaan via CLI](#penggunaan-via-cli)
7. [Penggunaan via curl (Full Pipeline)](#penggunaan-via-curl-full-pipeline)
8. [Struktur Proyek](#struktur-proyek)
9. [Endpoint API](#endpoint-api)

---

## Fitur Utama

| Fase | Nama | Deskripsi |
|------|------|-----------|
| **1** | Analisis Semantik Otomatis | Mendeteksi tipe kolom (ID, Numerik, Kategorikal, Boolean) dari sampel CSV |
| **2** | Validasi HITL | Dashboard interaktif untuk data steward menyesuaikan keputusan privasi & nilai ε (epsilon) |
| **3** | Mekanisme Differential Privacy | **Laplace Noise** untuk kolom numerik · **Randomized Response** untuk kolom kategorikal/boolean |
| **4** | Penyajian Aman | Output dilindungi HMAC-SHA256, dapat dibagikan via secure URL · CSV terproteksi bisa diunduh |

---

## Arsitektur Sistem

```
┌─────────────────────────────────────────────────────────┐
│                     BARASWARA System                    │
│                                                         │
│  ┌──────────────┐   HTTP/REST   ┌──────────────────┐   │
│  │  Frontend    │ ◄───────────► │  Backend         │   │
│  │  Next.js     │               │  FastAPI         │   │
│  │  :3000       │               │  :8000           │   │
│  └──────────────┘               └────────┬─────────┘   │
│                                          │              │
│                               ┌──────────▼──────────┐  │
│                               │  Privacy Engine     │  │
│                               │  - Laplace Noise    │  │
│                               │  - Randomized Resp. │  │
│                               │  - HMAC Storage     │  │
│                               └─────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Prasyarat

Pastikan perangkat lunak berikut sudah terinstal sebelum memulai:

| Kebutuhan | Versi Minimum | Cek Instalasi |
|-----------|---------------|---------------|
| Python | 3.10+ | `python3 --version` |
| pip | terbaru | `pip --version` |
| Node.js | 18+ | `node --version` |
| pnpm | terbaru | `pnpm --version` |

Jika `pnpm` belum terinstal:
```bash
npm install -g pnpm
```

---

## Instalasi

### 1. Kloning Repositori

```bash
git clone https://github.com/abibhaskara/BARASWARA-TEST.git
cd BARASWARA-TEST
```

---

### 2. Backend (FastAPI)

#### Langkah 1 — Buat Virtual Environment

```bash
python3 -m venv venv
```

#### Langkah 2 — Aktifkan Virtual Environment

```bash
# macOS / Linux
source venv/bin/activate

# Windows (Command Prompt)
venv\Scripts\activate.bat

# Windows (PowerShell)
venv\Scripts\Activate.ps1
```

> ⚠️ **Penting:** Anda harus selalu mengaktifkan `venv` setiap kali membuka terminal baru sebelum menjalankan perintah Python apa pun. Tanda bahwa venv aktif adalah munculnya prefix `(venv)` di awal prompt terminal.

#### Langkah 3 — Instal Dependensi Python

```bash
pip install -r requirements.txt
```

Paket utama yang akan diinstal:

| Paket | Versi | Fungsi |
|-------|-------|--------|
| `fastapi` | 0.136 | Framework API backend |
| `uvicorn` | 0.48 | ASGI server |
| `pandas` | ≥2.2 | Pemrosesan data CSV |
| `numpy` | 2.4 | Komputasi noise matematika |
| `plotly` | ≥5.0 | Visualisasi grafik |
| `pydantic` | 2.13 | Validasi skema data |
| `python-multipart` | ≥0.0.9 | Upload file |
| `requests` | ≥2.31 | HTTP client (CLI) |

---

### 3. Frontend (Next.js)

Buka **tab terminal baru** (tetap di root proyek), lalu jalankan:

#### Langkah 1 — Masuk ke Direktori Frontend

```bash
cd frontend
```

#### Langkah 2 — Instal Dependensi Node.js

```bash
pnpm install
```

Paket utama yang akan diinstal:

| Paket | Versi | Fungsi |
|-------|-------|--------|
| `next` | 16 | Framework React |
| `react` | 19 | Library UI |
| `lucide-react` | terbaru | Ikon UI |
| `tailwindcss` | 4 | Styling utilitas |
| `typescript` | 5 | Type safety |

---

## Menjalankan Aplikasi

Diperlukan **dua terminal** yang berjalan bersamaan.

### Terminal 1 — Backend (FastAPI)

```bash
# Dari root direktori proyek
source venv/bin/activate
uvicorn src.main:app --reload
```

Backend berjalan di: **http://localhost:8000**  
Dokumentasi Swagger API: **http://localhost:8000/docs**

### Terminal 2 — Frontend (Next.js)

```bash
# Dari root direktori proyek
cd frontend
pnpm run dev
```

Dashboard berjalan di: **http://localhost:3000**

> 💡 **Tips:** Jika backend gagal jalan dengan error `Address already in use`, berarti port 8000 sudah dipakai proses lain. Matikan proses tersebut dengan:
> ```bash
> lsof -ti:8000 | xargs kill -9
> ```

---

## Penggunaan via CLI

Skrip `privacy_cli.py` memungkinkan akses cepat ke analisis pre-check langsung dari terminal, tanpa membuka browser.

### Prasyarat

Pastikan backend sudah berjalan di port 8000 (lihat bagian [Menjalankan Aplikasi](#menjalankan-aplikasi)).

### Penggunaan

```bash
# Aktifkan venv terlebih dahulu
source venv/bin/activate

# Jalankan analisis pada file CSV
python3 privacy_cli.py "Data Nilai Mahasiswa.csv"
```

### Contoh Output

```
🚀 Mengunggah & menganalisis 'Data Nilai Mahasiswa.csv' via BARASWARA Engine...

✅ Analisis Sukses!
============================================================
Nama Berkas : Data Nilai Mahasiswa.csv
Total Baris : 134
Total Kolom : 4
============================================================
NAMA KOLOM           | TIPE SEMANTIK             | REKOMENDASI AKSI
------------------------------------------------------------
No                   | ID / Unique Identifier    | IGNORE
Nama                 | ID / Unique Identifier    | IGNORE
UTS                  | Continuous Numeric        | LAPLACE
UAS                  | Continuous Numeric        | LAPLACE
============================================================
```

---

## Penggunaan via curl (Full Pipeline)

Untuk pengujian integrasi penuh atau penggunaan lanjutan tanpa browser.

### Fase 1 — Pre-check CSV

Analisis tipe semantik kolom dari berkas CSV.

```bash
curl -X POST \
  -F "file=@Data Nilai Mahasiswa.csv" \
  http://localhost:8000/v1/privacy-engine/pre-check
```

### Fase 2 — Konfirmasi Konfigurasi Privasi

Kirim konfigurasi final dan dapatkan `config_id`.

```bash
curl -X POST http://localhost:8000/v1/privacy-engine/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "Data Nilai Mahasiswa.csv",
    "total_rows": 134,
    "columns": [
      {"column_name": "No",   "semantic_type": "ID / Unique Identifier", "action": "IGNORE",  "epsilon": 1.0},
      {"column_name": "Nama", "semantic_type": "ID / Unique Identifier", "action": "IGNORE",  "epsilon": 1.0},
      {"column_name": "UTS",  "semantic_type": "Continuous Numeric",     "action": "LAPLACE", "epsilon": 0.5},
      {"column_name": "UAS",  "semantic_type": "Continuous Numeric",     "action": "LAPLACE", "epsilon": 0.5}
    ]
  }'
```

Contoh response:
```json
{
  "status": "confirmed",
  "config_id": "e1216bd9-b35c-4ae8-8334-abefbdce1229",
  "filename": "Data Nilai Mahasiswa.csv",
  "total_columns": 4,
  "message": "Konfigurasi berhasil disimpan. Siap untuk eksekusi pipeline."
}
```

### Fase 3 — Eksekusi Pipeline Differential Privacy

Jalankan pipeline privasi dengan `config_id` dari langkah sebelumnya.

```bash
curl -X POST http://localhost:8000/v1/pipeline/execute \
  -F "config_id=e1216bd9-b35c-4ae8-8334-abefbdce1229" \
  -F "file=@Data Nilai Mahasiswa.csv"
```

### Fase 4 — Akses Hasil Terlindungi

Dari response eksekusi, gunakan `secure_hash` untuk mengakses hasil:

```bash
# Metadata & URL viewer
curl http://localhost:8000/v1/results/<secure_hash>

# Data JSON mentah
curl http://localhost:8000/v1/results/<secure_hash>/raw
```

Contoh response metadata:
```json
{
  "status": "valid",
  "secure_hash": "ecb6971d7a03",
  "filename": "Data Nilai Mahasiswa.csv",
  "viewer_url": "http://localhost:3000/results/ecb6971d7a03"
}
```

Buka `viewer_url` di browser untuk melihat visualisasi grafik perbandingan data asli vs data terproteksi.

---

## Struktur Proyek

```
BARASWARA-TEST/
├── src/                        # Backend FastAPI
│   ├── main.py                 # Entry point aplikasi
│   ├── routers/                # Definisi endpoint API
│   │   ├── privacy_engine.py   # Endpoint pre-check & confirm
│   │   └── pipeline.py         # Endpoint execute & results
│   ├── schemas/                # Skema Pydantic (request/response)
│   └── services/               # Logika bisnis
│       ├── heuristics_engine.py  # Deteksi semantik kolom
│       ├── pipeline_engine.py    # Eksekusi Differential Privacy
│       ├── storage_engine.py     # Penyimpanan & HMAC secure URL
│       └── config_store.py       # Manajemen konfigurasi sesi
│
├── frontend/                   # Frontend Next.js
│   ├── app/
│   │   ├── page.tsx            # Halaman utama dashboard (upload & HITL)
│   │   ├── results/[hash]/     # Halaman berbagi hasil (secure URL)
│   │   └── globals.css         # Konfigurasi global Tailwind
│   └── package.json
│
├── data/                       # Direktori output hasil pipeline
├── privacy_cli.py              # CLI tool pre-check cepat
├── requirements.txt            # Dependensi Python
├── pyproject.toml              # Konfigurasi proyek Python
├── ROADMAP.md                  # Rencana pengembangan fitur
└── README.md                   # Dokumentasi ini
```

---

## Endpoint API

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `POST` | `/v1/privacy-engine/pre-check` | Upload CSV & analisis semantik kolom |
| `POST` | `/v1/privacy-engine/confirm` | Simpan konfigurasi privasi, dapatkan `config_id` |
| `POST` | `/v1/pipeline/execute` | Eksekusi pipeline DP, hasilkan output terproteksi |
| `GET`  | `/v1/results/{hash}` | Ambil metadata & viewer URL hasil |
| `GET`  | `/v1/results/{hash}/raw` | Ambil data JSON mentah hasil |
| `GET`  | `/docs` | Dokumentasi Swagger interaktif |

---

> **Prototype v0.3.0** — Dikembangkan sebagai sistem penelitian untuk anonimisasi data pendidikan berbasis Differential Privacy.
