"""IAE premises and tax-element rows round-trip through an encrypted profile.

The rows are written through the profile fact writer into a real encrypted
profile and read back through the stored record and the domain decoder, so
the schema, the writer's judge and the record grammar are checked to agree
on one stored shape: distinct surfaces, an absent fact left absent, and a
correction that clears what it no longer states.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.contribuyente.iae_local_facts import (
    IAE_ELEMENTO_TRIBUTARIO_SECTION,
    IAE_LOCAL_SECTION,
    IAE_LOCAL_SUPERFICIE_SECTION,
    iae_elementos_from_facts,
    iae_local_row_values,
    iae_locales_from_facts,
    iae_superficie_row_values,
    iae_superficies_from_facts,
)
from cadrumo.domain.contribuyente.iae_local_record import SuperficieRegla14Clase
from cadrumo.domain.contribuyente.inmueble_facts import facts_for_row
from cadrumo.domain.user_profile.values import UserProfileFact, UserProfileRecord

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


class _World:
    """One registered, authenticated profile and the authority the writes run under."""

    def __init__(self, profile_id: str, operation: PinnedAuthorityOperation) -> None:
        self.profile_id = profile_id
        self.operation = operation

    def record(self) -> UserProfileRecord:
        return ProfileRecordRepository.for_current_session(
            self.profile_id, profile_decode_context=self.operation.profile_decode_context()
        ).load(self.profile_id)

    def facts(self) -> dict[str, str]:
        return {fact.path: str(fact.value) for fact in self.record().facts if fact.value is not None}

    def write(self, values: dict[str, str | None]) -> UserProfileRecord:
        current = self.record()
        return apply_profile_fact_changes(
            profile_id=self.profile_id,
            changes=tuple(UserProfileFact(path=path, value=value) for path, value in values.items()),
            door=ProfileFactWriteDoor.MANAGER_ROW,
            expected_record=current,
            profile_decode_context=self.operation.profile_decode_context(),
        )


@pytest.fixture
def world(tmp_path: Path) -> Iterator[_World]:
    secret = f"iae-local-custody-{tmp_path.name}"
    with (
        override_settings(cadrumo_output_language="", cadrumo_secret_passphrase=secret),
        isolated_profile_storage_root(tmp_path=tmp_path),
        bundled_indexed_authority().operation() as operation,
    ):
        outcome = register_profile_with_credentials(
            label="IAE premises custody",
            passphrase=secret,
            profile_create_context=operation.profile_create_context(),
            profile_decode_context=operation.profile_decode_context(),
        )
        authenticate_profile_for_invocation(
            name=outcome.label,
            passphrase_callback=secret.__str__,
            profile_decode_context=operation.profile_decode_context(),
        )
        register_minimal_profile(profile_id=outcome.profile_id)
        yield _World(outcome.profile_id, operation)


_LOCAL = {
    "actividad": "0",
    "afectacion": "ejercicio",
    "via_sg": "CL",
    "via_nombre": "Sintetica",
    "postcode": "28001",
    "province_code": "28",
    "municipality_code": "28079",
    "municipality_name": "Ciudad Sintetica",
    "superficie_total": "120",
    "superficie_rectificada": "96",
    "superficie_computable": "90",
}
_CLASS_SIN_REDUCCION = {"local": "0", "clase": "0.1", "total": "80", "rectificada": "80", "computable": "68"}
_CLASS_ALMACEN = {"local": "0", "clase": "5.0", "total": "40", "rectificada": "22"}
_INDIRECT = {
    "actividad": "0",
    "afectacion": "indirecta",
    "uso_destino_code": "01",
    "uso_destino_description": "Almacen",
}
_ELEMENT = {"actividad": "0", "linea": "1", "code": "01", "description": "Obreros", "numero": "3.50"}


def test_premises_and_tax_elements_round_trip_through_encrypted_custody(world: _World) -> None:
    before = world.record()

    published = world.write(
        {
            "activities.0.description": "Actividad sintetica",
            "censo.aeat_delegacion_code": "28",
            "censo.aeat_administracion_code": "601",
            "contact.fiscal_address_municipality_code": "28079",
            **facts_for_row(IAE_LOCAL_SECTION, 0, _LOCAL),
            **facts_for_row(IAE_LOCAL_SECTION, 1, _INDIRECT),
            **facts_for_row(IAE_LOCAL_SUPERFICIE_SECTION, 0, _CLASS_SIN_REDUCCION),
            **facts_for_row(IAE_LOCAL_SUPERFICIE_SECTION, 1, _CLASS_ALMACEN),
            **facts_for_row(IAE_ELEMENTO_TRIBUTARIO_SECTION, 0, _ELEMENT),
        }
    )

    assert published.record_revision == before.record_revision + 1
    stored = world.facts()
    assert stored["censo.aeat_administracion_code"] == "601"
    locales = iae_locales_from_facts(stored)
    assert [iae_local_row_values(local) for local in locales] == [_LOCAL, _INDIRECT]
    classes = iae_superficies_from_facts(stored)
    assert [iae_superficie_row_values(entry) for entry in classes] == [_CLASS_SIN_REDUCCION, _CLASS_ALMACEN]
    assert [(entry.local, entry.clase) for entry in classes] == [
        (0, SuperficieRegla14Clase.SIN_REDUCCION),
        (0, SuperficieRegla14Clase.ALMACEN),
    ]
    assert classes[1].computable is None
    (element,) = iae_elementos_from_facts(stored)
    assert (element.linea, element.numero) == (1, Decimal("3.50"))


def test_an_unstated_fact_stays_absent_and_a_correction_clears_what_it_no_longer_states(world: _World) -> None:
    world.write({"activities.0.description": "Actividad sintetica", **facts_for_row(IAE_LOCAL_SECTION, 0, _LOCAL)})

    world.write({f"{IAE_LOCAL_SECTION}.0.superficie_total": None, f"{IAE_LOCAL_SECTION}.0.superficie_computable": "0"})

    stored = world.facts()
    assert f"{IAE_LOCAL_SECTION}.0.superficie_total" not in stored
    assert "censo.aeat_delegacion_code" not in stored
    (local,) = iae_locales_from_facts(stored)
    assert (local.superficie_total, local.superficie_rectificada, local.superficie_computable) == (None, 96, 0)
