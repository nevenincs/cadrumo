"""A counterparty's filing name is stated through the registered counterparty operation.

The production registry and the real executor run over a stored profile: a
statement stores the name on the counterparty's encrypted record and serves it
back, a view shows it, the same statement again changes nothing, and parts that
form no filing name are refused with the registered code before anything is
written.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

import pytest

from ...adapters.persistence.profile.counterparty_establishment import build_counterparty_establishment_repository
from ...application.ledger.counterparty_establishment import (
    CounterpartyFilingNameInputError,
    confirmed_counterparty_facts_key,
)
from ...application.ledger.counterparty_operation import (
    LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
    CounterpartyFilingNameRendering,
    LedgerCounterpartyRequest,
    LedgerCounterpartyResult,
)
from ...core.errors.error_codes import get_registered_error_code
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.filing.declared_party_name import DeclaredPartyKind
from . import registered_executor_case_support as conformance

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SUPPLIER_CIF = "B00015016"
_DEFINITION = LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID


def _statement(profile_id: UUID, **parts: object) -> LedgerCounterpartyRequest:
    return LedgerCounterpartyRequest.model_validate(
        {
            "profile_id": profile_id,
            "action": "filing_name",
            "tax_identifier": _SUPPLIER_CIF,
            "asserted_by": "operator",
            **parts,
        }
    )


def test_a_statement_stores_the_name_a_view_shows_it_and_a_retry_changes_nothing(tmp_path: Path) -> None:
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

        statement = _statement(
            profile_id,
            party_kind=DeclaredPartyKind.ENTITY.value,
            razon_social="Suministros Ficticios del Norte Sociedad Limitada",
            renderings=(CounterpartyFilingNameRendering(width=40, text="Suministros Ficticios del Norte S.L."),),
        )
        effect, stated = run(statement)

        assert effect is OperationEffect.UPDATED
        assert stated.recorded is True
        assert stated.filing_name is not None
        assert stated.filing_name.razon_social == "Suministros Ficticios del Norte Sociedad Limitada"
        assert stated.filing_name.renderings == statement.renderings
        assert stated.filing_name.asserted_by == "operator"
        key = confirmed_counterparty_facts_key(_SUPPLIER_CIF)
        assert key is not None
        persisted = build_counterparty_establishment_repository(bucket_id=str(profile_id)).load(key)
        assert persisted is not None
        assert persisted.declared_filing_name is not None
        assert persisted.declared_filing_name.razon_social == "Suministros Ficticios del Norte Sociedad Limitada"

        effect, viewed = run(
            LedgerCounterpartyRequest(profile_id=profile_id, action="view", tax_identifier=_SUPPLIER_CIF)
        )
        assert effect is OperationEffect.NONE
        assert viewed.filing_name == stated.filing_name

        effect, retried = run(statement)
        assert effect is OperationEffect.NONE
        assert retried.recorded is False
        assert retried.filing_name == stated.filing_name


def test_parts_that_form_no_filing_name_are_refused_and_nothing_is_written(tmp_path: Path) -> None:
    with conformance.conformance_operation_runtime(
        tmp_path / "runtime", cleanup=conformance.OperationRuntimeCloseWitness()
    ) as (driver, _registry, profile_id):
        # A natural person with neither a second surname nor the statement that there is none.
        _submitted, observed = asyncio.run(
            driver.run(
                definition_id=_DEFINITION,
                subject_ref=profile_operation_subject(str(profile_id)),
                payload=_statement(
                    profile_id,
                    party_kind=DeclaredPartyKind.NATURAL_PERSON.value,
                    primer_apellido="Ejemplo",
                    nombre="Ana",
                ),
            )
        )

        assert observed.projection.terminal_condition is OperationTerminalCondition.REFUSED
        assert observed.projection.effect is OperationEffect.NONE
        assert observed.projection.refusal_ref == get_registered_error_code(CounterpartyFilingNameInputError).code
        key = confirmed_counterparty_facts_key(_SUPPLIER_CIF)
        assert key is not None
        assert build_counterparty_establishment_repository(bucket_id=str(profile_id)).load(key) is None


def test_a_filing_name_statement_carries_only_its_own_answer() -> None:
    profile_id = UUID("5aa00000-0000-4000-8000-0000000000ee")
    statement = _statement(profile_id, party_kind="entity", razon_social="Ficticia, S.L.")
    assert LedgerCounterpartyRequest.model_validate_json(statement.model_dump_json()) == statement

    for invalid in (
        {"action": "filing_name", "razon_social": "Ficticia, S.L."},
        {"action": "filing_name", "party_kind": "entity", "razon_social": "Ficticia, S.L.", "provincia_code": "08"},
        {"action": "filing_name", "party_kind": "entity", "territorial_scope": "es_mainland"},
        {"action": "confirm", "territorial_scope": "es_mainland", "party_kind": "entity"},
        {"action": "view", "asserted_by": None, "razon_social": "Ficticia, S.L."},
    ):
        with pytest.raises(ValueError):
            LedgerCounterpartyRequest.model_validate(
                {"profile_id": profile_id, "tax_identifier": _SUPPLIER_CIF, "asserted_by": "operator", **invalid}
            )
