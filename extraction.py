import os
import json
import time
from datetime import date
from dotenv import load_dotenv
from google import genai
from google.genai import types
import base

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Si le premier modèle est occupé, le programme essaie le suivant
MODELES = [
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
]

CONSIGNE = """Tu es l'assistant budget d'une femme en Côte d'Ivoire.
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


def analyser(message):
    consigne = CONSIGNE.format(aujourdhui=date.today().isoformat())
    derniere_erreur = None
    for modele in MODELES:
        for essai in range(2):
            try:
                reponse = client.models.generate_content(
                    model=modele,
                    contents=consigne + message,
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
                print("(modèle utilisé :", modele + ")")
                return json.loads(reponse.text)
            except Exception as e:
                derniere_erreur = e
                texte = str(e)
                if "503" in texte or "429" in texte:
                    time.sleep(2)
                    continue
                if "404" in texte:
                    break
                raise
        print("(" + modele + " est occupé, j'essaie un autre modèle...)")
    raise derniere_erreur


def completer_montant(operation):
    # Si le montant manque, on le demande à l'utilisatrice
    while operation.get("montant") is None:
        reponse = input("Combien pour '" + operation["description"] + "' ? ")
        try:
            operation["montant"] = float(reponse.replace(" ", "").replace(",", "."))
        except ValueError:
            print("Écris juste un nombre, par exemple 2500.")
    return operation


base.creer_table()

while True:
    message = input("Écris tes dépenses ou revenus (b = bilan, q = quitter) : ")
    if message.lower() == "q":
        break
    if message.lower() == "b":
        base.bilan()
        continue
    try:
        for operation in analyser(message):
            operation = completer_montant(operation)
            base.ajouter(operation)
            print("Enregistré :", operation)
    except Exception as e:
        print("ERREUR :", e)