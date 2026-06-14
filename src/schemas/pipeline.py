"""
schemas/pipeline.py
Pydantic models untuk request/response endpoint Pipeline Execute (Fase 3).
"""

from typing import Any, Literal
from pydantic import BaseModel, Field


# ── Request: jalankan pipeline ───────────────────────────────────────────────
class ExecuteRequest(BaseModel):
    """Request body untuk POST /v1/pipeline/execute."""
    config_id: str = Field(..., description="UUID konfigurasi dari endpoint /confirm")


# ── Sub-schema: statistik satu kolom numerik ─────────────────────────────────
class NumericStats(BaseModel):
    column_name: str
    original_mean: float
    protected_mean: float
    original_std: float
    protected_std: float
    epsilon_used: float


# ── Sub-schema: distribusi satu kolom kategorik ──────────────────────────────
class CategoryDistribution(BaseModel):
    column_name: str
    distribution: dict[str, int] = Field(
        ..., description="Frekuensi tiap nilai unik dalam kolom kategorik"
    )


# ── Sub-schema: summary eksekusi ─────────────────────────────────────────────
class PipelineSummary(BaseModel):
    total_rows_processed: int
    columns_ignored: int
    columns_laplace: int
    columns_randomized: int
    columns_reviewed: int


# ── Response: hasil eksekusi pipeline ────────────────────────────────────────
class ExecuteResponse(BaseModel):
    """Response setelah pipeline privasi berhasil dieksekusi."""
    status: Literal["success"] = "success"
    result_id: str = Field(..., description="UUID unik hasil ini, dipakai sebagai hash URL")
    result_url: str = Field(..., description="URL backend untuk mengakses hasil via hash")
    # ── Fields yang dibutuhkan frontend ────────────────────────────────
    secure_hash: str = Field(default="", description="HMAC-SHA256 hash pendek untuk URL publik")
    viewer_url: str = Field(default="", description="URL frontend (port 3000) untuk hasil viewer")
    download_url: str = Field(default="", description="URL download CSV terproteksi")
    filename: str
    summary: PipelineSummary
    numeric_stats: list[NumericStats] = Field(default_factory=list)
    category_distributions: list[CategoryDistribution] = Field(default_factory=list)
    charts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List chart Plotly dalam format JSON (fig.to_json()) untuk tiap kolom"
    )
    message: str = "Pipeline privasi berhasil dieksekusi. Data aman untuk dipublikasikan."
