"""
cli.py — CLI-Einstiegspunkte: validate, clean-structure, clean-semantic, main.
Layer 6: importiert aus allen Layern.

Exports: cli_validate, cli_clean_structure, cli_clean_semantic, main
"""

import sys
import os
import json
import argparse
from datetime import datetime
from collections import defaultdict

from .config import config, logger, WIKI_ROOT
from .linter import lint_all, fix_page
from .backup import _backup_file, _atomic_write
from .batch import process_batch
from .entities import refresh_entity_description
from .classifier import _sanitize_topic
from .pages import _page_file_path
from .openrouter import call_openrouter, _extract_json_object


# ============================================================================
# Helpers
# ============================================================================

def _group_issues_by_path(issues: list) -> dict:
    grouped: dict = defaultdict(list)
    for issue in issues:
        grouped[issue.path].append(issue)
    return grouped


def _abs_from_rel(rel_path: str) -> str:
    return os.path.join(WIKI_ROOT, rel_path)


def _kind_from_rel(rel_path: str) -> str:
    parts = rel_path.replace("\\", "/").split("/")
    return "entity" if parts[0] == "entities" else "topic"


# ============================================================================
# CLI Entry Points
# ============================================================================

def cli_validate():
    """--validate: Readonly-Lint. Exit 1 bei errors, Exit 0 wenn clean."""
    issues = lint_all()
    if not issues:
        print("✓ Keine Strukturprobleme gefunden.")
        sys.exit(0)

    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    for i in sorted(issues, key=lambda x: (x.path, x.severity)):
        marker = "✗" if i.severity == "error" else "⚠"
        fix_hint = " [fixable]" if i.fix_available else ""
        print(f"  {marker} [{i.severity.upper()}] {i.path}: {i.kind} — {i.detail}{fix_hint}")

    print(f"\n  {len(errors)} Fehler, {len(warnings)} Warnung(en).")
    sys.exit(1 if errors else 0)


def cli_clean_structure(dry_run: bool):
    """--clean-structure [--dry-run]: Fixes anwenden mit automatischem Backup."""
    issues = lint_all()
    fixable = [i for i in issues if i.fix_available]

    if not fixable:
        if not issues:
            print("✓ Keine Strukturprobleme gefunden.")
        else:
            print(f"⚠ {len(issues)} Issue(s), kein automatischer Fix verfügbar.")
            for i in issues:
                print(f"  {i.path}: {i.kind} — {i.detail}")
        return

    grouped = _group_issues_by_path(fixable)
    run_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    fixed_count = 0

    for rel_path in sorted(grouped):
        abs_path = _abs_from_rel(rel_path)
        if not os.path.exists(abs_path):
            logger.warning(f"Linter: {rel_path} nicht mehr auf Disk.")
            continue

        kind = _kind_from_rel(rel_path)
        new_content, applied = fix_page(abs_path, kind, grouped[rel_path])

        if new_content is None or not applied:
            continue

        with open(abs_path, "r", encoding="utf-8") as fh:
            old_content = fh.read()

        if new_content == old_content:
            continue  # idempotent — keine effektive Änderung

        if dry_run:
            print(f"  [DRY-RUN] {rel_path}: {applied}")
        else:
            _backup_file(abs_path, run_ts)
            _atomic_write(abs_path, new_content)
            print(f"  ✓ {rel_path}: {applied}")
            fixed_count += 1

    if not dry_run:
        if fixed_count:
            backup_root = config["directories"].get("backups", "./wiki_backups")
            print(f"\n  {fixed_count} Datei(en) bereinigt → Backup: {backup_root}/{run_ts}/")
        else:
            print("  ✓ Keine effektiven Änderungen nötig.")


def cli_clean_semantic(slug: str):
    """
    --clean-semantic <slug>: LLM-Qualitätsdiagnose für ein Topic oder Entity.
    Verändert NICHTS — gibt JSON auf stdout aus.
    """
    slug = _sanitize_topic(slug)
    if not slug:
        logger.error("Ungültiger Slug.")
        sys.exit(1)

    topic_path = _page_file_path(slug, "topic")
    entity_path = _page_file_path(slug, "entity")

    if os.path.exists(topic_path):
        abs_path, kind = topic_path, "topic"
    elif os.path.exists(entity_path):
        abs_path, kind = entity_path, "entity"
    else:
        logger.error(f"Seite '{slug}' nicht gefunden (weder topics/ noch entities/).")
        sys.exit(1)

    with open(abs_path, "r", encoding="utf-8") as fh:
        content = fh.read()

    system_prompt = """Du bist ein Wiki-Qualitätsanalyst. Analysiere die folgende Wiki-Seite.

Antworte AUSSCHLIESSLICH mit validem JSON ohne Fences:
{
  "summary": "1-2 Sätze Gesamtbewertung",
  "strengths": ["was gut ist"],
  "issues": [
    {"kind": "...", "description": "...", "severity": "error|warning|suggestion"}
  ],
  "suggestions": ["konkrete Verbesserungsvorschläge"]
}"""

    raw = call_openrouter(
        model=config["models"]["text_update"],
        messages=[{"role": "user", "content": f"Wiki-Seite ({kind}/{slug}.md):\n\n{content[:6000]}"}],
        system_prompt=system_prompt,
        max_tokens=1200,
    )

    if not raw:
        print(json.dumps({"error": "LLM lieferte keine Antwort"}, ensure_ascii=False, indent=2))
        sys.exit(1)

    data = _extract_json_object(raw)
    print(json.dumps(data if data else {"raw": raw}, ensure_ascii=False, indent=2))


# ============================================================================
# main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="LLM-Wiki Processor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python processor.py                             # Batch-Verarbeitung (Standard)
  python processor.py --validate                  # Strukturprüfung (readonly, exit 1 bei Fehlern)
  python processor.py --clean-structure           # Strukturprobleme automatisch fixen (mit Backup)
  python processor.py --clean-structure --dry-run # Vorschau ohne Änderungen
  python processor.py --clean-semantic rag        # LLM-Diagnose für topics/rag.md
  python processor.py --refresh-entity llama_3   # Entity-Description neu schreiben
        """,
    )
    parser.add_argument(
        "--refresh-entity",
        metavar="SLUG",
        help="Description einer bestehenden Entity neu schreiben lassen (mit Backup)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Strukturprüfung: readonly, exit 1 bei Fehlern",
    )
    parser.add_argument(
        "--clean-structure",
        action="store_true",
        help="Strukturprobleme automatisch fixen (erstellt Backup)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Zusammen mit --clean-structure: zeigt Änderungen ohne sie anzuwenden",
    )
    parser.add_argument(
        "--clean-semantic",
        metavar="SLUG",
        help="LLM-Qualitätsanalyse für eine Seite (readonly, gibt JSON aus)",
    )
    args = parser.parse_args()

    if args.validate:
        cli_validate()
        return

    if args.clean_structure:
        cli_clean_structure(dry_run=args.dry_run)
        return

    if args.clean_semantic:
        cli_clean_semantic(args.clean_semantic)
        return

    if args.refresh_entity:
        slug = _sanitize_topic(args.refresh_entity)
        if not slug:
            logger.error("Ungültiger Entity-Slug.")
            sys.exit(1)
        ok = refresh_entity_description(slug)
        sys.exit(0 if ok else 1)

    process_batch()
