"""Withdrawing a counterparty's filing name removes the name and nothing else.

The production registry and the real executor run over a stored profile. A
record that also holds an establishment answer and a provincia keeps both,
unchanged and with their own attribution; a record whose only answer was the
name goes with it; withdrawing where no name is stated writes nothing.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

import pytest

from ...adapters.persistence.profile.counterparty_establishment import build_counterparty_establishment_repository
from ...application.ledger.counterparty_establishment import (
    ConfirmedCounterpartyFacts,
    confirmed_counterparty_facts_key,
)
from ...application.ledger.counterparty_operation import (
    LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
    LedgerCounterpartyRequest,
    LedgerCounterpartyResult,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.filing.declared_party_name import DeclaredPartyKind
from . import registered_executor_case_support as conformance

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SUPPLIER_CIF = "B00015016"
_DEFINITION = LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID
_NAME = "Suministros Ficticios del Norte, S.L."


def _request(profile_id: UUID, action: str, **fields: object) -> LedgerCounterpartyRequest:
    return LedgerCounterpartyRequest.model_validate(
        {"profile_id": profile_id, "action": action, "tax_identifier": _SUPPLIER_CIF, **fields}
    )


def _stated_name(profile_id: UUID) -> LedgerCounterpartyRequest:
    return _request(
        profile_id,
        "filing_name",
        asserted_by="operator",
        party_kind=DeclaredPartyKind.ENTITY.value,
        razon_social=_NAME,
    )


def _stored(profile_id: UUID) -> ConfirmedCounterpartyFacts | None:
    key = confirmed_counterparty_facts_key(_SUPPLIER_CIF)
    assert key is not None
    return build_counterparty_establishment_repository(bucket_id=str(profile_id)).load(key)


def test_withdrawing_the_name_keeps_the_establishment_and_provincia_answers(tmp_path: Path) -> None:
    with conformance.conformance_operation_runtime(
        tmp_path / "runtime", cleanup=conformance.OperationRuntimeCloseWitness()
    ) as (driver, registry, profile_id):

        def run(request: LedgerCounterpartyRequest) -> tuple[OperationEffect, LedgerCounterpartyResult]:
            submitted, observed = asyncio.run(
                driver.run(
                    definition_id=_DEFINITION,
                    subject_ref=profile_operation_subject(str(profile_id)),
                    payload=request,
                )
            )
            assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
            effect = observed.projection.effect
            assert isinstance(effect, OperationEffect)
            return effect, conformance.resolve_result_projection(
                driver,
                registry,
                definition_id=_DEFINITION,
                operation_id=submitted.receipt.operation_id,
                terminal_revision=observed.projection.revision,
                projection_type=LedgerCounterpartyResult,
            )

        run(_request(profile_id, "confirm", asserted_by="operator", territorial_scope="es_canarias", note="invoice"))
        run(_request(profile_id, "provincia", asserted_by="operator", provincia_code="08"))
        run(_stated_name(profile_id))
        before = _stored(profile_id)
        assert before is not None
        assert before.declared_filing_name is not None

        effect, withdrawal = run(_request(profile_id, "withdraw_filing_name"))

        assert effect is OperationEffect.UPDATED
        assert (withdrawal.withdrawn, withdrawal.changed) == (True, True)
        assert withdrawal.filing_name is None
        assert withdrawal.facts is not None
        assert withdrawal.facts.provincia_code == "08"
        assert withdrawal.facts.territorial_scope == "es_canarias"
        after = _stored(profile_id)
        assert after is not None
        assert after.declared_filing_name is None
        assert (after.filing_name_asserted_by, after.filing_name_asserted_at) == (None, None)
        # Everything else is the record as it was, down to its attribution.
        assert after == before.model_copy(
            update={"declared_filing_name": None, "filing_name_asserted_by": None, "filing_name_asserted_at": None}
        )

        _effect, viewed = run(_request(profile_id, "view"))
        assert viewed.filing_name is None
        assert viewed.provincia_code == "08"
        assert viewed.resolution is not None
        assert viewed.resolution.territorial_scope == "es_canarias"
        assert {slot.state for slot in viewed.filing_name_slots} == {"missing"}

        effect, repeated = run(_request(profile_id, "withdraw_filing_name"))
        assert effect is OperationEffect.NONE
        assert (repeated.withdrawn, repeated.changed) == (False, False)
        assert _stored(profile_id) == after


def test_a_record_holding_only_the_name_goes_with_it_and_an_unstated_name_writes_nothing(tmp_path: Path) -> None:
    with conformance.conformance_operation_runtime(
        tmp_path / "runtime", cleanup=conformance.OperationRuntimeCloseWitness()
    ) as (driver, registry, profile_id):

        def run(request: LedgerCounterpartyRequest) -> tuple[OperationEffect, LedgerCounterpartyResult]:
            submitted, observed = asyncio.run(
                driver.run(
                    definition_id=_DEFINITION,
                    subject_ref=profile_operation_subject(str(profile_id)),
                    payload=request,
                )
            )
            assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
            effect = observed.projection.effect
            assert isinstance(effect, OperationEffect)
            return effect, conformance.resolve_result_projection(
                driver,
                registry,
                definition_id=_DEFINITION,
                operation_id=submitted.receipt.operation_id,
                terminal_revision=observed.projection.revision,
                projection_type=LedgerCounterpartyResult,
            )

        effect, nothing = run(_request(profile_id, "withdraw_filing_name"))
        assert effect is OperationEffect.NONE
        assert (nothing.withdrawn, nothing.facts) == (False, None)

        run(_stated_name(profile_id))
        assert _stored(profile_id) is not None
        effect, withdrawal = run(_request(profile_id, "withdraw_filing_name"))

        assert effect is OperationEffect.UPDATED
        assert (withdrawal.withdrawn, withdrawal.facts) == (True, None)
        assert _stored(profile_id) is None


def test_a_filing_name_withdrawal_carries_only_the_counterparty() -> None:
    profile_id = UUID("5aa00000-0000-4000-8000-0000000000ef")
    withdrawal = _request(profile_id, "withdraw_filing_name", country_code="ES")
    assert LedgerCounterpartyRequest.model_validate_json(withdrawal.model_dump_json()) == withdrawal

    for invalid in (
        {"party_kind": "entity"},
        {"razon_social": "Ficticia, S.L."},
        {"asserted_by": "operator"},
        {"note": "not a statement"},
        {"territorial_scope": "es_canarias"},
        {"evidenced_scope": "es_canarias"},
        {"provincia_code": "08"},
    ):
        with pytest.raises(ValueError):
            _request(profile_id, "withdraw_filing_name", **invalid)
