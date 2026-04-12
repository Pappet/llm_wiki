"""
secondary.py — Deterministisches Appending an Sekundär-Topic-Seiten.
Layer 4: importiert aus Layer 0-2.

Exports: update_secondary_page_deterministic, SECONDARY_MENTIONS_HEADING
"""

import os
from datetime import datetime

from .config import logger
from .constants import SECONDARY_MENTIONS_HEADING
from .sections import parse_sections, reassemble_page, _slugify_heading, _make_section
from .pages import _page_file_path


def update_secondary_page_deterministic(secondary_page, references, existing_pages):
    if not references:
        return

    wiki_file = _page_file_path(secondary_page, "topic")
    today = datetime.now().strftime("%Y-%m-%d")
    entry_lines = [
        f"- [{today}] Im Kontext von [{r['from_page']}]({r['from_page']}.md): {r['context']}"
        for r in references
    ]
    entries_block = "\n".join(entry_lines) + "\n"

    if not os.path.exists(wiki_file):
        title = secondary_page.replace('_', ' ').title()
        content = (
            f"# {title}\n\n"
            f"*Querverweis-Ziel, wartet auf eigene Inhalte.*\n\n"
            f"{SECONDARY_MENTIONS_HEADING}\n\n{entries_block}"
        )
        try:
            tmp = wiki_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(content)
            os.rename(tmp, wiki_file)
            logger.info(f"✓ Sekundärer Stub: topics/{secondary_page}.md")
        except Exception as e:
            logger.error(f"Fehler: {e}")
        return

    try:
        with open(wiki_file, "r", encoding="utf-8") as f:
            existing = f.read()
    except Exception as e:
        logger.error(f"Kann {wiki_file} nicht lesen: {e}")
        return

    parsed = parse_sections(existing)
    mentions_slug = _slugify_heading(SECONDARY_MENTIONS_HEADING)
    found = False
    for i, s in enumerate(parsed['sections']):
        if s['slug'] == mentions_slug:
            new_body = s['body'].rstrip() + "\n" + entries_block
            if not new_body.endswith('\n\n'):
                new_body = new_body.rstrip() + '\n\n'
            parsed['sections'][i] = {
                'heading': s['heading'], 'slug': s['slug'],
                'body': new_body, 'original': s['heading'] + '\n' + new_body,
            }
            found = True
            break

    if not found:
        parsed['sections'].append(_make_section(SECONDARY_MENTIONS_HEADING, entries_block.rstrip()))

    new_content = reassemble_page(parsed['preamble'], parsed['sections'])

    try:
        tmp = wiki_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.rename(tmp, wiki_file)
        logger.info(f"✓ Sekundär-Append: topics/{secondary_page}.md (+{len(references)})")
    except Exception as e:
        logger.error(f"Fehler: {e}")
