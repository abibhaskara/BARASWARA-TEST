## BARASWARA-RESTAPI

Sistem Automatic Compliance API untuk proteksi data privasi siswa dengan implementasi **Differential Privacy** (Laplace Noise Injection).

## Fitur Utama
- REST API berbasis FastAPI.
- Proteksi privasi data dengan algoritma Laplace Noise.
- Performa tinggi (Latency ~1ms).
- Validasi data dengan load testing (Apache JMeter).

## Instalasi
1. Clone repositori:
   `git clone https://github.com/abibhaskara/BARASWARA-RESTAPI.git`
2. Buat virtual environment:
   `python -m venv venv && source venv/bin/activate`
3. Install dependencies:
   `pip install -r requirements.txt`
4. Jalankan API:
   `uvicorn src.main:app --reload`