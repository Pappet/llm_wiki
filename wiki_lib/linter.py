"""
linter.py — Strukturlinter und automatische Fix-Funktionen für Wiki-Seiten.
Layer 3: importiert aus Layer 0-2.

Bug 1 fix: _fix_missing_h1 — korrekte Trennung "\n" nach Frontmatter-Ende.
Bug 3 fix: Drei-Phasen-Lint — _lint_phase1 (fence+ws), _lint_phase1_5 (H1 via Regex),
           _lint_phase2 (section-Parser-abhängig, skipped bei unclosed_fence).

Exports: Issue, lint_page, lint_all, fix_page,
         _check_fence_parity, _lint_phase1, _lint_phase1_5, _lint_phase2,
         _fix_trailing_whitespace, _fix_unclosed_fence, _fix_excessive_blanks,
         _fix_missing_h1, _fix_multi_h1, _fix_duplicate_sections,
         _fix_empty_mentions, _fix_frontmatter_drift, _FIX_ORDER
"""

import os
import re
from dataclasses import dataclass
from collections import defaultdict

from .config import WIKI_ROOT, TOPICS_DIR, ENTITIES_DIR, logger
from .constants import RESERVED_WIKI_FILES, MENTIONS_HEADING
from .frontmatter import parse_frontmatter, serialize_frontmatter
from .sections import (
    parse_sections, reassemble_page, _slugify_heading,
    _split_fm_body, _body_without_frontmatter,
)


# ============================================================================
# Issue Dataclass
# ============================================================================

@dataclass
class Issue:
    path: str          # relativer Pfad ab wiki/
    kind: str          # "multi_h1" | "missing_h1" | "unclosed_fence" |
                       # "excessive_blank_lines" | "trailing_whitespace" |
                       # "duplicate_section" | "empty_mentions" |
                       # "frontmatter_drift"
    severity: str      # "error" | "warning"
    detail: str        # human-readable
    fix_available: bool


# ============================================================================
# Phase Pre / Phase 1: Fence-Parität + Trailing Whitespace
# ============================================================================

def _check_fence_parity(content: str):
    """Returns (is_odd, count). True wenn ungerade Anzahl ``` Marker."""
    count = len(re.findall(r'^```', content, re.MULTILINE))
    return (count % 2 != 0), count


def _lint_phase1(rel_path: str, content: str) -> list:
    """Fence-Parität und Trailing Whitespace — läuft immer, kein Parser."""
    issues = []

    is_odd, count = _check_fence_parity(content)
    if is_odd:
        issues.append(Issue(
            path=rel_path,
            kind="unclosed_fence",
            severity="error",
            detail=f"{count} Fence-Marker (ungerade — ein Block ist nicht geschlossen)",
            fix_available=True,
        ))

    trailing_lines = [i + 1 for i, ln in enumerate(content.splitlines()) if ln != ln.rstrip()]
    if trailing_lines:
        sample = trailing_lines[:5]
        issues.append(Issue(
            path=rel_path,
            kind="trailing_whitespace",
            severity="warning",
            detail=f"Trailing Whitespace in {len(trailing_lines)} Zeile(n), z.B. {sample}",
            fix_available=True,
        ))

    return issues


# ============================================================================
# Phase 1.5: H1-Checks via Regex (parser-unabhängig, läuft auch bei unclosed_fence)
# ============================================================================

def _lint_phase1_5(rel_path: str, content: str) -> list:
    """missing_h1 und multi_h1 per Regex — unabhängig vom Section-Parser."""
    issues = []
    body = _body_without_frontmatter(content)

    h1_matches = re.findall(r'^# [^#\n].+', body, re.MULTILINE)
    if not h1_matches:
        issues.append(Issue(
            path=rel_path,
            kind="missing_h1",
            severity="error",
            detail="Kein H1-Titel vorhanden",
            fix_available=True,
        ))
    elif len(h1_matches) > 1:
        issues.append(Issue(
            path=rel_path,
            kind="multi_h1",
            severity="error",
            detail=f"{len(h1_matches)} H1-Überschriften — nur eine erlaubt",
            fix_available=True,
        ))

    return issues


# ============================================================================
# Phase 2: Parser-abhängige Checks (wird bei unclosed_fence übersprungen)
# ============================================================================

def _lint_phase2(rel_path: str, content: str, kind: str) -> list:
    """Duplicate sections, empty mentions, frontmatter drift — braucht funktionierenden Parser."""
    issues = []
    body = _body_without_frontmatter(content)

    # Excessive blank lines (3+ consecutive = \n\n\n\n in file)
    if re.search(r'\n{4,}', body):
        count = len(re.findall(r'\n{4,}', body))
        issues.append(Issue(
            path=rel_path,
            kind="excessive_blank_lines",
            severity="warning",
            detail=f"{count} Stelle(n) mit 3+ aufeinanderfolgenden Leerzeilen",
            fix_available=True,
        ))

    # Duplicate H2 sections
    parsed = parse_sections(body)
    slugs = [s['slug'] for s in parsed['sections']]
    seen: set = set()
    dupes: set = set()
    for slug in slugs:
        if slug in seen:
            dupes.add(slug)
        seen.add(slug)
    if dupes:
        issues.append(Issue(
            path=rel_path,
            kind="duplicate_section",
            severity="error",
            detail=f"Doppelte H2-Sektionen: {sorted(dupes)}",
            fix_available=True,
        ))

    # Empty mentions sections
    empty_headings = []
    for s in parsed['sections']:
        heading_norm = s['heading'].lstrip('#').strip().lower()
        if heading_norm in ("erwähnt in", "erwähnungen"):
            if not s['body'].strip():
                empty_headings.append(s['heading'].strip())
    if empty_headings:
        issues.append(Issue(
            path=rel_path,
            kind="empty_mentions",
            severity="warning",
            detail=f"Leere Mentions-Sektion(en): {empty_headings}",
            fix_available=True,
        ))

    # Frontmatter drift (entities only)
    if kind == "entity" and content.startswith("---"):
        fm, _ = parse_frontmatter(content)
        fm_count = fm.get("mention_count", 0)
        actual_count = 0
        mentions_slug_target = _slugify_heading(MENTIONS_HEADING)
        for s in parsed['sections']:
            if s['slug'] == mentions_slug_target:
                actual_count = sum(
                    1 for ln in s['body'].splitlines()
                    if re.match(r'^\s*-\s*\[\d{4}-\d{2}-\d{2}\]', ln)
                )
                break
        if fm_count != actual_count:
            issues.append(Issue(
                path=rel_path,
                kind="frontmatter_drift",
                severity="warning",
                detail=f"mention_count={fm_count} im Frontmatter, {actual_count} Backlink-Zeile(n) gezählt",
                fix_available=True,
            ))

    return issues


# ============================================================================
# Public lint entry points
# ============================================================================

def lint_page(abs_path: str, kind: str) -> list:
    """
    Lintet eine einzelne Seite. Drei Phasen:
    - Phase 1:   fence + whitespace (immer)
    - Phase 1.5: H1-Checks via Regex (immer, parser-unabhängig)
    - Phase 2:   section-Parser-Checks (nur wenn kein unclosed_fence)
    """
    try:
        with open(abs_path, "r", encoding="utf-8") as fh:
            content = fh.read()
    except Exception as e:
        return [Issue(
            path=abs_path,
            kind="unclosed_fence",
            severity="error",
            detail=f"Datei nicht lesbar: {e}",
            fix_available=False,
        )]

    rel_path = os.path.relpath(abs_path, WIKI_ROOT)
    p1  = _lint_phase1(rel_path, content)
    p15 = _lint_phase1_5(rel_path, content)  # läuft IMMER, parser-unabhängig

    if any(i.kind == "unclosed_fence" for i in p1):
        return p1 + p15  # Parser-abhängige Phase skippen

    return p1 + p15 + _lint_phase2(rel_path, content, kind)


def lint_all() -> list:
    """Lintet alle Seiten in topics/ und entities/. Returns list[Issue]."""
    issues = []

    if os.path.isdir(TOPICS_DIR):
        for f in sorted(os.listdir(TOPICS_DIR)):
            if not f.endswith(".md") or f in RESERVED_WIKI_FILES:
                continue
            issues.extend(lint_page(os.path.join(TOPICS_DIR, f), "topic"))

    if os.path.isdir(ENTITIES_DIR):
        for f in sorted(os.listdir(ENTITIES_DIR)):
            if not f.endswith(".md"):
                continue
            issues.extend(lint_page(os.path.join(ENTITIES_DIR, f), "entity"))

    return issues


# ============================================================================
# Fix-Funktionen (alle idempotent, string-in / string-out)
# ============================================================================

def _fix_trailing_whitespace(content: str) -> str:
    lines = content.splitlines()
    result = "\n".join(ln.rstrip() for ln in lines)
    if content.endswith("\n"):
        result += "\n"
    return result


def _fix_unclosed_fence(content: str) -> str:
    """Fügt einen schließenden ``` ans Ende an wenn Anzahl ungerade."""
    is_odd, _ = _check_fence_parity(content)
    if not is_odd:
        return content
    if not content.endswith("\n"):
        content += "\n"
    return content + "```\n"


def _fix_excessive_blanks(content: str) -> str:
    """Reduziert 3+ aufeinanderfolgende Leerzeilen auf 2."""
    return re.sub(r'\n{4,}', '\n\n\n', content)


def _fix_missing_h1(content: str, abs_path: str) -> str:
    """
    Fügt H1 aus Dateiname ein, direkt nach Frontmatter (oder am Dateianfang).
    Bug 1 fix: after_fm kann mit 0, 1, 2+ Newlines starten — normalisieren
    auf genau eine Leerzeile vor dem H1-Block.
    """
    slug = os.path.splitext(os.path.basename(abs_path))[0]
    title = slug.replace("_", " ").title()
    h1_block = f"# {title}\n\n"

    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end > 0:
            after_fm = content[end + 4:]
            if re.search(r'^# [^#\n]', after_fm, re.MULTILINE):
                return content  # bereits vorhanden
            body_trimmed = after_fm.lstrip("\n")
            return content[:end + 4] + "\n" + h1_block + body_trimmed

    if re.search(r'^# [^#\n]', content, re.MULTILINE):
        return content
    return h1_block + content.lstrip("\n")


def _fix_multi_h1(content: str) -> str:
    """Konvertiert alle H1 außer dem ersten zu H2."""
    lines = content.splitlines(keepends=True)
    first_seen = False
    result = []
    for line in lines:
        if re.match(r'^# [^#]', line):
            if not first_seen:
                first_seen = True
                result.append(line)
            else:
                result.append("## " + line[2:])
        else:
            result.append(line)
    return "".join(result)


def _fix_duplicate_sections(content: str) -> str:
    """
    Merged doppelte H2-Sektionen: Bodies konkateniert in Reihenfolge,
    erster Header gewinnt.
    """
    fm_prefix, body = _split_fm_body(content)
    parsed = parse_sections(body)

    first_occurrence: dict = {}
    to_remove = []

    for i, s in enumerate(parsed['sections']):
        slug = s['slug']
        if slug not in first_occurrence:
            first_occurrence[slug] = i
        else:
            fi = first_occurrence[slug]
            merged_body = (
                parsed['sections'][fi]['body'].rstrip('\n') + '\n\n'
                + parsed['sections'][i]['body']
            )
            h = parsed['sections'][fi]['heading']
            parsed['sections'][fi] = {
                'heading': h, 'slug': slug,
                'body': merged_body,
                'original': h + '\n' + merged_body,
            }
            to_remove.append(i)

    parsed['sections'] = [s for i, s in enumerate(parsed['sections']) if i not in to_remove]
    new_body = reassemble_page(parsed['preamble'], parsed['sections'])
    return fm_prefix + new_body


def _fix_empty_mentions(content: str) -> str:
    """Entfernt leere ## Erwähnungen / ## Erwähnt in Sektionen."""
    fm_prefix, body = _split_fm_body(content)
    parsed = parse_sections(body)

    filtered = [
        s for s in parsed['sections']
        if not (
            s['heading'].lstrip('#').strip().lower() in ("erwähnt in", "erwähnungen")
            and not s['body'].strip()
        )
    ]
    parsed['sections'] = filtered
    new_body = reassemble_page(parsed['preamble'], parsed['sections'])
    return fm_prefix + new_body


def _fix_frontmatter_drift(content: str) -> str:
    """Korrigiert mention_count im Frontmatter anhand tatsächlicher Backlink-Zeilen."""
    if not content.startswith("---"):
        return content
    if content.find("\n---", 3) < 0:
        return content

    fm, body = parse_frontmatter(content)
    parsed = parse_sections(body)

    actual_count = 0
    target_slug = _slugify_heading(MENTIONS_HEADING)
    for s in parsed['sections']:
        if s['slug'] == target_slug:
            actual_count = sum(
                1 for ln in s['body'].splitlines()
                if re.match(r'^\s*-\s*\[\d{4}-\d{2}-\d{2}\]', ln)
            )
            break

    fm["mention_count"] = actual_count
    return serialize_frontmatter(fm, body)


# ============================================================================
# fix_page orchestrator
# ============================================================================

# Reihenfolge ist semantisch fix — Änderung hat Konsequenzen
_FIX_ORDER = [
    "trailing_whitespace",
    "unclosed_fence",
    "excessive_blank_lines",
    "missing_h1",
    "multi_h1",
    "duplicate_section",
    "empty_mentions",
    "frontmatter_drift",
]


def fix_page(abs_path: str, kind: str, issues: list):
    """
    Wendet alle verfügbaren Fixes für die gegebenen Issues an.
    Returns: (new_content: str | None, applied_fixes: list[str])
    Schreibt NICHT auf Disk — Caller macht Backup + Schreiben.
    """
    try:
        with open(abs_path, "r", encoding="utf-8") as fh:
            content = fh.read()
    except Exception as e:
        return None, [f"LESEFEHLER: {e}"]

    issue_kinds = {i.kind for i in issues if i.fix_available}
    applied = []

    for fix_kind in _FIX_ORDER:
        if fix_kind not in issue_kinds:
            continue
        if fix_kind == "trailing_whitespace":
            content = _fix_trailing_whitespace(content)
        elif fix_kind == "unclosed_fence":
            content = _fix_unclosed_fence(content)
        elif fix_kind == "excessive_blank_lines":
            content = _fix_excessive_blanks(content)
        elif fix_kind == "missing_h1":
            content = _fix_missing_h1(content, abs_path)
        elif fix_kind == "multi_h1":
            content = _fix_multi_h1(content)
        elif fix_kind == "duplicate_section":
            content = _fix_duplicate_sections(content)
        elif fix_kind == "empty_mentions":
            content = _fix_empty_mentions(content)
        elif fix_kind == "frontmatter_drift":
            content = _fix_frontmatter_drift(content)
        applied.append(fix_kind)

    return content, applied
