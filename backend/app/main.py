from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from app.routes import onboard, pitch, feedback, profile, realtime

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


@app.get("/health")
async def health():
    return {"status": "ok"}
