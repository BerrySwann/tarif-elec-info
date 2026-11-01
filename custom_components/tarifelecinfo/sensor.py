"""Capteurs exposes par l integration Tarif EDF."""
from __future__ import annotations

from dataclasses import dataclass
import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CONTRAT, CONF_PUISSANCE, CONTRAT_LABELS, DOMAIN, NAME
from .tariff import prochaine_date_effet


@dataclass(frozen=True, kw_only=True)
class Desc(SensorEntityDescription):
    cle: str = ""


DESCRIPTIONS = (
    Desc(key="prix_hp", cle="hp_kwh", name="Tarif heures pleines",
         native_unit_of_measurement="%s/kWh" % CURRENCY_EURO,
         suggested_display_precision=4, state_class=SensorStateClass.MEASUREMENT,
         icon="mdi:flash"),
    Desc(key="prix_hc", cle="hc_kwh", name="Tarif heures creuses",
         native_unit_of_measurement="%s/kWh" % CURRENCY_EURO,
         suggested_display_precision=4, state_class=SensorStateClass.MEASUREMENT,
         icon="mdi:flash-off"),
    Desc(key="abonnement", cle="abonnement_mois", name="Abonnement mensuel",
         native_unit_of_measurement="%s/mois" % CURRENCY_EURO,
         suggested_display_precision=2,
         icon="mdi:calendar-month"),
    Desc(key="source", cle="__source", name="Source des prix", icon="mdi:database"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    donnees = hass.data[DOMAIN][entry.entry_id]
    coordinator = donnees["coordinator"]
    options = {**entry.data, **entry.options}
    async_add_entities(
        [TarifSensor(coordinator, entry, d) for d in DESCRIPTIONS]
        + [ProchainChangement(coordinator, entry), JoursRestants(coordinator, entry)]
        + [
            InfoAbonnement(entry, "puissance", "Puissance souscrite",
                           options.get(CONF_PUISSANCE), "kVA", "mdi:counter"),
            InfoAbonnement(entry, "option", "Option tarifaire",
                           CONTRAT_LABELS.get(options.get(CONF_CONTRAT), options.get(CONF_CONTRAT)),
                           None, "mdi:lightning-bolt"),
        ]
    )


class InfoAbonnement(SensorEntity):
    """Ce qui a ete choisi a l installation : puissance souscrite et option tarifaire."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry, cle, nom, valeur, unite, icone) -> None:
        self._attr_unique_id = "%s_info_%s" % (entry.entry_id, cle)
        self._attr_name = nom
        self._attr_native_value = valeur
        self._attr_icon = icone
        if unite:
            self._attr_native_unit_of_measurement = unite
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}, "name": NAME}


class TarifSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, description: Desc) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = "%s_%s" % (entry.entry_id, description.key)
        self._attr_name = description.name
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}, "name": NAME}

    @property
    def native_value(self):
        prix = self.coordinator.data or {}
        if self.entity_description.cle == "__source":
            return prix.get("source")
        return prix.get(self.entity_description.cle)


class ProchainChangement(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = "%s_prochain_changement" % entry.entry_id
        self._attr_name = "Prochain changement"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}, "name": NAME}

    @property
    def native_value(self):
        return prochaine_date_effet(datetime.date.today())


class JoursRestants(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "j"
    _attr_icon = "mdi:timer-sand"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = "%s_jours_restants" % entry.entry_id
        self._attr_name = "Jours avant changement"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}, "name": NAME}

    @property
    def native_value(self):
        return (prochaine_date_effet(datetime.date.today()) - datetime.date.today()).days
