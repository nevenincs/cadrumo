"""Inspect real encrypted repository state in owning fixtures."""

from __future__ import annotations

from .....application.calculations.observations_repository import (
    IvaWalletDecisionEnvelopePayload,
    require_observation_period,
)
from .....core.external_constants import UTF_8_ENCODING
from .....core.identity.tax_id import same_tax_identifier
from .....core.period import Period
from .....domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ...storage.envelope.contract import Envelope
from ..calculation_observations import IvaWalletDecisionRepository


def load_decision_history(
    self: IvaWalletDecisionRepository, taxpayer_nif: str, target_period: Period
) -> tuple[IvaCompensationReconciliationDecision, ...]:
    """Return decision history for one taxpayer and target period.

    Returns an immutable tuple of :class:`IvaCompensationReconciliationDecision`.
    """
    filing_period = require_observation_period(target_period)
    decisions: list[IvaCompensationReconciliationDecision] = []
    for record in self._objects.list_records(
        self.history_namespace, expected_class=self.sensitivity, max_supported_version=self.history_schema_version
    ):
        envelope = Envelope[IvaWalletDecisionEnvelopePayload].model_validate_json(record.payload.decode(UTF_8_ENCODING))
        decision = envelope.payload.decision
        if same_tax_identifier(decision.taxpayer_nif, taxpayer_nif) and decision.target_period == filing_period:
            decisions.append(decision)
    return tuple(sorted(decisions, key=lambda item: (item.decided_at, item.wallet_captured_at or item.decided_at)))
