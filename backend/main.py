from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rich.traceback import install

from core.database import create_tables
from models.demucs import Demucs
from models.maqam import Maqam  # noqa: F401 — imported so create_tables() creates the table
from routes.auth_router import router as auth_router
from routes.basic_pitch_router import router as basic_pitch_router
from routes.crepe_router import router as crepe_router
from routes.demucs_router import router as demucs_router
from routes.eastern_pipeline_router import router as eastern_pipeline_router
from routes.eastern_router import router as eastern_router
from routes.microtonal_router import router as microtonal_router
from routes.pipeline_router import router as pipeline_router
from routes.progress_router import router as progress_router
from routes.sheet_music_router import router as sheet_music_router
from routes.transpose_router import router as transpose_router
from shared.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: create database tables on startup."""
    logger.info("Creating database tables...")
    await create_tables()
    logger.info("Database tables created.")
    yield


app = FastAPI(
    title="Songify API",
    description="Audio-to-sheet-music transcription service",
    version="2.0.0",
    lifespan=lifespan,
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

install(show_locals=True)
logger.info("Starting the Songify API...")

app.include_router(auth_router, prefix="/api")
app.include_router(demucs_router, prefix="/api")
app.include_router(crepe_router, prefix="/api")
app.include_router(basic_pitch_router, prefix="/api")
app.include_router(pipeline_router, prefix="/api")
app.include_router(progress_router, prefix="/api")
app.include_router(microtonal_router)
app.include_router(sheet_music_router, prefix="/api")
app.include_router(eastern_pipeline_router, prefix="/api")
app.include_router(eastern_router, prefix="/api")
app.include_router(transpose_router, prefix="/api")


@app.get("/")
def read_root():
    return {"message": "Songify API v2.0 - Audio to Sheet Music"}


@app.get("/model")
def get_model():
    model = Demucs()
    return {"model": model.health_check()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
