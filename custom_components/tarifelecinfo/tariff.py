"""Lecture des prix du tarif bleu.

Deux sources, dans cet ordre :
1. la grille de prix publique du fournisseur (PDF) : ce sont les prix TTC, les seuls qui correspondent
   a ce que le client paie. Lecture par position avec pymupdf.
2. le fichier public du contrat (CSV) : utilise si pymupdf est absent. Il donne
   le HT et le TTC, mais il est publie avec du retard.
"""
from __future__ import annotations

import csv
import io
import logging
import re
import urllib.request

from homeassistant.util import Throttle
import datetime

from .const import URL_GRILLE_FOURNISSEUR, URL_GOUV_BASE, URL_GOUV_HPHC

_LOGGER = logging.getLogger(__name__)

UA = {"User-Agent": "Mozilla/5.0 (compatible; HA-tarif-edf-alerte)"}


def _telecharge(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as rep:
        return rep.read()


def lit_grille_edf(puissance: int = 6) -> dict | None:
    """Prix TTC lus dans la grille publique du fournisseur, ou None si on ne sait pas lire le PDF."""
    try:
        import pymupdf
    except ImportError:
        _LOGGER.warning("pymupdf absent : lecture de la grille publique du fournisseur impossible")
        return None
    try:
        data = _telecharge(URL_GRILLE_FOURNISSEUR, 120)
        doc = pymupdf.open(stream=data, filetype="pdf")
        page = doc[0]
        mots = page.get_text("words")

        def centre(w):
            return (w[0] + w[2]) / 2.0

        entete = [w for w in mots if 318 < w[1] < 340]
        pleines = [w for w in entete if w[4] == "Pleines"]
        creuses = [w for w in entete if w[4] == "Creuses"]
        if not pleines or not creuses:
            _LOGGER.warning("grille publique du fournisseur : en-tetes Pleines/Creuses introuvables")
            return None
        pleines.sort(key=lambda w: -w[0])
        creuses.sort(key=lambda w: -w[0])
        x_hp, x_hc = centre(pleines[0]), centre(creuses[0])

        lignes = [w for w in mots if re.fullmatch(r"\d{1,2}", w[4]) and 340 < w[0] < 400]
        cible = [w for w in lignes if w[4] == str(puissance)]
        if not cible:
            _LOGGER.warning("grille publique du fournisseur : puissance %s absente du tableau", puissance)
            return None
        y = cible[0][1]

        bande = [w for w in mots if abs(w[1] - y) < 8 and re.fullmatch(r"\d{1,3},\d{2}", w[4])]

        def valeur(xc, tol=25):
            trouve = [w for w in bande if abs(centre(w) - xc) < tol]
            return trouve[0][4] if trouve else None

        abo = [w for w in bande if 395 < centre(w) < 425]
        hp, hc = valeur(x_hp), valeur(x_hc)
        if not hp or not hc:
            return None
        resultat = {
            "source": "grille publique du fournisseur (TTC)",
            "puissance": puissance,
            "hp_kwh": float(hp.replace(",", ".")) / 100.0,
            "hc_kwh": float(hc.replace(",", ".")) / 100.0,
            "abonnement_mois": float(abo[0][4].replace(",", ".")) if abo else None,
            "date_effet": None,
            "ht_seulement": False,
        }
        doc.close()
        return resultat
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("grille publique du fournisseur illisible : %s", err)
        return None


def lit_data_gouv(contrat: str = "hphc", puissance: int = 6) -> dict | None:
    """Repli : fichier officiel data.gouv (mise a jour en retard, mais stable)."""
    url = URL_GOUV_HPHC if contrat == "hphc" else URL_GOUV_BASE
    try:
        txt = _telecharge(url).decode("utf-8", "replace")
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("data.gouv injoignable : %s", err)
        return None
    lecteur = csv.DictReader(io.StringIO(txt), delimiter=";")
    aujourd_hui = datetime.date.today()
    meilleure = None
    for ligne in lecteur:
        p = (ligne.get("P_SOUSCRITE") or "").strip()
        if p not in (str(puissance), "%d.0" % puissance):
            continue
        try:
            debut = datetime.datetime.strptime(ligne["DATE_DEBUT"].strip(), "%d/%m/%Y").date()
        except Exception:  # noqa: BLE001
            continue
        fin_txt = (ligne.get("DATE_FIN") or "").strip()
        try:
            fin = datetime.datetime.strptime(fin_txt, "%d/%m/%Y").date() if fin_txt else None
        except Exception:  # noqa: BLE001
            fin = None
        if debut <= aujourd_hui and (fin is None or aujourd_hui <= fin):
            if meilleure is None or debut > meilleure[0]:
                meilleure = (debut, ligne)
    if not meilleure:
        return None
    debut, ligne = meilleure

    def nombre(cle):
        v = (ligne.get(cle) or "").replace(",", ".").strip()
        try:
            return float(v) if v else None
        except ValueError:
            return None

    return {
        "source": "data.gouv",
        "puissance": puissance,
        "hp_kwh": nombre("PART_VARIABLE_HP_TTC"),
        "hc_kwh": nombre("PART_VARIABLE_HC_TTC"),
        "abonnement_mois": nombre("PART_FIXE_TTC"),
        "date_effet": debut.isoformat(),
        "ht_seulement": False,
    }


def lit_prix(contrat: str, puissance: int) -> dict | None:
    """Prix TTC : grille publique du fournisseur d abord, data.gouv en repli."""
    prix = lit_grille_edf(puissance)
    if prix and prix.get("hp_kwh"):
        prix["contrat"] = contrat
        return prix
    prix = lit_data_gouv(contrat, puissance)
    if prix:
        prix["contrat"] = contrat
    return prix


def prochaine_date_effet(aujourd_hui: datetime.date) -> datetime.date:
    candidats = []
    for annee in (aujourd_hui.year, aujourd_hui.year + 1):
        for mois in (2, 8):
            d = datetime.date(annee, mois, 1)
            if d > aujourd_hui:
                candidats.append(d)
    return min(candidats)


def formate_prix(prix: dict | None) -> str:
    if not prix or prix.get("hp_kwh") is None:
        return "prix indisponibles"
    return ("HP %.4f EUR/kWh, HC %.4f EUR/kWh" % (prix["hp_kwh"], prix["hc_kwh"]))
