"""
services/storage_engine.py

Persistent Storage Engine — Simpan konfigurasi & hasil pipeline ke disk (JSON files).
Menggantikan in-memory store yang hilang saat server restart.

Struktur direktori:
    data/
    ├── configs/
    │   └── {config_id}.json   ← konfigurasi HITL yang dikonfirmasi user
    └── results/
        └── {result_id}.json   ← hasil eksekusi pipeline (charts, stats, dll)

Keamanan URL:
    result_id (UUID) TIDAK langsung diekspos ke publik.
    Yang diekspos adalah secure_hash = HMAC-SHA256(result_id, SECRET_KEY).
    Hash pendek (12 karakter) digunakan sebagai slug URL yang aman.
"""

import hashlib
import hmac
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Konfigurasi ─────────────────────────────────────────────────────────────
BASE_DATA_DIR = Path(__file__).parent.parent.parent / "data"
CONFIGS_DIR = BASE_DATA_DIR / "configs"
RESULTS_DIR = BASE_DATA_DIR / "results"

# Secret key untuk HMAC — di production ganti dari env variable
SECRET_KEY = os.environ.get("BARASWARA_SECRET_KEY", "baraswara-dev-secret-2026")

# Buat direktori jika belum ada
CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Hash Utilities
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_id() -> str:
    """Generate UUID v4 baru sebagai ID internal."""
    return str(uuid.uuid4())


def make_secure_hash(internal_id: str, length: int = 12) -> str:
    """
    Buat hash URL-safe dari internal_id menggunakan HMAC-SHA256.

    Hash ini yang diekspos ke publik — tidak bisa di-reverse ke internal_id
    tanpa SECRET_KEY.

    Args:
        internal_id: UUID internal (tidak diekspos).
        length: Panjang hash yang diambil (karakter hex, default 12).

    Returns:
        String hex pendek, misalnya: "a3f92c1d8b47"
    """
    signature = hmac.new(  # type: ignore[attr-defined]  # noqa: S324
        key=SECRET_KEY.encode("utf-8"),
        msg=internal_id.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return signature[:length]


def verify_secure_hash(internal_id: str, provided_hash: str) -> bool:
    """
    Verifikasi apakah provided_hash cocok dengan internal_id.

    Returns:
        True jika valid, False jika tidak.
    """
    expected = make_secure_hash(internal_id, length=len(provided_hash))
    return hmac.compare_digest(expected, provided_hash)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Config Storage (HITL Configurations)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def save_config(config_data: dict[str, Any]) -> str:
    """
    Simpan konfigurasi HITL ke disk sebagai JSON, kembalikan config_id.

    Returns:
        config_id — UUID string untuk dipakai endpoint /pipeline/execute.
    """
    config_id = generate_id()
    payload = {
        "config_id": config_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data": config_data,
    }
    path = CONFIGS_DIR / f"{config_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Config disimpan ke disk: %s (file=%s)", config_id[:8], path.name)
    return config_id


def get_config(config_id: str) -> dict[str, Any] | None:
    """
    Ambil konfigurasi dari disk berdasarkan config_id.

    Returns:
        Dict data konfigurasi, atau None jika tidak ditemukan.
    """
    path = CONFIGS_DIR / f"{config_id}.json"
    if not path.exists():
        logger.warning("Config tidak ditemukan di disk: %s", config_id[:8])
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload["data"]
    except Exception as exc:
        logger.error("Gagal membaca config %s: %s", config_id[:8], exc)
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Result Storage (Pipeline Execution Results)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def save_result(result_data: dict[str, Any]) -> tuple[str, str]:
    """
    Simpan hasil pipeline ke disk, kembalikan (result_id, secure_hash).

    result_id  — ID internal (tidak diekspos ke publik).
    secure_hash — Hash URL-safe yang diekspos sebagai URL publik.

    Returns:
        Tuple (result_id, secure_hash).
    """
    result_id = generate_id()
    secure_hash = make_secure_hash(result_id)
    payload = {
        "result_id": result_id,
        "secure_hash": secure_hash,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data": result_data,
    }
    path = RESULTS_DIR / f"{result_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "Result disimpan ke disk: id=%s hash=%s (file=%s)",
        result_id[:8], secure_hash, path.name,
    )
    return result_id, secure_hash


def get_result_by_hash(secure_hash: str) -> dict[str, Any] | None:
    """
    Cari dan verifikasi hasil berdasarkan secure_hash.

    Iterasi semua file hasil, verifikasi HMAC, kembalikan data jika cocok.

    Returns:
        Dict data hasil, atau None jika hash tidak valid.
    """
    for path in RESULTS_DIR.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            stored_hash = payload.get("secure_hash", "")
            # Verifikasi pakai compare_digest (timing-safe)
            if hmac.compare_digest(stored_hash, secure_hash):
                logger.info("Result ditemukan via hash: %s", secure_hash)
                return payload["data"]
        except Exception:
            continue
    logger.warning("Tidak ada result untuk hash: %s", secure_hash)
    return None


def get_result_by_id(result_id: str) -> dict[str, Any] | None:
    """
    Ambil hasil berdasarkan result_id internal (untuk internal use saja).

    Returns:
        Dict data hasil, atau None jika tidak ditemukan.
    """
    path = RESULTS_DIR / f"{result_id}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload["data"]
    except Exception as exc:
        logger.error("Gagal membaca result %s: %s", result_id[:8], exc)
        return None


def update_result(result_id: str, result_data: dict[str, Any]) -> None:
    """
    Update data hasil yang sudah tersimpan (untuk menyempurnakan data setelah save awal).
    """
    path = RESULTS_DIR / f"{result_id}.json"
    if not path.exists():
        logger.warning("Result %s tidak ditemukan untuk di-update", result_id[:8])
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["data"] = result_data
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.error("Gagal update result %s: %s", result_id[:8], exc)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Anonymized CSV Storage
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def save_anonymized_csv(result_id: str, df: Any) -> None:
    """
    Simpan DataFrame terproteksi ke disk sebagai file CSV.
    """
    path = RESULTS_DIR / f"{result_id}.csv"
    try:
        df.to_csv(path, index=False, encoding="utf-8")
        logger.info("CSV Terproteksi disimpan ke disk: %s (file=%s)", result_id[:8], path.name)
    except Exception as exc:
        logger.error("Gagal menyimpan CSV terproteksi %s: %s", result_id[:8], exc)


def get_anonymized_csv_path(result_id: str) -> Path:
    """
    Ambil Path berkas CSV terproteksi berdasarkan result_id.
    """
    return RESULTS_DIR / f"{result_id}.csv"


def get_result_id_by_hash(secure_hash: str) -> str | None:
    """
    Cari result_id internal berdasarkan secure_hash secara aman.
    """
    for path in RESULTS_DIR.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            stored_hash = payload.get("secure_hash", "")
            if hmac.compare_digest(stored_hash, secure_hash):
                return payload.get("result_id")
        except Exception:
            continue
    return None

