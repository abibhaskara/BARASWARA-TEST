"""
schemas/privacy_engine.py
Pydantic models untuk response struktur endpoint Privacy Engine.
"""

from typing import Literal
from pydantic import BaseModel, Field


# ── Tipe literal untuk semantic classification ──────────────────────────────
SemanticType = Literal[
    "ID / Unique Identifier",
    "Continuous Numeric",
    "Boolean / Binary",
    "Categorical",
    "Unknown",
]

RecommendedAction = Literal[
    "IGNORE",
    "LAPLACE",
    "RANDOMIZED_RESPONSE",
    "REVIEW",
]


# ── Sub-schema: metadata berkas ──────────────────────────────────────────────
class FileMetadata(BaseModel):
    filename: str = Field(..., description="Nama berkas CSV yang diunggah")
    total_rows: int = Field(..., description="Jumlah total baris data (sebelum sampling)")
    total_columns: int = Field(..., description="Jumlah total kolom")


# ── Sub-schema: rekomendasi per kolom ────────────────────────────────────────
class ColumnRecommendation(BaseModel):
    column_name: str = Field(..., description="Nama kolom")
    semantic_type: SemanticType = Field(..., description="Klasifikasi semantik kolom")
    missing_values: int = Field(..., ge=0, description="Jumlah sel kosong (missing values)")
    recommended_action: RecommendedAction = Field(
        ..., description="Rekomendasi mekanisme privasi"
    )


# ── Root response schema ─────────────────────────────────────────────────────
class PreCheckResponse(BaseModel):
    status: Literal["success"] = "success"
    file_metadata: FileMetadata
    schema_recommendation: list[ColumnRecommendation]


# ── Schema untuk Fase 2: Konfirmasi Konfigurasi ──────────────────────────────

class ColumnConfig(BaseModel):
    column_name: str
    semantic_type: str
    action: RecommendedAction
    epsilon: float = Field(default=1.0, ge=0.01, le=10.0)


class ConfirmRequest(BaseModel):
    filename: str
    total_rows: int
    columns: list[ColumnConfig]


class ConfirmResponse(BaseModel):
    status: Literal["confirmed"] = "confirmed"
    config_id: str
    filename: str
    total_columns: int
    message: str
