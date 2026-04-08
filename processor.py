import os
import json
import shutil
import base64
import logging
import re
import difflib
import requests
from logging.handlers import RotatingFileHandler
from collections import defaultdict
from dotenv import load_dotenv

# --- LOGGING SETUP ---
LOG_FILE = "wiki_processor.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logger.info("Starte Wiki-Prozessor...")

# Lade Umgebungsvariablen und Config
load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY")

if not API_KEY:
    logger.critical("OPENROUTER_API_KEY fehlt in der .env Datei! Abbruch.")
    raise ValueError("OPENROUTER_API_KEY fehlt in der .env Datei!")

try:
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    logger.info("config.json erfolgreich geladen.")
except Exception as e:
    logger.critical(f"Fehler beim Laden der config.json: {e}")
    raise

# Ordnerstruktur sicherstellen
DIRS = config["directories"]
for name, path in DIRS.items():
    os.makedirs(path, exist_ok=True)
    logger.debug(f"Ordner verifiziert: {path}")

# Globale Regeln laden
GLOBAL_RULES = ""
rules_file = config.get("files", {}).get("system_rules", "./system_rules.md")
if os.path.exists(rules_file):
    try:
        with open(rules_file, "r", encoding="utf-8") as f:
            GLOBAL_RULES = f.read()
        logger.info(f"Zentrale Wiki-Regeln aus '{rules_file}' geladen.")
    except Exception as e:
        logger.error(f"Konnte {rules_file} nicht lesen: {e}")
else:
    logger.warning(f"Keine globale Regeldatei gefunden unter '{rules_file}'. Mache ohne weiter.")

def get_existing_wiki_pages():
    """Gibt eine Liste von Dicts {name, title} aller existierenden Wiki-Seiten zurück."""
    wiki_dir = DIRS["wiki"]
    if not os.path.exists(wiki_dir):
        return []
    pages = []
    for f in os.listdir(wiki_dir):
        if not f.endswith(".md") or f == "index.md":
            continue
        name = f[:-3]
        title = name
        subheadings = []
        try:
            with open(os.path.join(wiki_dir, f), "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not title or title == name:
                        if line.startswith("# "):
                            title = line[2:].strip()
                    elif line.startswith("## "):
                        subheadings.append(line[3:].strip())
                        if len(subheadings) >= 4:
                            break
        except Exception:
            pass
        pages.append({"name": name, "title": title, "subheadings": subheadings})
    return pages

def generate_index_file():
    """Erstellt eine index.md mit Links zu allen existierenden Wiki-Seiten."""
    wiki_dir = DIRS["wiki"]
    pages = get_existing_wiki_pages()
    
    if not pages:
        return
        
    pages.sort(key=lambda p: p["name"])
    index_path = os.path.join(wiki_dir, "index.md")

    content = "# 📚 Wiki Index\n\nAutomatisch generierte Übersicht aller verfügbaren Themen-Seiten:\n\n"
    for page in pages:
        content += f"- [{page['title']}]({page['name']}.md)\n"
        
    try:
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("Wiki-Index (index.md) wurde erfolgreich generiert/aktualisiert.")
    except Exception as e:
        logger.error(f"Fehler beim Generieren der index.md: {e}")

def call_openrouter(model, messages, system_prompt=None):
    """
    Robuste API-Kommunikation mit OpenRouter via requests.
    """
    base_url = config["openrouter_url"].rstrip("/")
    url = f"{base_url}/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/llm-wiki",
        "X-Title": "LLM Wiki Bot"
    }

    api_messages = []
    if system_prompt:
        api_messages.append({"role": "system", "content": system_prompt})
    
    if isinstance(messages, list) and len(messages) > 0 and isinstance(messages[0], dict) and "role" in messages[0]:
        api_messages.extend(messages)
    else:
        api_messages.append({"role": "user", "content": messages})

    payload = {
        "model": model,
        "messages": api_messages,
        "temperature": 0.3,
        "max_tokens": 2000
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Fehler bei OpenRouter ({resp.status_code}): {resp.text[:500]}")
            return None

        try:
            data = resp.json()
        except ValueError:
            logger.error(f"OpenRouter lieferte kein valides JSON (Status {resp.status_code}). Raw Response: '{resp.text[:500]}'")
            return None

        if "error" in data:
            logger.error(f"OpenRouter Fehler: {data['error']}")
            return None

        choices = data.get("choices")
        if not choices:
            logger.error(f"Unerwartetes JSON-Format (keine 'choices'): {data}")
            return None

        content = choices[0].get("message", {}).get("content")
        
        if content is None:
            refusal = choices[0].get("message", {}).get("refusal")
            if refusal:
                logger.warning(f"Modell {model} hat die Antwort verweigert: {refusal}")
            else:
                logger.warning(f"Modell {model} hat 'None' als Content geliefert.")
            return None

        return content.strip()

    except requests.exceptions.Timeout:
        logger.error(f"Timeout bei OpenRouter für Modell {model}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Netzwerk- oder Request-Fehler bei OpenRouter: {e}")
        return None
    except Exception as e:
        logger.error(f"Unerwarteter Fehler in call_openrouter: {e}", exc_info=True)
        return None

def encode_image(image_path):
    """Liest ein Bild und wandelt es in Base64 um."""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Fehler beim Kodieren des Bildes {image_path}: {e}")
        raise

def _build_classification_excerpt(text):
    """Extrahiert URL, Titel und Inhaltsanfang für die Klassifizierung."""
    source_url = None
    doc_title = None
    body = text

    # Frontmatter parsen (---\nQuelle: ...\n---)
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            for line in text[3:end].splitlines():
                if line.lower().startswith("quelle:"):
                    source_url = line[7:].strip()
            body = text[end + 3:].strip()

    # Ersten H1-Titel aus dem Body extrahieren
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            doc_title = stripped[2:].strip()
            break

    parts = []
    if source_url:
        parts.append(f"Quelle-URL: {source_url}")
    if doc_title:
        parts.append(f"Dokumenttitel: {doc_title}")
    parts.append(f"Inhalt:\n{body[:2000]}")

    return "\n".join(parts)


def classify_content(text=None, image_path=None, existing_pages=None):
    """
    Fragt die KI nach dem passenden Themengebiet, orientiert sich primär am bestehenden Index.
    existing_pages: Liste von Dicts {name, title}
    """
    if existing_pages:
        lines = []
        for p in existing_pages:
            entry = f'- {p["name"]}: "{p["title"]}"'
            if p.get("subheadings"):
                entry += f' [{", ".join(p["subheadings"])}]'
            lines.append(entry)
        existing_str = "\n".join(lines)
    else:
        existing_str = "Noch keine Seiten vorhanden"

    system_prompt = f"""Du bist ein Router für ein Datei-basiertes Wiki-System.
Deine Aufgabe ist es, Notizen einem passenden Thema zuzuordnen.

Hier ist der Index der BEREITS EXISTIERENDEN Themen-Seiten in unserem Wiki (Format: Dateiname: "Seitentitel"):
{existing_str}

REGELN:
1. Wenn die Notiz inhaltlich gut zu einem der existierenden Themen passt, antworte EXAKT mit dem Dateinamen (linke Spalte).
2. Falls keines der bestehenden Themen direkt passt, erfinde ein neues Thema (maximal 1-2 Wörter, durch Unterstrich getrennt).
3. Antworte AUSSCHLIESSLICH mit dem Dateinamen des Themas (ohne Dateiendung). Keine Sätze, keine Sonderzeichen, keine Erklärungen."""
    
    model = config["models"]["classification"]
    messages = []

    if text and not image_path:
        messages.append({"role": "user", "content": f"Klassifiziere diese Notiz:\n{_build_classification_excerpt(text)}"})
    elif image_path:
        model = config["models"]["vision_update"]
        try:
            base64_image = encode_image(image_path)
            ext = image_path.rsplit(".", 1)[-1].lower()
            mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
            mime_type = mime_map.get(ext, "image/jpeg")
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "Klassifiziere den Inhalt dieses Bildes für ein technisches Wiki."},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                ]
            })
        except Exception:
            return "fehlerhafte_bilder"

    raw_content = call_openrouter(model=model, messages=messages, system_prompt=system_prompt)
    
    if not raw_content:
        logger.warning(f"Klassifizierung fehlgeschlagen für Modell '{model}'. Fallback auf 'allgemein'.")
        return "allgemein"

    topic = raw_content.lower().replace(" ", "_").replace("-", "_")
    topic = "".join(c for c in topic if c.isalnum() or c == "_").strip("_")

    if not topic:
        logger.warning("KI hat nach der Säuberung einen leeren String zurückgegeben. Fallback auf 'allgemein'.")
        return "allgemein"

    # Fuzzy-Abgleich gegen bestehende Seiten (deterministisch, kein API-Call)
    if existing_pages:
        page_names = [p["name"] for p in existing_pages]
        matches = difflib.get_close_matches(topic, page_names, n=1, cutoff=0.75)
        if matches and matches[0] != topic:
            logger.info(f"Fuzzy-Match: '{topic}' → '{matches[0]}' (bestehende Seite)")
            topic = matches[0]

    logger.info(f"Klassifizierung abgeschlossen: Modell '{model}' wählte Thema '{topic}'.")
    return topic

def process_batch():
    raw_dir = DIRS["raw"]
    files = [f for f in os.listdir(raw_dir) if os.path.isfile(os.path.join(raw_dir, f))]
    
    if not files:
        logger.info("Keine neuen Dateien im raw-Ordner. Beende Prozess.")
        return

    logger.info(f"{len(files)} neue Dateien zur Verarbeitung gefunden.")
    topics = defaultdict(lambda: {"texts": [], "images": [], "files_to_move": []})
    
    existing_pages = get_existing_wiki_pages()

    # 1. Dateien einlesen und klassifizieren
    for file in files:
        filepath = os.path.join(raw_dir, file)
        ext = file.split('.')[-1].lower()

        if ext in ['txt', 'md']:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                topic = classify_content(text=content, existing_pages=existing_pages)
                topics[topic]["texts"].append(content)
                topics[topic]["files_to_move"].append(filepath)
                logger.info(f"Datei '{file}' -> Thema: '{topic}'")
            except Exception as e:
                logger.error(f"Fehler beim Einlesen der Text/Markdown-Datei {file}: {e}")
                continue

        elif ext in ['jpg', 'jpeg', 'png', 'webp']:
            topic = classify_content(image_path=filepath, existing_pages=existing_pages)
            topics[topic]["images"].append(filepath)
            topics[topic]["files_to_move"].append(filepath)
            logger.info(f"Bilddatei '{file}' -> Thema: '{topic}'")
        else:
            logger.warning(f"Ignoriere Datei '{file}': Nicht unterstütztes Format.")
            continue

        if not any(p["name"] == topic for p in existing_pages):
            existing_pages.append({"name": topic, "title": topic, "subheadings": []})
            logger.debug(f"Neues Thema '{topic}' zum laufenden Index hinzugefügt.")

    # 2. Wiki-Seiten generieren/updaten
    for topic, data in topics.items():
        logger.info(f"Starte Update für Wiki-Seite: {topic}.md")
        wiki_file = os.path.join(DIRS["wiki"], f"{topic}.md")

        existing_content = ""
        if os.path.exists(wiki_file):
            try:
                with open(wiki_file, "r", encoding="utf-8") as f:
                    existing_content = f.read()
                logger.debug(f"Bestehender Inhalt von {topic}.md geladen.")
            except Exception as e:
                logger.error(f"Konnte bestehende Wiki-Datei {wiki_file} nicht lesen: {e}")

        # System Prompt aufbauen
        other_pages = [p for p in existing_pages if p["name"] != topic]
        existing_str = ", ".join(p["name"] for p in other_pages)

        system_prompt = f"Du pflegst ein technisches Markdown-Wiki. Dein aktuelles Thema ist: '{topic}'.\n"
        system_prompt += "Integriere die neuen Informationen sinnvoll in den bestehenden Inhalt. Lösche keine bestehenden Fakten. Antworte NUR mit dem reinen Markdown-Inhalt.\n\n"

        if existing_str:
            system_prompt += f"QUERVERWEISE VERWENDEN: In unserem Wiki existieren bereits Seiten zu folgenden Themen: [{existing_str}]. Wenn im Text Konzepte auftauchen, die thematisch zu einer dieser Seiten passen, formatiere sie als Markdown-Link (Beispiel: [Linktext](Dateiname.md)).\n\n"

        if GLOBAL_RULES:
            system_prompt += f"--- GLOBALE WIKI-REGELN ---\n{GLOBAL_RULES}\n------------------------------------------\n"

        # Content zusammenbauen
        messages_for_api = []
        
        if data["images"]:
            user_content = []
            if existing_content:
                user_content.append({"type": "text", "text": f"--- BESTEHENDER WIKI-INHALT ---\n{existing_content}\n\n--- NEUE NOTIZEN ---"})
            else:
                logger.info(f"Wiki-Seite {topic}.md existiert noch nicht. Wird neu angelegt.")
                user_content.append({"type": "text", "text": "Dies ist eine neue Wiki-Seite. Formatiere die folgenden Notizen als sauberes Markdown-Dokument.\n\n--- NEUE NOTIZEN ---"})

            for text in data["texts"]:
                user_content.append({"type": "text", "text": text + "\n---\n"})

            for img_path in data["images"]:
                try:
                    base64_image = encode_image(img_path)
                    ext = img_path.rsplit(".", 1)[-1].lower()
                    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
                    mime_type = mime_map.get(ext, "image/jpeg")
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}
                    })
                except Exception as e:
                    logger.error(f"Bild {img_path} konnte nicht für die API vorbereitet werden und wird übersprungen.")
            
            messages_for_api.append({"role": "user", "content": user_content})
        else:
            text_content = ""
            if existing_content:
                text_content += f"--- BESTEHENDER WIKI-INHALT ---\n{existing_content}\n\n--- NEUE NOTIZEN ---\n"
            else:
                logger.info(f"Wiki-Seite {topic}.md existiert noch nicht. Wird neu angelegt.")
                text_content += "Dies ist eine neue Wiki-Seite. Formatiere die folgenden Notizen als sauberes Markdown-Dokument.\n\n--- NEUE NOTIZEN ---\n"

            for text in data["texts"]:
                text_content += text + "\n---\n"
                
            messages_for_api.append({"role": "user", "content": text_content})

        model_to_use = config["models"]["vision_update"] if data["images"] else config["models"]["text_update"]
        logger.info(f"Sende Daten für {topic}.md an Modell: {model_to_use}")

        new_wiki_content = call_openrouter(model=model_to_use, messages=messages_for_api, system_prompt=system_prompt)

        if not new_wiki_content:
            logger.error(f"Fehler: Modell '{model_to_use}' hat keine gültigen Daten geliefert. Überspringe Update für {topic}.md")
            continue
            
        new_wiki_content = re.sub(r'^```[a-zA-Z]*\n?', '', new_wiki_content)
        new_wiki_content = re.sub(r'\n?```\s*$', '', new_wiki_content)

        try:
            with open(wiki_file, "w", encoding="utf-8") as f:
                f.write(new_wiki_content.strip())
            
            logger.info(f"Erfolgreich gespeichert: {topic}.md")
            
            for fp in data["files_to_move"]:
                try:
                    target_path = os.path.join(DIRS["processed"], os.path.basename(fp))
                    shutil.move(fp, target_path)
                    logger.debug(f"Verschoben: {fp} -> {target_path}")
                except Exception as e:
                    logger.error(f"Fehler beim Verschieben von {fp}: {e}")

        except Exception as e:
            logger.error(f"Fehler beim Speichern der Datei {topic}.md: {e}", exc_info=True)

    # 3. Zum Schluss den Index updaten, damit er auch die neu angelegten Seiten enthält
    generate_index_file()
    logger.info("Verarbeitungsdurchlauf komplett beendet.")

if __name__ == "__main__":
    process_batch()