"""
GreenGuard AI - Main FastAPI Application

Run with:
    uvicorn app:app --reload --host 0.0.0.0 --port 8000

Endpoints:
    GET  /api/status              -> online/offline mode + db health check
    POST /api/scan                -> upload medicine image, get trust score
    POST /api/chat                -> ask the AI assistant a question
    POST /api/translate           -> translate any text to target language
    GET  /api/history             -> recent scan history (for dashboard)
    GET  /api/stats               -> aggregate stats for dashboard charts
"""

import os
import shutil
import uuid

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import init_db, db_session
from seed_data import seed
from ocr_module import analyze_package_image
from trust_score import compute_trust_score
from ai_assistant import ask_assistant, is_online
from translation import translate_text

app = FastAPI(title="GreenGuard AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.on_event("startup")
def startup():
    init_db()
    seed()


class ChatRequest(BaseModel):
    query: str


class TranslateRequest(BaseModel):
    text: str
    target_lang: str = "ta"


@app.get("/api/status")
def status():
    return {
        "server": "running",
        "ai_mode": "online" if is_online() else "offline",
    }


@app.post("/api/scan")
async def scan_medicine(image: UploadFile = File(...)):
    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file.")

    ext = os.path.splitext(image.filename)[1] or ".jpg"
    save_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}{ext}")

    with open(save_path, "wb") as f:
        shutil.copyfileobj(image.file, f)

    try:
        ocr_fields = analyze_package_image(save_path)
        result = compute_trust_score(ocr_fields)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {e}")

    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO scan_history
               (extracted_text, matched_medicine_id, trust_score, verdict, mode_used)
               VALUES (?, ?, ?, ?, ?)""",
            (
                ocr_fields.get("raw_text", ""),
                None,
                result["trust_score"],
                result["verdict"],
                "offline",
            ),
        )

    return {
        "ocr_fields": ocr_fields,
        "result": result,
    }


@app.post("/api/chat")
def chat(req: ChatRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    try:
        answer, mode = ask_assistant(req.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assistant error: {e}")
    return {"answer": answer, "mode_used": mode}


@app.post("/api/translate")
def translate(req: TranslateRequest):
    result = translate_text(req.text, req.target_lang)
    return result


@app.get("/api/history")
def history(limit: int = 20):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM scan_history ORDER BY scanned_at DESC LIMIT ?", (limit,)
        )
        rows = [dict(r) for r in cur.fetchall()]
    return {"history": rows}


@app.get("/api/stats")
def stats():
    with db_session() as conn:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) as total FROM scan_history")
        total = cur.fetchone()["total"]

        cur.execute("""SELECT verdict, COUNT(*) as count
                       FROM scan_history GROUP BY verdict""")
        verdict_breakdown = {row["verdict"]: row["count"] for row in cur.fetchall()}

        cur.execute("SELECT AVG(trust_score) as avg_score FROM scan_history")
        avg_row = cur.fetchone()
        avg_score = round(avg_row["avg_score"], 1) if avg_row["avg_score"] is not None else 0

        cur.execute("""SELECT trust_score, scanned_at FROM scan_history
                       ORDER BY scanned_at ASC LIMIT 30""")
        trend = [{"score": r["trust_score"], "time": r["scanned_at"]} for r in cur.fetchall()]

        flagged = verdict_breakdown.get("Likely Counterfeit", 0)

    return {
        "total_scans": total,
        "average_score": avg_score,
        "flagged_count": flagged,
        "verdict_breakdown": verdict_breakdown,
        "trend": trend,
    }


FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")