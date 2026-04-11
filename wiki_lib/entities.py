"""
entities.py — Entity-Seiten-Verwaltung: Erstellen, Backlink-Append, Description-Refresh.
Layer 4: importiert aus Layer 0-3.

Exports: _ensure_entity_page, _format_backlink_line, _append_entity_backlink,
         refresh_entity_description
"""

import os
import re
import shutil
from datetime import datetime

from .config import config, logger, ENTITIES_DIR
from .constants import MENTIONS_HEADING, DESCRIPTION_MAX_CHARS
from .frontmatter import parse_frontmatter, serialize_frontmatter
from .sections import parse_sections, reassemble_page, _slugify_heading, _make_section
from .pages import _page_file_path
from .openrouter import call_openrouter
from .logbook import append_log_entries, _log_entry


def _format_backlink_line(date, backlink):
    """Formatiert eine einzelne Backlink-Zeile."""
    role = backlink.get("role", "mentioned")
    from_slug = backlink["from_slug"]
    from_title = backlink.get("from_title", from_slug.replace("_", " ").title())
    context = backlink.get("context", "").strip()
    link = f"[{from_title}](../topics/{from_slug}.md)"
    if context:
        return f"- [{date}] {role} in {link}: {context}"
    return f"- [{date}] {role} in {link}"


def _ensure_entity_page(entity, first_backlink):
    """
    Stellt sicher dass die Entity-Seite existiert. Erstellt sie bei Bedarf.
    first_backlink: dict {from_slug, role, context}
    Returns: True wenn neu angelegt.
    """
    path = _page_file_path(entity["slug"], "entity")
    if os.path.exists(path):
        return False

    today = datetime.now().strftime("%Y-%m-%d")
    name = entity.get("name", entity["slug"])
    description = entity.get("description", "") or ""

    fm = {
        "type": entity["type"],
        "name": name,
        "aliases": [],
        "first_seen": today,
        "last_updated": today,
        "mention_count": 1,
    }

    body_lines = [f"# {name}", ""]
    if description:
        body_lines.append(f"*{description}*")
        body_lines.append("")
    body_lines.append(MENTIONS_HEADING)
    body_lines.append("")
    body_lines.append(_format_backlink_line(today, first_backlink))
    body_lines.append("")

    content = serialize_frontmatter(fm, "\n".join(body_lines))

    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.rename(tmp, path)
        logger.info(f"✓ Entity-Seite erstellt: {entity['slug']}.md ({entity['type']})")
        return True
    except Exception as e:
        logger.error(f"Fehler beim Erstellen der Entity-Seite {entity['slug']}: {e}")
        return False


def _append_entity_backlink(entity_slug, backlink):
    """
    Appendet eine Backlink-Zeile an die Entity-Seite. Deterministisch, kein LLM.
    Updated gleichzeitig mention_count und last_updated im Frontmatter.
    """
    path = _page_file_path(entity_slug, "entity")
    if not os.path.exists(path):
        logger.error(f"Entity-Seite {entity_slug}.md existiert nicht — kann nicht appenden.")
        return False

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Kann {path} nicht lesen: {e}")
        return False

    fm, body = parse_frontmatter(content)
    parsed = parse_sections(body)

    today = datetime.now().strftime("%Y-%m-%d")
    new_line = _format_backlink_line(today, backlink)

    mentions_slug = _slugify_heading(MENTIONS_HEADING)
    found = False
    for i, s in enumerate(parsed['sections']):
        if s['slug'] == mentions_slug:
            new_body = s['body'].rstrip() + "\n" + new_line + "\n"
            if not new_body.endswith('\n\n'):
                new_body = new_body.rstrip() + '\n\n'
            parsed['sections'][i] = {
                'heading': s['heading'],
                'slug': s['slug'],
                'body': new_body,
                'original': s['heading'] + '\n' + new_body,
            }
            found = True
            break

    if not found:
        parsed['sections'].append(_make_section(MENTIONS_HEADING, new_line))

    new_body_full = reassemble_page(parsed['preamble'], parsed['sections'])

    fm["last_updated"] = today
    fm["mention_count"] = fm.get("mention_count", 0) + 1

    new_content = serialize_frontmatter(fm, new_body_full)

    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.rename(tmp, path)
        logger.info(f"✓ Entity-Backlink: {entity_slug} (+1 mention, jetzt {fm['mention_count']})")
        return True
    except Exception as e:
        logger.error(f"Fehler beim Entity-Append {entity_slug}: {e}")
        return False


def refresh_entity_description(entity_slug):
    """
    CLI-Pfad: holt alle Backlinks der Entity, lädt die erwähnten Topic-Sektionen,
    und lässt das LLM eine neue Description schreiben. Body (Backlinks) unverändert.
    """
    path = _page_file_path(entity_slug, "entity")
    if not os.path.exists(path):
        logger.error(f"Entity-Seite {entity_slug}.md existiert nicht.")
        return False

    backup_path = path + ".bak"
    try:
        shutil.copy2(path, backup_path)
        logger.info(f"Backup erstellt: {backup_path}")
    except Exception as e:
        logger.error(f"Backup fehlgeschlagen: {e}")
        return False

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    fm, body = parse_frontmatter(content)
    parsed = parse_sections(body)

    backlink_refs = []
    mentions_slug = _slugify_heading(MENTIONS_HEADING)
    for s in parsed['sections']:
        if s['slug'] == mentions_slug:
            for line in s['body'].splitlines():
                m = re.search(r'\[([^\]]+)\]\(\.\./topics/([^)]+)\.md\)', line)
                if m:
                    backlink_refs.append(m.group(2))
            break

    if not backlink_refs:
        logger.warning(f"Entity {entity_slug} hat keine Backlinks — refresh sinnlos.")
        return False

    entity_name = fm.get("name", entity_slug)
    aliases = fm.get("aliases", []) or []
    search_terms = (
        [entity_name.lower()]
        + [a.lower() for a in aliases]
        + [entity_slug.replace("_", " ").lower()]
    )

    context_blocks = []
    seen_topics = set()
    for topic_slug in backlink_refs:
        if topic_slug in seen_topics:
            continue
        seen_topics.add(topic_slug)
        from .pages import _page_file_path as _pfp
        topic_path = _pfp(topic_slug, "topic")
        if not os.path.exists(topic_path):
            continue
        try:
            with open(topic_path, "r", encoding="utf-8") as f:
                topic_content = f.read()
        except Exception:
            continue

        topic_parsed = parse_sections(topic_content)
        relevant_sections = []
        for s in topic_parsed['sections']:
            body_lower = s['body'].lower()
            if any(term in body_lower for term in search_terms):
                relevant_sections.append(s)

        if not relevant_sections:
            full_body = (
                topic_parsed['preamble']
                + ''.join(s['original'] for s in topic_parsed['sections'])
            )[:2000]
            context_blocks.append(f"### Aus [{topic_slug}]\n{full_body}")
        else:
            for s in relevant_sections:
                context_blocks.append(f"### Aus [{topic_slug}] / {s['heading']}\n{s['body'][:2000]}")

    if not context_blocks:
        logger.warning(f"Keine relevanten Sektionen gefunden für {entity_slug}.")
        return False

    context_str = "\n\n".join(context_blocks)

    system_prompt = f"""Du schreibst die Kurzbeschreibung für eine Wiki-Entity neu.
Name der Entity: {entity_name}
Typ: {fm.get('type', 'concept')}

Du bekommst als Kontext alle Wiki-Sektionen, in denen diese Entity erwähnt wird.
Deine Aufgabe: eine kompakte, präzise Beschreibung in 1-3 Sätzen (max {DESCRIPTION_MAX_CHARS} Zeichen).

REGELN:
1. Antworte NUR mit der Beschreibung. Keine Überschrift, keine Fences, keine Erklärung.
2. Keine Meta-Kommentare wie "Diese Entity ist...".
3. Faktisch, knapp, neutral.
4. Die Beschreibung soll erklären WAS die Entity ist, nicht wie sie erwähnt wurde."""

    user_content = f"Kontext aus dem Wiki:\n\n{context_str}\n\nSchreibe jetzt die Kurzbeschreibung."

    model = config["models"]["text_update"]
    raw = call_openrouter(
        model=model,
        messages=[{"role": "user", "content": user_content}],
        system_prompt=system_prompt,
        max_tokens=400,
    )

    if not raw:
        logger.error(f"LLM lieferte keine Response für {entity_slug}. Backup bleibt, Datei unverändert.")
        return False

    new_desc = raw.strip()
    new_desc = re.sub(r'^```[a-zA-Z]*\n?', '', new_desc)
    new_desc = re.sub(r'\n?```\s*$', '', new_desc).strip()
    new_desc = new_desc.strip('*').strip()
    new_desc = new_desc[:DESCRIPTION_MAX_CHARS]

    if not new_desc:
        logger.error("Neue Description ist leer. Abbruch.")
        return False

    new_preamble_lines = [f"# {entity_name}", "", f"*{new_desc}*", ""]
    new_preamble = "\n".join(new_preamble_lines) + "\n"

    new_body_full = new_preamble + ''.join(s['original'] for s in parsed['sections'])

    today = datetime.now().strftime("%Y-%m-%d")
    fm["last_updated"] = today
    new_content = serialize_frontmatter(fm, new_body_full)

    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.rename(tmp, path)
        logger.info(f"✓ Entity {entity_slug} refreshed (Backup: {os.path.basename(backup_path)})")
        append_log_entries([_log_entry("entity_refresh", f"{entity_slug} | neue Description: '{new_desc[:80]}...'")])
        return True
    except Exception as e:
        logger.error(f"Fehler beim Schreiben von {entity_slug} nach Refresh: {e}")
        return False
