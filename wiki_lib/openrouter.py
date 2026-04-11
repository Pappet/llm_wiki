"""
openrouter.py — OpenRouter-API-Client und verwandte Hilfsfunktionen.
Layer 1: importiert nur aus Layer 0 (config).

Exports: call_openrouter, encode_image, _strip_json_fences,
         _extract_json_object, _build_classification_excerpt
"""

import re
import json
import base64
import requests

from .config import config, API_KEY, logger


def call_openrouter(model, messages, system_prompt=None, max_tokens=None):
    base_url = config["openrouter_url"].rstrip("/")
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/llm-wiki",
        "X-Title": "LLM Wiki Bot",
    }
    api_messages = []
    if system_prompt:
        api_messages.append({"role": "system", "content": system_prompt})
    if isinstance(messages, list) and messages and isinstance(messages[0], dict) and "role" in messages[0]:
        api_messages.extend(messages)
    else:
        api_messages.append({"role": "user", "content": messages})

    payload = {
        "model": model,
        "messages": api_messages,
        "temperature": 0.3,
        "max_tokens": max_tokens or config["max_tokens"]["classification"],
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError:
            logger.error(f"HTTP Fehler OpenRouter ({resp.status_code}): {resp.text[:500]}")
            return None
        try:
            data = resp.json()
        except ValueError:
            logger.error(f"OpenRouter: kein JSON (Status {resp.status_code})")
            return None
        if "error" in data:
            logger.error(f"OpenRouter Fehler: {data['error']}")
            return None
        choices = data.get("choices")
        if not choices:
            return None
        content = choices[0].get("message", {}).get("content")
        if content is None:
            refusal = choices[0].get("message", {}).get("refusal")
            if refusal:
                logger.warning(f"Modell {model} hat verweigert: {refusal}")
            return None
        return content.strip()
    except requests.exceptions.Timeout:
        logger.error(f"Timeout bei OpenRouter für Modell {model}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Netzwerk-Fehler bei OpenRouter: {e}")
        return None
    except Exception as e:
        logger.error(f"Unerwarteter Fehler in call_openrouter: {e}", exc_info=True)
        return None


def encode_image(image_path):
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        logger.error(f"Fehler beim Kodieren des Bildes {image_path}: {e}")
        raise


def _strip_json_fences(raw):
    raw = raw.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    return raw.strip()


def _extract_json_object(raw):
    if not raw:
        return None
    raw = _strip_json_fences(raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _build_classification_excerpt(text, body_limit=3000):
    source_url = None
    doc_title = None
    body = text
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            for line in text[3:end].splitlines():
                if line.lower().startswith("quelle:"):
                    source_url = line[7:].strip()
            body = text[end + 3:].strip()
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
    parts.append(f"Inhalt:\n{body[:body_limit]}")
    return "\n".join(parts)
