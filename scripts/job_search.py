#!/usr/bin/env python3
"""
Recherche quotidienne d'offres d'emploi – Chef de projet / PO CDI Paris
Utilise DuckDuckGo (recherche web sans API ni compte).
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

# ── Configuration ─────────────────────────────────────────────────────────────
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
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Referer": "https://duckduckgo.com/",
}

QUERIES = [
    '"chef de projet" CDI Paris recrutement -stage -alternance',
    '"product owner" CDI Paris recrutement -stage -alternance',
    '"chef de projet" CDI "île-de-france" grande entreprise',
]

JOB_SITES = {
    "welcometothejungle.com": "Welcome to the Jungle",
    "indeed.fr":              "Indeed",
    "linkedin.com/jobs":      "LinkedIn",
    "apec.fr":                "APEC",
    "hellowork.com":          "HelloWork",
    "francetravail.fr":       "France Travail",
    "monster.fr":             "Monster",
    "cadremploi.fr":          "Cadremploi",
    "jobteaser.com":          "JobTeaser",
}

# ── Recherche DuckDuckGo ──────────────────────────────────────────────────────
def ddg_search(query: str) -> list[dict]:
    """Recherche sur DuckDuckGo Lite et retourne les résultats."""
    params = urlencode({"q": query, "kl": "fr-fr"})
    url = f"https://lite.duckduckgo.com/lite/?{params}"
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except URLError as e:
        print(f"  ⚠ Erreur DDG : {e}")
        return []

    print(f"  HTML reçu : {len(html)} chars")

    results = []
    # DDG Lite : les liens sont dans des <a class="result-link">
    for m in re.finditer(
        r'<a[^>]+class="result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html, re.DOTALL | re.IGNORECASE
    ):
        link  = m.group(1).strip()
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        title = re.sub(r"\s+", " ", title)
        if link.startswith("http") and title:
            results.append({"title": title, "url": link})

    print(f"  → {len(results)} résultats bruts")
    return results


def is_job_site(url: str) -> str | None:
    """Retourne le nom du site si c'est un site d'emploi connu."""
    for domain, name in JOB_SITES.items():
        if domain in url:
            return name
    return None


# ── Collecte ──────────────────────────────────────────────────────────────────
raw_results: list[dict] = []

for query in QUERIES:
    print(f"\nRecherche DDG : {query!r}")
    for r in ddg_search(query):
        source = is_job_site(r["url"])
        if source:
            r["source"] = source
            raw_results.append(r)

# Dédupliquer par URL
unique: dict[str, dict] = {}
for r in raw_results:
    if r["url"] not in unique:
        unique[r["url"]] = r

offers = list(unique.values())
print(f"\nTotal offres sur sites emploi : {len(offers)}")

# ── Email HTML ────────────────────────────────────────────────────────────────
def fmt_offer(o: dict) -> str:
    return f"""
    <div style="background:#fff;border:1px solid #e0e0e0;border-radius:8px;
                padding:16px 20px;margin-bottom:14px;">
      <p style="margin:0 0 4px;font-size:11px;color:#888;text-transform:uppercase;
                letter-spacing:.5px;">{o.get('source','Web')}</p>
      <h3 style="margin:0 0 8px;font-size:16px;">
        <a href="{o['url']}" style="color:#3b5bdb;text-decoration:none;">{o['title']}</a>
      </h3>
      <a href="{o['url']}" style="display:inline-block;padding:6px 14px;
         background:#3b5bdb;color:#fff;border-radius:5px;text-decoration:none;
         font-size:13px;">Voir l'offre →</a>
    </div>"""


def build_html(offers: list[dict]) -> str:
    body = "".join(fmt_offer(o) for o in offers) if offers else (
        '<p style="font-size:16px;color:#555;">Aucune offre trouvée aujourd\'hui.</p>'
    )
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f6fb;font-family:-apple-system,Arial,sans-serif;">
  <div style="max-width:640px;margin:30px auto;">
    <div style="background:#1a1a2e;border-radius:10px 10px 0 0;padding:28px 32px;">
      <h1 style="margin:0;color:#fff;font-size:22px;">🔍 Offres du jour</h1>
      <p style="margin:6px 0 0;color:#a0aec0;font-size:14px;">
        Chef de Projet / PO · CDI · Paris · {TODAY}</p>
    </div>
    <div style="background:#3b5bdb;padding:12px 32px;">
      <p style="margin:0;color:#fff;font-size:15px;">
        <strong>{len(offers)} offre(s)</strong> trouvées sur le web aujourd'hui</p>
    </div>
    <div style="padding:24px 32px;">{body}</div>
    <div style="padding:16px 32px;text-align:center;font-size:11px;color:#aaa;">
      Sources : LinkedIn · WTTJ · Indeed · APEC · Cadremploi · France Travail
    </div>
  </div>
</body></html>"""


# ── Envoi ─────────────────────────────────────────────────────────────────────
subject   = f"🔍 Offres du jour – Chef de Projet/PO CDI Paris – {TODAY} ({len(offers)} offre(s))"
html_body = build_html(offers)

msg = MIMEMultipart("alternative")
msg["Subject"] = subject
msg["From"]    = GMAIL_USER
msg["To"]      = RECIPIENT
msg.attach(MIMEText(html_body, "html"))

print(f"\nEnvoi à {RECIPIENT}…")
with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(GMAIL_USER, GMAIL_PASS)
    server.sendmail(GMAIL_USER, RECIPIENT, msg.as_string())
print("✅ Email envoyé !")
