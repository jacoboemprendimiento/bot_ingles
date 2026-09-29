#!/usr/bin/env python3
"""
Revisa el feed Atom del blog de la profesora y manda una notificación
por Telegram cuando aparece una entrada nueva relevante para 1º Bach.

Una entrada es relevante si:
  1. su texto menciona 1º Bach en cualquier forma ("1º. Bach", "1 Bachillerato B",
     "1º y 2º Bachillerato"...), o
  2. lleva una de las imágenes-etiqueta de la clase (la bombilla).

Guarda en state.json los ids de las entradas ya vistas para no avisar dos veces.
Ese state.json lo actualiza y sube al repo el propio workflow de GitHub Actions.
"""

import html
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import feedparser
import requests

FEED_URL = "https://riosginerlisbon.blogspot.com/feeds/posts/default"
STATE_FILE = Path(__file__).parent / "state.json"
MAX_SEEN_IDS = 200  # el feed solo devuelve las últimas ~25 entradas, de sobra

# --- Reglas de texto (se aplican ya normalizado: sin tildes, "º" ni puntuación) ---
# "1 Bach", "1º. Bach", "1 Bachillerato A/B"...
# El (?<!\d) evita que "21 Bachillerato" cuele como si fuera "1 Bach".
RELEVANT_PATTERN = re.compile(r"(?<!\d)1\s*bach")
# "1º y 2º Bachillerato", "1º/2º Bach"...
BOTH_PATTERN = re.compile(r"(?<!\d)1\s*(?:y|e|and)?\s*2\s*bach")

# --- Reglas de imagen ---
# La profesora marca cada clase con una imagen. Basta con la parte única del
# enlace (ignora el sufijo de tamaño tipo "=w200-h171", que cambia según el post).
IMAGE_MARKERS = {
    "bombilla": (
        "AVvXsEi-GXMHPJ4UKfc26L3fp7djM1oGNwT4C5ecw64quf2uuq6ePA9AYSRt3eAWRf8WZbHURXVSj0H"
        "dc5kLY4kaeq_FP169CLqzJuG0MrxO8SoyUyZm94BiTlW_qRxbNTmyFw_NXbr869oc1sFSYhG57_pdQhW"
        "zlV3iNuZyq-f2OXzt8ZQn-rwrlY_a9zP-aB8"
    ),
}

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def normalize(text: str) -> str:
    """minúsculas, sin tildes, sin 'º'/'°', sin puntuación, espacios simplificados.

    Quitar la puntuación es importante: la profesora a veces escribe
    "1º. Bach" o "1º: Bach", y sin este paso el punto o los dos puntos
    se quedaban entre el "1" y "bach", impidiendo la detección.
    """
    text = text.replace("º", "").replace("°", "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def html_to_text(raw: str) -> str:
    """Quita las etiquetas HTML (y con ellas las URLs) y deja solo el texto visible."""
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    return re.sub(r"\s+", " ", raw).strip()


def entry_html(entry) -> str:
    """Todo el HTML de la entrada (resumen, contenido y miniaturas)."""
    parts = [entry.get("summary", "")]
    for c in entry.get("content", []):
        parts.append(c.get("value", ""))
    for t in entry.get("media_thumbnail", []):
        parts.append(t.get("url", ""))
    return "\n".join(parts)


def why_relevant(title: str, raw_html: str):
    """Devuelve el motivo (texto) si la entrada es relevante para 1º Bach, o None."""
    text = normalize(f"{title} {html_to_text(raw_html)}")
    if RELEVANT_PATTERN.search(text) or BOTH_PATTERN.search(text):
        return "menciona 1º Bach"
    for name, marker in IMAGE_MARKERS.items():
        if marker in raw_html:  # se busca en el HTML tal cual, sin normalizar
            return f"lleva la imagen de la {name}"
    return None


def preview(title: str, raw_html: str, limit: int = 100) -> str:
    """Texto corto para mostrar en el aviso (muchas entradas no tienen título)."""
    text = title.strip() or html_to_text(raw_html)
    if not text:
        return "(solo imagen, sin texto)"
    return text if len(text) <= limit else text[: limit - 1] + "…"


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"seen_ids": []}


def save_state(state: dict) -> None:
    # Se conserva el orden (los más recientes al final) y se recorta por el principio
    state["seen_ids"] = state["seen_ids"][-MAX_SEEN_IDS:]
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def send_notification(label: str, link: str, reason: str = "") -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("AVISO: falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID, no se envía notificación.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    text = f"📌 Nueva entrada en el blog de inglés\n\n{label}"
    if reason:
        text += f"\n({reason})"
    text += f"\n{link}"
    resp = requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "disable_web_page_preview": False,
        },
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"ERROR enviando a Telegram: {resp.status_code} {resp.text}", file=sys.stderr)
    else:
        print(f"Notificación enviada: {label}")


def main() -> int:
    feed = feedparser.parse(FEED_URL)
    if feed.bozo and not feed.entries:
        print(f"No se pudo leer el feed: {feed.bozo_exception}", file=sys.stderr)
        return 1

    state = load_state()
    seen_list = state["seen_ids"]  # lista ordenada (el orden importa para el recorte)
    seen = set(seen_list)

    if not seen:
        # Primera ejecución: no avisamos de todo el histórico, solo lo memorizamos.
        print("Primera ejecución: guardando estado inicial sin enviar avisos.")
        for e in reversed(feed.entries):
            seen_list.append(e.id)
        save_state(state)
        return 0

    # feedparser devuelve las entradas de más reciente a más antigua
    new_entries = [e for e in feed.entries if e.id not in seen]
    if not new_entries:
        print("Sin novedades.")
        return 0

    # Procesamos de la más antigua a la más nueva, para avisar en orden
    for entry in reversed(new_entries):
        title = entry.get("title", "") or ""
        raw = entry_html(entry)
        link = entry.get("link", FEED_URL)
        seen_list.append(entry.id)

        reason = why_relevant(title, raw)
        label = preview(title, raw)
        if reason:
            print(f"Entrada relevante ({reason}): {label}")
            send_notification(label, link, reason)
        else:
            print(f"Entrada nueva pero no relevante para 1º Bach: {label}")

    save_state(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
