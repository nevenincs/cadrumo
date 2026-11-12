"""Property and lease admission inside the repeatable-row operation, against a real encrypted profile.

The generic ``config profile add-row`` command and the specific ``inmueble`` and
``arrendamiento`` verbs submit the same registered row operations, so one case here
speaks for all of them: the leaves typed are admitted into one canonical stored form,
the row lands at a stable position, an edit changes only the named leaves, and what
would orphan a lease or an accessory is refused naming the command that resolves it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path

import pytest

from ...adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from ...adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ...application.user_profile.login_session import authenticate_profile_for_invocation
from ...application.user_profile.operations import build_user_profile_operation_definitions
from ...application.user_profile.profile_operation_contracts import (
    PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID,
)
from ...application.user_profile.profile_operation_execution import ProfileRepeatableRowRemoveOperationExecutor
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...application.user_profile.registration import register_profile_with_credentials
from ...application.user_profile.rental_records import RentalLedgerReferences
from ...application.user_profile.section_rows import (
    add_profile_repeatable_section_row,
    remove_profile_repeatable_section_row,
    update_profile_repeatable_section_row,
)
from ...core.config import override_settings
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...domain.contribuyente.inmueble_facts import (
    ARRENDAMIENTO_SECTION,
    INMUEBLE_SECTION,
    inmuebles_from_facts,
    rows_from_facts,
)
from ...domain.user_profile.errors import ProfileSchemaValidationError, UserProfileValidationError

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

YEAR = filing_year_envelope().horizon
CATASTRAL = "9872023VH5797S0001WX"
TENANT = "12345678Z"


class _World:
    def __init__(self, profile_id: str, operation: PinnedAuthorityOperation) -> None:
        self.profile_id = profile_id
        self.operation = operation
        self.leases_named_by_ledger: dict[str, int] = {}
        self.properties_named_by_ledger: dict[str, int] = {}

    def ledger_references(self, *, profile_id: str) -> RentalLedgerReferences:
        assert profile_id == self.profile_id
        return RentalLedgerReferences(leases=self.leases_named_by_ledger, properties=self.properties_named_by_ledger)

    def facts(self) -> dict[str, object]:
        record = ProfileRecordRepository.for_current_session(
            self.profile_id, profile_decode_context=self.operation.profile_decode_context()
        ).load(self.profile_id)
        return {fact.path: fact.value for fact in record.facts if fact.value is not None}

    def add(self, section: str, values: dict[str, str]) -> int:
        decode = self.operation.profile_decode_context()
        return add_profile_repeatable_section_row(
            profile_id=self.profile_id,
            section_key=section,
            values=values,
            schema=decode.schema,
            profile_decode_context=decode,
            authority=self.operation,
        ).row_index

    def edit(self, section: str, row: int, values: dict[str, str], clear_fields: tuple[str, ...] = ()) -> bool:
        decode = self.operation.profile_decode_context()
        return update_profile_repeatable_section_row(
            profile_id=self.profile_id,
            section_key=section,
            row_key=str(row),
            values=values,
            clear_fields=clear_fields,
            schema=decode.schema,
            profile_decode_context=decode,
            authority=self.operation,
        ).changed

    def remove(self, section: str, row: int) -> None:
        decode = self.operation.profile_decode_context()
        remove_profile_repeatable_section_row(
            profile_id=self.profile_id,
            section_key=section,
            row_key=str(row),
            schema=decode.schema,
            profile_decode_context=decode,
            rental_ledger_references=self.ledger_references,
        )

    def stored(self, section: str, row: int) -> dict[str, str]:
        return rows_from_facts(section, self.facts())[row]


@pytest.fixture
def world(tmp_path: Path) -> Iterator[_World]:
    secret = f"rental-doors-{tmp_path.name}"
    with (
        override_settings(cadrumo_output_language="", cadrumo_secret_passphrase=secret),
        isolated_profile_storage_root(tmp_path=tmp_path),
        bundled_indexed_authority().operation() as operation,
    ):
        outcome = register_profile_with_credentials(
            label="Rental doors",
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


def _property() -> dict[str, str]:
    return {
        "situacion": "1",
        "referencia_catastral": CATASTRAL.lower(),
        "titularidad_regimen": "pleno_dominio",
        "titular": "primer_declarante",
        "porcentaje_propiedad": "100",
        "importe_adquisicion": "150000",
        "valores_catastrales": f"{YEAR}:80000:48000",
    }


def _lease(inmueble: int) -> dict[str, str]:
    return {
        "inmueble": str(inmueble),
        "fecha_contrato": date(YEAR, 1, 10).isoformat(),
        "fecha_inicio": date(YEAR, 2, 1).isoformat(),
        "inquilinos": f"{TENANT.lower()}:otra:no",
    }


def _refusal(world: _World, act: Callable[[], object]) -> UserProfileValidationError:
    before = world.facts()
    with pytest.raises(UserProfileValidationError) as refused:
        act()
    assert world.facts() == before
    return refused.value


def test_a_property_is_stored_in_its_canonical_form_at_a_stable_position(world: _World) -> None:
    row = world.add(INMUEBLE_SECTION, _property())

    (record,) = inmuebles_from_facts(world.facts())
    assert row == record.clave
    assert record.referencia_catastral == CATASTRAL
    assert str(world.facts()[f"{INMUEBLE_SECTION}.{row}.importe_adquisicion"]) == "150000.00"


def test_an_incoherent_property_is_refused_naming_the_leaf_and_the_add_door(world: _World) -> None:
    refused = _refusal(world, lambda: world.add(INMUEBLE_SECTION, _property() | {"porcentaje_propiedad": "100.5"}))

    assert refused.translated_message == "application.user_profile.errors.rental_row_invalid"
    assert (refused.context or {})["door"] == "aeat config profile inmueble add"


def test_an_edit_changes_only_the_named_leaves_and_a_clear_removes_one(world: _World) -> None:
    row = world.add(INMUEBLE_SECTION, _property())

    changed = world.edit(INMUEBLE_SECTION, row, {"direccion": "Calle Sintetica 1"}, ("valores_catastrales",))

    (record,) = inmuebles_from_facts(world.facts())
    assert changed
    assert record.direccion == "Calle Sintetica 1"
    assert record.valores_catastrales == ()
    assert record.referencia_catastral == CATASTRAL


def test_an_edit_that_states_what_is_stored_changes_nothing(world: _World) -> None:
    row = world.add(INMUEBLE_SECTION, _property())

    assert not world.edit(INMUEBLE_SECTION, row, {"importe_adquisicion": "150000.00"})


def test_an_incoherent_edit_is_refused_by_the_operation_naming_the_edit_door(world: _World) -> None:
    row = world.add(INMUEBLE_SECTION, _property())

    refused = _refusal(world, lambda: world.edit(INMUEBLE_SECTION, row, {"porcentaje_propiedad": "50"}))

    assert refused.translated_message == "application.user_profile.errors.rental_row_invalid"
    assert refused.context == {"leaf": "importes_movimientos", "door": "aeat config profile inmueble edit"}


def test_a_co_owned_property_states_what_its_ledger_rows_hold(world: _World) -> None:
    half = _property() | {"porcentaje_propiedad": "50"}

    _refusal(world, lambda: world.add(INMUEBLE_SECTION, half))
    row = world.add(INMUEBLE_SECTION, half | {"importes_movimientos": "parte_propia"})

    assert world.stored(INMUEBLE_SECTION, row)["importes_movimientos"] == "parte_propia"


def test_an_accessory_names_an_existing_other_property_as_its_principal(world: _World) -> None:
    principal = world.add(INMUEBLE_SECTION, _property())

    missing = _refusal(world, lambda: world.add(INMUEBLE_SECTION, {"situacion": "5", "inmueble_principal": "9"}))
    assert missing.translated_message == "application.user_profile.errors.rental_principal_missing"
    assert (missing.context or {})["door"] == "aeat config profile inmueble add"

    accessory = world.add(INMUEBLE_SECTION, {"situacion": "5", "inmueble_principal": str(principal)})
    assert world.stored(INMUEBLE_SECTION, accessory)["inmueble_principal"] == str(principal)

    own = _refusal(world, lambda: world.edit(INMUEBLE_SECTION, accessory, {"inmueble_principal": str(accessory)}))
    assert own.translated_message == "application.user_profile.errors.rental_row_invalid"
    assert (own.context or {})["leaf"] == "inmueble_principal"


def test_a_principal_with_an_accessory_cannot_be_removed_until_the_accessory_goes(world: _World) -> None:
    principal = world.add(INMUEBLE_SECTION, _property())
    accessory = world.add(INMUEBLE_SECTION, {"situacion": "5", "inmueble_principal": str(principal)})

    refused = _refusal(world, lambda: world.remove(INMUEBLE_SECTION, principal))
    assert refused.translated_message == "application.user_profile.errors.rental_property_has_accessories"
    assert (refused.context or {})["accessories"] == str(accessory)

    world.remove(INMUEBLE_SECTION, accessory)
    world.remove(INMUEBLE_SECTION, principal)
    assert inmuebles_from_facts(world.facts()) == ()


def test_a_lease_must_name_a_property_the_profile_holds(world: _World) -> None:
    refused = _refusal(world, lambda: world.add(ARRENDAMIENTO_SECTION, _lease(7)))

    assert refused.translated_message == "application.user_profile.errors.rental_lease_property_missing"
    assert (refused.context or {})["door"] == "aeat config profile inmueble add"


def test_a_tenant_identifier_is_checked_unless_declared_foreign(world: _World) -> None:
    row = world.add(INMUEBLE_SECTION, _property())

    invalid = _refusal(
        world, lambda: world.add(ARRENDAMIENTO_SECTION, _lease(row) | {"inquilinos": "99999999A:otra:no"})
    )
    assert invalid.translated_message == "application.user_profile.errors.rental_tenant_id_invalid"
    assert (invalid.context or {})["door"] == "aeat config profile arrendamiento add"

    lease = world.add(ARRENDAMIENTO_SECTION, _lease(row) | {"inquilinos": "99999999A:otra:si"})
    assert world.stored(ARRENDAMIENTO_SECTION, lease)["inquilinos"] == "99999999A:otra:si"
    edit = _refusal(world, lambda: world.edit(ARRENDAMIENTO_SECTION, lease, {"inquilinos": "99999999A:otra:no"}))
    assert (edit.context or {})["door"] == "aeat config profile arrendamiento edit"


def test_a_lease_states_no_more_tenants_than_the_form_has_identification_slots(world: _World) -> None:
    row = world.add(INMUEBLE_SECTION, _property())

    def tenants(count: int) -> dict[str, str]:
        return _lease(row) | {"inquilinos": ";".join(f"EXTRANJERO{n}:otra:si" for n in range(count))}

    lease = world.add(ARRENDAMIENTO_SECTION, tenants(3))
    assert world.stored(ARRENDAMIENTO_SECTION, lease)["inquilinos"].count(";") == 2
    refused = _refusal(world, lambda: world.add(ARRENDAMIENTO_SECTION, tenants(4)))
    assert refused.translated_message == "application.user_profile.errors.rental_row_invalid"
    assert (refused.context or {})["leaf"] == "inquilinos"


def test_a_lease_is_stored_in_its_canonical_form_and_carries_the_lau_fact(world: _World) -> None:
    row = world.add(INMUEBLE_SECTION, _property())

    lease = world.add(ARRENDAMIENTO_SECTION, _lease(row) | {"renta_inicial": "850", "incumple_lau_17_6": "true"})

    stored = world.stored(ARRENDAMIENTO_SECTION, lease)
    assert stored["renta_inicial"] == "850.00"
    assert stored["incumple_lau_17_6"] == "true"
    assert stored["inquilinos"] == f"{TENANT}:otra:no"


def test_a_property_a_lease_names_cannot_be_removed_until_the_lease_goes(world: _World) -> None:
    property_row = world.add(INMUEBLE_SECTION, _property())
    lease_row = world.add(ARRENDAMIENTO_SECTION, _lease(property_row))

    refused = _refusal(world, lambda: world.remove(INMUEBLE_SECTION, property_row))
    assert refused.translated_message == "application.user_profile.errors.rental_property_has_leases"
    assert (refused.context or {})["door"] == "aeat config profile arrendamiento remove"

    world.remove(ARRENDAMIENTO_SECTION, lease_row)
    world.remove(INMUEBLE_SECTION, property_row)
    assert inmuebles_from_facts(world.facts()) == ()


def test_an_edit_cannot_point_a_lease_at_a_missing_property(world: _World) -> None:
    row = world.add(INMUEBLE_SECTION, _property())
    lease = world.add(ARRENDAMIENTO_SECTION, _lease(row))

    refused = _refusal(world, lambda: world.edit(ARRENDAMIENTO_SECTION, lease, {"inmueble": "42"}))

    assert refused.translated_message == "application.user_profile.errors.rental_lease_property_missing"


def test_a_removed_position_is_never_given_to_the_next_property(world: _World) -> None:
    first = world.add(INMUEBLE_SECTION, _property())
    world.remove(INMUEBLE_SECTION, first)

    second = world.add(INMUEBLE_SECTION, {"situacion": "5"})

    assert second != first


def test_a_retired_leaf_is_refused_as_undeclared_for_both_sections(world: _World) -> None:
    row = world.add(INMUEBLE_SECTION, _property())
    lease = world.add(ARRENDAMIENTO_SECTION, _lease(row))

    for section, key in ((INMUEBLE_SECTION, row), (ARRENDAMIENTO_SECTION, lease)):
        with pytest.raises(ProfileSchemaValidationError):
            world.edit(section, key, {"anejo_referencia_catastral": CATASTRAL})


def test_a_property_a_ledger_row_names_is_not_removed(world: _World) -> None:
    row = world.add(INMUEBLE_SECTION, _property())
    world.properties_named_by_ledger = {str(row): 2}

    refusal = _refusal(world, lambda: world.remove(INMUEBLE_SECTION, row))

    assert "aeat app ledger classify" in str(refusal.context)
    world.properties_named_by_ledger = {}
    world.remove(INMUEBLE_SECTION, row)
    assert row not in rows_from_facts(INMUEBLE_SECTION, world.facts())


def test_a_lease_a_ledger_row_names_is_not_removed(world: _World) -> None:
    property_row = world.add(INMUEBLE_SECTION, _property())
    lease_row = world.add(ARRENDAMIENTO_SECTION, _lease(property_row))
    world.leases_named_by_ledger = {str(lease_row): 1}

    refusal = _refusal(world, lambda: world.remove(ARRENDAMIENTO_SECTION, lease_row))

    assert "aeat app ledger classify" in str(refusal.context)
    assert lease_row in rows_from_facts(ARRENDAMIENTO_SECTION, world.facts())


@pytest.mark.parametrize("reader", [None, "given"])
def test_the_remove_operation_is_composed_with_or_without_a_ledger_read(reader: str | None) -> None:
    def read(*, profile_id: str) -> RentalLedgerReferences:
        return RentalLedgerReferences(leases={}, properties={})

    definitions = build_user_profile_operation_definitions(read if reader is not None else None)
    definition = next(
        item for item in definitions if item.definition_id == PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID
    )

    assert type(definition.executor_factory.create()) is ProfileRepeatableRowRemoveOperationExecutor
