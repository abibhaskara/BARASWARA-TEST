"""
services/pipeline_engine.py

Core Engine: Eksekusi Pipeline Privasi & Generasi Analytics (Fase 3)
─────────────────────────────────────────────────────────────────────
Modul ini bertugas:
1. Menerima DataFrame CSV + konfigurasi HITL yang sudah dikonfirmasi user.
2. Mengaplikasikan mekanisme privasi yang sesuai per kolom:
   - IGNORE  → Kolom dibuang/tidak disertakan dalam output
   - LAPLACE → Injeksi Laplace noise (Differential Privacy untuk data numerik)
   - RANDOMIZED_RESPONSE → Randomized Response (DP untuk data kategorik/binary)
   - REVIEW  → Kolom dibiarkan apa adanya (butuh review manual)
3. Menghitung statistik agregat dari data yang sudah diproteksi.
4. Menghasilkan chart Plotly dalam format JSON untuk ditampilkan di frontend.

Referensi Matematika:
═════════════════════
Laplace Mechanism:
    noise ~ Laplace(0, sensitivity/epsilon)
    sensitivity = range(kolom) / n_unique  (estimasi lokal)
    Makin kecil epsilon → makin banyak noise → makin privat.

Randomized Response (untuk kategori):
    Dengan probabilitas e^ε / (e^ε + k - 1), jawaban asli dikembalikan.
    Dengan probabilitas 1 / (e^ε + k - 1), salah satu jawaban lain dipilih acak.
    k = jumlah kategori unik.
"""

import io
import logging
import math
from typing import Any

import numpy as np
import pandas as pd

from src.schemas.pipeline import (
    CategoryDistribution,
    ExecuteResponse,
    NumericStats,
    PipelineSummary,
)

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helpers Mekanisme Privasi
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _apply_laplace(series: pd.Series, epsilon: float) -> pd.Series:
    """
    Injeksi Laplace noise ke kolom numerik.

    Sensitivity diestimasi dari range data dan jumlah nilai unik.
    Rumus: scale = sensitivity / epsilon
    """
    numeric = pd.to_numeric(series, errors="coerce")
    # Estimasi sensitivity dari range data
    data_range = float(numeric.max() - numeric.min())
    n_unique = int(numeric.nunique())
    sensitivity = data_range / max(n_unique, 1)
    sensitivity = max(sensitivity, 1.0)  # Minimal sensitivity = 1.0

    scale = sensitivity / max(epsilon, 1e-9)
    noise = np.random.laplace(0, scale, size=len(numeric))
    protected = numeric + noise
    logger.debug(
        "Laplace applied: col='%s', sensitivity=%.4f, epsilon=%.4f, scale=%.4f",
        series.name, sensitivity, epsilon, scale,
    )
    return protected


def _apply_randomized_response(series: pd.Series, epsilon: float) -> pd.Series:
    """
    Randomized Response untuk kolom kategorik/binary.

    Setiap nilai punya probabilitas e^ε / (e^ε + k-1) dikembalikan apa adanya,
    dan probabilitas 1/(e^ε + k-1) diganti ke kategori lain secara acak.
    """
    categories = series.dropna().unique().tolist()
    k = len(categories)
    if k <= 1:
        return series  # Tidak bisa randomize kalau cuma 1 kategori

    exp_eps = math.exp(epsilon)
    p_keep = exp_eps / (exp_eps + k - 1)
    p_flip = 1.0 - p_keep

    def randomize_value(val: Any) -> Any:
        if pd.isna(val):
            return val
        if np.random.random() < p_keep:
            return val  # Kembalikan nilai asli
        else:
            # Pilih kategori lain secara acak (exclude nilai asli)
            others = [c for c in categories if c != val]
            return np.random.choice(others) if others else val

    logger.debug(
        "RR applied: col='%s', k=%d, epsilon=%.4f, p_keep=%.4f",
        series.name, k, epsilon, p_keep,
    )
    return series.map(randomize_value)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Pipeline Utama
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def apply_privacy(
    df: pd.DataFrame,
    columns_config: list[dict[str, Any]],
) -> tuple[pd.DataFrame, list[NumericStats], list[CategoryDistribution], dict[str, int]]:
    """
    Terapkan mekanisme privasi ke DataFrame sesuai konfigurasi user.

    Args:
        df: DataFrame input (data asli dari CSV).
        columns_config: List dict dari ColumnConfig — setiap item berisi
                        column_name, action, epsilon.

    Returns:
        Tuple (df_protected, numeric_stats, category_distributions, action_counts).
    """
    df_protected = df.copy()
    numeric_stats: list[NumericStats] = []
    category_distributions: list[CategoryDistribution] = []
    action_counts = {"IGNORE": 0, "LAPLACE": 0, "RANDOMIZED_RESPONSE": 0, "REVIEW": 0}

    cols_to_drop: list[str] = []

    for col_conf in columns_config:
        col_name = col_conf["column_name"]
        action = col_conf["action"]
        epsilon = float(col_conf.get("epsilon", 1.0))

        # Lewati kalau kolom tidak ada di DataFrame
        if col_name not in df_protected.columns:
            logger.warning("Kolom '%s' tidak ada di CSV, dilewati.", col_name)
            continue

        action_counts[action] = action_counts.get(action, 0) + 1

        if action == "IGNORE":
            # Tandai untuk dibuang setelah loop selesai
            cols_to_drop.append(col_name)

        elif action == "LAPLACE":
            original_series = pd.to_numeric(df_protected[col_name], errors="coerce")
            protected_series = _apply_laplace(df_protected[col_name], epsilon)
            df_protected[col_name] = protected_series

            # Catat statistik perbandingan sebelum-sesudah
            numeric_stats.append(NumericStats(
                column_name=col_name,
                original_mean=round(float(original_series.mean()), 4) if not original_series.isna().all() else 0.0,
                protected_mean=round(float(protected_series.mean()), 4) if not protected_series.isna().all() else 0.0,
                original_std=round(float(original_series.std()), 4) if not original_series.isna().all() else 0.0,
                protected_std=round(float(protected_series.std()), 4) if not protected_series.isna().all() else 0.0,
                epsilon_used=epsilon,
            ))

        elif action == "RANDOMIZED_RESPONSE":
            protected_series = _apply_randomized_response(df_protected[col_name], epsilon)
            df_protected[col_name] = protected_series

            # Catat distribusi nilai setelah randomisasi
            dist = protected_series.dropna().astype(str).value_counts().to_dict()
            category_distributions.append(CategoryDistribution(
                column_name=col_name,
                distribution={k: int(v) for k, v in dist.items()},
            ))

        elif action == "REVIEW":
            # Biarkan kolom apa adanya, tapi catat distribusinya jika teks
            if not pd.api.types.is_numeric_dtype(df_protected[col_name]):
                dist = df_protected[col_name].dropna().astype(str).value_counts().head(20).to_dict()
                category_distributions.append(CategoryDistribution(
                    column_name=col_name,
                    distribution={k: int(v) for k, v in dist.items()},
                ))

    # Buang kolom IGNORE setelah semua kolom diproses
    df_protected.drop(columns=cols_to_drop, inplace=True, errors="ignore")
    logger.info(
        "Privacy pipeline selesai. Dibuang: %d, Laplace: %d, RR: %d, Review: %d",
        action_counts.get("IGNORE", 0),
        action_counts.get("LAPLACE", 0),
        action_counts.get("RANDOMIZED_RESPONSE", 0),
        action_counts.get("REVIEW", 0),
    )

    return df_protected, numeric_stats, category_distributions, action_counts


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Chart Generation (Plotly → JSON)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_plotly_charts(
    numeric_stats: list[NumericStats],
    category_distributions: list[CategoryDistribution],
    df_protected: pd.DataFrame,
    df_original: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """
    Generate chart Plotly dalam format dict JSON untuk setiap kolom yang diproses.

    Returns:
        List dict — setiap dict punya key 'title', 'type', dan 'plotly_json'.
    """
    try:
        import plotly.graph_objects as go
        import json
    except ImportError:
        logger.error("Plotly tidak terinstall. Jalankan: pip install plotly")
        return []

    charts: list[dict[str, Any]] = []

    # ── Chart 1: Bar chart perbandingan mean sebelum-sesudah (Laplace columns) ──
    if numeric_stats:
        col_names = [s.column_name for s in numeric_stats]
        orig_means = [s.original_mean for s in numeric_stats]
        prot_means = [s.protected_mean for s in numeric_stats]

        fig = go.Figure(data=[
            go.Bar(
                name="Mean Asli",
                x=col_names,
                y=orig_means,
                marker_color="#6366f1",
                opacity=0.85,
            ),
            go.Bar(
                name="Mean Terproteksi (DP)",
                x=col_names,
                y=prot_means,
                marker_color="#22d3ee",
                opacity=0.85,
            ),
        ])
        fig.update_layout(
            title="Perbandingan Mean: Data Asli vs Terproteksi (Laplace Noise)",
            xaxis_title="Kolom",
            yaxis_title="Nilai Mean",
            barmode="group",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#1e1e2e"),
            legend=dict(orientation="h", y=1.1),
        )
        charts.append({
            "title": "Perbandingan Mean Data Asli vs Terproteksi",
            "type": "bar_comparison",
            "plotly_json": json.loads(fig.to_json()),
        })

        # ── Tambahan: Scatter plot perbandingan titik data baris-per-baris ──
        if df_original is not None:
            for stat in numeric_stats[:2]:  # Batasi maks 2 scatter plot numerik
                col_name = stat.column_name
                if col_name in df_original.columns and col_name in df_protected.columns:
                    orig_series = pd.to_numeric(df_original[col_name], errors="coerce")
                    prot_series = pd.to_numeric(df_protected[col_name], errors="coerce")
                    
                    # Ambil indeks baris dan nilai yang valid (non-null)
                    mask = orig_series.notna() & prot_series.notna()
                    orig_vals = orig_series[mask].tolist()
                    prot_vals = prot_series[mask].tolist()
                    indices = orig_series[mask].index.tolist()

                    if len(orig_vals) > 0:
                        fig_scatter = go.Figure()
                        
                        # Titik Nilai Asli
                        fig_scatter.add_trace(go.Scatter(
                            x=indices,
                            y=orig_vals,
                            mode="markers",
                            name="Nilai Asli",
                            marker=dict(color="#94a3b8", size=6, opacity=0.7),
                        ))
                        
                        # Titik Nilai Terproteksi (DP)
                        fig_scatter.add_trace(go.Scatter(
                            x=indices,
                            y=prot_vals,
                            mode="markers",
                            name="Nilai Terproteksi (DP)",
                            marker=dict(color="#6366f1", size=6, opacity=0.7),
                        ))

                        # Garis horizontal Rata-rata Asli
                        fig_scatter.add_hline(
                            y=stat.original_mean,
                            line_dash="dash",
                            line_color="#ef4444",
                            annotation_text=f"Mean Asli: {stat.original_mean:.2f}",
                            annotation_position="top left",
                        )
                        
                        # Garis horizontal Rata-rata Terproteksi
                        fig_scatter.add_hline(
                            y=stat.protected_mean,
                            line_dash="dash",
                            line_color="#10b981",
                            annotation_text=f"Mean Terproteksi: {stat.protected_mean:.2f}",
                            annotation_position="bottom right",
                        )

                        fig_scatter.update_layout(
                            title=f"Pencaran Titik Data: Kolom {col_name} (Asli vs Terproteksi)",
                            xaxis_title="Baris Data (Indeks)",
                            yaxis_title="Nilai",
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#1e1e2e"),
                            legend=dict(orientation="h", y=1.15),
                        )

                        charts.append({
                            "title": f"Sebaran Titik Data: {col_name}",
                            "type": "scatter_comparison",
                            "column": col_name,
                            "plotly_json": json.loads(fig_scatter.to_json()),
                        })

    # ── Chart 2: Bar chart distribusi per kolom kategorik ────────────────────
    for cat_dist in category_distributions[:4]:  # Maks 4 chart kategorik
        if not cat_dist.distribution:
            continue

        labels = list(cat_dist.distribution.keys())[:20]  # Top 20 kategori
        values = [cat_dist.distribution[l] for l in labels]

        # Warna gradient untuk bar
        colors = [f"hsl({int(240 + i * (60/max(len(labels),1)))}, 70%, 60%)" for i in range(len(labels))]

        fig = go.Figure(data=[
            go.Bar(
                x=labels,
                y=values,
                marker_color=colors,
                text=values,
                textposition="auto",
            )
        ])
        fig.update_layout(
            title=f"Distribusi Kolom: {cat_dist.column_name}",
            xaxis_title="Nilai",
            yaxis_title="Frekuensi",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#1e1e2e"),
            xaxis=dict(tickangle=-30),
        )
        charts.append({
            "title": f"Distribusi: {cat_dist.column_name}",
            "type": "bar_distribution",
            "column": cat_dist.column_name,
            "plotly_json": json.loads(fig.to_json()),
        })

    # ── Chart 3: Scatter/histogram untuk kolom numerik yang masih ada ────────
    numeric_cols_in_df = [
        col for col in df_protected.columns
        if pd.api.types.is_numeric_dtype(df_protected[col])
    ]
    for col in numeric_cols_in_df[:2]:  # Maks 2 histogram numerik
        series = df_protected[col].dropna()
        if len(series) < 2:
            continue

        fig = go.Figure(data=[
            go.Histogram(
                x=series.tolist(),
                nbinsx=20,
                marker_color="#a78bfa",
                opacity=0.85,
                name=col,
            )
        ])
        fig.update_layout(
            title=f"Distribusi Nilai (Post-DP): {col}",
            xaxis_title="Nilai",
            yaxis_title="Frekuensi",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#1e1e2e"),
        )
        charts.append({
            "title": f"Histogram Terproteksi: {col}",
            "type": "histogram",
            "column": col,
            "plotly_json": json.loads(fig.to_json()),
        })

    logger.info("%d chart berhasil digenerate.", len(charts))
    return charts


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Entry Point Pipeline
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_pipeline(
    file_bytes: bytes,
    config_data: dict[str, Any],
    result_id: str,
    base_url: str = "http://localhost:8000",
    secure_hash: str = "",
) -> ExecuteResponse:
    """
    Entry point utama pipeline privasi.

    Args:
        file_bytes: Konten CSV dalam bytes.
        config_data: Dict dari ConfirmRequest (sudah di-save di config store).
        result_id: UUID untuk result URL.
        base_url: Base URL server untuk generate result_url.

    Returns:
        ExecuteResponse yang siap di-serialize ke JSON.
    """
    import csv
    from src.services.config_store import save_anonymized_csv

    # ── Load CSV ──────────────────────────────────────────────────────────────
    sep = ","
    try:
        sample = file_bytes[:2048].decode("utf-8", errors="ignore")
        if sample:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample, delimiters=[",", ";", "\t"])
            sep = dialect.delimiter
    except Exception:
        pass

    try:
        df = pd.read_csv(io.BytesIO(file_bytes), sep=sep)
    except Exception as exc:
        raise ValueError(f"CSV tidak bisa dibaca: {exc}") from exc

    total_rows = len(df)
    columns_config = config_data.get("columns", [])

    # ── Eksekusi privasi ──────────────────────────────────────────────────────
    df_protected, numeric_stats, category_distributions, action_counts = apply_privacy(
        df, columns_config
    )

    # ── Simpan CSV terproteksi ke disk ────────────────────────────────────────
    save_anonymized_csv(result_id, df_protected)

    # ── Generate charts ───────────────────────────────────────────────────────
    charts = generate_plotly_charts(numeric_stats, category_distributions, df_protected, df_original=df)

    # ── Bangun summary ────────────────────────────────────────────────────────
    summary = PipelineSummary(
        total_rows_processed=total_rows,
        columns_ignored=action_counts.get("IGNORE", 0),
        columns_laplace=action_counts.get("LAPLACE", 0),
        columns_randomized=action_counts.get("RANDOMIZED_RESPONSE", 0),
        columns_reviewed=action_counts.get("REVIEW", 0),
    )

    # Gunakan secure_hash di URL jika tersedia, fallback ke result_id
    url_slug = secure_hash if secure_hash else result_id
    return ExecuteResponse(
        result_id=result_id,
        result_url=f"{base_url}/v1/results/{url_slug}",
        filename=config_data.get("filename", "unknown.csv"),
        summary=summary,
        numeric_stats=numeric_stats,
        category_distributions=category_distributions,
        charts=charts,
    )

