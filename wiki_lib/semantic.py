"""
semantic.py — Layer 4: LLM-Analyse + Auto-Apply-Fixes
"""

import os
import json
from datetime import datetime

from .config import config, logger
from .constants import AUTO_APPLICABLE_KINDS
from .pages import get_existing_wiki_pages, _page_file_path
from .openrouter import call_openrouter, _extract_json_object
from .sections import parse_sections, reassemble_page
from .updates import _update_section_surgical
from .diagnostics import (
    load_diagnostics, save_diagnostics, refresh_stale_status,
    _content_hash, set_issue_status
)
from .backup import _backup_file, _atomic_write

# Falls nicht in constants.py, hier als Notlösung:
_AUTO_APPLICABLE = {
    "duplicate_content",
    "redundant_paragraphs",
    "malformed_list",
    "section_misplaced",
}
AUTO_APPLICABLE_KINDS = getattr(
    __import__("wiki_lib.constants", fromlist=["AUTO_APPLICABLE_KINDS"]), 
    "AUTO_APPLICABLE_KINDS", 
    _AUTO_APPLICABLE
)

def _build_context_list(existing_pages, current_slug, kind):
    """Baut kompakte Liste der anderen Seiten (1 Satz-Description, falls Entity)."""
    lines = []
    for p in existing_pages:
        # Selbst-Referenz ausschließen
        if p["name"] == current_slug and p["kind"] == kind:
            continue
        
        if p["kind"] == "topic":
            desc = f"{p['title']} ({len(p.get('subheadings', []))} sections)"
            lines.append(f"- topic/{p['name']}: {desc[:40]}")
        else:
             desc = p.get("description", "Entity")
             lines.append(f"- entity/{p['name']}: {desc[:40]}")
    return "\n".join(lines)

def analyze_page(slug: str, kind: str) -> tuple[dict | None, int]:
    """
    Das LLM-Diagnose-Tool.
    Returns: (Diagnose-Dict, Anzahl neuer Issues)
    """
    path = _page_file_path(slug, kind)
    if not os.path.exists(path):
        logger.error(f"analyze_page: Datei {path} nicht gefunden.")
        return None, 0

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Page laden, Hash berechnen
    current_hash = _content_hash(content)

    # 2. Bestehende Diagnosen laden und alte offene als stale setzen, falls Datei verändert
    refresh_stale_status(slug, kind, current_hash)
    old_diag = load_diagnostics(slug, kind)
    
    # 3. Kontext bauen (Alle Seiten-Titel)
    all_pages = get_existing_wiki_pages()
    context_str = _build_context_list(all_pages, slug, kind)

    # 4. LLM Call
    system_prompt = f"""Du bist ein Wiki-Qualitätsanalyst. Analysiere die gegebene Seite und identifiziere
STRUKTURELLE ODER SEMANTISCHE PROBLEME, die der Autor nicht selbst sieht.

DU DARFST NICHT bewerten ob Fakten inhaltlich korrekt sind — nur ob Struktur,
Verlinkung und Konsistenz stimmen.

ISSUE-KINDS (nutze GENAU einen von diesen):
- duplicate_content: Zwei Sektionen sagen im Kern dasselbe
- redundant_paragraphs: Innerhalb einer Sektion wiederholen sich Aussagen
- malformed_list: Aufzählung liegt als Fließtext vor, sollte Liste sein
- section_misplaced: Inhalt steht unter falschem Heading
- contradicts_other_page: Aussage widerspricht einer Aussage in einer anderen Seite
- missing_context: Konzept wird vorausgesetzt, aber nicht verlinkt, obwohl eine
                   passende Wiki-Seite existiert
- potentially_outdated: Formulierung deutet auf mögliche Veralterung hin
                        (z.B. "neue Feature", "Release 2024")

Für jede Issue:
- description: 1-2 Sätze, konkret und aktionable
- severity: "error" | "warning" | "suggestion"
- sections_involved: Liste der exakten Sektion-Slugs (Nutze ZWINGEND Unterstriche _ statt Bindestriche -! WICHTIG: Bei "duplicate_content" MÜSSEN exakt ZWEI Slugs stehen. Leer, wenn seitenweit.)

BESTEHENDE WIKI-SEITEN (für contradicts_other_page und missing_context):
{context_str}

ANTWORT: Valides JSON, keine Fences.
{{
  "issues": [
    {{
      "kind": "duplicate_content",
      "severity": "warning",
      "description": "...",
      "sections_involved": ["slug_a", "slug_b"]
    }}
  ]
}}

Wenn keine Probleme: {{"issues": []}}"""

    model = config["models"]["classification"] # Using classif. model or text? 
    # System prompt specifically says using structured JSON, typically text_update or classif is fine. 
    # As logic suggests, classification is usually around 50 tokens inside limits, but here we expect JSON output.
    raw = call_openrouter(
        model=model,
        messages=[{"role": "user", "content": f"Wiki-Seite ({kind}/{slug}.md):\n\n{content[:32000]}"}],
        system_prompt=system_prompt,
        max_tokens=2000,
    )

    if not raw:
        return None, 0

    data = _extract_json_object(raw)
    if not data or "issues" not in data:
        data = {"issues": []}

    # 5. Alte Issues verarbeiten, identische 'open' mergen / neu anlegen
    new_issues = data["issues"]
    stored_issues = []
    
    highest_id = 0
    if old_diag and "issues" in old_diag:
        for iss in old_diag["issues"]:
            stored_issues.append(iss)
            if iss.get("id", "").startswith("iss_"):
                try:
                    num = int(iss["id"][4:])
                    highest_id = max(highest_id, num)
                except ValueError:
                    pass

    # Filter out semantic-duplicates: if a new issue matches an old one (same kind & sections_involved)
    # we don't add it as completely new if the old one is dismissed or still open.
    # Actually wait: The requirement is: "Dismiss ist keine Löschung... Wenn LLM beim nächsten Lauf dieselbe Issue findet... wird sie automatisch auf dismissed gesetzt".
    # And if old is applied or stale? We only avoid noise if it's already dismissed or open.
    n_new_added = 0
    now = datetime.now().isoformat()

    for n_iss in new_issues:
        n_iss["auto_applicable"] = n_iss.get("kind") in AUTO_APPLICABLE_KINDS
        if n_iss.get("kind") == "section_misplaced":
            # Extra requirement: disable auto_apply for misplaced section due to complexity.
            n_iss["auto_applicable"] = False 

        # Check for matches
        match = None
        for o_iss in stored_issues:
            if o_iss.get("kind") == n_iss.get("kind") and set(o_iss.get("sections_involved", [])) == set(n_iss.get("sections_involved", [])):
                match = o_iss
                break
        
        if match:
            # If match exists and is dismissed, we just ignore the new finding (or we could update the old, but it's dismissed anyway).
            # If match exists and is open, we already have it.
            # If match exists and is stale/applied, it means it was "fixed" but LLM found it AGAIN in new content. This means it re-appeared!
            if match["status"] in ["dismissed", "open"]:
                continue
        
        # Completely new or re-appeared after being stale
        highest_id += 1
        n_iss["id"] = f"iss_{highest_id:03d}"
        n_iss["status"] = "open"
        n_iss["detected_at"] = now
        # Fallback if properties missing
        n_iss.setdefault("sections_involved", [])
        
        stored_issues.append(n_iss)
        n_new_added += 1

    final_diag = {
        "slug": slug,
        "kind": kind,
        "last_analyzed": now,
        "model_used": model,
        "content_hash": current_hash,
        "issues": stored_issues
    }
    
    # 6. Speichern
    save_diagnostics(slug, kind, final_diag)
    
    return final_diag, n_new_added

def apply_issue(slug: str, kind: str, issue_id: str, dry_run: bool = False):
    """
    Auto-Apply für eine spezifische Issue.
    """
    path = _page_file_path(slug, kind)
    if not os.path.exists(path):
        return False, "Wiki-Datei nicht gefunden."

    diag = load_diagnostics(slug, kind)
    if not diag:
        return False, "Diagnosedaten nicht gefunden."

    # 1. Issue aus Diagnose-Datei holen
    issue = None
    for iss in diag.get("issues", []):
        if iss.get("id") == issue_id:
            issue = iss
            break
            
    if not issue:
        return False, "Issue-ID nicht gefunden."
        
    if issue.get("status") != "open":
        return False, f"Issue ist nicht 'open' (aktuell: {issue.get('status')})."

    if not issue.get("auto_applicable"):
         return False, "Issue-Art ist nicht auto-applicable."

    # 2. Content-Hash checken
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    current_hash = _content_hash(content)
    if diag.get("content_hash") != current_hash:
        # Mark as stale instead 
        refresh_stale_status(slug, kind, current_hash)
        return False, "Inhalt hat sich seit Diagnose geändert. Issue ist stale."

    # 3. Parsen der Sections
    parsed = parse_sections(content)
    sections = parsed.get("sections", [])
    
    ikind = issue.get("kind")
    sections_involved = [s.replace("-", "_") for s in issue.get("sections_involved", [])]

    model = config["models"].get("text_update", "google/gemini-3.1-flash-lite-preview")
    
    new_sections_state = list(sections)
    applied_info = ""

    # 4 & 5. Fix Prompt bauen & Update
    if ikind == "duplicate_content":
        if len(sections_involved) < 2:
            return False, "Weniger als 2 Sektionen betroffen."
        
        sec_a_slug = sections_involved[0]
        sec_b_slug = sections_involved[1]
        
        idx_a = -1
        idx_b = -1
        for i, s in enumerate(new_sections_state):
             if s["slug"] == sec_a_slug: idx_a = i
             elif s["slug"] == sec_b_slug: idx_b = i
                
        if idx_a == -1 or idx_b == -1:
             return False, "Sektionen(n) beim Parsen nicht gefunden."

        sec_a = new_sections_state[idx_a]
        sec_b = new_sections_state[idx_b]

        sys_prompt = "Die folgenden zwei Sektionen überlappen. Schreibe eine einzige zusammengeführte Sektion, die keine Fakten verliert. Gib nur den Body zurück (ohne Heading, ohne Fences)."
        user_prompt = f"--- Sektion A: {sec_a['heading']} ---\n{sec_a['body']}\n\n--- Sektion B: {sec_b['heading']} ---\n{sec_b['body']}"

        merged_body = call_openrouter(model=model, messages=[{"role": "user", "content": user_prompt}], system_prompt=sys_prompt, max_tokens=16000)
        if not merged_body:
             return False, "LLM gab keine Antwort."
             
        # Cleanup
        merged_body = merged_body.strip()
        merged_body = merged_body.removeprefix("```markdown").removeprefix("```")
        merged_body = merged_body.removesuffix("```").strip()

        # Shrinkage
        old_len = len(sec_a['body'].strip()) + len(sec_b['body'].strip())
        new_len = len(merged_body)
        if new_len < old_len * 0.85:
             logger.warning(f"Merge schrumpfte zu stark: {new_len} vs {old_len}")
             return False, "Merge abgebrochen - Verlust von Fakten befürchtet (>15% kürzer)."

        merged_body += "\n\n"
             
        # Ersetze A, lösche B
        new_sections_state[idx_a] = {
             "heading": sec_a["heading"],
             "slug": sec_a["slug"],
             "body": merged_body,
             "original": sec_a["heading"] + "\n" + merged_body
        }
        del new_sections_state[max(idx_a, idx_b)] # Lösche die höhere Nummer zuerst, 
        if min(idx_a, idx_b) != max(idx_a, idx_b): # falls beide indices nicht gleich sind (sollten sie nicht)
             # actually better:
             idx_to_remove = idx_b if idx_a < idx_b else idx_b
             del new_sections_state[idx_b if idx_b > idx_a else idx_b + 1] # wait, simple array mutation:
             
        new_sections_state = [s for s in new_sections_state if s["slug"] != sec_b["slug"]]
        applied_info = f"Merged '{sec_a_slug}' und '{sec_b_slug}'."

    elif ikind == "redundant_paragraphs":
        if not sections_involved:
            return False, "Keine Sektion angegeben."
        sec_slug = sections_involved[0]
        
        idx = -1
        for i, s in enumerate(new_sections_state):
             if s["slug"] == sec_slug: idx = i
        if idx == -1: return False, "Sektion nicht gefunden."
        
        sec = new_sections_state[idx]
        sys_prompt = "In dieser Sektion wiederholen sich Aussagen. Entferne die Wiederholungen, behalte alle unique Fakten. Gib nur den Body zurück (ohne Heading/Fences)."
        user_prompt = f"--- Sektion: {sec['heading']} ---\n{sec['body']}"

        clean_body = call_openrouter(model=model, messages=[{"role": "user", "content": user_prompt}], system_prompt=sys_prompt, max_tokens=16000)
        if not clean_body: return False, "LLM Fehler"
        
        clean_body = clean_body.strip()
        clean_body = clean_body.removeprefix("```markdown").removeprefix("```").removesuffix("```").strip()

        if len(clean_body) < len(sec['body'].strip()) * 0.70:
             return False, "Kürzung abgebrochen - Resultat ist zu kurz (<70%)."
             
        clean_body += "\n\n"
        new_sections_state[idx] = {
            "heading": sec["heading"],
            "slug": sec["slug"],
            "body": clean_body,
            "original": sec["heading"] + "\n" + clean_body
        }
        applied_info = f"Redundanzen aus '{sec_slug}' entfernt."

    elif ikind == "malformed_list":
        if not sections_involved:
             return False, "Keine Sektion angegeben."
        sec_slug = sections_involved[0]
        
        idx = -1
        for i, s in enumerate(new_sections_state):
             if s["slug"] == sec_slug: idx = i
        if idx == -1: return False, "Sektion nicht gefunden."

        sec = new_sections_state[idx]
        sys_prompt = "Formuliere diesen Abschnitt als Markdown-Aufzählung um, ohne Inhalt zu verändern. Gib nur den Body zurück."
        user_prompt = f"--- Sektion: {sec['heading']} ---\n{sec['body']}"
        
        list_body = call_openrouter(model=model, messages=[{"role": "user", "content": user_prompt}], system_prompt=sys_prompt, max_tokens=16000)
        if not list_body: return False, "LLM Fehler"
        
        list_body = list_body.strip().removeprefix("```markdown").removeprefix("```").removesuffix("```").strip()
        
        # Deterministischer Check
        if "\n-" not in "\n" + list_body and "\n*" not in "\n" + list_body:
             return False, "LLM formatiere nicht als Liste."

        list_body += "\n\n"
        new_sections_state[idx] = {
            "heading": sec["heading"],
            "slug": sec["slug"],
            "body": list_body,
            "original": sec["heading"] + "\n" + list_body
        }
        applied_info = f"'{sec_slug}' in Liste formatiert."

    else:
        return False, f"Kind '{ikind}' nicht auto-applicable."

    # 6. Reassemble Page
    new_content = reassemble_page(parsed["preamble"], new_sections_state)
    
    if new_content == content:
        return False, "Keine Änderungen generiert."

    # 7. Backup and Write
    if not dry_run:
        run_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        _backup_file(path, run_ts)
        _atomic_write(path, new_content)
        
        # Neue Content-Hash ins Diagnostics und Issue auf applied
        new_hash = _content_hash(new_content)
        diag["content_hash"] = new_hash
        save_diagnostics(slug, kind, diag)
        set_issue_status(slug, kind, issue_id, "applied", datetime.now().isoformat())

    return True, applied_info
