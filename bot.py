import os
import re
import json
import base64
import logging
import requests
import discord
from datetime import datetime
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler

# --- LOGGING SETUP ---
LOG_FILE = "wiki_bot.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logger.info("Starte Wiki-Collector Bot...")

# --- KONFIGURATION LADEN ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
API_KEY = os.getenv("OPENROUTER_API_KEY")

if not DISCORD_TOKEN:
    logger.critical("DISCORD_TOKEN fehlt in der .env Datei! Abbruch.")
    raise ValueError("DISCORD_TOKEN fehlt!")

if not API_KEY:
    logger.critical("OPENROUTER_API_KEY fehlt in der .env Datei! Abbruch.")
    raise ValueError("OPENROUTER_API_KEY fehlt!")

try:
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    logger.info("config.json erfolgreich geladen.")
except Exception as e:
    logger.critical(f"Fehler beim Laden der config.json: {e}")
    raise

# Ordnerstruktur
DIRS = config["directories"]
RAW_DIR = DIRS["raw"]
os.makedirs(RAW_DIR, exist_ok=True)
MAX_URLS = config.get("max_urls_per_message", 5)

AUDIO_MIME_MAP = {
    "ogg": "audio/ogg",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "m4a": "audio/mp4",
    "mpeg": "audio/mpeg",
}

_raw_ids = os.getenv("ALLOWED_CHANNEL_IDS", "")
ALLOWED_CHANNEL_IDS = set(int(cid.strip()) for cid in _raw_ids.split(",") if cid.strip())

# URL-Deduplizierung
SEEN_URLS_FILE = os.path.join(os.path.dirname(RAW_DIR), "seen_urls.json")

def _load_seen_urls():
    if os.path.exists(SEEN_URLS_FILE):
        try:
            with open(SEEN_URLS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def _save_seen_urls(seen: set):
    try:
        with open(SEEN_URLS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(seen), f)
    except Exception as e:
        logger.error(f"Fehler beim Speichern der seen_urls: {e}")

SEEN_URLS = _load_seen_urls()

# Discord Setup
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def extract_urls(text):
    """Findet alle URLs in einem Text, bereinigt trailing Satzzeichen."""
    urls = re.findall(r'https?://\S+', text)
    return [u.rstrip('.,;:!?)]\'"') for u in urls]

def fetch_url_as_markdown(url):
    """Nutzt die Jina API, um eine Webseite als Markdown zu extrahieren."""
    try:
        headers = {
            "X-Return-Format": "markdown",
            "X-No-Cache": "true"
        }
        response = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=20)
        
        if response.status_code == 200:
            return response.text
        else:
            logger.error(f"Jina API Fehler {response.status_code} für URL: {url}")
            return None
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der URL {url}: {e}")
        return None

def transcribe_audio(filepath):
    """Nutzt ein multimodales OpenRouter Modell zur Transkription von Audio."""
    logger.info(f"Starte Transkription für: {filepath}")
    
    try:
        with open(filepath, "rb") as f:
            b64_audio = base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Konnte Audio-Datei {filepath} nicht lesen: {e}")
        return None

    ext = filepath.split('.')[-1].lower()
    mime_type = AUDIO_MIME_MAP.get(ext, "audio/ogg")

    base_url = config["openrouter_url"].rstrip("/")
    url = f"{base_url}/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/llm-wiki",
        "X-Title": "LLM Wiki Bot"
    }

    model = config["models"].get("audio_transcription", "google/gemini-1.5-flash")

    # Wir nutzen das standardisierte Image-URL Feld für Base64-Daten (OpenRouter Norm)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text", 
                        "text": "Du bist ein präzises Transkriptions-System. Höre dir diese Audio-Datei an und antworte AUSSCHLIESSLICH mit dem gesprochenen Text. Keine Einleitung, keine Erklärungen."
                    },
                    {
                        "type": "image_url", 
                        "image_url": {"url": f"data:{mime_type};base64,{b64_audio}"}
                    }
                ]
            }
        ],
        "temperature": 0.1,
        "max_tokens": 1500
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        
        if "error" in data:
            logger.error(f"OpenRouter Fehler bei Audio-Transkription: {data['error']}")
            return None
            
        transcription = data.get("choices", [])[0].get("message", {}).get("content")
        return transcription.strip() if transcription else None

    except Exception as e:
        logger.error(f"Fehler bei der Audio-API-Anfrage: {e}", exc_info=True)
        return None

@client.event
async def on_ready():
    logger.info(f'✅ Bot erfolgreich eingeloggt als {client.user}')
    logger.info(f'📂 Warte auf Input im Verzeichnis: {RAW_DIR}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if ALLOWED_CHANNEL_IDS and message.channel.id not in ALLOWED_CHANNEL_IDS:
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    content_saved = False

    # 1. URLs verarbeiten
    urls = extract_urls(message.content)[:MAX_URLS]
    if urls:
        await message.add_reaction("⏳")
        for i, url in enumerate(urls):
            if url in SEEN_URLS:
                logger.info(f"URL bereits verarbeitet, überspringe: {url}")
                await message.add_reaction("🔁")
                continue
            logger.info(f"Verarbeite URL: {url}")
            md_content = fetch_url_as_markdown(url)
            if md_content:
                filename = f"webpage_{timestamp}_{i}.md"
                filepath = os.path.join(RAW_DIR, filename)
                try:
                    with open(filepath + ".tmp", "w", encoding="utf-8") as f:
                        f.write(f"---\nQuelle: {url}\nDatum: {datetime.now().isoformat()}\n---\n\n")
                        f.write(md_content)
                    os.rename(filepath + ".tmp", filepath)
                    SEEN_URLS.add(url)
                    _save_seen_urls(SEEN_URLS)
                    content_saved = True
                    logger.info(f"Webseite gespeichert: {filename}")
                except Exception as e:
                    logger.error(f"Fehler beim Speichern der Webseite {filename}: {e}")

    # 2. Text verarbeiten (ohne URLs)
    text_only = message.content
    for url in urls:
        text_only = text_only.replace(url, "").strip()

    if text_only:
        filename = f"memo_{timestamp}.md"
        filepath = os.path.join(RAW_DIR, filename)
        try:
            with open(filepath + ".tmp", "w", encoding="utf-8") as f:
                f.write(text_only)
            os.rename(filepath + ".tmp", filepath)
            content_saved = True
            logger.info(f"Text-Memo gespeichert: {filename}")
        except Exception as e:
            logger.error(f"Fehler beim Speichern des Memos {filename}: {e}")

    # 3. Anhänge (Bilder, Dokumente, Audio) verarbeiten
    if message.attachments:
        await message.add_reaction("📥")
        for i, attachment in enumerate(message.attachments):
            safe_filename = "".join(c for c in attachment.filename if c.isalnum() or c in "._-")
            filepath = os.path.join(RAW_DIR, f"att_{timestamp}_{i}_{safe_filename}")

            try:
                await attachment.save(filepath + ".tmp")
                os.rename(filepath + ".tmp", filepath)
                content_saved = True
                logger.info(f"Anhang gespeichert: {safe_filename}")

                # Audio direkt transkribieren
                ext = safe_filename.split('.')[-1].lower()
                if ext in ['ogg', 'mp3', 'wav', 'm4a']:
                    await message.add_reaction("🎙️")
                    transcription = transcribe_audio(filepath)

                    if transcription:
                        trans_filename = f"transkript_{timestamp}_{i}.md"
                        trans_filepath = os.path.join(RAW_DIR, trans_filename)
                        with open(trans_filepath + ".tmp", "w", encoding="utf-8") as f:
                            f.write(f"--- Audio Transkription ---\n{transcription}")
                        os.rename(trans_filepath + ".tmp", trans_filepath)
                        logger.info(f"Audio erfolgreich transkribiert in {trans_filename}")
                        
                        # Wir löschen die originale Audio-Datei, um Platz auf dem Pi zu sparen
                        os.remove(filepath)
                        logger.debug(f"Originale Audio-Datei {filepath} gelöscht.")
                    else:
                        logger.warning("Audio-Transkription lieferte kein Ergebnis.")
                        
            except Exception as e:
                logger.error(f"Fehler bei der Verarbeitung des Anhangs {attachment.filename}: {e}")

    # UI-Feedback im Discord
    if content_saved:
        try:
            await message.clear_reactions()
        except:
            pass 
        await message.add_reaction("✅")

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)