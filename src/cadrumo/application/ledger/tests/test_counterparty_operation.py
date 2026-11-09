"""The counterparty operation's published schemas contain only wire-safe values."""

from __future__ import annotations

from uuid import uuid4

import pytest

from ..counterparty_establishment_ports import CounterpartyEstablishmentRepositoryProtocol
from ..counterparty_operation import (
    CounterpartyProvinciaChoice,
    CounterpartyResolutionProjection,
    LedgerCounterpartyRequest,
    LedgerCounterpartyResult,
    build_ledger_counterparty_definition,
    build_ledger_counterparty_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _unused_repository(*, bucket_id: str) -> CounterpartyEstablishmentRepositoryProtocol:
    """Schema binding must not open a repository or inspect its outer adapter."""
    raise AssertionError(f"unexpected repository access for {bucket_id}")


def test_counterparty_public_schema_binds_and_round_trips_scalar_projection() -> None:
    """Reject domain token hooks at registration while retaining three-state facts."""
    definition = build_ledger_counterparty_definition(_unused_repository)
    registration = build_ledger_counterparty_registration(definition)
    assert registration.contract.definition_id == definition.definition_id

    profile_id = uuid4()
    request = LedgerCounterpartyRequest(
        profile_id=profile_id,
        action="view",
        tax_identifier="B00015016",
        evidenced_scope="es_mainland",
    )
    assert LedgerCounterpartyRequest.model_validate_json(request.model_dump_json()) == request

    result = LedgerCounterpartyResult(
        profile_id=profile_id,
        action="view",
        tax_identifier=request.tax_identifier,
        evidenced_scope=request.evidenced_scope,
        resolution=CounterpartyResolutionProjection(
            confirmed_scope="es_canarias",
            evidenced_scope="es_mainland",
            contradiction_detail="The printed evidence disagrees with the prior confirmation.",
        ),
        provincia_code="35",
        provincia_choices=(
            CounterpartyProvinciaChoice(code="35", name="Palmas, Las"),
            CounterpartyProvinciaChoice(code="38", name="Santa Cruz de Tenerife"),
        ),
    )
    assert LedgerCounterpartyResult.model_validate_json(result.model_dump_json()) == result
