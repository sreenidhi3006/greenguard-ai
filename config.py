"""
GreenGuard AI - Configuration
Keep all environment-dependent settings here so you never hardcode
keys/paths inside logic files.
"""

import os

# ---------- IBM Granite / watsonx (ONLINE mode) ----------
# Get these from https://cloud.ibm.com/ after creating a watsonx.ai project
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID", "gemini-2.0-flash")
# ---------- Local / OFFLINE model (via Ollama) ----------
# Install Ollama (https://ollama.com) then run: ollama pull phi3:mini
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OFFLINE_MODEL_NAME = os.getenv("OFFLINE_MODEL_NAME", "granite3.1-dense:2b")

# ---------- Translation ----------
GOOGLE_TRANSLATE_API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY", "")

# ---------- Database ----------
DB_PATH = os.getenv("DB_PATH", os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "greenguard.db"))

# ---------- RAG ----------
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"     # small, fully offline, ~80MB
FAISS_INDEX_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "medicine_index.faiss")

# ---------- Connectivity check ----------
CONNECTIVITY_CHECK_URL = "https://8.8.8.8"
CONNECTIVITY_TIMEOUT_SECONDS = 2

# ---------- Trust score thresholds ----------
TRUST_SCORE_FAKE_THRESHOLD = 50       # below this => "Likely Counterfeit"
TRUST_SCORE_SUSPICIOUS_THRESHOLD = 75  # below this => "Needs Verification"
