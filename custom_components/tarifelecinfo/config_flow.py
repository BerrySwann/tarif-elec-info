"""Configuration de l integration Tarif EDF.

Parcours impose a l installation :
 1. l utilisateur choisit son abonnement (option tarifaire + puissance) ;
 2. une etape lui affiche les prix lus a la source, avec leur date d effet ;
 3. une etape lui demande sur quel telephone envoyer les alertes : un seul
    telephone = preselectionne, plusieurs = choix obligatoire, aucun = on continue
    mais on le rappelle dans les notifications.
"""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_CONTRAT,
    CONF_HEURE_VEILLE,
    CONF_JOURS_AVANT,
    CONF_NOTIFY,
    CONF_PUISSANCE,
    CONTRAT_LABELS,
    CONTRATS,
    DEFAUT_HEURE_VEILLE,
    DEFAUT_JOURS_AVANT,
    DOMAIN,
    NAME,
    PUISSANCES,
)
from .tariff import formate_prix, lit_prix

_LOGGER = logging.getLogger(__name__)


def telefones(hass) -> list[str]:
    """Services notify.* qui ressemblent a un telephone (application mobile)."""
    trouves = []
    for domaine, services in hass.services.async_services().items():
        if domaine != "notify":
            continue
        for nom in services:
            if nom.startswith("mobile_app_"):
                trouves.append("notify.%s" % nom)
    return sorted(trouves)


class TarifEdfConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Etape par etape."""

    VERSION = 1

    def __init__(self) -> None:
        self._donnees: dict = {}
        self._prix: dict | None = None

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            self._donnees.update(user_input)
            return await self.async_step_prix()
        schema = vol.Schema(
            {
                vol.Required(CONF_CONTRAT, default="hphc"): vol.In(
                    {c: CONTRAT_LABELS.get(c, c) for c in CONTRATS}
                ),
                vol.Required(CONF_PUISSANCE, default=6): vol.In(PUISSANCES),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_prix(self, user_input=None) -> FlowResult:
        """Premier ecran d information : les prix en vigueur, lus a la source."""
        if user_input is not None:
            return await self.async_step_notif()

        if self._prix is None:
            self._prix = await self.hass.async_add_executor_job(
                lit_prix, self._donnees.get(CONF_CONTRAT, "hphc"), self._donnees.get(CONF_PUISSANCE, 6)
            )
        prix = self._prix or {}
        if prix.get("date_effet"):
            depuis = "Depuis le %s" % prix["date_effet"]
        else:
            depuis = "Prix en vigueur (date d effet non fournie par la source)"
        source = prix.get("source") or "source indisponible"
        texte = "%s : %s. Source : %s." % (depuis, formate_prix(prix), source)
        if not prix:
            texte = (
                "Les prix n ont pas pu etre lus a la source pour le moment. "
                "L integration les relira toutes les 6 heures et les publiera des qu elle les aura."
            )
        return self.async_show_form(
            step_id="prix",
            data_schema=vol.Schema({}),
            description_placeholders={"prix": texte},
        )

    async def async_step_notif(self, user_input=None) -> FlowResult:
        """Deuxieme ecran : sur quel telephone prevenir."""
        telephones = telefones(self.hass)
        if user_input is not None:
            choix = user_input.get(CONF_NOTIFY) or ""
            if telephones and not choix:
                return self.async_show_form(
                    step_id="notif",
                    data_schema=self._schema_notif(telephones),
                    errors={CONF_NOTIFY: "telephone_obligatoire"},
                    description_placeholders={"details": "Choisis un telephone dans la liste."},
                )
            self._donnees[CONF_NOTIFY] = choix
            self._donnees[CONF_JOURS_AVANT] = DEFAUT_JOURS_AVANT
            self._donnees[CONF_HEURE_VEILLE] = DEFAUT_HEURE_VEILLE
            await self.async_set_unique_id(
                "%s_%s_%s" % (self._donnees[CONF_CONTRAT], self._donnees[CONF_PUISSANCE], choix or "sans_telephone")
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=NAME, data=self._donnees)

        if not telephones:
            details = (
                "Aucun telephone n est enregistre dans Home Assistant. Tu peux continuer : les alertes "
                "s afficheront dans les notifications de Home Assistant. Ajoute l application mobile puis "
                "reviens dans Options pour recevoir aussi sur le telephone."
            )
        elif len(telephones) == 1:
            details = "Un seul telephone detecte : il est preselectionne."
        else:
            details = "Plusieurs telephones detectes : choisis celui qui doit recevoir les alertes."
        return self.async_show_form(
            step_id="notif",
            data_schema=self._schema_notif(telephones),
            description_placeholders={"details": details},
        )

    def _schema_notif(self, telephones: list[str]):
        if not telephones:
            return vol.Schema({})
        defaut = telephones[0] if len(telephones) == 1 else None
        if defaut:
            return vol.Schema({vol.Required(CONF_NOTIFY, default=defaut): vol.In(telephones)})
        return vol.Schema({vol.Required(CONF_NOTIFY): vol.In(telephones)})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TarifEdfOptionsFlow(config_entry)


class TarifEdfOptionsFlow(config_entries.OptionsFlow):
    """Modifier le telephone, le delai d annonce et l heure du rappel."""

    def __init__(self, config_entry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        telephones = telefones(self.hass)
        actuel = {**self._entry.data, **self._entry.options}
        if user_input is not None:
            choix = user_input.get(CONF_NOTIFY) or ""
            if telephones and not choix:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._schema(telephones, actuel),
                    errors={CONF_NOTIFY: "telephone_obligatoire"},
                )
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="init", data_schema=self._schema(telephones, actuel))

    def _schema(self, telephones, actuel):
        champs = {
            vol.Optional(CONF_JOURS_AVANT, default=actuel.get(CONF_JOURS_AVANT, DEFAUT_JOURS_AVANT)):
                vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
            vol.Optional(CONF_HEURE_VEILLE, default=actuel.get(CONF_HEURE_VEILLE, DEFAUT_HEURE_VEILLE)):
                vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
        }
        if telephones:
            options = [""] + telephones
            champs[vol.Optional(CONF_NOTIFY, default=actuel.get(CONF_NOTIFY, ""))] = vol.In(options)
        return vol.Schema(champs)
