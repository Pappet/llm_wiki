"""
pages.py — Wiki-Seiten-Discovery, Pfad-Helpers und einmalige Migration.
Layer 2: importiert aus Layer 0 (config, constants) und Layer 1 (frontmatter).

Exports: _page_file_path, _relative_link, get_existing_wiki_pages,
         _read_page_meta, _read_entity_meta, migrate_flat_wiki_to_topics
"""

import os
import shutil

from .config import WIKI_ROOT, TOPICS_DIR, ENTITIES_DIR, DIRS, logger
from .constants import RESERVED_WIKI_FILES
from .frontmatter import parse_frontmatter


def _page_file_path(name, kind):
    """Absoluter Pfad zu einer Wiki-Seite, abhängig von Art."""
    if kind == "entity":
        return os.path.join(ENTITIES_DIR, f"{name}.md")
    return os.path.join(TOPICS_DIR, f"{name}.md")


def _relative_link(from_kind, to_kind, to_slug):
    """Baut einen relativen Markdown-Link zwischen Seiten in topics/ bzw. entities/."""
    if from_kind == to_kind:
        return f"{to_slug}.md"
    return f"../{'entities' if to_kind == 'entity' else 'topics'}/{to_slug}.md"


def get_existing_wiki_pages():
    """
    Sammelt alle Wiki-Seiten aus topics/ und entities/.
    Returns: list of dicts mit {name, kind, title, subheadings, path, type?, description?}
    """
    pages = []

    if os.path.isdir(TOPICS_DIR):
        for f in os.listdir(TOPICS_DIR):
            if not f.endswith(".md") or f in RESERVED_WIKI_FILES:
                continue
            name = f[:-3]
            full = os.path.join(TOPICS_DIR, f)
            title, subheadings = _read_page_meta(full, name)
            pages.append({
                "name": name,
                "kind": "topic",
                "title": title,
                "subheadings": subheadings,
                "path": full,
            })

    if os.path.isdir(ENTITIES_DIR):
        for f in os.listdir(ENTITIES_DIR):
            if not f.endswith(".md"):
                continue
            name = f[:-3]
            full = os.path.join(ENTITIES_DIR, f)
            fm, title, description = _read_entity_meta(full, name)
            pages.append({
                "name": name,
                "kind": "entity",
                "title": title,
                "type": fm.get("type", "concept"),
                "description": description,
                "aliases": fm.get("aliases", []) or [],
                "mention_count": fm.get("mention_count", 0),
                "path": full,
            })

    return pages


def _read_page_meta(path, fallback_name):
    """Liest H1-Titel und die ersten paar H2-Subheadings einer Topic-Seite."""
    title = fallback_name
    subheadings = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if title == fallback_name and line.startswith("# "):
                    title = line[2:].strip()
                elif line.startswith("## "):
                    subheadings.append(line[3:].strip())
                    if len(subheadings) >= 4:
                        break
    except Exception:
        pass
    return title, subheadings


def _read_entity_meta(path, fallback_name):
    """Liest Frontmatter + Titel + Description-Zeile einer Entity-Seite."""
    title = fallback_name
    description = ""
    fm = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        fm, body = parse_frontmatter(content)
        title = fm.get("name", fallback_name)
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("*") and stripped.endswith("*") and len(stripped) > 2:
                description = stripped[1:-1].strip()
                break
    except Exception:
        pass
    return fm, title, description


def migrate_flat_wiki_to_topics():
    """
    Einmalige Migration: verschiebt .md-Dateien aus wiki/ nach wiki/topics/.
    Läuft idempotent — macht nichts wenn wiki/ bereits leer ist.
    """
    moved = []
    for f in os.listdir(WIKI_ROOT):
        full = os.path.join(WIKI_ROOT, f)
        if not os.path.isfile(full):
            continue
        if not f.endswith(".md"):
            continue
        if f in RESERVED_WIKI_FILES:
            continue
        target = os.path.join(TOPICS_DIR, f)
        if os.path.exists(target):
            logger.warning(f"Migration: {f} existiert bereits in topics/, überspringe.")
            continue
        try:
            shutil.move(full, target)
            moved.append(f)
        except Exception as e:
            logger.error(f"Migration-Fehler bei {f}: {e}")
    if moved:
        logger.info(f"Migration: {len(moved)} Datei(en) von wiki/ → wiki/topics/ verschoben: {moved}")
