"""The property and lease doors' request path against a real encrypted profile.

Each case composes what ``config profile inmueble`` and ``config profile arrendamiento``
do around the registered row operations: the leaves typed are admitted into one
canonical stored form, the row lands at a stable position, an edit changes only the
named leaves, and a removal that would orphan a lease is refused. The writes go
through the same row operations the verbs submit.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from .....adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from .....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from .....application.user_profile.login_session import authenticate_profile_for_invocation
from .....application.user_profile.profile_record_repository import ProfileRecordRepository
from .....application.user_profile.registration import register_profile_with_credentials
from .....application.user_profile.rental_records import (
    canonical_arrendamiento_values,
    canonical_inmueble_values,
    require_inmueble_removable,
)
from .....application.user_profile.section_rows import (
    add_profile_repeatable_section_row,
    remove_profile_repeatable_section_row,
    update_profile_repeatable_section_row,
)
from .....core.config import override_settings
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.contribuyente.inmueble_facts import (
    ARRENDAMIENTO_SECTION,
    INMUEBLE_SECTION,
    arrendamientos_from_facts,
    inmuebles_from_facts,
)
from .....domain.user_profile.errors import UserProfileValidationError
from ..rental_row_doors import merged_row

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

YEAR = filing_year_envelope().horizon
CATASTRAL = "9872023VH5797S0001WX"
TENANT = "12345678Z"


class _World:
    def __init__(self, profile_id: str, operation: PinnedAuthorityOperation) -> None:
        self.profile_id = profile_id
        self.operation = operation

    def facts(self) -> dict[str, object]:
        record = ProfileRecordRepository.for_current_session(
            self.profile_id, profile_decode_context=self.operation.profile_decode_context()
        ).load(self.profile_id)
        return {fact.path: fact.value for fact in record.facts if fact.value is not None}

    def add(self, section: str, stored: dict[str, str]) -> int:
        decode = self.operation.profile_decode_context()
        return add_profile_repeatable_section_row(
            profile_id=self.profile_id,
            section_key=section,
            values=stored,
            schema=decode.schema,
            profile_decode_context=decode,
        ).row_index

    def edit(self, section: str, row: int, before: dict[str, str], after: dict[str, str]) -> None:
        decode = self.operation.profile_decode_context()
        update_profile_repeatable_section_row(
            profile_id=self.profile_id,
            section_key=section,
            row_key=str(row),
            values={leaf: value for leaf, value in after.items() if before.get(leaf) != value},
            clear_fields=tuple(leaf for leaf in before if leaf not in after),
            schema=decode.schema,
            profile_decode_context=decode,
        )

    def remove(self, section: str, row: int) -> None:
        decode = self.operation.profile_decode_context()
        remove_profile_repeatable_section_row(
            profile_id=self.profile_id,
            section_key=section,
            row_key=str(row),
            schema=decode.schema,
            profile_decode_context=decode,
        )


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


def test_a_property_is_stored_in_its_canonical_form_at_a_stable_position(world: _World) -> None:
    row = world.add(INMUEBLE_SECTION, canonical_inmueble_values(_property()))

    (record,) = inmuebles_from_facts(world.facts())
    assert row == record.clave
    assert record.referencia_catastral == CATASTRAL
    assert str(world.facts()[f"{INMUEBLE_SECTION}.{row}.importe_adquisicion"]) == "150000.00"


def test_an_incoherent_property_is_refused_before_anything_is_written(world: _World) -> None:
    before = world.facts()

    with pytest.raises(UserProfileValidationError) as refused:
        canonical_inmueble_values(_property() | {"porcentaje_propiedad": "100.5"})

    assert refused.value.translated_message == "application.user_profile.errors.rental_row_invalid"
    assert world.facts() == before


def test_an_edit_changes_only_the_named_leaves_and_a_clear_removes_one(world: _World) -> None:
    row = world.add(INMUEBLE_SECTION, canonical_inmueble_values(_property()))
    stored = {
        leaf.removeprefix(f"{INMUEBLE_SECTION}.{row}."): str(value)
        for leaf, value in world.facts().items()
        if leaf.startswith(f"{INMUEBLE_SECTION}.{row}.")
    }

    after = canonical_inmueble_values(
        merged_row(stored, {"direccion": "Calle Sintetica 1"}, ("valores_catastrales",)), clave=row
    )
    world.edit(INMUEBLE_SECTION, row, stored, after)

    (record,) = inmuebles_from_facts(world.facts())
    assert record.direccion == "Calle Sintetica 1"
    assert record.valores_catastrales == ()
    assert record.referencia_catastral == CATASTRAL


def test_a_lease_must_name_a_property_the_profile_holds_and_a_valid_tenant(world: _World) -> None:
    with pytest.raises(UserProfileValidationError) as missing:
        canonical_arrendamiento_values(_lease(7), inmuebles=(), operation=world.operation)
    assert missing.value.translated_message == "application.user_profile.errors.rental_lease_property_missing"

    row = world.add(INMUEBLE_SECTION, canonical_inmueble_values(_property()))
    properties = inmuebles_from_facts(world.facts())
    with pytest.raises(UserProfileValidationError) as invalid:
        canonical_arrendamiento_values(
            _lease(row) | {"inquilinos": "99999999A:otra:no"}, inmuebles=properties, operation=world.operation
        )
    assert invalid.value.translated_message == "application.user_profile.errors.rental_tenant_id_invalid"

    foreign = canonical_arrendamiento_values(
        _lease(row) | {"inquilinos": "99999999A:otra:si"}, inmuebles=properties, operation=world.operation
    )
    assert foreign["inquilinos"] == "99999999A:otra:si"


def test_a_property_a_lease_names_cannot_be_removed_until_the_lease_goes(world: _World) -> None:
    property_row = world.add(INMUEBLE_SECTION, canonical_inmueble_values(_property()))
    lease_row = world.add(
        ARRENDAMIENTO_SECTION,
        canonical_arrendamiento_values(
            _lease(property_row), inmuebles=inmuebles_from_facts(world.facts()), operation=world.operation
        ),
    )

    with pytest.raises(UserProfileValidationError) as refused:
        require_inmueble_removable(property_row, arrendamientos_from_facts(world.facts()))
    assert refused.value.translated_message == "application.user_profile.errors.rental_property_has_leases"

    world.remove(ARRENDAMIENTO_SECTION, lease_row)
    require_inmueble_removable(property_row, arrendamientos_from_facts(world.facts()))
    world.remove(INMUEBLE_SECTION, property_row)
    assert inmuebles_from_facts(world.facts()) == ()


def test_a_removed_position_is_never_given_to_the_next_property(world: _World) -> None:
    first = world.add(INMUEBLE_SECTION, canonical_inmueble_values(_property()))
    world.remove(INMUEBLE_SECTION, first)

    second = world.add(INMUEBLE_SECTION, canonical_inmueble_values({"situacion": "5"}))

    assert second != first
