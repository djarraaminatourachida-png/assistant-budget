

import time
from datetime import date
 
import pandas as pd
import streamlit as st
 
import base
import moteur
 
st.set_page_config(page_title="Mon budget", page_icon="💰")
base.creer_table()
 
for cle, valeur in {"chat": [], "en_attente": [], "message": None}.items():
    if cle not in st.session_state:
        st.session_state[cle] = valeur
 
 
def fcfa(n):
    return f"{int(n):,}".replace(",", " ") + " FCFA"
 
 
if st.session_state.message:
    st.success(st.session_state.message)
    st.session_state.message = None
 
d = moteur.donnees_du_mois()
 
# ---------- En-tête et bilan ----------
st.caption("Mois en cours : " + date.today().strftime("%m/%Y"))
st.title("Mon budget")
 
st.metric("Il te reste ce mois-ci", fcfa(d["reste_actuel"]))
part = min(max(d["depenses"] / d["revenus"], 0.0), 1.0) if d["revenus"] else 0.0
st.progress(part, text="Dépensé : " + fcfa(d["depenses"]) + " sur " + fcfa(d["revenus"]))
 
if not d["revenus"]:
    st.info("Ajoute un revenu pour voir ta prévision de fin de mois.")
elif d["reste_prevu"] < 0:
    st.warning("Prévision de fin de mois : à ce rythme, tu dépenseras plus que tes revenus (il manquerait environ " + fcfa(-d["reste_prevu"]) + ").")
else:
    st.info("Prévision de fin de mois : à ce rythme, il te restera environ " + fcfa(d["reste_prevu"]) + ".")
 
# ---------- Saisie ----------
st.subheader("Ajouter une dépense ou un revenu")
with st.form("saisie", clear_on_submit=True):
    texte = st.text_input("Écris comme tu parles", placeholder="Ex : j'ai payé 2,5k de taxi")
    envoyer = st.form_submit_button("Ajouter")
 
if envoyer and texte.strip():
    operations = None
    try:
        with st.spinner("Je lis ta phrase..."):
            operations = moteur.analyser(texte)
    except Exception as e:
        st.error("Je n'ai pas réussi à lire ta phrase. Réessaie dans un instant.")
        with st.expander("Détail de l'erreur"):
            st.write(str(e))
    if operations is not None:
        if not operations:
            st.warning("Je n'ai trouvé ni dépense ni revenu dans ta phrase.")
        else:
            enregistrees = []
            for op in operations:
                if op.get("montant") is None:
                    op["_id"] = time.time_ns()
                    st.session_state.en_attente.append(op)
                else:
                    base.ajouter(op)
                    enregistrees.append(op)
            if enregistrees:
                st.session_state.message = "Enregistré : " + ", ".join(
                    str(o.get("description")) + " (" + fcfa(o["montant"]) + ")" for o in enregistrees
                )
            st.rerun()
 
# ---------- Montants manquants ----------
if st.session_state.en_attente:
    st.subheader("Il me manque un montant")
    with st.form("montants"):
        valeurs = []
        for op in st.session_state.en_attente:
            valeurs.append(
                st.number_input(
                    "Combien pour « " + str(op.get("description")) + " » ?",
                    min_value=0,
                    step=500,
                    key="montant_" + str(op["_id"]),
                )
            )
        confirmer = st.form_submit_button("Enregistrer")
    if confirmer:
        restantes = []
        for op, valeur in zip(st.session_state.en_attente, valeurs):
            if valeur > 0:
                op["montant"] = valeur
                base.ajouter(op)
            else:
                restantes.append(op)
        st.session_state.en_attente = restantes
        st.session_state.message = "Enregistré."
        st.rerun()
 
# ---------- Dernières opérations ----------
st.subheader("Dernières opérations")
lignes = moteur.dernieres_operations()
if lignes:
    df = pd.DataFrame(lignes, columns=["id", "date", "description", "categorie", "nature", "type", "montant"])
    df["montant"] = df.apply(lambda r: -r["montant"] if r["type"] == "depense" else r["montant"], axis=1)
    st.dataframe(df[["date", "description", "categorie", "nature", "montant"]], hide_index=True)
else:
    st.caption("Aucune opération pour l'instant. Écris ta première dépense ci-dessus.")
 
# ---------- Graphique ----------
if d["par_categorie"]:
    st.subheader("Où va ton argent ?")
    st.bar_chart(pd.Series(d["par_categorie"]))
 
# ---------- Corriger ----------
with st.expander("Corriger ou supprimer"):
    if lignes:
        choix = {}
        for l in lignes:
            choix[str(l[1]) + " · " + str(l[2]) + " · " + fcfa(l[6])] = l[0]
        etiquette = st.selectbox("Quelle opération ?", list(choix.keys()))
        if st.button("Supprimer cette opération"):
            moteur.supprimer_operation(choix[etiquette])
            st.session_state.message = "Opération supprimée."
            st.rerun()
    sure = st.checkbox("Je veux effacer toutes les données de test")
    if st.button("Tout effacer") and sure:
        moteur.tout_effacer()
        st.session_state.message = "Toutes les opérations ont été effacées."
        st.rerun()
 
# ---------- Chat ----------
st.subheader("Demande à ton assistant")
for m in st.session_state.chat:
    with st.chat_message(m["role"]):
        st.write(m["content"])
 
question = st.chat_input("Ex : puis-je acheter un sac à 20000 ?")
if question:
    st.session_state.chat.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Je regarde tes chiffres..."):
                reponse = moteur.repondre(question)
        except Exception:
            reponse = "Oups, je n'arrive pas à répondre pour l'instant. Réessaie dans un instant."
        st.write(reponse)
    st.session_state.chat.append({"role": "assistant", "content": reponse})
 

