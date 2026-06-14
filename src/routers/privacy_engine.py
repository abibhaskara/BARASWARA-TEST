"""
routers/privacy_engine.py

Router FastAPI untuk Privacy Engine — Tahap 1 & 2.
Endpoint: POST /v1/privacy-engine/pre-check
"""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from src.schemas.privacy_engine import ConfirmRequest, ConfirmResponse, PreCheckResponse
from src.services.heuristics_engine import analyze_csv
from src.services.storage_engine import save_config

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/privacy-engine",
    tags=["Privacy Engine"],
)

# Ukuran maksimum berkas yang diterima: 10 MB
MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB


@router.post(
    "/pre-check",
    response_model=PreCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Analisis & Rekomendasi Mekanisme Privasi CSV",
    description=(
        "Menerima berkas `.csv`, melakukan inferensi tipe semantik setiap kolom "
        "secara otomatis (tanpa intervensi manual), lalu mengembalikan rekomendasi "
        "mekanisme Differential Privacy yang sesuai untuk setiap kolom."
    ),
)
async def pre_check(
    file: UploadFile = File(
        ...,
        description="Berkas CSV yang akan dianalisis (maks. 10 MB).",
    ),
) -> PreCheckResponse:
    """
    **POST /v1/privacy-engine/pre-check**

    ### Alur Kerja:
    1. Validasi ekstensi & tipe konten berkas.
    2. Baca konten berkas ke memori (bytes).
    3. Validasi ukuran berkas.
    4. Serahkan ke `analyze_csv()` untuk analisis heuristik.
    5. Kembalikan `PreCheckResponse` dalam format JSON.

    ### Error Codes:
    - `400` — Berkas bukan CSV atau format tidak valid.
    - `413` — Ukuran berkas melebihi batas 10 MB.
    - `422` — Payload tidak sesuai (tidak ada file yang dikirim).
    - `500` — Kesalahan server internal.
    """
    # ── Validasi 1: Ekstensi berkas ──────────────────────────────────────────
    if file.filename is None or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_FILE_TYPE",
                "message": (
                    f"Berkas '{file.filename}' bukan CSV. "
                    "Harap unggah berkas dengan ekstensi .csv"
                ),
            },
        )

    # ── Validasi 2: Content-Type (opsional tapi defensif) ───────────────────
    allowed_content_types = {
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",  # Beberapa klien mengirim tipe ini untuk CSV
        "text/plain",
    }
    if file.content_type and file.content_type not in allowed_content_types:
        logger.warning(
            "Content-Type tidak biasa untuk CSV: '%s'. Melanjutkan dengan validasi ekstensi.",
            file.content_type,
        )

    # ── Baca konten berkas ───────────────────────────────────────────────────
    try:
        file_bytes = await file.read()
    except Exception as exc:
        logger.exception("Gagal membaca stream berkas: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "FILE_READ_ERROR",
                "message": "Terjadi kesalahan saat membaca berkas. Coba lagi.",
            },
        ) from exc
    finally:
        await file.close()

    # ── Validasi 3: Ukuran berkas ────────────────────────────────────────────
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error": "FILE_TOO_LARGE",
                "message": (
                    f"Ukuran berkas ({len(file_bytes) / 1024 / 1024:.2f} MB) "
                    f"melebihi batas maksimum 10 MB."
                ),
            },
        )

    # ── Validasi 4: Berkas tidak kosong ──────────────────────────────────────
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "EMPTY_FILE",
                "message": "Berkas yang diunggah kosong (0 bytes).",
            },
        )

    # ── Analisis Heuristik ───────────────────────────────────────────────────
    try:
        result = analyze_csv(file_bytes=file_bytes, filename=file.filename)
    except ValueError as exc:
        # ValueError dilempar oleh analyze_csv jika CSV tidak valid
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_CSV_FORMAT",
                "message": str(exc),
            },
        ) from exc
    except Exception as exc:
        logger.exception("Kesalahan tak terduga saat analisis: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ANALYSIS_FAILED",
                "message": "Analisis gagal karena kesalahan internal. Coba lagi.",
            },
        ) from exc

    logger.info(
        "Pre-check selesai: '%s' — %d kolom dianalisis.",
        file.filename,
        len(result.schema_recommendation),
    )
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /v1/privacy-engine/confirm
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post(
    "/confirm",
    response_model=ConfirmResponse,
    status_code=status.HTTP_200_OK,
    summary="Simpan Konfigurasi Privasi HITL",
    description=(
        "Menerima keputusan konfigurasi privasi per kolom dari user (HITL), "
        "menyimpannya ke disk, dan mengembalikan `config_id` untuk digunakan "
        "pada endpoint /pipeline/execute."
    ),
)
async def confirm_config(payload: ConfirmRequest) -> ConfirmResponse:
    """
    **POST /v1/privacy-engine/confirm**

    Simpan konfigurasi HITL (pilihan aksi & epsilon per kolom) ke disk.
    Kembalikan `config_id` sebagai tiket untuk eksekusi pipeline.
    """
    config_data = {
        "filename": payload.filename,
        "total_rows": payload.total_rows,
        "columns": [col.model_dump() for col in payload.columns],
    }

    config_id = save_config(config_data)

    logger.info(
        "Konfigurasi dikonfirmasi: config_id=%s, file='%s', %d kolom.",
        config_id[:8], payload.filename, len(payload.columns),
    )

    return ConfirmResponse(
        status="confirmed",
        config_id=config_id,
        filename=payload.filename,
        total_columns=len(payload.columns),
        message="Konfigurasi berhasil disimpan. Siap untuk eksekusi pipeline.",
    )
