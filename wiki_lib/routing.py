"""
routing.py — LLM-basiertes Routing von Notizen auf Wiki-Sektionen.
Layer 3: importiert aus Layer 0-2.

Exports: _route_notes_to_sections
"""

import re

from .config import config, logger
from .openrouter import call_openrouter, _extract_json_object
from .sections import _slugify_heading


def _route_notes_to_sections(notes, parsed_page, topic):
    if not notes:
        return []
    if parsed_page['sections']:
        section_lines = []
        for s in parsed_page['sections']:
            hint = re.sub(r'\s+', ' ', s['body'].strip())[:200]
            section_lines.append(f"  - slug='{s['slug']}'  heading='{s['heading']}'  hint='{hint}...'")
        sections_str = "\n".join(section_lines)
    else:
        sections_str = "  (keine Sektionen)"
    notes_str = "\n\n".join(f"[Notiz {i}]\n{note[:1500]}" for i, note in enumerate(notes))

    system_prompt = f"""Router für Wiki-Updates. Thema: '{topic}'. Für jede Notiz: welche H2-Sektion oder neue?

SEKTIONEN:
{sections_str}

REGELN:
1. Bevorzuge bestehende Sektionen.
2. Neue Sektion nur bei klar abgrenzbarem neuem Aspekt.
3. Jede Notiz MUSS geroutet werden.
4. Neue Headings: auf Deutsch, "## Xxx".

JSON:
{{
  "routes": [
    {{"note": 0, "target_slug": "installation", "is_new": false}},
    {{"note": 1, "target_slug": null, "is_new": true, "new_heading": "## Troubleshooting"}}
  ]
}}"""

    raw = call_openrouter(
        model=config["models"]["classification"],
        messages=[{"role": "user", "content": notes_str}],
        system_prompt=system_prompt,
        max_tokens=1000,
    )
    if not raw:
        return None
    data = _extract_json_object(raw)
    if not data or "routes" not in data:
        return None
    existing_slugs = {s['slug'] for s in parsed_page['sections']}
    routes = []
    for r in (data.get("routes") or []):
        if not isinstance(r, dict):
            continue
        try:
            note_idx = int(r.get("note"))
        except (ValueError, TypeError):
            continue
        if note_idx < 0 or note_idx >= len(notes):
            continue
        is_new = bool(r.get("is_new"))
        if is_new:
            new_heading = (r.get("new_heading") or "").strip()
            if not new_heading:
                continue
            if not new_heading.startswith("## "):
                new_heading = "## " + new_heading.lstrip("#").strip()
            routes.append({"note": note_idx, "target_slug": None, "is_new": True, "new_heading": new_heading})
        else:
            target_slug = r.get("target_slug")
            if not target_slug or target_slug not in existing_slugs:
                continue
            routes.append({"note": note_idx, "target_slug": target_slug, "is_new": False})
    return routes
