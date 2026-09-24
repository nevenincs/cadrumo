"""Retrieving the same AEAT IVA wallet twice credits the compensation once.

Each capture is stored under a key that includes its capture time, so two
retrievals of one wallet are two records. What may not happen is that both
reach Modelo 303: the period's prior-compensation binding has to come from the
one current decision, with every earlier capture kept only as audit history.

Driven through the same two steps the calculation gate takes, over a real
encrypted store: load the period's current decision, then resolve it to the
binding.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from cadrumo.adapters.outbound.aeat.sede.schema import IvaCompensationWalletObservation, IvaCompensationWalletRow
from cadrumo.adapters.persistence.profile.calculation_observations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.application.calculations.binding_prefill import BindingPrefillReport
from cadrumo.application.calculations.iva_wallet_reconciliation import (
    IvaWalletDecisionSourceResolver,
    reconcile_modelo_303_iva_compensation,
)
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.tests.aeat_literal_fixtures import aeat_url

from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TAXPAYER = "12345678Z"
_BUCKET_ID = "36363636-3636-4363-8363-363636363636"
_PERIOD = Period.from_year_and_code(2026, "2T")
_BINDING = "modelo-303-compensacion-pendiente-anteriores"
_FIRST_CAPTURE = datetime(2026, 5, 19, 10, 0, tzinfo=UTC)
_PENDING = Decimal("1200")


def _wallet(captured_at: datetime) -> IvaCompensationWalletObservation:
    return IvaCompensationWalletObservation(
        taxpayer_nif=_TAXPAYER,
        authenticated_identity=_TAXPAYER,
        target_year=2026,
        target_period=_PERIOD,
        rows=(
            IvaCompensationWalletRow(
                generation_year=2026,
                generation_period=Period.from_year_and_code(2026, "1T"),
                generated_amount=_PENDING,
                applied_amount=Decimal("0"),
                pending_amount=_PENDING,
                raw_label="2026 1T",
            ),
        ),
        total_pending=_PENDING,
        source_url=AnyHttpUrl(aeat_url("sede", "/iva/compensaciones")),
        captured_at=captured_at,
        raw_sha256="a" * 64,
    )


def test_a_wallet_retrieved_twice_credits_the_prior_compensation_once(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        observations = CalculationObservationRepository(objects=profile.repository)
        decisions = IvaWalletDecisionRepository(objects=profile.repository)
        snapshot = published_authority_operation().snapshot("303", filing_year=2026, period="2T")

        with bundled_indexed_authority().operation() as operation:
            for captured_at in (_FIRST_CAPTURE, _FIRST_CAPTURE + timedelta(hours=3)):
                reconcile_modelo_303_iva_compensation(
                    snapshot,
                    taxpayer_nif=_TAXPAYER,
                    wallet=_wallet(captured_at),
                    repository=observations,
                    decision_repository=decisions,
                    decided_at=captured_at,
                    local_recurrence=None,
                    prefill_report=BindingPrefillReport(prefilled=(), binding_values={}),
                    operation=operation,
                )

        history = decisions.load_decision_history(_TAXPAYER, _PERIOD)
        current = decisions.load_decision(_TAXPAYER, _PERIOD)
        assert len(history) == 2, "each retrieval keeps its own audit event"
        assert len(decisions.list_decisions()) == 1, "one period holds one current decision"
        assert current is not None
        assert current.wallet_amount == _PENDING

        resolution = IvaWalletDecisionSourceResolver(current).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=2026,
                period=_PERIOD,
                revision=snapshot.revision,
            ),
        )

    assert resolution.binding_values == {_BINDING: _PENDING}
