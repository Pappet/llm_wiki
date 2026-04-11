"""
logbook.py — Wiki-Index-Generierung und Append-Only-Log.
Layer 2: importiert aus Layer 0 (config, constants) und Layer 2 (pages).

Exports: generate_index_file, append_log_entries, _log_entry
"""

import os
from datetime import datetime
from collections import defaultdict

from .config import WIKI_ROOT, logger
from .constants import RESERVED_WIKI_FILES
from .pages import get_existing_wiki_pages


def generate_index_file():
    pages = get_existing_wiki_pages()
    if not pages:
        return
    topics = sorted([p for p in pages if p["kind"] == "topic"], key=lambda p: p["name"])
    entities = sorted(
        [p for p in pages if p["kind"] == "entity"],
        key=lambda p: (p.get("type", ""), p["name"]),
    )

    lines = ["# 📚 Wiki Index\n"]
    if topics:
        lines.append("\n## Topics\n")
        for p in topics:
            lines.append(f"- [{p['title']}](topics/{p['name']}.md)")
    if entities:
        lines.append("\n## Entities\n")
        by_type = defaultdict(list)
        for p in entities:
            by_type[p.get("type", "concept")].append(p)
        for etype in sorted(by_type.keys()):
            lines.append(f"\n### {etype.title()}\n")
            for p in by_type[etype]:
                desc = f" — *{p['description']}*" if p.get("description") else ""
                lines.append(f"- [{p['title']}](entities/{p['name']}.md){desc}")
    lines.append("")

    try:
        with open(os.path.join(WIKI_ROOT, "index.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        logger.info("index.md aktualisiert.")
    except Exception as e:
        logger.error(f"Fehler beim Generieren der index.md: {e}")


def append_log_entries(entries):
    if not entries:
        return
    log_path = os.path.join(WIKI_ROOT, "log.md")
    is_new = (not os.path.exists(log_path)) or os.path.getsize(log_path) == 0
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            if is_new:
                f.write("# Wiki Log\n\nChronologisches Append-Only-Log aller Aktionen.\n\n")
            for e in entries:
                f.write(e.rstrip() + "\n")
    except Exception as e:
        logger.error(f"Fehler beim Schreiben von log.md: {e}")


def _log_entry(action, details):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"## [{ts}] {action} | {details}"
