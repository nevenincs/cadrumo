"""IAE premises, surface-class and tax-element admission inside the repeatable-row operation.

The generic ``config profile add-row``, ``edit-row`` and ``remove-row`` commands
submit these row operations against a real encrypted profile: a row is stored in
its canonical form, a malformed or repeated row is refused naming its leaf and
the command that resolves it, a row reference must name a stored row, and a row
an IAE row still names cannot be removed. Nothing is stored by a refusal.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from ...adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from ...adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ...application.user_profile.fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
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
from ...domain.contribuyente.iae_local_facts import (
    IAE_ELEMENTO_TRIBUTARIO_SECTION,
    IAE_LOCAL_SECTION,
    IAE_LOCAL_SUPERFICIE_SECTION,
    iae_locales_from_facts,
    iae_superficies_from_facts,
)
from ...domain.contribuyente.inmueble_facts import rows_from_facts
from ...domain.user_profile.errors import UserProfileValidationError
from ...domain.user_profile.values import UserProfileFact

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_ACTIVITIES = "activities"


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

    def edit(self, section: str, row: int, values: dict[str, str]) -> bool:
        decode = self.operation.profile_decode_context()
        return update_profile_repeatable_section_row(
            profile_id=self.profile_id,
            section_key=section,
            row_key=str(row),
            values=values,
            clear_fields=(),
            schema=decode.schema,
            profile_decode_context=decode,
            authority=self.operation,
        ).changed

    def remove(self, section: str, row: int | str) -> None:
        decode = self.operation.profile_decode_context()
        remove_profile_repeatable_section_row(
            profile_id=self.profile_id,
            section_key=section,
            row_key=str(row),
            schema=decode.schema,
            profile_decode_context=decode,
            rental_ledger_references=_ledger_without_links,
        )

    def stored(self, section: str, row: int) -> dict[str, str]:
        return rows_from_facts(section, self.facts())[row]


@pytest.fixture
def world(tmp_path: Path) -> Iterator[_World]:
    secret = f"iae-doors-{tmp_path.name}"
    with (
        override_settings(cadrumo_output_language="", cadrumo_secret_passphrase=secret),
        isolated_profile_storage_root(tmp_path=tmp_path),
        bundled_indexed_authority().operation() as operation,
    ):
        outcome = register_profile_with_credentials(
            label="IAE doors",
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


def _refusal(world: _World, act: Callable[[], object]) -> UserProfileValidationError:
    before = world.facts()
    with pytest.raises(UserProfileValidationError) as refused:
        act()
    assert world.facts() == before
    return refused.value


def _activity_and_local(world: _World) -> tuple[int, int]:
    activity = world.add(_ACTIVITIES, {"description": "Comercio sintetico"})
    local = world.add(
        IAE_LOCAL_SECTION,
        {"actividad": str(activity), "afectacion": "ejercicio", "superficie_total": "120"},
    )
    return activity, local


def test_a_local_and_its_surface_class_are_stored_and_read_as_records(world: _World) -> None:
    _, local = _activity_and_local(world)

    row = world.add(
        IAE_LOCAL_SUPERFICIE_SECTION, {"local": str(local), "clase": "5.0", "total": "40", "computable": "0"}
    )

    (record,) = iae_superficies_from_facts(world.facts())
    assert world.stored(IAE_LOCAL_SUPERFICIE_SECTION, row) == {
        "local": str(local),
        "clase": "5.0",
        "total": "40",
        "computable": "0",
    }
    assert record.rectificada is None
    assert [item.clave for item in iae_locales_from_facts(world.facts())] == [local]


def test_a_malformed_surface_is_refused_naming_the_leaf_and_the_add_door(world: _World) -> None:
    _, local = _activity_and_local(world)

    refused = _refusal(
        world, lambda: world.add(IAE_LOCAL_SUPERFICIE_SECTION, {"local": str(local), "clase": "5.0", "total": "-3"})
    )

    assert refused.translated_message == "application.user_profile.errors.iae_row_invalid"
    assert refused.context == {"leaf": "total", "door": "aeat config profile add-row iae_local_superficie"}


def test_a_local_states_each_surface_class_once(world: _World) -> None:
    _, local = _activity_and_local(world)
    first = world.add(IAE_LOCAL_SUPERFICIE_SECTION, {"local": str(local), "clase": "5.0", "total": "40"})

    refused = _refusal(
        world, lambda: world.add(IAE_LOCAL_SUPERFICIE_SECTION, {"local": str(local), "clase": "5.0", "total": "9"})
    )

    assert refused.translated_message == "application.user_profile.errors.iae_row_repeated"
    assert (refused.context or {})["row"] == first


def test_an_edit_that_repeats_another_rows_class_is_refused(world: _World) -> None:
    _, local = _activity_and_local(world)
    world.add(IAE_LOCAL_SUPERFICIE_SECTION, {"local": str(local), "clase": "5.0"})
    second = world.add(IAE_LOCAL_SUPERFICIE_SECTION, {"local": str(local), "clase": "6.0"})

    refused = _refusal(world, lambda: world.edit(IAE_LOCAL_SUPERFICIE_SECTION, second, {"clase": "5.0"}))

    assert refused.translated_message == "application.user_profile.errors.iae_row_repeated"


def test_a_reference_must_name_a_stored_row(world: _World) -> None:
    _, local = _activity_and_local(world)
    absent = local + 7

    refused = _refusal(world, lambda: world.add(IAE_LOCAL_SUPERFICIE_SECTION, {"local": str(absent), "clase": "1.1"}))

    assert refused.translated_message == "application.user_profile.errors.iae_row_reference_missing"
    assert refused.context == {
        "leaf": "local",
        "row": str(absent),
        "section": IAE_LOCAL_SECTION,
        "door": "aeat config profile add-row iae_local_superficie",
    }


def test_a_tax_element_line_is_stated_once_per_activity(world: _World) -> None:
    activity, _ = _activity_and_local(world)
    line = {"actividad": str(activity), "linea": "1", "code": "01", "numero": "3"}
    world.add(IAE_ELEMENTO_TRIBUTARIO_SECTION, line)

    refused = _refusal(world, lambda: world.add(IAE_ELEMENTO_TRIBUTARIO_SECTION, line | {"numero": "4"}))

    assert refused.translated_message == "application.user_profile.errors.iae_row_repeated"


def test_a_local_its_surface_rows_name_cannot_be_removed(world: _World) -> None:
    _, local = _activity_and_local(world)
    surface = world.add(IAE_LOCAL_SUPERFICIE_SECTION, {"local": str(local), "clase": "4.0"})

    refused = _refusal(world, lambda: world.remove(IAE_LOCAL_SECTION, local))

    assert refused.translated_message == "application.user_profile.errors.iae_row_referenced"
    assert refused.context == {
        "row": local,
        "section": IAE_LOCAL_SUPERFICIE_SECTION,
        "rows": str(surface),
        "door": "aeat config profile remove-row iae_local_superficie",
    }

    world.remove(IAE_LOCAL_SUPERFICIE_SECTION, surface)
    world.remove(IAE_LOCAL_SECTION, local)
    assert iae_locales_from_facts(world.facts()) == ()


def test_an_activity_a_local_names_cannot_be_removed(world: _World) -> None:
    activity, local = _activity_and_local(world)

    refused = _refusal(world, lambda: world.remove(_ACTIVITIES, activity))

    assert refused.context == {
        "row": activity,
        "section": IAE_LOCAL_SECTION,
        "rows": str(local),
        "door": "aeat config profile remove-row iae_local",
    }


def test_a_local_may_name_the_unindexed_activity_the_setup_wizard_writes_as_row_zero(world: _World) -> None:
    apply_profile_fact_changes(
        profile_id=world.profile_id,
        changes=(UserProfileFact(path=f"{_ACTIVITIES}.description", value="Actividad del asistente"),),
        door=ProfileFactWriteDoor.MANAGER_FIELD,
        profile_decode_context=world.operation.profile_decode_context(),
    )

    local = world.add(IAE_LOCAL_SECTION, {"actividad": "0", "afectacion": "indirecta"})

    assert world.stored(IAE_LOCAL_SECTION, local)["actividad"] == "0"
    refused = _refusal(world, lambda: world.remove(_ACTIVITIES, ""))
    assert (refused.context or {})["rows"] == str(local)
