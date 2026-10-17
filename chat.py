import os
import re
import json
import time
import calendar
from datetime import date
from dotenv import load_dotenv
from google import genai
from google.genai import types
import base

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODELES = [
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
]

CONSIGNE = """Tu es l'assistant budget d'une femme en Côte d'Ivoire. Tu l'aides à prendre de meilleures décisions financières.

Voici ses chiffres du mois, déjà calculés par le programme :
{chiffres}

Règles :
- Utilise UNIQUEMENT ces chiffres. Ne calcule rien toi-même et n'invente aucun chiffre.
- Si "prix_achat" est null, demande-lui simplement le prix.
- Compare "reste_prevu_apres_achat" et "reste_actuel_apres_achat" : dis-lui clairement si elle peut acheter, si c'est risqué, ou s'il vaut mieux attendre.
- S'il y a beaucoup d'envies ("envies_ce_mois"), tu peux le mentionner gentiment.
- Réponds en français simple, en la tutoyant, en 3 ou 4 phrases courtes.
- Termine par un conseil concret. Ne parle pas d'investissement ni de crédit.

Sa question : """


def lire_montant(texte):
    t = texte.lower().replace("\u202f", " ")
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*k\b", t)
    if m:
        return int(float(m.group(1).replace(",", ".")) * 1000)
    m = re.search(r"(\d[\d \.]*\d|\d)", t)
    if m:
        return int(re.sub(r"[ \.]", "", m.group(1)))
    return None


def chiffres(question):
    aujourdhui = date.today()
    mois = aujourdhui.strftime("%Y-%m")
    jours_du_mois = calendar.monthrange(aujourdhui.year, aujourdhui.month)[1]
    c = base.connexion()

    def somme(condition):
        requete = "SELECT COALESCE(SUM(montant), 0) FROM operations WHERE date LIKE ? AND " + condition
        return c.execute(requete, (mois + "%",)).fetchone()[0]

    revenus = somme("type = 'revenu'")
    depenses = somme("type = 'depense'")
    fixes = somme("type = 'depense' AND recurrente = 1")
    variables = somme("type = 'depense' AND recurrente = 0")
    envies = somme("type = 'depense' AND nature = 'envie'")
    c.close()

    variables_prevues = variables / aujourdhui.day * jours_du_mois
    reste_actuel = revenus - depenses
    reste_prevu = revenus - fixes - variables_prevues
    prix = lire_montant(question)

    return {
        "jours_restants_dans_le_mois": jours_du_mois - aujourdhui.day,
        "revenus_ce_mois": int(revenus),
        "depenses_ce_mois": int(depenses),
        "reste_actuel": int(reste_actuel),
        "reste_prevu_fin_de_mois": int(reste_prevu),
        "envies_ce_mois": int(envies),
        "prix_achat": prix,
        "reste_actuel_apres_achat": int(reste_actuel - prix) if prix else None,
        "reste_prevu_apres_achat": int(reste_prevu - prix) if prix else None,
    }


def repondre(question):
    donnees = chiffres(question)
    consigne = CONSIGNE.format(chiffres=json.dumps(donnees, ensure_ascii=False, indent=2))
    derniere_erreur = None
    for modele in MODELES:
        for essai in range(2):
            try:
                reponse = client.models.generate_content(
                    model=modele,
                    contents=consigne + question,
                )
                return reponse.text
            except Exception as e:
                derniere_erreur = e
                texte = str(e)
                if "503" in texte or "429" in texte:
                    time.sleep(2)
                    continue
                if "404" in texte:
                    break
                raise
    raise derniere_erreur


base.creer_table()

while True:
    question = input("Pose ta question (q pour quitter) : ")
    if question.lower() == "q":
        break
    try:
        print()
        print(repondre(question))
        print()
    except Exception as e:
        print("ERREUR :", e)