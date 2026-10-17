import os
import calendar
import sqlite3
from datetime import date

NOM_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "budget.db")


def connexion():
    return sqlite3.connect(NOM_BASE)


def creer_table():
    c = connexion()
    c.execute("""CREATE TABLE IF NOT EXISTS operations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        montant REAL,
        categorie TEXT,
        description TEXT,
        date TEXT,
        recurrente INTEGER,
        nature TEXT)""")
    c.commit()
    c.close()


def ajouter(op):
    c = connexion()
    c.execute(
        "INSERT INTO operations (type, montant, categorie, description, date, recurrente, nature) VALUES (?,?,?,?,?,?,?)",
        (
            op.get("type"),
            op.get("montant"),
            op.get("categorie"),
            op.get("description"),
            op.get("date"),
            1 if op.get("recurrente") else 0,
            op.get("nature"),
        ),
    )
    c.commit()
    c.close()


def bilan():
    c = connexion()
    revenus = c.execute("SELECT COALESCE(SUM(montant), 0) FROM operations WHERE type = 'revenu'").fetchone()[0]
    depenses = c.execute("SELECT COALESCE(SUM(montant), 0) FROM operations WHERE type = 'depense'").fetchone()[0]
    par_categorie = c.execute(
        "SELECT categorie, SUM(montant) FROM operations WHERE type = 'depense' GROUP BY categorie ORDER BY SUM(montant) DESC"
    ).fetchall()
    c.close()
    print("--- BILAN ---")
    print("Revenus  :", int(revenus), "FCFA")
    print("Dépenses :", int(depenses), "FCFA")
    print("Reste    :", int(revenus - depenses), "FCFA")
    for categorie, total in par_categorie:
        print("  -", categorie, ":", int(total), "FCFA")
    prevision()


def prevision(aujourdhui=None):
    aujourdhui = aujourdhui or date.today()
    mois = aujourdhui.strftime("%Y-%m")
    jours_ecoules = aujourdhui.day
    jours_du_mois = calendar.monthrange(aujourdhui.year, aujourdhui.month)[1]

    c = connexion()
    revenus = c.execute(
        "SELECT COALESCE(SUM(montant), 0) FROM operations WHERE type = 'revenu' AND date LIKE ?",
        (mois + "%",),
    ).fetchone()[0]
    fixes = c.execute(
        "SELECT COALESCE(SUM(montant), 0) FROM operations WHERE type = 'depense' AND recurrente = 1 AND date LIKE ?",
        (mois + "%",),
    ).fetchone()[0]
    variables = c.execute(
        "SELECT COALESCE(SUM(montant), 0) FROM operations WHERE type = 'depense' AND recurrente = 0 AND date LIKE ?",
        (mois + "%",),
    ).fetchone()[0]
    c.close()

    variables_prevues = variables / jours_ecoules * jours_du_mois
    reste_prevu = revenus - fixes - variables_prevues

    print("--- PRÉVISION DE FIN DE MOIS ---")
    print("Revenus du mois                  :", int(revenus), "FCFA")
    print("Dépenses qui reviennent (loyer...):", int(fixes), "FCFA")
    print("Autres dépenses jusqu'ici         :", int(variables), "FCFA (en", jours_ecoules, "jours)")
    print("Autres dépenses prévues (au total):", int(variables_prevues), "FCFA")
    print("Il te restera environ             :", int(reste_prevu), "FCFA")
    if reste_prevu < 0:
        print("Attention : à ce rythme, tu dépenseras plus que tes revenus.")