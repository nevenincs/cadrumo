"""A ledger row names a savings position and its concept through the add, classify and CSV doors.

The profile is a real encrypted profile and the ledger ports are the production composition, so each
case reads the row back from storage. The position's existence in the profile is not judged here.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple
from uuid import UUID

import pytest
from pydantic import ValidationError

from ...adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from ...adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ...application.ledger.action_ports import LedgerActionPorts
from ...application.ledger.classify_correlation import classification_selected_fields_match
from ...application.ledger.classify_patch import (
    build_bulk_row_classification_patch,
    resolve_classification_patch_values,
)
from ...application.ledger.classify_requests import LedgerClassifyPatch
from ...application.ledger.classify_result_projection import classification_result_from_action
from ...application.ledger.ledger_add_command import prepare_ledger_add_command
from ...application.ledger.ledger_add_contracts import LedgerAddRequest
from ...application.ledger.manual_update import update_manual_transaction_fields
from ...application.ledger.models import (
    BulkClassifyRow,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
)
from ...application.ledger.tests.manual_transaction_support import create_manual_transaction
from ...application.user_profile.login_session import authenticate_profile_for_invocation
from ...application.user_profile.registration import register_profile_with_credentials
from ...core.config import override_settings
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.capital_mobiliario_facts import resolve_capital_mobiliario_concept_vocabulary
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.models import Transaction
from ...domain.transactions.savings_link import SAVINGS_LINK_IRPF_CATEGORY
from ..ledger_action_composition import compose_ledger_action_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon
_POSITION = "deposito-1"
_REFUSED = (TransactionValidationError, ValidationError)
_LINK_FIELDS = ("business_classification", "irpf_category", "posicion_ref", "concepto_capital_mobiliario")


class _World(NamedTuple):
    profile_id: str
    operation: PinnedAuthorityOperation


def _row(world: _World, ports: LedgerActionPorts, **fields: object) -> Transaction:
    values: dict[str, object] = {
        "bucket_id": world.profile_id,
        "booked_date": date(_YEAR, 5, 2),
        "amount": Decimal("40.00"),
        "direction": TransactionDirection.INCOMING,
        "description": "interest",
        "business_classification": BusinessClassification.NOT_YET_PROCESSED,
        **fields,
    }
    return create_manual_transaction(ManualLedgerTransactionCommand.model_validate(values), ports=ports).transaction


def _concept(world: _World, ports: LedgerActionPorts, token: str) -> object:
    seed = _row(world, ports, description=f"seed {token}")
    return resolve_classification_patch_values(
        LedgerClassifyPatch(concepto_capital_mobiliario=token),
        ("concepto_capital_mobiliario",),
        current=seed,
        operation=world.operation,
    )["concepto_capital_mobiliario"]


def _update_result(
    world: _World, ports: LedgerActionPorts, transaction: Transaction, **fields: object
) -> ManualLedgerTransactionResult:
    return update_manual_transaction_fields(
        bucket_id=world.profile_id,
        transaction_id=transaction.transaction_id,
        patch=ManualLedgerTransactionPatch.model_validate(fields),
        actor="tester",
        source_command="aeat app ledger classify",
        ports=ports,
    )


def _update(world: _World, ports: LedgerActionPorts, transaction: Transaction, **fields: object) -> Transaction:
    return _update_result(world, ports, transaction, **fields).transaction


def _stored(ports: LedgerActionPorts, transaction: Transaction) -> Transaction:
    return ports.transaction_repository.load().transactions[transaction.transaction_id]


@pytest.fixture
def world(tmp_path: Path) -> Iterator[_World]:
    secret = f"ledger-savings-{tmp_path.name}"
    with (
        override_settings(cadrumo_output_language="", cadrumo_secret_passphrase=secret),
        isolated_profile_storage_root(tmp_path=tmp_path),
        bundled_indexed_authority().operation() as operation,
    ):
        outcome = register_profile_with_credentials(
            label="Ledger savings links",
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


@pytest.fixture
def ports(world: _World) -> LedgerActionPorts:
    return compose_ledger_action_ports(bucket_id=world.profile_id, operation=world.operation)


def test_an_income_row_added_with_a_position_and_concept_keeps_both(world: _World, ports: LedgerActionPorts) -> None:
    concept = _concept(world, ports, "intereses")

    created = _row(
        world,
        ports,
        business_classification=BusinessClassification.BUSINESS,
        irpf_category=SAVINGS_LINK_IRPF_CATEGORY,
        posicion_ref=_POSITION,
        concepto_capital_mobiliario=concept,
    )

    stored = _stored(ports, created)
    assert stored.posicion_ref == _POSITION
    assert str(stored.concepto_capital_mobiliario) == "intereses"


def test_every_declared_concept_can_be_linked_through_classification(world: _World, ports: LedgerActionPorts) -> None:
    for token in resolve_capital_mobiliario_concept_vocabulary(authority=world.operation).tokens:
        created = _row(world, ports, description=f"row {token}")
        patch = resolve_classification_patch_values(
            LedgerClassifyPatch(
                business_classification="BUSINESS",
                irpf_category=SAVINGS_LINK_IRPF_CATEGORY,
                posicion_ref=f"  {_POSITION}  ",
                concepto_capital_mobiliario=token,
            ),
            _LINK_FIELDS,
            current=created,
            operation=world.operation,
        )

        updated = _update(world, ports, created, **patch)

        stored = _stored(ports, updated)
        assert stored.posicion_ref == _POSITION
        assert str(stored.concepto_capital_mobiliario) == token


def test_a_concept_the_registry_does_not_declare_is_refused(world: _World, ports: LedgerActionPorts) -> None:
    created = _row(world, ports)

    with pytest.raises(Exception, match="bogus_concepto"):
        resolve_classification_patch_values(
            LedgerClassifyPatch(concepto_capital_mobiliario="bogus_concepto"),
            ("concepto_capital_mobiliario",),
            current=created,
            operation=world.operation,
        )


@pytest.mark.parametrize("category", [None, "trabajo", "capital_inmobiliario"])
def test_a_linked_business_row_not_under_the_savings_category_is_refused(
    world: _World, ports: LedgerActionPorts, category: str | None
) -> None:
    created = _row(world, ports)
    concept = _concept(world, ports, "intereses")

    with pytest.raises(_REFUSED):
        _update(
            world,
            ports,
            created,
            business_classification=BusinessClassification.BUSINESS,
            irpf_category=category,
            posicion_ref=_POSITION,
            concepto_capital_mobiliario=concept,
        )

    assert _stored(ports, created).posicion_ref is None


def test_a_linked_personal_row_carries_no_category(world: _World, ports: LedgerActionPorts) -> None:
    created = _row(world, ports)
    concept = _concept(world, ports, "intereses")

    linked = _update(
        world,
        ports,
        created,
        business_classification=BusinessClassification.PERSONAL,
        posicion_ref=_POSITION,
        concepto_capital_mobiliario=concept,
    )
    assert _stored(ports, linked).posicion_ref == _POSITION


def test_a_position_without_a_concept_and_a_concept_without_a_position_are_refused(
    world: _World, ports: LedgerActionPorts
) -> None:
    created = _row(world, ports)
    concept = _concept(world, ports, "intereses")

    with pytest.raises(_REFUSED):
        _update(world, ports, created, business_classification=BusinessClassification.PERSONAL, posicion_ref=_POSITION)
    with pytest.raises(_REFUSED):
        _update(
            world,
            ports,
            created,
            business_classification=BusinessClassification.PERSONAL,
            concepto_capital_mobiliario=concept,
        )


def test_a_row_naming_a_position_and_a_lease_is_refused(world: _World, ports: LedgerActionPorts) -> None:
    created = _row(world, ports)
    concept = _concept(world, ports, "intereses")

    with pytest.raises(_REFUSED):
        _update(
            world,
            ports,
            created,
            business_classification=BusinessClassification.PERSONAL,
            posicion_ref=_POSITION,
            concepto_capital_mobiliario=concept,
            arrendamiento_ref="1",
        )


def test_clearing_both_fields_removes_the_link(world: _World, ports: LedgerActionPorts) -> None:
    concept = _concept(world, ports, "dividendos")
    created = _row(
        world,
        ports,
        business_classification=BusinessClassification.BUSINESS,
        irpf_category=SAVINGS_LINK_IRPF_CATEGORY,
        posicion_ref=_POSITION,
        concepto_capital_mobiliario=concept,
    )
    cleared = resolve_classification_patch_values(
        LedgerClassifyPatch(posicion_ref="  ", concepto_capital_mobiliario=""),
        ("posicion_ref", "concepto_capital_mobiliario"),
        current=created,
        operation=world.operation,
    )
    assert cleared == {"posicion_ref": None, "concepto_capital_mobiliario": None}

    updated = _update(world, ports, created, **cleared)

    stored = _stored(ports, updated)
    assert stored.posicion_ref is None
    assert stored.concepto_capital_mobiliario is None


def test_the_csv_table_links_a_row_and_refuses_a_wrong_category(world: _World, ports: LedgerActionPorts) -> None:
    good = _row(world, ports)
    bad = _row(world, ports, description="other")
    columns = frozenset({"irpf_category", "posicion_ref", "concepto_capital_mobiliario"})

    patch = build_bulk_row_classification_patch(
        BulkClassifyRow(
            transaction_id=good.transaction_id,
            classification=BusinessClassification.BUSINESS,
            irpf_category=SAVINGS_LINK_IRPF_CATEGORY,
            posicion_ref=_POSITION,
            concepto_capital_mobiliario="intereses",
        ),
        columns,
        current=good,
        operation=world.operation,
    )
    updated = _update(world, ports, good, **{name: getattr(patch, name) for name in patch.model_fields_set})
    assert _stored(ports, updated).posicion_ref == _POSITION

    wrong = build_bulk_row_classification_patch(
        BulkClassifyRow(
            transaction_id=bad.transaction_id,
            classification=BusinessClassification.BUSINESS,
            irpf_category="trabajo",
            posicion_ref=_POSITION,
            concepto_capital_mobiliario="intereses",
        ),
        columns,
        current=bad,
        operation=world.operation,
    )
    with pytest.raises(_REFUSED):
        _update(world, ports, bad, **{name: getattr(wrong, name) for name in wrong.model_fields_set})


def _add_request(world: _World, *, irpf_category: str) -> LedgerAddRequest:
    return LedgerAddRequest(
        profile_id=UUID(world.profile_id),
        booked_date=date(_YEAR, 5, 2).isoformat(),
        amount="40.00",
        direction="INCOMING",
        description="interest",
        business_classification="BUSINESS",
        irpf_category=irpf_category,
        posicion_ref=_POSITION,
        concepto_capital_mobiliario="intereses",
    )


def test_the_add_request_resolves_the_concept_into_the_command(world: _World) -> None:
    command = prepare_ledger_add_command(
        _add_request(world, irpf_category=SAVINGS_LINK_IRPF_CATEGORY), world.operation, actor="tester"
    )

    assert command.posicion_ref == _POSITION
    assert str(command.concepto_capital_mobiliario) == "intereses"


def test_the_add_request_refuses_a_business_row_under_another_category(world: _World) -> None:
    with pytest.raises(_REFUSED):
        prepare_ledger_add_command(_add_request(world, irpf_category="trabajo"), world.operation, actor="tester")


def test_a_settled_classification_is_correlated_with_the_savings_link(world: _World, ports: LedgerActionPorts) -> None:
    created = _row(world, ports)
    patch = LedgerClassifyPatch(
        business_classification="BUSINESS",
        irpf_category=SAVINGS_LINK_IRPF_CATEGORY,
        posicion_ref=_POSITION,
        concepto_capital_mobiliario="intereses",
    )
    resolved = resolve_classification_patch_values(patch, _LINK_FIELDS, current=created, operation=world.operation)
    result = classification_result_from_action(
        UUID(world.profile_id), _update_result(world, ports, created, **resolved)
    )

    assert result.posicion_ref == _POSITION
    assert result.concepto_capital_mobiliario == "intereses"
    assert classification_selected_fields_match(patch=patch, fields=_LINK_FIELDS, m210=None, result=result)
    stale = patch.model_copy(update={"posicion_ref": "otra"})
    assert not classification_selected_fields_match(patch=stale, fields=_LINK_FIELDS, m210=None, result=result)
