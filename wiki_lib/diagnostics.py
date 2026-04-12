"""
diagnostics.py — Layer 3: Diagnose-Datei-Management, Hash, Status-Transitions.
Keine LLM-Calls hier — nur Dateiverwaltung und Hash-Logik.
"""

import os
import json
import hashlib
from datetime import datetime

from .config import DIAGNOSTICS_DIR, logger

def _ensure_dir():
    os.makedirs(DIAGNOSTICS_DIR, exist_ok=True)

def _diagnostics_path(slug: str, kind: str) -> str:
    _ensure_dir()
    return os.path.join(DIAGNOSTICS_DIR, f"{kind}_{slug}.json")

def _content_hash(content: str) -> str:
    """SHA256 hex des Inhalts."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def load_diagnostics(slug: str, kind: str) -> dict | None:
    """Lädt JSON, gibt None zurück wenn keine Diagnose existiert."""
    path = _diagnostics_path(slug, kind)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Fehler beim Laden von Diagnose {path}: {e}")
        return None

def save_diagnostics(slug: str, kind: str, data: dict) -> None:
    """Atomares Schreiben via .tmp + rename."""
    path = _diagnostics_path(slug, kind)
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.rename(tmp_path, path)
    except Exception as e:
        logger.error(f"Fehler beim Speichern von Diagnose {path}: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def refresh_stale_status(slug: str, kind: str, current_content_hash: str) -> int:
    """Markiert alle open-Issues als stale wenn Hash nicht mehr stimmt.
    Returns: Anzahl der auf stale gesetzten Issues."""
    data = load_diagnostics(slug, kind)
    if not data:
        return 0

    if data.get("content_hash") == current_content_hash:
        return 0

    stale_count = 0
    now = datetime.now().isoformat()
    for issue in data.get("issues", []):
        if issue.get("status") == "open":
            issue["status"] = "stale"
            issue["stale_at"] = now
            stale_count += 1
    
    if stale_count > 0:
        save_diagnostics(slug, kind, data)
    
    return stale_count

def list_all_diagnostics() -> list[dict]:
    """Für --show-diagnostics ohne Argument: alle JSON-Dateien einlesen und zurückgeben."""
    _ensure_dir()
    all_diags = []
    for filename in os.listdir(DIAGNOSTICS_DIR):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(DIAGNOSTICS_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                all_diags.append(json.load(f))
        except Exception as e:
            logger.error(f"Konnte Diagnose-Datei {filepath} nicht lesen: {e}")
    return all_diags

def set_issue_status(slug: str, kind: str, issue_id: str, new_status: str, timestamp: str = None) -> bool:
    """Ändert Status einer Issue."""
    data = load_diagnostics(slug, kind)
    if not data:
        return False
    
    found = False
    for issue in data.get("issues", []):
        if issue.get("id") == issue_id:
            issue["status"] = new_status
            if timestamp is None:
                timestamp = datetime.now().isoformat()
            if new_status == "applied":
                issue["applied_at"] = timestamp
            elif new_status == "dismissed":
                issue["dismissed_at"] = timestamp
            elif new_status == "stale":
                issue["stale_at"] = timestamp
            found = True
            break
            
    if found:
        save_diagnostics(slug, kind, data)
    return found

def get_open_issues(slug: str, kind: str) -> list[dict]:
    """Convenience: alle issues wo status == 'open'. 
    Achtung: Dies ist eine pure-helper Funktion. Normalerweise wird vor dem Finden von offnen 
    Issues refresh_stale_status vom Caller aufgerufen wenn der Content aktuell überprüft wird."""
    data = load_diagnostics(slug, kind)
    if not data:
        return []
    return [iss for iss in data.get("issues", []) if iss.get("status") == "open"]

