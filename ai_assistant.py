"""
GreenGuard AI - AI Chat Assistant (Online/Offline Hybrid)

ONLINE mode uses Google Gemini (free tier, no card required) instead of
IBM Granite/watsonx - swapped in because watsonx account verification
required a card. OFFLINE mode still uses a local model via Ollama,
unchanged.

Requires:
    pip install requests   (already in requirements.txt)
    A free Gemini API key from https://aistudio.google.com (no card needed)
"""

import requests
from typing import Tuple

from config import (
    GEMINI_API_KEY, GEMINI_MODEL_ID,
    OLLAMA_URL, OFFLINE_MODEL_NAME,
    CONNECTIVITY_CHECK_URL, CONNECTIVITY_TIMEOUT_SECONDS,
)
from rag_module import retrieve, build_context_string

SYSTEM_PROMPT = """You are GreenGuard AI, an assistant that helps everyday
consumers verify whether a medicine or wellness product (especially ones
marketed as "eco-friendly", "organic", "ayurvedic", or "herbal") is likely
genuine or counterfeit.

Rules you must always follow:
- Base your answer ONLY on the verified medicine context provided to you.
- If the context does not contain a clear match, say so honestly - do NOT
  guess or invent license numbers, batch formats, or manufacturer details.
- Never diagnose medical conditions or recommend medicines to take.
- If something looks suspicious, tell the user clearly and suggest they
  verify with the AYUSH/FSSAI portal or avoid the product.
- Keep answers short, plain-language, and non-technical.
"""


def is_online() -> bool:
    """Quick connectivity check used to decide which model to call."""
    try:
        requests.get(CONNECTIVITY_CHECK_URL, timeout=CONNECTIVITY_TIMEOUT_SECONDS)
        return True
    except requests.RequestException:
        return False


# ---------- ONLINE: Google Gemini API ----------

def _call_gemini_api(system_prompt: str, user_prompt: str) -> str:
    """
    Calls Google's Gemini API (generateContent endpoint). Free tier,
    no card or billing setup needed.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set in environment.")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL_ID}:generateContent?key={GEMINI_API_KEY}"
    )

    resp = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json={
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 300},
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# ---------- OFFLINE: local model via Ollama ----------

def _call_local_model(prompt: str) -> str:
    """
    Calls a locally-running Ollama model (no internet needed).
    Requires Ollama running on the same machine: `ollama serve`
    and the model pulled: `ollama pull granite3.1-dense:2b`
    """
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": OFFLINE_MODEL_NAME,
            "prompt": prompt,
            "stream": False,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()


# ---------- Public entry point ----------

def ask_assistant(user_query: str) -> Tuple[str, str]:
    """
    Main function called by the API layer.
    Returns (answer_text, mode_used) where mode_used is 'online' or 'offline'.
    """
    retrieved_docs = retrieve(user_query, top_k=3)
    context = build_context_string(retrieved_docs)

    user_prompt = (
        f"VERIFIED MEDICINE CONTEXT:\n{context}\n\n"
        f"USER QUESTION: {user_query}\n\n"
        f"ANSWER:"
    )

    if is_online():
        try:
            answer = _call_gemini_api(SYSTEM_PROMPT, user_prompt)
            return answer, "online"
        except Exception as e:
            print(f"[ai_assistant] Gemini call failed ({e}), falling back to offline model.")

    full_prompt = f"{SYSTEM_PROMPT}\n\n{user_prompt}"
    answer = _call_local_model(full_prompt)
    return answer, "offline"


if __name__ == "__main__":
    q = "Is Ashwagandha Immunity Capsules by Himalaya genuine?"
    ans, mode = ask_assistant(q)
    print(f"[{mode}] {ans}")