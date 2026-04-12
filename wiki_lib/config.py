"""
config.py — Konfiguration, Logging und Verzeichnis-Konstanten.
Layer 0: keine wiki_lib-Imports.

Exports: config, DIRS, WIKI_ROOT, TOPICS_DIR, ENTITIES_DIR, DIAGNOSTICS_DIR, GLOBAL_RULES, API_KEY, logger
"""

import os
import json
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# --- Logging ---
LOG_FILE = "wiki_processor.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# --- API Key ---
load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY")
if not API_KEY:
    logger.critical("OPENROUTER_API_KEY fehlt in der .env Datei! Abbruch.")
    raise ValueError("OPENROUTER_API_KEY fehlt in der .env Datei!")

# --- config.json ---
try:
    with open("config.json", "r", encoding="utf-8") as _f:
        config = json.load(_f)
except Exception as _e:
    logger.critical(f"Fehler beim Laden der config.json: {_e}")
    raise

# --- Verzeichnisse ---
DIRS = config["directories"]
WIKI_ROOT = DIRS["wiki"]
TOPICS_DIR = os.path.join(WIKI_ROOT, "topics")
ENTITIES_DIR = os.path.join(WIKI_ROOT, "entities")
DIAGNOSTICS_DIR = DIRS.get("diagnostics", "./wiki_diagnostics")

for _path in (DIRS["raw"], DIRS["processed"], WIKI_ROOT, TOPICS_DIR, ENTITIES_DIR):
    os.makedirs(_path, exist_ok=True)

# --- Globale Wiki-Regeln ---
GLOBAL_RULES = ""
_rules_file = config.get("files", {}).get("system_rules", "./system_rules.md")
if os.path.exists(_rules_file):
    try:
        with open(_rules_file, "r", encoding="utf-8") as _f:
            GLOBAL_RULES = _f.read()
    except Exception as _e:
        logger.error(f"Konnte {_rules_file} nicht lesen: {_e}")
