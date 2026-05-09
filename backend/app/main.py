from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Load .env from the repo root regardless of where uvicorn is launched from.
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")
load_dotenv()  # also pick up any local backend/.env override if present

from app.routes import onboard, pitch, feedback, profile, realtime
from app.services.storage_service import PUBLIC_GENERATED_DIR

app = FastAPI(title="PitchSnap API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(onboard.router)
app.include_router(pitch.router)
app.include_router(feedback.router)
app.include_router(profile.router)
app.include_router(realtime.router)
app.mount("/generated", StaticFiles(directory=PUBLIC_GENERATED_DIR), name="generated")


@app.get("/health")
async def health():
    return {"status": "ok"}
