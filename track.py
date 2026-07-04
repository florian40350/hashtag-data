#!/usr/bin/env python3
"""
track.py — collecteur de hashtags pour GitHub Actions
------------------------------------------------------
Exécuté automatiquement par GitHub toutes les X minutes (voir track.yml).
Relève le nombre de publications de chaque hashtag listé dans HASHTAGS,
et met à jour history.json (que GitHub Actions committe ensuite).

Les identifiants (cookies Instagram) sont lus depuis les SECRETS GitHub
via des variables d'environnement — jamais en clair dans le code.

Configuration des hashtags : modifie la liste HASHTAGS ci-dessous.
"""

import json
import os
import random
import time
from datetime import datetime, timezone

import requests

# =================================================================
# HASHTAGS À SUIVRE — ajoute/retire ce que tu veux ici
# =================================================================
HASHTAGS = ["btc"]

HISTORY_FILE = "history.json"

# Identifiants lus depuis les secrets GitHub (variables d'environnement)
SESSION_COOKIES = {
    "sessionid": os.environ.get("IG_SESSIONID", ""),
    "csrftoken": os.environ.get("IG_CSRFTOKEN", ""),
    "ds_user_id": os.environ.get("IG_DS_USER_ID", ""),
}

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "x-ig-app-id": "936619743392459",
    "x-requested-with": "XMLHttpRequest",
    "Accept": "*/*",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Referer": "https://www.instagram.com/",
}


def get_count(hashtag: str) -> int:
    cookies = {k: v for k, v in SESSION_COOKIES.items() if v}
    if "sessionid" not in cookies:
        raise RuntimeError("Secret IG_SESSIONID manquant dans GitHub.")
    if cookies.get("csrftoken"):
        HEADERS["x-csrftoken"] = cookies["csrftoken"]

    url = f"https://www.instagram.com/api/v1/tags/web_info/?tag_name={hashtag}"
    r = requests.get(url, headers=HEADERS, cookies=cookies, timeout=20)

    if r.status_code == 404:
        raise RuntimeError(f"404 pour #{hashtag} (inexistant ou session expirée).")
    if r.status_code in (401, 403):
        raise RuntimeError("Accès refusé : sessionid invalide/expiré.")
    if r.status_code == 429:
        raise RuntimeError("Limite Instagram (429).")
    r.raise_for_status()

    if "json" not in r.headers.get("Content-Type", "") or r.text.lstrip().startswith("<"):
        raise RuntimeError("Instagram a renvoyé du HTML : session non reconnue.")

    d = r.json()
    d = d.get("data", d)
    if isinstance(d, dict):
        if "media_count" in d:
            return int(d["media_count"])
        if "count" in d:
            return int(d["count"])
        if isinstance(d.get("hashtag"), dict) and "media_count" in d["hashtag"]:
            return int(d["hashtag"]["media_count"])
    raise RuntimeError("Structure de réponse inattendue.")


def load_history() -> dict:
    if os.path.isfile(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_history(data: dict):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    history = load_history()
    # timestamp avec fuseau (non ambigu) — heure locale de l'exécuteur = UTC sur GitHub
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    any_success = False
    for i, tag in enumerate(HASHTAGS):
        tag = tag.lstrip("#").lower()
        try:
            count = get_count(tag)
            history.setdefault(tag, []).append({"timestamp": now, "count": count})
            print(f"#{tag} → {count}")
            any_success = True
        except Exception as e:
            print(f"#{tag} ÉCHEC : {e}")
        if i < len(HASHTAGS) - 1:
            time.sleep(random.uniform(5, 15))

    if any_success:
        save_history(history)
        print("history.json mis à jour.")
    else:
        print("Aucun relevé réussi — history.json inchangé.")
        # sortie 0 quand même pour ne pas spammer d'emails d'échec GitHub


if __name__ == "__main__":
    main()
