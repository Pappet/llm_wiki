"""
backup.py — Backup-Helfer und atomares Schreiben.
Layer 1: importiert nur aus Layer 0 (config).

Exports: _make_backup_path, _backup_file, _atomic_write
"""

import os
import shutil

from .config import config, WIKI_ROOT, logger


def _make_backup_path(run_timestamp: str, rel_path: str) -> str:
    backup_root = config["directories"].get("backups", "./wiki_backups")
    return os.path.join(backup_root, run_timestamp, rel_path)


def _backup_file(src_abs: str, run_timestamp: str) -> str:
    """Erstellt Backup unter backups/<timestamp>/<rel_path>. Lazy mkdir."""
    rel = os.path.relpath(src_abs, WIKI_ROOT)
    dst = _make_backup_path(run_timestamp, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src_abs, dst)
    return dst


def _atomic_write(path: str, content: str) -> None:
    """Schreibt content atomar via .tmp → rename."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(content)
    os.rename(tmp, path)
