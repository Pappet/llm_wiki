"""
batch.py — Batch-Orchestration: liest raw/, klassifiziert, updated Wiki und Entities.
Layer 5: importiert aus Layer 0-4.

Exports: _register_new_topic_in_list, _register_new_entity_in_list, process_batch
"""

import os
import re
from datetime import datetime
from collections import defaultdict

from .config import config, logger, DIRS
from .pages import get_existing_wiki_pages, _page_file_path, migrate_flat_wiki_to_topics
from .classifier import classify_content_multi, bootstrap_initial_topics, _sanitize_topic
from .openrouter import _build_classification_excerpt
from .logbook import append_log_entries, _log_entry, generate_index_file
from .entities import _ensure_entity_page, _append_entity_backlink
from .secondary import update_secondary_page_deterministic
from .updates import _execute_primary_update


def _register_new_topic_in_list(name, existing_pages):
    if not any(p["name"] == name and p["kind"] == "topic" for p in existing_pages):
        existing_pages.append({
            "name": name,
            "kind": "topic",
            "title": name.replace("_", " ").title(),
            "subheadings": [],
            "path": _page_file_path(name, "topic"),
        })


def _register_new_entity_in_list(entity, existing_pages):
    if not any(p["name"] == entity["slug"] and p["kind"] == "entity" for p in existing_pages):
        existing_pages.append({
            "name": entity["slug"],
            "kind": "entity",
            "title": entity.get("name", entity["slug"]),
            "type": entity["type"],
            "description": entity.get("description", ""),
            "aliases": [],
            "mention_count": 0,
            "path": _page_file_path(entity["slug"], "entity"),
        })


def process_batch():
    migrate_flat_wiki_to_topics()

    raw_dir = DIRS["raw"]
    files = [f for f in os.listdir(raw_dir) if os.path.isfile(os.path.join(raw_dir, f))]
    if not files:
        logger.info("Keine neuen Dateien. Ende.")
        return

    logger.info(f"{len(files)} neue Dateien zur Verarbeitung gefunden.")
    existing_pages = get_existing_wiki_pages()
    n_topics = sum(1 for p in existing_pages if p["kind"] == "topic")
    n_entities = sum(1 for p in existing_pages if p["kind"] == "entity")
    logger.info(f"Bestehend: {n_topics} Topic(s), {n_entities} Entity/ies")

    # Phase 1: Einlesen
    file_entries = []
    for file in files:
        filepath = os.path.join(raw_dir, file)
        ext = file.split('.')[-1].lower()
        if ext in ['txt', 'md']:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                file_entries.append({"path": filepath, "ext": ext, "content": content})
            except Exception as e:
                logger.error(f"Fehler beim Einlesen von {file}: {e}")
        elif ext in ['jpg', 'jpeg', 'png', 'webp']:
            file_entries.append({"path": filepath, "ext": ext, "content": None})
        else:
            logger.warning(f"Ignoriere {file}: Format nicht unterstützt.")

    if not file_entries:
        return

    # Phase 2: Cold-Start Bootstrap
    bootstrap_mapping = {}
    text_entries = [(i, e) for i, e in enumerate(file_entries) if e["content"] is not None]
    is_cold_start = n_topics < 3 and len(text_entries) >= 3
    if is_cold_start:
        logger.info(f"COLD-START: {n_topics} Topics, {len(text_entries)} Notizen. Bootstrap.")
        notes_for_bootstrap = [
            {"index": i, "excerpt": _build_classification_excerpt(e["content"], body_limit=1500)}
            for i, e in text_entries
        ]
        bootstrap_mapping = bootstrap_initial_topics(notes_for_bootstrap)
        for topic in set(bootstrap_mapping.values()):
            _register_new_topic_in_list(topic, existing_pages)

    # Phase 3: Klassifikation
    primary_updates = defaultdict(lambda: {"texts": [], "images": [], "files_to_move": []})
    secondary_updates = defaultdict(list)
    primary_entity_refs = defaultdict(list)
    all_entity_assignments = []

    for i, entry in enumerate(file_entries):
        filepath = entry["path"]
        filename = os.path.basename(filepath)

        if i in bootstrap_mapping:
            primary_name = bootstrap_mapping[i]
            classification = {
                "primary": {
                    "page": primary_name,
                    "is_new": False,
                    "title": primary_name.replace("_", " ").title(),
                },
                "secondary": [],
                "entities": [],
            }
            logger.info(f"'{filename}' → Bootstrap: '{primary_name}'")
        elif entry["content"] is not None:
            classification = classify_content_multi(text=entry["content"], existing_pages=existing_pages)
        else:
            classification = classify_content_multi(image_path=filepath, existing_pages=existing_pages)

        primary_page = classification["primary"]["page"]
        if entry["content"] is not None:
            primary_updates[primary_page]["texts"].append(entry["content"])
        else:
            primary_updates[primary_page]["images"].append(filepath)
        primary_updates[primary_page]["files_to_move"].append(filepath)

        for sec in classification["secondary"]:
            secondary_updates[sec["page"]].append({
                "from_page": primary_page,
                "context": sec["context"],
            })

        for ent in classification["entities"]:
            primary_entity_refs[primary_page].append(ent)
            if entry["content"]:
                snippet = re.sub(r'\s+', ' ', entry["content"]).strip()[:120]
            else:
                snippet = f"Bild: {filename}"
            all_entity_assignments.append({
                "entity": ent,
                "from_slug": primary_page,
                "from_title": classification["primary"]["title"],
                "role": ent["role"],
                "context": snippet,
            })
            _register_new_entity_in_list(ent, existing_pages)

        _register_new_topic_in_list(primary_page, existing_pages)
        for s in classification["secondary"]:
            _register_new_topic_in_list(s["page"], existing_pages)

    logger.info(
        f"Klassifikation fertig. Primaries: {len(primary_updates)}, "
        f"Secondaries: {len(secondary_updates)}, "
        f"Entity-Assignments: {len(all_entity_assignments)}"
    )

    # Phase 4: Primary-Updates
    logger.info(f"=== {len(primary_updates)} Primary-Update(s) ===")
    log_entries = []
    for topic, data in primary_updates.items():
        seen_slugs = set()
        deduped_refs = []
        for ref in primary_entity_refs.get(topic, []):
            if ref["slug"] not in seen_slugs:
                seen_slugs.add(ref["slug"])
                deduped_refs.append(ref)
        success, log_detail = _execute_primary_update(topic, data, existing_pages, deduped_refs)
        if success and log_detail:
            log_entries.append(_log_entry("primary_update", log_detail))

    # Phase 5: Secondary-Updates
    logger.info(f"=== {len(secondary_updates)} Secondary-Update(s) ===")
    for sec_page, refs in secondary_updates.items():
        if sec_page in primary_updates:
            continue
        update_secondary_page_deterministic(sec_page, refs, existing_pages)
        log_entries.append(_log_entry("secondary_append", f"topics/{sec_page}.md | +{len(refs)}"))

    # Phase 6: Entity-Updates
    logger.info(f"=== {len(all_entity_assignments)} Entity-Assignment(s) ===")
    entity_create_count = 0
    entity_append_count = 0
    for assignment in all_entity_assignments:
        ent = assignment["entity"]
        backlink = {
            "from_slug": assignment["from_slug"],
            "from_title": assignment["from_title"],
            "role": assignment["role"],
            "context": assignment["context"],
        }
        if ent["is_new"]:
            if not os.path.exists(_page_file_path(ent["slug"], "entity")):
                if _ensure_entity_page(ent, backlink):
                    entity_create_count += 1
                    log_entries.append(_log_entry("entity_create", f"entities/{ent['slug']}.md | {ent['type']}"))
            else:
                _append_entity_backlink(ent["slug"], backlink)
                entity_append_count += 1
        else:
            _append_entity_backlink(ent["slug"], backlink)
            entity_append_count += 1

    logger.info(f"Entity-Ergebnis: {entity_create_count} neu, {entity_append_count} appends")

    if log_entries:
        append_log_entries(log_entries)
    generate_index_file()
    logger.info("Verarbeitungsdurchlauf komplett beendet.")
