"""Constantes de l integration Tarif EDF."""

DOMAIN = "tarifelecinfo"
NAME = "TarifElecInfo"

CONF_CONTRAT = "contrat"
CONF_PUISSANCE = "puissance"
CONF_NOTIFY = "notify_service"
CONF_JOURS_AVANT = "jours_avant"
CONF_HEURE_VEILLE = "heure_veille"

CONTRATS = ["hphc", "base", "tempo"]
CONTRAT_LABELS = {
    "hphc": "Heures pleines / Heures creuses",
    "base": "Option Base (prix unique)",
    "tempo": "Tempo",
}
PUISSANCES = [3, 6, 9, 12, 15, 18, 24, 30, 36]

DEFAUT_JOURS_AVANT = 9
DEFAUT_HEURE_VEILLE = 20

URL_GRILLE_FOURNISSEUR = ("https://particulier.edf.fr/content/dam/2-Actifs/Documents/Offres/"
               "Grille_prix_Tarif_Bleu.pdf")
URL_CRE_DELIB = ("https://www.cre.fr/documents/deliberations/"
                 "tarifs-reglementes-de-vente-delectricite-en-france-metropolitaine-continentale-"
                 "et-en-zones-non-interconnectees.html")
URL_GOUV_HPHC = "https://www.data.gouv.fr/fr/datasets/r/f7303b3a-93c7-4242-813d-84919034c416"
URL_GOUV_BASE = "https://www.data.gouv.fr/fr/datasets/r/c13d05e5-9e55-4d03-bf7e-042a2ade7e49"

SCAN_INTERVAL_H = 6
