#!/usr/bin/env python3
"""
Revisa el feed Atom del blog de la profesora y manda una notificación
push (vía ntfy.sh) cuando aparece una entrada nueva relevante para 1º Bach.

Guarda en state.json el id de la última entrada vista, para no avisar
dos veces de lo mismo. Ese state.json se actualiza y se sube al repo
por el propio workflow de GitHub Actions.
"""

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

# Patrón que detecta "1 Bach", "1º Bach", "1 Bachillerato A/B", etc.
# tras normalizar el texto (sin tildes, sin "º", en minúsculas).
# El (?<!\d) evita que "21 Bachillerato" cuele como si fuera "1 Bach".
RELEVANT_PATTERN = re.compile(r"(?<!\d)1\s*bach")

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


def is_relevant(title: str, summary: str) -> bool:
    haystack = normalize(f"{title} {summary}")
    return bool(RELEVANT_PATTERN.search(haystack))


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"seen_ids": []}


def save_state(state: dict) -> None:
    # Nos quedamos solo con los últimos 50 ids para que el fichero no crezca sin límite
    state["seen_ids"] = state["seen_ids"][-50:]
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def send_notification(title: str, link: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("AVISO: falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID, no se envía notificación.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    text = f"📌 Nueva entrada en el blog de inglés\n\n{title}\n{link}"
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
        print(f"Notificación enviada: {title}")


def main() -> int:
    feed = feedparser.parse(FEED_URL)
    if feed.bozo and not feed.entries:
        print(f"No se pudo leer el feed: {feed.bozo_exception}", file=sys.stderr)
        return 1

    state = load_state()
    seen_ids = set(state["seen_ids"])
    first_run = len(seen_ids) == 0

    # feedparser ya devuelve las entradas ordenadas de más reciente a más antigua
    new_entries = [e for e in feed.entries if e.id not in seen_ids]

    if first_run:
        # En la primera ejecución no avisamos de todo el histórico,
        # solo guardamos lo que ya existe como "ya visto".
        print("Primera ejecución: guardando estado inicial sin enviar avisos.")
        for e in feed.entries:
            seen_ids.add(e.id)
        state["seen_ids"] = list(seen_ids)
        save_state(state)
        return 0

    if not new_entries:
        print("Sin novedades.")
        return 0

    # Procesamos de la más antigua a la más nueva, para avisar en orden
    for entry in reversed(new_entries):
        title = entry.get("title", "(sin título)")
        summary = entry.get("summary", "")
        link = entry.get("link", FEED_URL)
        seen_ids.add(entry.id)

        if is_relevant(title, summary):
            print(f"Entrada relevante encontrada: {title}")
            send_notification(title, link)
        else:
            print(f"Entrada nueva pero no relevante para 1º Bach: {title}")

    state["seen_ids"] = list(seen_ids)
    save_state(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
