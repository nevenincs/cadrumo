"""Savings position admission inside the repeatable-row operation, against a real encrypted profile.

The generic ``config profile add-row`` command and the specific ``posicion`` verbs
submit the same registered row operations, so one case here speaks for all of them:
the leaves typed are admitted into one canonical stored form, the row lands at a
stable position, an edit changes only the named leaves, and a source state outside
the pinned country catalogue or a Spanish payer identifier without its control
character is refused naming the command that resolves it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path

import pytest

from ...adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from ...adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ...application.user_profile.login_session import authenticate_profile_for_invocation
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
from ...domain.contribuyente.inmueble_facts import rows_from_facts
from ...domain.contribuyente.posicion_facts import POSICION_SECTION, posiciones_from_facts
from ...domain.user_profile.errors import ProfileSchemaValidationError, UserProfileValidationError

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

YEAR = filing_year_envelope().horizon
PAYER = "B00000000"
PAYER_WITHOUT_CONTROL = "B00000001"
FOREIGN_STATE = "DE"
UNCATALOGUED_STATE = "QQ"


def _ledger_without_links(*, profile_id: str) -> RentalLedgerReferences:
    return RentalLedgerReferences(leases={}, properties={})


class _World:
    def __init__(self, profile_id: str, operation: PinnedAuthorityOperation) -> None:
        self.profile_id = profile_id
        self.operation = operation

    def facts(self) -> dict[str, object]:
        record = ProfileRecordRepository.for_current_session(
            self.profile_id, profile_decode_context=self.operation.profile_decode_context()
        ).load(self.profile_id)
        return {fact.path: fact.value for fact in record.facts if fact.value is not None}

    def add(self, values: dict[str, str]) -> int:
        decode = self.operation.profile_decode_context()
        return add_profile_repeatable_section_row(
            profile_id=self.profile_id,
            section_key=POSICION_SECTION,
            values=values,
            schema=decode.schema,
            profile_decode_context=decode,
            authority=self.operation,
        ).row_index

    def edit(self, row: int, values: dict[str, str], clear_fields: tuple[str, ...] = ()) -> bool:
        decode = self.operation.profile_decode_context()
        return update_profile_repeatable_section_row(
            profile_id=self.profile_id,
            section_key=POSICION_SECTION,
            row_key=str(row),
            values=values,
            clear_fields=clear_fields,
            schema=decode.schema,
            profile_decode_context=decode,
            authority=self.operation,
        ).changed

    def remove(self, row: int) -> None:
        decode = self.operation.profile_decode_context()
        remove_profile_repeatable_section_row(
            profile_id=self.profile_id,
            section_key=POSICION_SECTION,
            row_key=str(row),
            schema=decode.schema,
            profile_decode_context=decode,
            rental_ledger_references=_ledger_without_links,
        )

    def stored(self, row: int) -> dict[str, str]:
        return rows_from_facts(POSICION_SECTION, self.facts())[row]


@pytest.fixture
def world(tmp_path: Path) -> Iterator[_World]:
    secret = f"posicion-doors-{tmp_path.name}"
    with (
        override_settings(cadrumo_output_language="", cadrumo_secret_passphrase=secret),
        isolated_profile_storage_root(tmp_path=tmp_path),
        bundled_indexed_authority().operation() as operation,
    ):
        outcome = register_profile_with_credentials(
            label="Posicion doors",
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


def _position() -> dict[str, str]:
    return {
        "tipo": "cuenta",
        "pagador_nif": PAYER.lower(),
        "pagador_nombre": "Banco Sintetico",
        "pais_origen": "es",
        "porcentaje_titularidad": "50",
        "fecha_inicio": date(YEAR - 2, 3, 1).isoformat(),
        "identificador": "0042",
    }


def _refusal(world: _World, act: Callable[[], object]) -> UserProfileValidationError:
    before = world.facts()
    with pytest.raises(UserProfileValidationError) as refused:
        act()
    assert world.facts() == before
    return refused.value


def test_a_position_is_stored_in_its_canonical_form_at_a_stable_position(world: _World) -> None:
    row = world.add(_position())

    (record,) = posiciones_from_facts(world.facts())
    assert record.clave == row
    assert world.stored(row) == {
        "tipo": "cuenta",
        "pagador_nif": PAYER,
        "pagador_nombre": "Banco Sintetico",
        "pais_origen": "ES",
        "porcentaje_titularidad": "50.00",
        "fecha_inicio": date(YEAR - 2, 3, 1).isoformat(),
        "identificador": "0042",
    }


def test_an_incoherent_position_is_refused_naming_the_leaf_and_the_add_door(world: _World) -> None:
    refused = _refusal(world, lambda: world.add(_position() | {"porcentaje_titularidad": "0"}))

    assert refused.translated_message == "application.user_profile.errors.posicion_row_invalid"
    assert refused.context == {"leaf": "porcentaje_titularidad", "door": "aeat config profile posicion add"}


def test_a_required_fact_left_out_is_refused_naming_it(world: _World) -> None:
    row = _position()
    del row["fecha_inicio"]

    refused = _refusal(world, lambda: world.add(row))

    assert (refused.context or {})["leaf"] == "fecha_inicio"


def test_a_source_state_the_pinned_catalogue_does_not_hold_is_refused(world: _World) -> None:
    refused = _refusal(world, lambda: world.add(_position() | {"pais_origen": UNCATALOGUED_STATE}))

    assert refused.translated_message == "application.user_profile.errors.posicion_country_unknown"
    assert refused.context == {"pais": UNCATALOGUED_STATE, "door": "aeat config profile posicion add"}


def test_a_spanish_payer_identifier_must_hold_its_control_character(world: _World) -> None:
    refused = _refusal(world, lambda: world.add(_position() | {"pagador_nif": PAYER_WITHOUT_CONTROL}))

    assert refused.translated_message == "application.user_profile.errors.posicion_payer_id_invalid"
    assert refused.context == {"door": "aeat config profile posicion add"}


def test_a_foreign_payer_identifier_keeps_only_its_shape_check(world: _World) -> None:
    row = world.add(_position() | {"pagador_nif": PAYER_WITHOUT_CONTROL, "pais_origen": FOREIGN_STATE})

    assert world.stored(row)["pagador_nif"] == PAYER_WITHOUT_CONTROL

    refused = _refusal(world, lambda: world.edit(row, {"pais_origen": "ES"}))
    assert refused.translated_message == "application.user_profile.errors.posicion_payer_id_invalid"
    assert refused.context == {"door": "aeat config profile posicion edit"}


def test_an_edit_changes_only_the_named_leaves_and_a_clear_removes_one(world: _World) -> None:
    row = world.add(_position())
    end = date(YEAR - 1, 12, 31).isoformat()

    assert world.edit(row, {"fecha_fin": end, "pagador_nombre": "Banco Sintetico Dos"}, ("identificador",))

    stored = world.stored(row)
    assert stored["fecha_fin"] == end
    assert stored["pagador_nombre"] == "Banco Sintetico Dos"
    assert "identificador" not in stored
    assert stored["pagador_nif"] == PAYER


def test_an_edit_that_states_what_is_stored_changes_nothing(world: _World) -> None:
    row = world.add(_position())

    assert not world.edit(row, {"porcentaje_titularidad": "50.00"})


def test_an_incoherent_edit_is_refused_naming_the_edit_door(world: _World) -> None:
    row = world.add(_position())

    refused = _refusal(world, lambda: world.edit(row, {"fecha_fin": date(YEAR - 3, 1, 1).isoformat()}))

    assert refused.context == {"leaf": "fecha_fin", "door": "aeat config profile posicion edit"}


def test_a_required_fact_cannot_be_cleared(world: _World) -> None:
    row = world.add(_position())

    refused = _refusal(world, lambda: world.edit(row, {}, ("pagador_nif",)))

    assert (refused.context or {})["leaf"] == "pagador_nif"


def test_an_undeclared_leaf_is_refused(world: _World) -> None:
    row = world.add(_position())

    with pytest.raises(ProfileSchemaValidationError):
        world.edit(row, {"saldo": "1000"})


def test_a_removed_position_is_never_given_to_the_next_one(world: _World) -> None:
    first = world.add(_position())
    world.remove(first)

    second = world.add(_position() | {"tipo": "valores_negociables"})

    assert second != first
    assert [record.clave for record in posiciones_from_facts(world.facts())] == [second]
