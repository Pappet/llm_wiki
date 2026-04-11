"""
sections.py — Markdown-Section-Parser und verwandte String-Helpers.
Layer 2: importiert aus Layer 0 (config).

Exports: _slugify_heading, parse_sections, reassemble_page, _make_section,
         _load_or_init_page, _body_without_frontmatter, _split_fm_body
"""

import os
import re

from .config import logger


def _slugify_heading(heading_line):
    text = heading_line.lstrip('#').strip().lower()
    text = re.sub(r'[^\w\s-]', '', text, flags=re.UNICODE)
    text = re.sub(r'[\s-]+', '_', text).strip('_')
    return text or "_unnamed"


def parse_sections(content):
    if not content:
        return {'preamble': '', 'sections': []}
    lines = content.splitlines(keepends=True)
    preamble_lines = []
    sections = []
    current_heading_line = None
    current_body_lines = []
    in_fence = False

    def flush():
        nonlocal current_heading_line, current_body_lines
        if current_heading_line is not None:
            body = ''.join(current_body_lines)
            sections.append({
                'heading': current_heading_line.rstrip('\n'),
                'slug': _slugify_heading(current_heading_line),
                'body': body,
                'original': current_heading_line + body,
            })
        current_heading_line = None
        current_body_lines = []

    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        is_h2 = (not in_fence) and line.startswith("## ") and not line.startswith("### ")
        if is_h2:
            flush()
            current_heading_line = line
        elif current_heading_line is None:
            preamble_lines.append(line)
        else:
            current_body_lines.append(line)
    flush()
    return {'preamble': ''.join(preamble_lines), 'sections': sections}


def reassemble_page(preamble, sections):
    return preamble + ''.join(s['original'] for s in sections)


def _make_section(heading_line, body_text):
    heading_clean = heading_line.rstrip('\n')
    if not heading_clean.startswith("## "):
        heading_clean = "## " + heading_clean.lstrip("#").strip()
    body_clean = body_text.strip() + '\n\n'
    return {
        'heading': heading_clean,
        'slug': _slugify_heading(heading_clean),
        'body': body_clean,
        'original': heading_clean + '\n' + body_clean,
    }


def _load_or_init_page(wiki_file, topic):
    if os.path.exists(wiki_file):
        try:
            with open(wiki_file, "r", encoding="utf-8") as f:
                content = f.read()
            return parse_sections(content), False
        except Exception as e:
            logger.error(f"Konnte {wiki_file} nicht lesen: {e}")
            return {'preamble': '', 'sections': []}, True
    else:
        title = topic.replace('_', ' ').title()
        return {'preamble': f'# {title}\n\n', 'sections': []}, True


def _body_without_frontmatter(content: str) -> str:
    """Gibt den Body-Teil zurück (nach Frontmatter, falls vorhanden)."""
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end > 0:
            body = content[end + 4:]
            return body[1:] if body.startswith("\n") else body
    return content


def _split_fm_body(content: str):
    """
    Returns (fm_prefix, body).
    fm_prefix ist genau der Frontmatter-Block inkl. schließendem --- ohne
    zusätzliche Trailing-Newlines. body ist der exakte Rest (beginnt mit \n).
    Invariante: fm_prefix + body == content.
    """
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end > 0:
            fm_prefix = content[:end + 4]   # bis einschließlich "\n---"
            body = content[end + 4:]         # alles danach, unverändert
            return fm_prefix, body
    return "", content
