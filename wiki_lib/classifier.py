"""
classifier.py — Klassifikation von Notizen auf Wiki-Topics und Entity-Extraktion.
Layer 3: importiert aus Layer 0-2.

Exports: _sanitize_topic, _fallback_classification, _resolve_entity,
         _parse_classification, classify_content_multi, bootstrap_initial_topics
"""

import re
import json
import difflib
from collections import defaultdict

from .config import config, logger
from .constants import (
    ENTITY_TYPES, MAX_ENTITIES_PER_NOTE, ENTITY_FUZZY_CUTOFF,
    TOPIC_FUZZY_CUTOFF, DESCRIPTION_MAX_CHARS, IMAGE_MIME_MAP,
)
from .openrouter import call_openrouter, encode_image, _build_classification_excerpt, _extract_json_object


def _sanitize_topic(name):
    if not name:
        return ""
    topic = name.lower().strip().replace(" ", "_").replace("-", "_")
    topic = "".join(c for c in topic if c.isalnum() or c == "_").strip("_")
    return topic


def _fallback_classification():
    return {
        "primary": {"page": "allgemein", "is_new": False, "title": "Allgemein"},
        "secondary": [],
        "entities": [],
    }


def _resolve_entity(name_raw, type_raw, existing_entities):
    """
    Löst einen Entity-Namen zu einem (slug, is_new, type) Tupel auf.
    Fuzzy-Match nur innerhalb desselben Typs.
    """
    etype = (type_raw or "concept").strip().lower()
    if etype not in ENTITY_TYPES:
        etype = "concept"

    slug = _sanitize_topic(name_raw)
    if not slug:
        return None

    same_type_slugs = [e["name"] for e in existing_entities if e.get("type") == etype]
    if same_type_slugs:
        matches = difflib.get_close_matches(slug, same_type_slugs, n=1, cutoff=ENTITY_FUZZY_CUTOFF)
        if matches:
            return (matches[0], False, etype)

    for e in existing_entities:
        if e.get("type") != etype:
            continue
        for alias in (e.get("aliases") or []):
            if _sanitize_topic(alias) == slug:
                return (e["name"], False, etype)

    return (slug, True, etype)


def _parse_classification(raw, existing_pages):
    if not raw:
        return _fallback_classification()
    data = _extract_json_object(raw)
    if not data:
        logger.warning(f"Klassifikations-JSON nicht parsebar: {raw[:200]}")
        return _fallback_classification()

    primary_raw = data.get("primary")
    if not isinstance(primary_raw, dict) or not primary_raw.get("page"):
        return _fallback_classification()

    primary_name = _sanitize_topic(primary_raw["page"])
    if not primary_name:
        return _fallback_classification()

    topic_names = [p["name"] for p in existing_pages if p["kind"] == "topic"]
    if topic_names:
        matches = difflib.get_close_matches(primary_name, topic_names, n=1, cutoff=TOPIC_FUZZY_CUTOFF)
        if matches and matches[0] != primary_name:
            logger.info(f"Fuzzy-Match primary: '{primary_name}' → '{matches[0]}'")
            primary_name = matches[0]

    primary_is_new = primary_name not in topic_names
    primary_title = (primary_raw.get("title") or "").strip() or primary_name.replace("_", " ").title()

    result = {
        "primary": {"page": primary_name, "is_new": primary_is_new, "title": primary_title},
        "secondary": [],
        "entities": [],
    }

    seen_sec = {primary_name}
    for sec in (data.get("secondary") or []):
        if not isinstance(sec, dict):
            continue
        sec_name = _sanitize_topic(sec.get("page", ""))
        if not sec_name or sec_name in seen_sec:
            continue
        if topic_names:
            m = difflib.get_close_matches(sec_name, topic_names, n=1, cutoff=TOPIC_FUZZY_CUTOFF)
            if m:
                sec_name = m[0]
        context = (sec.get("context") or "").strip()
        if not context:
            continue
        result["secondary"].append({
            "page": sec_name,
            "is_new": sec_name not in topic_names,
            "context": context[:300],
        })
        seen_sec.add(sec_name)
        if len(result["secondary"]) >= 4:
            break

    existing_entities = [p for p in existing_pages if p["kind"] == "entity"]
    seen_ent = set()
    for ent in (data.get("entities") or [])[:MAX_ENTITIES_PER_NOTE]:
        if not isinstance(ent, dict):
            continue
        resolved = _resolve_entity(ent.get("name", ""), ent.get("type", ""), existing_entities)
        if not resolved:
            continue
        slug, is_new, etype = resolved
        if slug in seen_ent:
            continue
        seen_ent.add(slug)

        role = (ent.get("role") or "mentioned").strip().lower()
        if role not in {"primary", "benchmarked", "mentioned"}:
            role = "mentioned"

        description = (ent.get("description") or "").strip()
        if not is_new:
            description = ""
        else:
            description = description[:DESCRIPTION_MAX_CHARS]

        result["entities"].append({
            "name": ent.get("name", slug).strip(),
            "slug": slug,
            "type": etype,
            "is_new": is_new,
            "role": role,
            "description": description,
        })

    return result


def classify_content_multi(text=None, image_path=None, existing_pages=None):
    existing_pages = existing_pages or []

    topics = [p for p in existing_pages if p["kind"] == "topic"]
    entities = [p for p in existing_pages if p["kind"] == "entity"]

    if topics:
        topic_lines = []
        for p in topics:
            entry = f'- {p["name"]}: "{p["title"]}"'
            if p.get("subheadings"):
                entry += f' [{", ".join(p["subheadings"][:4])}]'
            topic_lines.append(entry)
        topics_str = "\n".join(topic_lines)
    else:
        topics_str = "(noch keine Topics vorhanden)"

    if entities:
        by_type = defaultdict(list)
        for e in entities:
            by_type[e.get("type", "concept")].append(e)
        ent_lines = []
        for etype in sorted(by_type.keys()):
            names = ", ".join(
                f"{e['name']} ({e.get('title', e['name'])})" for e in by_type[etype][:30]
            )
            ent_lines.append(f"  {etype}: {names}")
        entities_str = "\n".join(ent_lines)
    else:
        entities_str = "  (noch keine Entities vorhanden)"

    system_prompt = f"""Du bist ein Klassifikator für ein dateibasiertes Wiki.
Deine Aufgabe: Entscheide, welche Wiki-Seiten eine neue Notiz betrifft UND welche Entities sie erwähnt.

BESTEHENDE TOPIC-SEITEN (Format: name: "Titel" [Unterkapitel]):
{topics_str}

BESTEHENDE ENTITIES (nach Typ gruppiert):
{entities_str}

REGELN FÜR TOPICS:
1. Wähle GENAU EIN primary-Topic — das HAUPTTHEMA der Notiz.
2. Wähle 0 bis 4 secondary-Topics — Themen, die am Rand berührt werden.
3. Bevorzuge IMMER bestehende Seiten. Neue Topics nur wenn wirklich keine passt.
4. Neue Topic-Namen: 1-2 englische Wörter, snake_case, GENERISCH.

REGELN FÜR ENTITIES:
5. Extrahiere bis zu {MAX_ENTITIES_PER_NOTE} Entities aus der Notiz. Lieber weniger als mehr — nur das Wichtige.
6. Entity-Typen: GENAU EINER von {sorted(ENTITY_TYPES)}
   - tool: Software, Hardware, Services (PostgreSQL, RTX 4090, Obsidian)
   - model: KI/ML-Modelle mit Namen (Llama 3, Claude Opus, Stable Diffusion)
   - concept: Technische/wissenschaftliche Konzepte (Matched Filter, WebSocket, CNN)
   - project: Eigene oder benannte Projekte (ZeroClaw, Glitch Hunter)
   - person: Konkrete Personen mit Namen
7. Wenn eine Entity in der Liste oben schon existiert, benutze GENAU diesen Namen. Keine Varianten.
8. Für NEUE Entities: "description" ist 1-3 kompakte Sätze die beschreiben was die Entity ist. Für bestehende Entities: "description": null.
9. "role" ist eins von: "primary", "benchmarked", "mentioned".

ANTWORTE AUSSCHLIESSLICH MIT VALIDEM JSON, ohne Markdown-Fences, ohne Erklärung:
{{
  "primary": {{"page": "topic_name", "is_new": false, "title": null}},
  "secondary": [
    {{"page": "other_topic", "is_new": false, "context": "kurze Beschreibung"}}
  ],
  "entities": [
    {{"name": "Llama 3", "type": "model", "role": "benchmarked", "description": null}},
    {{"name": "RTX 4090", "type": "tool", "role": "mentioned", "description": "NVIDIA Consumer-GPU der Ada-Generation."}}
  ]
}}"""

    model = config["models"]["classification"]
    messages = []

    if text and not image_path:
        messages.append({
            "role": "user",
            "content": f"Klassifiziere diese Notiz:\n\n{_build_classification_excerpt(text)}",
        })
    elif image_path:
        model = config["models"]["vision_update"]
        try:
            base64_image = encode_image(image_path)
            ext = image_path.rsplit(".", 1)[-1].lower()
            mime_type = IMAGE_MIME_MAP.get(ext, "image/jpeg")
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "Klassifiziere den Inhalt dieses Bildes für ein technisches Wiki."},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}},
                ],
            })
        except Exception:
            return _fallback_classification()
    else:
        return _fallback_classification()

    raw = call_openrouter(model=model, messages=messages, system_prompt=system_prompt, max_tokens=1200)
    result = _parse_classification(raw, existing_pages)

    _ent_summary = [f"{e['slug']}({e['type']})" for e in result['entities']]
    logger.info(
        f"Klassifikation: primary='{result['primary']['page']}'"
        + (" (NEU)" if result['primary']['is_new'] else "")
        + (f", secondary={[s['page'] for s in result['secondary']]}" if result['secondary'] else "")
        + (f", entities={_ent_summary}" if _ent_summary else "")
    )
    return result


def bootstrap_initial_topics(notes):
    if len(notes) < 3:
        return {}
    notes_str = "\n\n".join(f"[Notiz {n['index']}]\n{n['excerpt'][:1000]}" for n in notes)
    system_prompt = """Du bist ein Wiki-Architekt. Schlage aus rohen Notizen eine initiale Topic-Struktur vor.

REGELN:
1. Erzeuge 3 bis 8 Topics MAXIMAL.
2. Topics sind GENERISCH und zukunftsfähig.
3. Topic-Namen: 1-2 englische Wörter, snake_case.
4. Jede Notiz bekommt GENAU EIN Primary-Topic.
5. Ähnliche Notizen → selbes Topic.

ANTWORTE AUSSCHLIESSLICH MIT VALIDEM JSON:
{
  "topics": [{"name": "topic_name", "title": "Titel"}],
  "assignments": [{"note": 0, "topic": "topic_name"}]
}"""
    raw = call_openrouter(
        model=config["models"]["classification"],
        messages=[{"role": "user", "content": f"Hier sind die rohen Notizen:\n\n{notes_str}"}],
        system_prompt=system_prompt,
        max_tokens=1500,
    )
    if not raw:
        return {}
    data = _extract_json_object(raw)
    if not data:
        return {}
    mapping = {}
    for a in (data.get("assignments") or []):
        if not isinstance(a, dict):
            continue
        try:
            note_idx = int(a.get("note"))
            topic = _sanitize_topic(a.get("topic", ""))
            if topic:
                mapping[note_idx] = topic
        except (ValueError, TypeError):
            continue
    logger.info(f"Cold-Start Bootstrap: {len(mapping)} von {len(notes)} Notizen zugeordnet.")
    return mapping
