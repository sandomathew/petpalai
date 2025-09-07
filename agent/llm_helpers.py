# agent/llm_helpers.py
import os
import json
import http.client

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "llama3.2")  # keep lightweight

def _chat(prompt: str) -> str:
    """
    Minimal Ollama chat call.
    """
    conn = http.client.HTTPConnection(OLLAMA_HOST, OLLAMA_PORT, timeout=5)
    payload = json.dumps({
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You classify short user replies in a chat."},
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "options": {"temperature": 0}
    })
    conn.request("POST", "/api/chat", body=payload, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    if resp.status != 200:
        return ""
    data = json.loads(resp.read().decode("utf-8"))
    return (data.get("message") or {}).get("content", "")

def detect_help_or_unknown(user_text: str) -> bool:
    """
    True if the user is asking for examples/help or says they don't know.
    """
    # quick rule for obvious phrases
    t = (user_text or "").lower()
    if any(k in t for k in ["example", "examples", "not sure", "don't know", "dont know", "help", "what are", "suggest"]):
        return True

    # fallback to LLM classification (very short & cheap)
    prompt = f"""Classify this reply. Output only ONE of: HELP, VALUE.
User reply: "{user_text}" """
    out = _chat(prompt).strip().upper()
    return out.startswith("HELP")

def suggest_examples(species: str) -> str:
    """
    Return a short comma-separated list of breed examples.
    """
    # You can call LLM here if you want dynamic, but we’ll keep it static & fast:
    from pet_manager.species_registry import SPECIES_BREEDS
    examples = SPECIES_BREEDS.get(species, [])[:6]
    return ", ".join(examples) if examples else "Labrador, Poodle, Beagle, Bulldog"
