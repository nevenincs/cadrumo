"""A ledger row names a stored lease or property, and the profile keeps a named row from being removed.

The profile is a real encrypted profile and the ledger ports are the production composition, so the
admission reads the stored property and lease rows and the removal guard reads the stored ledger rows.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

import pytest
from pydantic import ValidationError

from ...adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from ...adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ...application.ledger.action_ports import LedgerActionPorts
from ...application.ledger.classify_patch import (
    build_bulk_row_classification_patch,
    resolve_classification_patch_values,
)
from ...application.ledger.classify_requests import LedgerClassifyPatch
from ...application.ledger.manual_update import update_manual_transaction_fields
from ...application.ledger.models import BulkClassifyRow, ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from ...application.ledger.rental_link_admission import (
    LEASE_LIST_DOOR,
    PROPERTY_LIST_DOOR,
    rental_ledger_references,
)
from ...application.ledger.tests.manual_transaction_support import create_manual_transaction
from ...application.user_profile.login_session import authenticate_profile_for_invocation
from ...application.user_profile.registration import register_profile_with_credentials
from ...application.user_profile.section_rows import (
    add_profile_repeatable_section_row,
    remove_profile_repeatable_section_row,
)
from ...core.config import override_settings
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...domain.contribuyente.inmueble_facts import ARRENDAMIENTO_SECTION, INMUEBLE_SECTION
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.models import Transaction
from ...domain.transactions.rental_link import RENTAL_LINK_IRPF_CATEGORY
from ...domain.user_profile.errors import UserProfileValidationError
from ..ledger_action_composition import (
    compose_ledger_action_ports,
    load_ledger_rows_for_rental_references,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon


class _World(NamedTuple):
    profile_id: str
    operation: PinnedAuthorityOperation
    inmueble: int
    arrendamiento: int


def _row(world: _World, ports: LedgerActionPorts, **fields: object) -> Transaction:
    values: dict[str, object] = {
        "bucket_id": world.profile_id,
        "booked_date": date(_YEAR, 5, 2),
        "amount": Decimal("800.00"),
        "direction": TransactionDirection.INCOMING,
        "description": "rent",
        "business_classification": BusinessClassification.NOT_YET_PROCESSED,
        **fields,
    }
    return create_manual_transaction(ManualLedgerTransactionCommand.model_validate(values), ports=ports).transaction


def _update(world: _World, ports: LedgerActionPorts, transaction: Transaction, **fields: object) -> Transaction:
    return update_manual_transaction_fields(
        bucket_id=world.profile_id,
        transaction_id=transaction.transaction_id,
        patch=ManualLedgerTransactionPatch.model_validate(fields),
        actor="tester",
        source_command="aeat app ledger classify",
        ports=ports,
    ).transaction


def _stored(ports: LedgerActionPorts, transaction: Transaction) -> Transaction:
    return ports.transaction_repository.load().transactions[transaction.transaction_id]


@pytest.fixture
def world(tmp_path: Path) -> Iterator[_World]:
    secret = f"ledger-rental-{tmp_path.name}"
    with (
        override_settings(cadrumo_output_language="", cadrumo_secret_passphrase=secret),
        isolated_profile_storage_root(tmp_path=tmp_path),
        bundled_indexed_authority().operation() as operation,
    ):
        outcome = register_profile_with_credentials(
            label="Ledger rental links",
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
        decode = operation.profile_decode_context()
        inmueble = add_profile_repeatable_section_row(
            profile_id=outcome.profile_id,
            section_key=INMUEBLE_SECTION,
            values={
                "situacion": "1",
                "referencia_catastral": "9872023vh5797s0001wx",
                "titularidad_regimen": "pleno_dominio",
                "titular": "primer_declarante",
                "porcentaje_propiedad": "100",
                "importe_adquisicion": "150000",
                "valores_catastrales": f"{_YEAR}:80000:48000",
            },
            schema=decode.schema,
            profile_decode_context=decode,
            authority=operation,
        ).row_index
        arrendamiento = add_profile_repeatable_section_row(
            profile_id=outcome.profile_id,
            section_key=ARRENDAMIENTO_SECTION,
            values={
                "inmueble": str(inmueble),
                "fecha_contrato": date(_YEAR, 1, 10).isoformat(),
                "fecha_inicio": date(_YEAR, 2, 1).isoformat(),
                "inquilinos": "12345678z:otra:no",
            },
            schema=decode.schema,
            profile_decode_context=decode,
            authority=operation,
        ).row_index
        yield _World(outcome.profile_id, operation, inmueble, arrendamiento)


@pytest.fixture
def ports(world: _World) -> LedgerActionPorts:
    return compose_ledger_action_ports(bucket_id=world.profile_id, operation=world.operation)


def _remove(world: _World, section: str, row: int) -> None:
    decode = world.operation.profile_decode_context()
    remove_profile_repeatable_section_row(
        profile_id=world.profile_id,
        section_key=section,
        row_key=str(row),
        schema=decode.schema,
        profile_decode_context=decode,
        rental_ledger_references=rental_ledger_references(load_ledger_rows_for_rental_references),
    )


def test_an_income_row_added_with_a_stored_lease_keeps_the_link(world: _World, ports: LedgerActionPorts) -> None:
    created = _row(
        world,
        ports,
        business_classification=BusinessClassification.BUSINESS,
        irpf_category=RENTAL_LINK_IRPF_CATEGORY,
        arrendamiento_ref=str(world.arrendamiento),
    )

    assert _stored(ports, created).arrendamiento_ref == str(world.arrendamiento)


def test_an_expense_row_added_with_a_stored_property_and_concept_keeps_both(
    world: _World, ports: LedgerActionPorts
) -> None:
    patch = LedgerClassifyPatch(gasto_capital_inmobiliario="comunidad")
    concept = resolve_classification_patch_values(
        patch,
        ("gasto_capital_inmobiliario",),
        current=_row(world, ports, description="seed"),
        operation=world.operation,
    )["gasto_capital_inmobiliario"]

    created = _row(
        world,
        ports,
        direction=TransactionDirection.OUTGOING,
        business_classification=BusinessClassification.BUSINESS,
        irpf_category=RENTAL_LINK_IRPF_CATEGORY,
        inmueble_ref=str(world.inmueble),
        gasto_capital_inmobiliario=concept,
    )

    stored = _stored(ports, created)
    assert stored.inmueble_ref == str(world.inmueble)
    assert str(stored.gasto_capital_inmobiliario) == "comunidad"


def test_a_lease_the_profile_does_not_hold_is_refused_naming_the_listing_door(
    world: _World, ports: LedgerActionPorts
) -> None:
    with pytest.raises(TransactionValidationError) as refused:
        _row(
            world,
            ports,
            business_classification=BusinessClassification.BUSINESS,
            irpf_category=RENTAL_LINK_IRPF_CATEGORY,
            arrendamiento_ref=str(world.arrendamiento + 5),
        )

    assert refused.value.context == {"ref": str(world.arrendamiento + 5), "door": LEASE_LIST_DOOR}


@pytest.mark.parametrize("ref", ["lease-a", "01"])
def test_a_reference_that_is_not_a_canonical_row_key_is_refused(
    world: _World, ports: LedgerActionPorts, ref: str
) -> None:
    created = _row(world, ports)

    with pytest.raises(TransactionValidationError):
        _update(
            world,
            ports,
            created,
            business_classification=BusinessClassification.BUSINESS,
            irpf_category=RENTAL_LINK_IRPF_CATEGORY,
            inmueble_ref=ref,
        )


def test_a_property_the_profile_does_not_hold_is_refused_naming_the_listing_door(
    world: _World, ports: LedgerActionPorts
) -> None:
    created = _row(world, ports, direction=TransactionDirection.OUTGOING)

    with pytest.raises(TransactionValidationError) as refused:
        _update(
            world,
            ports,
            created,
            business_classification=BusinessClassification.BUSINESS,
            irpf_category=RENTAL_LINK_IRPF_CATEGORY,
            inmueble_ref=str(world.inmueble + 5),
        )

    assert refused.value.context == {"ref": str(world.inmueble + 5), "door": PROPERTY_LIST_DOOR}
    assert _stored(ports, created).inmueble_ref is None


@pytest.mark.parametrize("category", [None, "trabajo"])
def test_a_linked_business_row_not_under_the_rental_category_is_refused(
    world: _World, ports: LedgerActionPorts, category: str | None
) -> None:
    created = _row(world, ports)

    with pytest.raises((TransactionValidationError, ValidationError)):
        _update(
            world,
            ports,
            created,
            business_classification=BusinessClassification.BUSINESS,
            irpf_category=category,
            arrendamiento_ref=str(world.arrendamiento),
        )

    assert _stored(ports, created).arrendamiento_ref is None


def test_a_row_naming_a_lease_and_a_property_is_refused(world: _World, ports: LedgerActionPorts) -> None:
    created = _row(world, ports)

    with pytest.raises((TransactionValidationError, ValidationError)):
        _update(
            world,
            ports,
            created,
            business_classification=BusinessClassification.BUSINESS,
            irpf_category=RENTAL_LINK_IRPF_CATEGORY,
            arrendamiento_ref=str(world.arrendamiento),
            inmueble_ref=str(world.inmueble),
        )


def test_an_expense_concept_without_a_property_is_refused(world: _World, ports: LedgerActionPorts) -> None:
    created = _row(world, ports, direction=TransactionDirection.OUTGOING)
    concept = resolve_classification_patch_values(
        LedgerClassifyPatch(gasto_capital_inmobiliario="comunidad"),
        ("gasto_capital_inmobiliario",),
        current=created,
        operation=world.operation,
    )["gasto_capital_inmobiliario"]

    with pytest.raises((TransactionValidationError, ValidationError)):
        _update(
            world,
            ports,
            created,
            business_classification=BusinessClassification.BUSINESS,
            irpf_category=RENTAL_LINK_IRPF_CATEGORY,
            gasto_capital_inmobiliario=concept,
        )


def test_an_expense_concept_the_registry_does_not_declare_is_refused(world: _World, ports: LedgerActionPorts) -> None:
    created = _row(world, ports, direction=TransactionDirection.OUTGOING)

    with pytest.raises(Exception, match="bogus_concepto") as refused:
        resolve_classification_patch_values(
            LedgerClassifyPatch(gasto_capital_inmobiliario="bogus_concepto"),
            ("gasto_capital_inmobiliario",),
            current=created,
            operation=world.operation,
        )

    assert "bogus_concepto" in str(refused.value)


def test_the_csv_table_links_a_row_and_refuses_an_unknown_lease(world: _World, ports: LedgerActionPorts) -> None:
    good = _row(world, ports)
    bad = _row(world, ports, description="other")
    columns = frozenset({"irpf_category", "arrendamiento_ref"})

    patch = build_bulk_row_classification_patch(
        BulkClassifyRow(
            transaction_id=good.transaction_id,
            classification=BusinessClassification.BUSINESS,
            irpf_category=RENTAL_LINK_IRPF_CATEGORY,
            arrendamiento_ref=str(world.arrendamiento),
        ),
        columns,
        current=good,
        operation=world.operation,
    )
    updated = _update(world, ports, good, **{name: getattr(patch, name) for name in patch.model_fields_set})
    assert _stored(ports, updated).arrendamiento_ref == str(world.arrendamiento)

    unknown = build_bulk_row_classification_patch(
        BulkClassifyRow(
            transaction_id=bad.transaction_id,
            classification=BusinessClassification.BUSINESS,
            irpf_category=RENTAL_LINK_IRPF_CATEGORY,
            arrendamiento_ref=str(world.arrendamiento + 9),
        ),
        columns,
        current=bad,
        operation=world.operation,
    )
    with pytest.raises(TransactionValidationError) as refused:
        _update(world, ports, bad, **{name: getattr(unknown, name) for name in unknown.model_fields_set})
    assert LEASE_LIST_DOOR in str(refused.value.context)


def test_a_lease_a_ledger_row_names_is_kept_until_the_link_is_cleared(world: _World, ports: LedgerActionPorts) -> None:
    created = _row(
        world,
        ports,
        business_classification=BusinessClassification.BUSINESS,
        irpf_category=RENTAL_LINK_IRPF_CATEGORY,
        arrendamiento_ref=str(world.arrendamiento),
    )

    with pytest.raises(UserProfileValidationError) as refused:
        _remove(world, ARRENDAMIENTO_SECTION, world.arrendamiento)
    assert refused.value.context is not None
    assert refused.value.context["door"] == "aeat app ledger classify"
    assert refused.value.context["rows"] == 1

    _update(world, ports, created, arrendamiento_ref=None)
    _remove(world, ARRENDAMIENTO_SECTION, world.arrendamiento)


def test_a_property_a_ledger_row_names_is_kept_until_the_link_is_cleared(
    world: _World, ports: LedgerActionPorts
) -> None:
    _remove(world, ARRENDAMIENTO_SECTION, world.arrendamiento)
    created = _row(
        world,
        ports,
        direction=TransactionDirection.OUTGOING,
        business_classification=BusinessClassification.BUSINESS,
        irpf_category=RENTAL_LINK_IRPF_CATEGORY,
        inmueble_ref=str(world.inmueble),
    )

    with pytest.raises(UserProfileValidationError) as refused:
        _remove(world, INMUEBLE_SECTION, world.inmueble)
    assert refused.value.context is not None
    assert refused.value.context["door"] == "aeat app ledger classify"

    _update(world, ports, created, inmueble_ref=None)
    _remove(world, INMUEBLE_SECTION, world.inmueble)
