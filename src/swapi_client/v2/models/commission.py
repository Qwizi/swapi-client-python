"""
Commission model for SWAPI SDK.

Obsługuje:
- standardowe pola (id, name, status, itp. – przychodzą dynamicznie z JSON)
- attributes[]: lista słowników {id, type, value, ...}
- wygodny proxy do atrybutów: commission.attributes.get(id), .set(id, value)
- osobny save_attributes(), który PATCHuje tylko attributes
- dodatkowe metody domenowe: change_phase(), assign_user(), close(), reopen()
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import APIModel
from ..exceptions import SWAPIError


class AttributesProxy:
    """
    Proxy na attributes[] w Commission.

    Zamiast grzebać bezpośrednio w commission._attributes_by_id,
    używasz:

        commission.attributes.get(attr_id)
        commission.attributes.set(attr_id, value)
        commission.attributes.list()
    """

    def __init__(self, commission: "Commission") -> None:
        self._commission = commission

    def get(self, attr_id: int) -> Any:
        """
        Zwraca value dla danego attr_id lub None, jeśli go nie ma.
        """
        data = self._commission._attributes_by_id.get(attr_id)
        return data.get("value") if data else None

    def set(self, attr_id: int, value: Any) -> None:
        """
        Ustawia wartość atrybutu o zadanym ID.
        Zmiana trafia do buffora _attributes_dirty i zostanie wysłana
        przy wywołaniu Commission.save_attributes().
        """
        if attr_id not in self._commission._attributes_by_id:
            # Możesz to zmienić na silent ignore lub warning/log.
            raise KeyError(
                f"Attribute id={attr_id} does not exist on this Commission instance"
            )

        # Update _attributes_by_id immediately for in-memory reads
        existing_entry = self._commission._attributes_by_id[attr_id]
        # Preserve existing metadata (type, timestamps, etc.) and only update value
        updated_entry = dict(existing_entry)
        updated_entry["value"] = value
        self._commission._attributes_by_id[attr_id] = updated_entry

        # Record in _attributes_dirty for pending PATCH (replace/upsert, not duplicate)
        self._commission._attributes_dirty[attr_id] = value

    def list(self) -> List[Dict[str, Any]]:
        """
        Zwraca listę wszystkich atrybutów (surowe dicty).
        """
        return list(self._commission._attributes_by_id.values())


class Commission(APIModel):
    """
    Model Commission, reprezentujący zlecenie w SW API.

    Przykład użycia:

        from swapi_sdk import Commission, Q

        # lista otwartych zleceń
        open_comms = await Commission.objects().filter(status__eq="open").all()

        # jeden konkretny
        comm = await Commission.objects().get(123)

        # obsługa atrybutów
        current_val = comm.attributes.get(10)
        comm.attributes.set(10, "Nowa wartość")
        await comm.save_attributes()

        # zmiana statusu / fazy
        comm.change_phase("closed")
        await comm.save()
    """

    endpoint = "/api/commissions"
    # client ustawiasz z zewnątrz: Commission.client = swapi_client

    def __init__(self, data: Dict[str, Any]):

        # 1. Wyciągamy attributes, aby NIE były dynamicznie wrapowane
        raw_attrs = data.get("attributes") or []
        data_without_attrs = {k: v for k, v in data.items() if k != "attributes"}

        # 2. Dynamiczne pola (company, services, device, itp.)
        #    będą opakowane w DynamicObject / DynamicList
        super().__init__(data_without_attrs)

        # 3. We własnej strukturze przechowujemy attributes
        self._attributes_by_id = {
            int(item["id"]): dict(item)
            for item in raw_attrs
            if "id" in item
        }

        # Bufor zmian
        self._attributes_dirty = {}

        # 4. Nadpisujemy pole attributes → proxy (nie dirty, nie dynamic)
        object.__setattr__(self, "attributes", AttributesProxy(self))

    # ============================================================
    # ATTRIBUTES SAVE
    # ============================================================
    async def save_attributes(self) -> None:
        """
        Zapisuje zmienione atrybuty do SWAPI.

        Zakładamy endpoint:
            PATCH /commissions/{id}
            {
              "data": {
                "attributes": [
                  {"id": <id>, "value": <value>},
                  ...
                ]
              }
            }
        """
        if self.client is None:
            raise SWAPIError("Commission.client is not set")

        if self.pk is None:
            raise SWAPIError("Cannot save attributes for unsaved Commission (no pk)")

        if not self._attributes_dirty:
            # nie ma czego wysyłać
            return

        payload = {
            "data": {
                "attributes": [
                    {"id": attr_id, "value": value}
                    for attr_id, value in self._attributes_dirty.items()
                ]
            }
        }

        resp = await self.client.patch(f"{self.endpoint}/{self.pk}", json=payload)
        data = resp.get("data") or resp

        # Odświeżamy attributes z odpowiedzi
        new_attrs = data.get("attributes") or []
        self._attributes_by_id = {}

        for item in new_attrs:
            attr_id = item.get("id")
            if attr_id is None:
                continue
            self._attributes_by_id[int(attr_id)] = dict(item)

        # czyścimy bufor zmian
        self._attributes_dirty = {}

    # ============================================================
    # WYGODNE HELPERY
    # ============================================================
    def get_attribute(self, attr_id: int) -> Any:
        """
        Proxy na attributes.get().
        """
        return self.attributes.get(attr_id)

    def set_attribute(self, attr_id: int, value: Any) -> None:
        """
        Proxy na attributes.set().
        """
        self.attributes.set(attr_id, value)



class CommissionAttribute(APIModel):
    """
    Model Commission Attribute (pojedynczy atrybut zlecenia).
    """

    endpoint = "/api/commission_attributes"


class CommissionAttributeCriteria(APIModel):
    """
    Model Commission Attribute Criteria (kryteria atrybutu zlecenia).
    """

    endpoint = "/api/commission_attribute_criterias"

class CommissionAttributeRelations(APIModel):
    """
    Model Commission Attribute Relations (relacje atrybutu zlecenia).
    """

    endpoint = "/api/commission_attribute_relations"

class CommissionAttributeRelationActions(APIModel):
    """
    Model Commission Attribute Relation Actions (akcje relacji atrybutu zlecenia).
    """

    endpoint = "/api/commission_attribute_relation_actions"


class CommissionHistory(APIModel):
    """
    Model Commission History (historia zlecenia).
    """

    endpoint = "/api/commission_histories"


class CommissionPhase(APIModel):
    """
    Model Commission Phase (faza zlecenia).
    """

    endpoint = "/api/commission_phases"


class CommissionScopeType(APIModel):
    """
    Model Commission Scope Type (typ zakresu zlecenia).
    """

    endpoint = "/api/commission_scope_types"


class CommissionShortcut(APIModel):
    """
    Model Commission Shortcut (skrót zlecenia).
    """

    endpoint = "/api/commission_shortcuts"


class CommissionTemplate(APIModel):
    """
    Model Commission Template (szablon zlecenia).
    """

    endpoint = "/api/commission_templates"


class CommissionUsers(APIModel):
    """
    Model Commission Usership (użytkownik zlecenia).
    """

    endpoint = "/api/commissions_user_userss"




class Kanban(APIModel):
    """
    Model Kanban (tablica Kanban zlecenia).
    """

    endpoint = "/api/kanbans"