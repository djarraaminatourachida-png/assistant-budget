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

DOSSIER = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(DOSSIER, ".env"))
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Si le premier modèle est occupé, le programme essaie le suivant
MODELES = [
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
]

CONSIGNE_EXTRACTION = """Tu es l'assistant budget d'une femme en Côte d'Ivoire.
Tu l'aides à organiser son budget, anticiper ses dépenses et prendre de meilleures décisions financières.
Aujourd'hui, nous sommes le {aujourdhui}.

Lis son message et extrais TOUTES les opérations d'argent qu'il contient (il peut y en avoir plusieurs).
Réponds uniquement en JSON : une liste d'objets, un par opération, avec ces champs :
- type : "depense" si elle dépense ou envoie de l'argent, "revenu" si elle reçoit de l'argent
- montant : nombre entier en FCFA. La lettre k veut dire mille (2k = 2000, 2,5k = 2500, 15k = 15000). Les espaces ou les points séparent les milliers (2 500 ou 2.500 = 2500). Si le montant n'est pas dit, mets null. N'invente JAMAIS un montant.
- categorie : une seule, qui dépend du type.
  Si type = "depense" : transport, nourriture, logement, communication, sante, beaute, vetements, loisirs, education, commerce, famille, epargne, autre
  (beaute = coiffure, cheveux, tresses, ongles, maquillage, soins ; epargne = argent mis de côté, cotisation de tontine)
  Si type = "revenu" : salaire, ventes, aide_famille, bourse, tontine, autre_revenu
  (ventes = une cliente qui paie une commande ou un achat ; aide_famille = argent reçu de la famille ou d'un proche ; tontine = pot de tontine reçu)
- description : phrase très courte
- date : au format AAAA-MM-JJ (déduis "hier", "lundi"... depuis la date d'aujourd'hui ; sans précision, utilise la date d'aujourd'hui)
- recurrente : true si cela revient régulièrement (loyer, abonnement, tontine, forfait, salaire...), sinon false
- nature : pour une dépense, "besoin" (utile ou indispensable) ou "envie" (plaisir, non essentiel) ; pour un revenu, mets null

Si le message ne contient aucune opération d'argent, réponds par une liste vide [].

Message : """

CONSIGNE_CHAT = """Tu es l'assistant budget d'une femme en Côte d'Ivoire. Tu l'aides à organiser son argent et à prendre de meilleures décisions financières. Tu es bienveillant, clair et respectueux.

Voici ses chiffres du mois, déjà calculés par le programme :
{chiffres}

Règles sur les chiffres :
- Utilise UNIQUEMENT ces chiffres. Ne calcule rien toi-même et n'invente aucun chiffre.
- Si "prix_achat" est null, demande-lui simplement le prix (tu ne devines pas les prix).
- Compare "reste_prevu_apres_achat" et "reste_actuel_apres_achat" pour décider.

Règles sur le ton :
- Tutoie-la, parle simplement et avec chaleur. Pas de blagues, pas de moquerie, aucun jugement. Pas d'émojis.
- Ta première phrase donne CLAIREMENT ton verdict : elle peut acheter, c'est risqué, ou il vaut mieux attendre.
- Explique ensuite en une ou deux phrases pourquoi, avec ses chiffres (ce qu'il lui resterait, ou ce qui manque).
- S'il y a beaucoup d'envies ("envies_ce_mois"), dis-le avec douceur et propose d'en reporter une.
- Si "reste_actuel" est négatif, elle est en difficulté : sois encore plus doux et propose une seule action simple.
- Réponds en 3 ou 4 phrases courtes. Termine par un conseil concret. Ne parle pas d'investissement ni de crédit.

Sa question : """


def generer(contenu, en_json=False):
    """Appelle Gemini. Si un modèle est occupé, essaie le suivant."""
    config = types.GenerateContentConfig(response_mime_type="application/json") if en_json else None
    derniere_erreur = None
    for modele in MODELES:
        for essai in range(2):
            try:
                reponse = client.models.generate_content(model=modele, contents=contenu, config=config)
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


def analyser(message):
    consigne = CONSIGNE_EXTRACTION.format(aujourdhui=date.today().isoformat())
    donnees = json.loads(generer(consigne + message, en_json=True))
    if isinstance(donnees, dict):
        donnees = [donnees]
    return donnees


def lire_montant(texte):
    t = texte.lower().replace(" ", " ")
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*k\b", t)
    if m:
        return int(float(m.group(1).replace(",", ".")) * 1000)
    m = re.search(r"(\d[\d \.]*\d|\d)", t)
    if m:
        return int(re.sub(r"[ \.]", "", m.group(1)))
    return None


def donnees_du_mois():
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
    lignes = c.execute(
        "SELECT categorie, SUM(montant) FROM operations WHERE type = 'depense' AND date LIKE ? GROUP BY categorie ORDER BY SUM(montant) DESC",
        (mois + "%",),
    ).fetchall()
    c.close()

    variables_prevues = variables / aujourdhui.day * jours_du_mois
    return {
        "revenus": revenus,
        "depenses": depenses,
        "reste_actuel": revenus - depenses,
        "fixes": fixes,
        "variables": variables,
        "variables_prevues": variables_prevues,
        "reste_prevu": revenus - fixes - variables_prevues,
        "envies": envies,
        "jours_restants": jours_du_mois - aujourdhui.day,
        "par_categorie": {categorie: total for categorie, total in lignes},
    }


def chiffres(question):
    d = donnees_du_mois()
    prix = lire_montant(question)
    return {
        "jours_restants_dans_le_mois": d["jours_restants"],
        "revenus_ce_mois": int(d["revenus"]),
        "depenses_ce_mois": int(d["depenses"]),
        "reste_actuel": int(d["reste_actuel"]),
        "reste_prevu_fin_de_mois": int(d["reste_prevu"]),
        "envies_ce_mois": int(d["envies"]),
        "prix_achat": prix,
        "reste_actuel_apres_achat": int(d["reste_actuel"] - prix) if prix else None,
        "reste_prevu_apres_achat": int(d["reste_prevu"] - prix) if prix else None,
    }


def repondre(question):
    consigne = CONSIGNE_CHAT.format(chiffres=json.dumps(chiffres(question), ensure_ascii=False, indent=2))
    return generer(consigne + question)


def dernieres_operations(limite=15):
    c = base.connexion()
    lignes = c.execute(
        "SELECT id, date, description, categorie, nature, type, montant FROM operations ORDER BY id DESC LIMIT ?",
        (limite,),
    ).fetchall()
    c.close()
    return lignes


def supprimer_operation(identifiant):
    c = base.connexion()
    c.execute("DELETE FROM operations WHERE id = ?", (identifiant,))
    c.commit()
    c.close()


def tout_effacer():
    c = base.connexion()
    c.execute("DELETE FROM operations")
    c.commit()
    c.close()