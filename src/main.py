import logging
import logging.config

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.privacy import inject_laplace_noise
from src.routers import privacy_engine as privacy_engine_router
from src.routers import pipeline as pipeline_router

# ── Atur konfigurasi log biar gampang mantau server ──────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Inisialisasi Aplikasi FastAPI Utama ───────────────────────────────────────
app = FastAPI(
    title="BARASWARA — Privacy-as-a-Service API",
    description=(
        "Framework keren buat Otomatisasi compliance data analitik & privasi. "
        "Bikin data sensitif aman dipake lewat matematika sakti."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS Middleware (biar Next.js atau client lain bebas nembak API ini) ─────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Nanti di production ganti ke domain asli
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Pasang Router Privacy Engine (Fitur inti pre-check & confirm CSV) ──────────
app.include_router(privacy_engine_router.router)

# ── Pasang Router Pipeline (Eksekusi DP + Results viewer) ───────────────────
app.include_router(pipeline_router.router)


# ── Endpoint Jadul (Legacy) — ntar kita rapiin ke router terpisah ────────────
@app.get("/", tags=["Health"])
def read_root() -> dict:
    return {"message": "Sistem Automatic Compliance API Baraswara aktif", "version": "0.2.0"}



@app.get("/data-siswa", tags=["Legacy"])
def get_siswa_stats(value: float = 50.0, epsilon: float = 0.1) -> dict:
    """Endpoint legacy untuk uji injeksi Laplace noise."""
    data_aman = inject_laplace_noise(value, epsilon, sensitivity=1.0)
    return {
        "status": "success",
        "input_asli": value,
        "epsilon_digunakan": epsilon,
        "nilai_agregat_terproteksi": round(data_aman, 2),
    }