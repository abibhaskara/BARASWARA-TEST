"""
routers/pipeline.py

Router FastAPI untuk Pipeline Eksekusi Privasi (Fase 3 & 4).
Endpoints:
  - POST /v1/pipeline/execute       → Jalankan pipeline privasi + simpan hasil ke disk
  - GET  /v1/results/{secure_hash}  → Ambil hasil via Secure Hash URL (Fase 4)
  - GET  /v1/results/{secure_hash}/raw → Raw JSON hasil (untuk embed/API)

Keamanan (Fase 4):
  - URL publik menggunakan HMAC-SHA256 hash, bukan UUID langsung
  - Middleware memvalidasi hash sebelum menyajikan data
  - Hash tidak valid → 401 Unauthorized
"""

import logging

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse

from src.schemas.pipeline import ExecuteResponse
from src.services.config_store import (
    get_config,
    get_result_by_hash,
    make_secure_hash,
    save_result,
    update_result,
    get_result_id_by_hash,
    get_anonymized_csv_path,
)
from src.services.pipeline_engine import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1",
    tags=["Pipeline Eksekusi"],
)


# Ukuran maksimum berkas untuk pipeline: 10 MB
MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024
BASE_URL = "http://localhost:8000"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /v1/pipeline/execute
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post(
    "/pipeline/execute",
    response_model=ExecuteResponse,
    status_code=status.HTTP_200_OK,
    summary="Eksekusi Pipeline Privasi & Generate Analytics",
    description=(
        "Menerima `config_id` (dari endpoint /confirm) dan berkas CSV, "
        "menjalankan pipeline Differential Privacy per kolom, "
        "generate chart Plotly, dan menyimpan hasil ke disk. "
        "Mengembalikan `result_url` berupa Secure Hash URL (HMAC-SHA256)."
    ),
)
async def execute_pipeline(
    config_id: str = Form(..., description="UUID konfigurasi dari /confirm."),
    file: UploadFile = File(..., description="Berkas CSV yang sama (maks. 10 MB)."),
) -> ExecuteResponse:
    """
    **POST /v1/pipeline/execute**

    ### Alur Kerja:
    1. Validasi `config_id` → load konfigurasi dari disk.
    2. Validasi & baca berkas CSV.
    3. Jalankan pipeline privasi (apply_privacy + generate charts).
    4. Simpan hasil ke disk, buat Secure Hash URL.
    5. Return ExecuteResponse.

    ### Error Codes:
    - `400` — File bukan CSV, kosong, atau format tidak valid.
    - `404` — `config_id` tidak ditemukan di disk.
    - `413` — File > 10 MB.
    - `500` — Kesalahan internal pipeline.
    """
    # ── Validasi config_id ────────────────────────────────────────────────────
    config_data = get_config(config_id)
    if config_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "CONFIG_NOT_FOUND",
                "message": (
                    f"Konfigurasi '{config_id}' tidak ditemukan. "
                    "Ulangi proses pre-check & confirm."
                ),
            },
        )

    # ── Validasi berkas ───────────────────────────────────────────────────────
    if file.filename is None or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_FILE_TYPE", "message": "Harap unggah berkas .csv."},
        )

    try:
        file_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "FILE_READ_ERROR", "message": "Gagal membaca berkas."},
        ) from exc
    finally:
        await file.close()

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"error": "FILE_TOO_LARGE", "message": "Berkas melebihi batas 10 MB."},
        )
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "EMPTY_FILE", "message": "Berkas kosong (0 bytes)."},
        )

    # ── Reserve result_id + secure_hash di disk ───────────────────────────────
    result_id, secure_hash = save_result({"status": "processing"})
    result_url = f"{BASE_URL}/v1/results/{secure_hash}"

    # ── Jalankan Pipeline ─────────────────────────────────────────────────────
    try:
        response = run_pipeline(
            file_bytes=file_bytes,
            config_data=config_data,
            result_id=result_id,
            base_url=BASE_URL,
            secure_hash=secure_hash,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_CSV", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.exception("Pipeline gagal: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "PIPELINE_FAILED",
                "message": f"Pipeline gagal: {str(exc)[:300]}",
            },
        ) from exc

    # ── Simpan hasil final ke disk ────────────────────────────────────────────
    update_result(result_id, response.model_dump())

    logger.info(
        "Pipeline selesai: hash=%s, file=%s, %d charts.",
        secure_hash, file.filename, len(response.charts),
    )
    return response


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /v1/results/{secure_hash}/raw — JSON API (untuk frontend SPA)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get(
    "/results/{secure_hash}/raw",
    summary="Ambil Data Hasil Pipeline (JSON API)",
    description=(
        "Endpoint JSON untuk frontend — validasi secure hash dan kembalikan "
        "data hasil pipeline. Hash tidak valid → 401 Unauthorized."
    ),
)
async def get_result_raw(secure_hash: str) -> JSONResponse:
    """
    **GET /v1/results/{secure_hash}/raw**

    ### Keamanan (Fase 4 Middleware):
    - Hash divalidasi dengan `hmac.compare_digest` (timing-safe).
    - Hash tidak valid / tidak ditemukan → 401 Unauthorized.
    - Hash valid → 200 OK + data JSON.
    """
    result_data = get_result_by_hash(secure_hash)

    if result_data is None:
        logger.warning("Akses ditolak — hash tidak valid: %s", secure_hash)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "UNAUTHORIZED",
                "message": (
                    "Akses ditolak. URL tidak valid atau hasil sudah kedaluwarsa. "
                    "Pastikan Anda menggunakan URL yang benar dari hasil eksekusi pipeline."
                ),
            },
        )

    logger.info("Akses result diizinkan via hash: %s", secure_hash)
    return JSONResponse(content={"status": "success", "data": result_data})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /v1/results/{secure_hash} — Redirect ke frontend
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get(
    "/results/{secure_hash}",
    summary="Akses Hasil Pipeline via Secure Hash URL",
    description=(
        "Hash valid → informasi singkat + link ke frontend viewer. "
        "Hash tidak valid → 401 Unauthorized."
    ),
)
async def get_result_page(secure_hash: str, request: Request) -> JSONResponse:
    """
    **GET /v1/results/{secure_hash}**

    Validasi hash dan kembalikan metadata + link ke frontend result viewer.
    Frontend mengakses `/results/{secure_hash}` di port 3000 untuk render chart.
    """
    result_data = get_result_by_hash(secure_hash)

    if result_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "UNAUTHORIZED",
                "message": "URL tidak valid atau hasil tidak ditemukan.",
            },
        )

    # Kembalikan metadata ringkas + link ke frontend viewer
    summary = result_data.get("summary", {})
    return JSONResponse(content={
        "status": "valid",
        "secure_hash": secure_hash,
        "filename": result_data.get("filename", "unknown"),
        "summary": summary,
        "viewer_url": f"http://localhost:3000/results/{secure_hash}",
        "raw_api_url": f"{BASE_URL}/v1/results/{secure_hash}/raw",
    })


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /v1/results/{secure_hash}/download — Unduh CSV Hasil
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get(
    "/results/{secure_hash}/download",
    summary="Unduh Berkas CSV Terproteksi (Anonymized CSV)",
    description=(
        "Mengembalikan berkas CSV terproteksi hasil eksekusi pipeline. "
        "Menggunakan secure hash URL untuk otentikasi."
    ),
)
async def download_anonymized_csv(secure_hash: str):
    """
    **GET /v1/results/{secure_hash}/download**

    Validasi hash dan kembalikan berkas CSV hasil proteksi.
    Jika hash tidak valid atau berkas tidak ditemukan -> 401 Unauthorized.
    """
    result_id = get_result_id_by_hash(secure_hash)
    if result_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "UNAUTHORIZED",
                "message": "Akses ditolak. URL tidak valid atau hasil tidak ditemukan.",
            },
        )

    csv_path = get_anonymized_csv_path(result_id)
    if not csv_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FILE_NOT_FOUND",
                "message": "Berkas CSV terproteksi tidak ditemukan di disk.",
            },
        )

    # Dapatkan nama file asli (opsional) untuk penamaan unduhan
    result_data = get_result_by_hash(secure_hash)
    orig_filename = result_data.get("filename", "data.csv") if result_data else "data.csv"
    download_filename = f"anonymized_{orig_filename}"

    logger.info("Mengunduh berkas CSV terproteksi: result_id=%s, file=%s", result_id[:8], download_filename)
    return FileResponse(
        path=csv_path,
        media_type="text/csv",
        filename=download_filename,
    )

