#!/usr/bin/env python3
"""
Recherche quotidienne d'offres d'emploi – Chef de projet / PO CDI Paris
Utilise l'API officielle France Travail (francetravail.io)
Envoie un résumé par email chaque matin.
"""

import smtplib
import urllib.request
import urllib.parse
import os
import re
import json
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── Configuration ─────────────────────────────────────────────────────────────
GMAIL_USER = "adenikgnigla@gmail.com"
GMAIL_PASS = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT  = "adenikgnigla@gmail.com"

FT_CLIENT_ID     = os.environ["FRANCE_TRAVAIL_CLIENT_ID"]
FT_CLIENT_SECRET = os.environ["FRANCE_TRAVAIL_CLIENT_SECRET"]

PARIS_TIME = timezone(timedelta(hours=2))
TODAY      = datetime.now(PARIS_TIME).strftime("%d/%m/%Y")

# ── Auth France Travail (OAuth2 client_credentials) ───────────────────────────
def get_access_token() -> str:
    url  = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
    body = urllib.parse.urlencode({
        "grant_type":    "client_credentials",
        "client_id":     FT_CLIENT_ID,
        "client_secret": FT_CLIENT_SECRET,
        "scope":         "api_offresdemploiv2 o2dsoffre",
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())["access_token"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Erreur auth France Travail ({e.code}): {body}")
        raise

# ── Recherche d'offres ────────────────────────────────────────────────────────
def search_offers(token: str, keywords: str) -> list[dict]:
    """Appelle l'API France Travail et retourne une liste d'offres."""
    params = urllib.parse.urlencode({
        "motsCles":      keywords,
        "typeContrat":   "CDI",
        "departement":   "75",          # Paris (ajouter 92,93,94 si besoin)
        "publieeDepuis": "1",           # dernières 24h
        "sort":          "1",           # tri par date
        "range":         "0-49",
    })
    url = f"https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search?{params}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return data.get("resultats", [])
    except Exception as exc:
        print(f"  ⚠ Erreur API ({keywords}) : {exc}")
        return []

# ── Collecte ──────────────────────────────────────────────────────────────────
print("Obtention du token France Travail…")
token = get_access_token()
print("Token OK")

all_raw: list[dict] = []
for kw in ["chef de projet", "product owner"]:
    print(f"Recherche : {kw!r}…")
    results = search_offers(token, kw)
    print(f"  → {len(results)} offre(s)")
    all_raw.extend(results)

# Dédupliquer par ID
unique: dict[str, dict] = {}
for o in all_raw:
    oid = o.get("id", o.get("intitule", ""))
    if oid not in unique:
        unique[oid] = o

offers = list(unique.values())
print(f"\nTotal unique : {len(offers)} offre(s)")

# ── Formatage de l'email HTML ─────────────────────────────────────────────────
def fmt_offer(o: dict) -> str:
    title      = o.get("intitule", "Offre sans titre")
    company    = o.get("entreprise", {}).get("nom", "Entreprise non précisée")
    lieu       = o.get("lieuTravail", {}).get("libelle", "Paris")
    contrat    = o.get("typeContratLibelle", "CDI")
    desc_raw   = o.get("description", "")
    desc       = re.sub(r"\s+", " ", desc_raw).strip()[:280]
    url        = f"https://candidat.francetravail.fr/offres/recherche/detail/{o.get('id', '')}"

    return f"""
    <div style="background:#fff; border:1px solid #e0e0e0; border-radius:8px;
                padding:16px 20px; margin-bottom:16px;">
      <p style="margin:0 0 4px 0; font-size:11px; color:#888; text-transform:uppercase;
                letter-spacing:.5px;">France Travail</p>
      <h3 style="margin:0 0 6px 0; font-size:16px; color:#1a1a2e;">
        <a href="{url}" style="color:#3b5bdb; text-decoration:none;">{title}</a>
      </h3>
      <p style="margin:0 0 6px 0; font-size:13px; color:#444;">
        🏢 {company} &nbsp;·&nbsp; 📍 {lieu} &nbsp;·&nbsp; 📄 {contrat}
      </p>
      <p style="margin:0; font-size:13px; color:#555; line-height:1.5;">{desc}…</p>
      <a href="{url}" style="display:inline-block; margin-top:10px; padding:7px 16px;
         background:#3b5bdb; color:#fff; border-radius:5px; text-decoration:none;
         font-size:13px;">Voir l'offre →</a>
    </div>"""


def build_html(offers: list[dict]) -> str:
    if not offers:
        body = """<p style="font-size:16px; color:#555;">
          Aucune nouvelle offre aujourd'hui. Reviens demain !</p>"""
    else:
        body = "".join(fmt_offer(o) for o in offers)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f6fb;font-family:-apple-system,Arial,sans-serif;">
  <div style="max-width:640px;margin:30px auto;background:#f4f6fb;">

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
      Source : France Travail (francetravail.fr) &nbsp;|&nbsp;
      Profil : Chef de projet / PO · CDI · Paris · Grande entreprise · 2-5 ans
    </div>

  </div>
</body>
</html>"""


# ── Envoi ─────────────────────────────────────────────────────────────────────
subject  = f"🔍 Offres du jour – Chef de Projet / PO CDI Paris – {TODAY} ({len(offers)} offre(s))"
html_body = build_html(offers)

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
