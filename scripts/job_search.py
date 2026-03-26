#!/usr/bin/env python3
"""
Recherche quotidienne d'offres d'emploi – Chef de projet / PO CDI Paris
Scrape les pages publiques de France Travail (JSON-LD embarqué dans le HTML).
Aucune clé API requise.
"""

import smtplib
import os
import re
import json
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError
from html.parser import HTMLParser

# ── Configuration ─────────────────────────────────────────────
GMAIL_USER = "adenikgnigla@gmail.com"
GMAIL_PASS = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT  = "adenikgnigla@gmail.com"

PARIS_TIME = timezone(timedelta(hours=2))
TODAY      = datetime.now(PARIS_TIME).strftime("%d/%m/%Y")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── Recherche France Travail (scraping JSON-LD) ────────────────────────
def fetch_ft_offers(keywords: str) -> list[dict]:
    params = urlencode({
        "motsCles":        keywords,
        "lieux":           "75L",   # Paris
        "typeContrat":     "CDI",
        "sort":            "1",     # tri par date
        "offresPartenaires": "true",
    })
    url = f"https://candidat.francetravail.fr/offres/recherche?{params}"
    print(f"  GET {url[:80]}…")
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except URLError as e:
        print(f"  ⚠ Erreur réseau : {e}")
        return []

    # Cherche les blocs JSON-LD de type JobPosting
    offers = []
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE
    ):
        try:
            data = json.loads(match.group(1))
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "JobPosting":
                    offers.append(item)
        except (json.JSONDecodeError, AttributeError):
            continue

    print(f"  → {len(offers)} offre(s) JSON-LD trouvée(s)")
    return offers


# ── Collecte ──────────────────────────────────────────────────────
all_raw: list[dict] = []
for kw in ["chef de projet CDI", "product owner CDI"]:
    print(f"Recherche : {kw!r}…")
    all_raw.extend(fetch_ft_offers(kw))

# Dédupliquer par URL
unique: dict[str, dict] = {}
for o in all_raw:
    key = o.get("url") or o.get("identifier", {}).get("value", "") or o.get("title", "")
    if key and key not in unique:
        unique[key] = o

offers = list(unique.values())
print(f"\nTotal unique : {len(offers)} offre(s)")

# ── Formatage HTML ────────────────────────────────────────────────
def fmt_offer(o: dict) -> str:
    title   = o.get("title", "Offre sans titre")
    company = o.get("hiringOrganization", {}).get("name", "Entreprise non précisée")
    lieu    = o.get("jobLocation", {}).get("address", {}).get("addressLocality", "Paris")
    contrat = o.get("employmentType", "CDI")
    desc    = re.sub(r"<[^>]+>", " ", o.get("description", ""))
    desc    = re.sub(r"\s+", " ", desc).strip()[:280]
    url     = o.get("url", "https://candidat.francetravail.fr/offres/recherche")

    return f"""
    <div style="background:#fff;border:1px solid #e0e0e0;border-radius:8px;
                padding:16px 20px;margin-bottom:16px;">
      <p style="margin:0 0 4px;font-size:11px;color:#888;text-transform:uppercase;
                letter-spacing:.5px;">France Travail</p>
      <h3 style="margin:0 0 6px;font-size:16px;color:#1a1a2e;">
        <a href="{url}" style="color:#3b5bdb;text-decoration:none;">{title}</a>
      </h3>
      <p style="margin:0 0 6px;font-size:13px;color:#444;">
        🏢 {company} &nbsp;·&nbsp; 📍 {lieu} &nbsp;·&nbsp; 📄 {contrat}
      </p>
      <p style="margin:0;font-size:13px;color:#555;line-height:1.5;">{desc}…</p>
      <a href="{url}" style="display:inline-block;margin-top:10px;padding:7px 16px;
         background:#3b5bdb;color:#fff;border-radius:5px;text-decoration:none;
         font-size:13px;">Voir l'offre →</a>
    </div>"""


def build_html(offers: list[dict]) -> str:
    body = "".join(fmt_offer(o) for o in offers) if offers else (
        '<p style="font-size:16px;color:#555;">Aucune nouvelle offre aujourd\'hui.</p>'
    )
    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f6fb;font-family:-apple-system,Arial,sans-serif;">
  <div style="max-width:640px;margin:30px auto;">
    <div style="background:#1a1a2e;border-radius:10px 10px 0 0;padding:28px 32px;">
      <h1 style="margin:0;color:#fff;font-size:22px;">🔍 Offres du jour</h1>
      <p style="margin:6px 0 0;color:#a0aec0;font-size:14px;">
        Chef de Projet / Product Owner · CDI · Paris · {TODAY}
      </p>
    </div>
    <div style="background:#3b5bdb;padding:12px 32px;">
      <p style="margin:0;color:#fff;font-size:15px;">
        <strong>{len(offers)} offre(s)</strong> correspondent à ton profil aujourd'hui
      </p>
    </div>
    <div style="padding:24px 32px;">{body}</div>
    <div style="padding:16px 32px;text-align:center;font-size:11px;color:#aaa;">
      Source : France Travail · Profil : Chef de projet / PO · CDI · Paris · 2-5 ans
    </div>
  </div>
</body>
</html>"""


# ── Envoi email ───────────────────────────────────────────────────────
subject   = f"🔍 Offres du jour – Chef de Projet / PO CDI Paris – {TODAY} ({len(offers)} offre(s))"
html_body = build_html(offers)

msg = MIMEMultipart("alternative")
msg["Subject"] = subject
msg["From"]    = GMAIL_USER
msg["To"]      = RECIPIENT
msg.attach(MIMEText(html_body, "html"))

print(f"\nEnvoi email à {RECIPIENT}…")
with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(GMAIL_USER, GMAIL_PASS)
    server.sendmail(GMAIL_USER, RECIPIENT, msg.as_string())

print("✅ Email envoyé !")
