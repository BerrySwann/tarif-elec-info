"""Integration Tarif EDF - prix du tarif bleu et alerte avant changement.

Au demarrage :
 - lecture des prix TTC (grille publique du fournisseur, repli data.gouv), rafraichie toutes les 6 h ;
 - verification toutes les heures des deux echeances d alerte :
     * a J-N (defaut 9 jours) avant le 1er fevrier / le 1er aout : annonce ;
     * la veille au soir (defaut des 20 h) : rappel "ce soir minuit" ;
 - envoi sur le telephone choisi a l installation, et dans les notifications
   de Home Assistant dans tous les cas.
"""
from __future__ import annotations

import datetime
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store

from .const import (
    CONF_CONTRAT,
    CONF_HEURE_VEILLE,
    CONF_JOURS_AVANT,
    CONF_NOTIFY,
    CONF_PUISSANCE,
    DEFAUT_HEURE_VEILLE,
    DEFAUT_JOURS_AVANT,
    DOMAIN,
    NAME,
    SCAN_INTERVAL_H,
)
from .tariff import formate_prix, lit_prix, prochaine_date_effet

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]
STORAGE_KEY = "%s.etat" % DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Mise en place."""
    hass.data.setdefault(DOMAIN, {})

    options = {**entry.data, **entry.options}
    contrat = options.get(CONF_CONTRAT, "hphc")
    puissance = options.get(CONF_PUISSANCE, 6)

    async def _maj():
        try:
            prix = await hass.async_add_executor_job(lit_prix, contrat, puissance)
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed("lecture des prix impossible : %s" % err) from err
        return prix

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=NAME,
        update_method=_maj,
        update_interval=datetime.timedelta(hours=SCAN_INTERVAL_H),
    )
    await coordinator.async_config_entry_first_refresh()

    store = Store(hass, 1, STORAGE_KEY)
    etat = await store.async_load() or {}

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "store": store,
        "etat": etat,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _verifie(now=None):
        await _verifie_echeances(hass, entry, coordinator, store)

    entry.async_on_unload(async_track_time_interval(hass, _verifie, datetime.timedelta(hours=1)))
    hass.async_create_task(_verifie())

    entry.async_on_unload(entry.add_update_listener(_maj_options))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Dechargement."""
    decharge = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if decharge:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return decharge


async def _maj_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def _verifie_echeances(hass: HomeAssistant, entry: ConfigEntry, coordinator, store) -> None:
    """Deux alertes : a J-N et la veille au soir."""
    options = {**entry.data, **entry.options}
    jours_avant = int(options.get(CONF_JOURS_AVANT, DEFAUT_JOURS_AVANT))
    heure_veille = int(options.get(CONF_HEURE_VEILLE, DEFAUT_HEURE_VEILLE))
    notify_service = (options.get(CONF_NOTIFY) or "").strip()

    aujourd_hui = datetime.date.today()
    maintenant = datetime.datetime.now()
    date_effet = prochaine_date_effet(aujourd_hui)
    jours = (date_effet - aujourd_hui).days
    prix = coordinator.data or {}
    cle = date_effet.isoformat()

    etat = await store.async_load() or {}
    envois = []

    if jours == jours_avant and not etat.get("annonce_" + cle):
        envois.append(("annonce", cle, _message_annonce(date_effet, jours, prix)))
    if jours == 1 and maintenant.hour >= heure_veille and not etat.get("veille_" + cle):
        envois.append(("veille", cle, _message_veille(date_effet, prix)))

    for genre, cle_effet, message in envois:
        await _envoie(hass, notify_service, message)
        etat["%s_%s" % (genre, cle_effet)] = maintenant.isoformat(timespec="seconds")
        await store.async_save(etat)


def _message_annonce(date_effet: datetime.date, jours: int, prix: dict) -> str:
    debut = "Ton tarif EDF change dans %d jours, le %s." % (jours, date_effet.strftime("%d/%m/%Y"))
    if prix and prix.get("hp_kwh") is not None:
        return debut + " Prix lus a la source : %s. Source : %s." % (
            formate_prix(prix), prix.get("source", "inconnue"))
    return (debut + " Les prix ne sont pas encore publies a la source ; "
            "je te previenS des qu ils le sont.")


def _message_veille(date_effet: datetime.date, prix: dict) -> str:
    debut = ("A partir de ce soir minuit, le tarif passe aux nouvelles valeurs "
             "(effet %s)." % date_effet.strftime("%d/%m/%Y"))
    if prix and prix.get("hp_kwh") is not None:
        return debut + " %s." % formate_prix(prix)
    return debut + " La source n a pas encore publie les prix, je surveille."


async def _envoie(hass: HomeAssistant, notify_service: str, message: str) -> None:
    """Notification HA toujours, telephone en plus si configure."""
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {"title": "TarifElecInfo", "message": message, "notification_id": "tarif_edf_alerte"},
        blocking=False,
    )
    if not notify_service or "." not in notify_service:
        return
    domaine, service = notify_service.split(".", 1)
    try:
        await hass.services.async_call(domaine, service, {"message": message, "title": "TarifElecInfo"}, blocking=False)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("envoi sur %s impossible : %s", notify_service, err)
