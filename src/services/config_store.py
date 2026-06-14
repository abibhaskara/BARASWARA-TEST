"""
services/config_store.py

Wrapper tipis ke storage_engine — menjaga backward compatibility.
Semua data sekarang disimpan ke disk via storage_engine (persistent).
"""

from src.services.storage_engine import (
    generate_id,
    get_config,
    get_result_by_hash,
    get_result_by_id,
    make_secure_hash,
    save_config,
    save_result,
    update_result,
    verify_secure_hash,
    save_anonymized_csv,
    get_anonymized_csv_path,
    get_result_id_by_hash,
)

__all__ = [
    "generate_id",
    "save_config",
    "get_config",
    "save_result",
    "get_result_by_hash",
    "get_result_by_id",
    "update_result",
    "make_secure_hash",
    "verify_secure_hash",
    "save_anonymized_csv",
    "get_anonymized_csv_path",
    "get_result_id_by_hash",
]

