#!/usr/bin/env python3
"""
Recherche quotidienne d'offres d'emploi – Chef de projet / PO CDI Paris
Envoie un résumé par email chaque matin.
"""

import smtplib
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse
import os
import re
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── Configuration ────────────────────────────────────────────────────────────
GMAIL_USER  = "adenikgnigla@gmail.com"
GMAIL_PASS  = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT   = "adenikgnigla@gmail.com"

KEYWORDS    = ["chef de projet", "product owner", "po ", "project manager", "chef projet"]
EXCLUDE     = ["stage", "alternance", "apprentissage", "freelance", "indépendant"]

PARIS_TIME  = timezone(timedelta(hours=2))   # CEST – ajuste à +1 en hiver si besoin
TODAY       = datetime.now(PARIS_TIME).strftime("%d/%m/%Y")

# ── Sources RSS ───────────────────────────────────────────────────────────────
SOURCES = [
    {
        "name": "Indeed",
        "url": (
            "https://fr.indeed.com/rss?"
            + urllib.parse.urlencode({
                "q": "chef de projet CDI grande entreprise",
                "l": "Paris",
                "sort": "date",
                "fromage": "1",   # dernières 24h
            })
        ),
    },
    {
        "name": "Indeed – Product Owner",
        "url": (
            "https://fr.indeed.com/rss?"
            + urllib.parse.urlencode({
                "q": "product owner CDI Paris",
                "l": "Paris",
                "sort": "date",
                "fromage": "1",
            })
        ),
    },
    {
        "name": "APEC",
        "url": (
            "https://www.apec.fr/cms/rss/annonces.rss?"
            + urllib.parse.urlencode({
                "motsCles": "chef de projet",
                "lieux": "75-92-93-94",
                "typeContrat": "CDI",
            })
        ),
    },
    {
        "name": "APEC – Product Owner",
        "url": (
            "https://www.apec.fr/cms/rss/annonces.rss?"
            + urllib.parse.urlencode({
                "motsCles": "product owner",
                "lieux": "75-92-93-94",
                "typeContrat": "CDI",
            })
        ),
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def fetch_rss(url: str) -> list[dict]:
    """Télécharge et parse un flux RSS, retourne une liste d'offres."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 JobSearchBot/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        root = ET.fromstring(data)
        items = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link")  or "").strip()
            desc  = (item.findtext("description") or "").strip()
            # Nettoyage HTML basique dans la description
            desc  = re.sub(r"<[^>]+>", " ", desc)
            desc  = re.sub(r"\s+", " ", desc).strip()[:300]
            items.append({"title": title, "link": link, "desc": desc})
        return items
    except Exception as exc:
        print(f"  ⚠ Erreur RSS ({url[:60]}…) : {exc}")
        return []


def is_relevant(offer: dict) -> bool:
    """Filtre les offres selon les mots-clés et les exclusions."""
    text = (offer["title"] + " " + offer["desc"]).lower()
    has_keyword = any(kw in text for kw in KEYWORDS)
    has_exclude = any(ex in text for ex in EXCLUDE)
    return has_keyword and not has_exclude


def deduplicate(offers: list[dict]) -> list[dict]:
    seen_links = set()
    result = []
    for o in offers:
        if o["link"] not in seen_links:
            seen_links.add(o["link"])
            result.append(o)
    return result


# ── Collecte des offres ───────────────────────────────────────────────────────
all_offers: list[tuple[str, dict]] = []   # (source_name, offer)

for source in SOURCES:
    print(f"Fetching {source['name']}…")
    raw = fetch_rss(source["url"])
    relevant = [o for o in raw if is_relevant(o)]
    print(f"  → {len(raw)} offres brutes, {len(relevant)} pertinentes")
    all_offers.extend((source["name"], o) for o in relevant)

# Dédupliquer toutes les offres (même lien = même offre)
unique: dict[str, tuple[str, dict]] = {}
for src, offer in all_offers:
    if offer["link"] not in unique:
        unique[offer["link"]] = (src, offer)

final_offers = list(unique.values())
print(f"\nTotal : {len(final_offers)} offre(s) unique(s) trouvée(s)")


# ── Construction de l'email HTML ──────────────────────────────────────────────
def build_html(offers: list[tuple[str, dict]]) -> str:
    if not offers:
        body_content = """
        <p style="font-size:16px; color:#555;">
          Aucune nouvelle offre correspondant à ton profil aujourd'hui.<br>
          Reviens demain – le marché bouge vite !
        </p>"""
    else:
        cards = ""
        for src, o in offers:
            cards += f"""
        <div style="background:#fff; border:1px solid #e0e0e0; border-radius:8px;
                    padding:16px 20px; margin-bottom:16px;">
          <p style="margin:0 0 4px 0; font-size:11px; color:#888; text-transform:uppercase;
                    letter-spacing:.5px;">{src}</p>
          <h3 style="margin:0 0 8px 0; font-size:17px; color:#1a1a2e;">
            <a href="{o['link']}" style="color:#3b5bdb; text-decoration:none;">{o['title']}</a>
          </h3>
          <p style="margin:0; font-size:13px; color:#555; line-height:1.5;">{o['desc']}…</p>
          <a href="{o['link']}" style="display:inline-block; margin-top:10px; padding:7px 16px;
             background:#3b5bdb; color:#fff; border-radius:5px; text-decoration:none;
             font-size:13px;">Voir l'offre →</a>
        </div>"""
        body_content = cards

    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"></head>
<body style="margin:0; padding:0; background:#f4f6fb; font-family: -apple-system, Arial, sans-serif;">
  <div style="max-width:640px; margin:30px auto; background:#f4f6fb;">

    <!-- Header -->
    <div style="background:#1a1a2e; border-radius:10px 10px 0 0; padding:28px 32px;">
      <h1 style="margin:0; color:#fff; font-size:22px;">🔍 Offres du jour</h1>
      <p style="margin:6px 0 0 0; color:#a0aec0; font-size:14px;">
        Chef de Projet / Product Owner · CDI · Paris/IDF · {TODAY}
      </p>
    </div>

    <!-- Summary -->
    <div style="background:#3b5bdb; padding:12px 32px;">
      <p style="margin:0; color:#fff; font-size:15px;">
        <strong>{len(offers)} offre(s)</strong> correspondent à ton profil aujourd'hui
      </p>
    </div>

    <!-- Body -->
    <div style="padding:24px 32px;">
      {body_content}
    </div>

    <!-- Footer -->
    <div style="padding:16px 32px; text-align:center; font-size:11px; color:#aaa;">
      Sources : Indeed · APEC &nbsp;|&nbsp;
      Profil : Chef de projet / PO · CDI · Paris · Grande entreprise · 2-5 ans exp.
    </div>

  </div>
</body>
</html>"""


# ── Envoi de l'email ──────────────────────────────────────────────────────────
html_body = build_html(final_offers)

subject = f"🔍 Offres du jour – Chef de Projet / PO Paris CDI – {TODAY} ({len(final_offers)} offre(s))"

msg = MIMEMultipart("alternative")
msg["Subject"] = subject
msg["From"]    = GMAIL_USER
msg["To"]      = RECIPIENT
msg.attach(MIMEText(html_body, "html"))

print(f"\nEnvoi de l'email à {RECIPIENT}…")
with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(GMAIL_USER, GMAIL_PASS)
    server.sendmail(GMAIL_USER, RECIPIENT, msg.as_string())

print("✅ Email envoyé avec succès !")
