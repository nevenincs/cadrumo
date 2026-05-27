"""Encrypted persistence for past-filing casilla observations.

Stores `RegistryModeloObservation` records — `(modelo, filing_year,
period, casilla_values)` — as encrypted audit envelopes in the
`SecureObjectRepository`. The records are the substrate the
multi-year resolver consults so annual modelos can roll up prior
quarterlies, IVA prorrata can compute its four-year backward mean,
IS BIN carryforward can replay prior-year bases imponibles
negativas, and IVA regularización inversiones can apply its 5/10
year straight-line schedule.

Producers are out of scope for this module: the modelo filing flow
will write here when an operator successfully files via the app,
and the live-AEAT capture path will write here when justificantes
are parsed. This module exposes only the typed read/write surface.

Sensitivity is `AUDIT` — these records reconstruct exactly what
was filed and so are identity-bearing tax substrate. They are
stored encrypted at rest.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.storage import (
    CALCULATION_OBSERVATIONS_NAMESPACE,
    IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE,
    IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE,
    Envelope,
    SensitivityClass,
    safe_repository_id,
)
from ...adapters.persistence.storage.envelope._secure_repository import SecureBoundRepository
from ...domain.calculations.registry._bindings import RegistryModeloObservation
from ._iva_wallet_reconciliation import IvaCompensationReconciliationDecision


class _ObservationEnvelopePayload(BaseModel):
    """Serialisable wrapper around a `RegistryModeloObservation`.

    The runtime model lives in `_bindings.py` and is itself frozen
    pydantic v2 with `extra="forbid"`. We wrap it to keep the
    envelope schema identical to other repositories' shape (one
    `payload` field) and to leave room for future per-observation
    metadata (e.g., `captured_from`, `captured_at`, evidence
    pointer) without breaking the inner record.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    observation: RegistryModeloObservation
    captured_at: datetime
    source_kind: str = Field(
        min_length=1,
        max_length=64,
        description="Where this observation came from: app_filing | aeat_sede_justificante | operator_manual",
    )


class _IvaWalletDecisionEnvelopePayload(BaseModel):
    """Serialisable wrapper for an IVA wallet reconciliation decision."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    decision: IvaCompensationReconciliationDecision


def _decision_payload_digest(decision: IvaCompensationReconciliationDecision) -> str:
    return hashlib.sha256(decision.model_dump_json().encode("utf-8")).hexdigest()


def observation_key(modelo: str, filing_year: int, period: str) -> str:
    """Stable repository key for a `(modelo, filing_year, period)` triple.

    Validated through `safe_repository_id` so each component is
    constrained to the SecureObjectRepository's id contract before
    composition.
    """

    safe_repository_id(modelo, context="modelo")
    safe_repository_id(period, context="period")
    if not 2000 <= filing_year <= 2099:
        raise ValueError(f"observation filing_year {filing_year} out of supported range [2000, 2099]")
    return f"{modelo}:{filing_year}:{period}"


def iva_wallet_decision_key(taxpayer_nif: str, target_year: int, target_period: str) -> str:
    """Opaque latest-decision key for one taxpayer and Modelo 303 target period.

    Secure-object payloads are encrypted, but object keys are storage metadata.
    Hash the taxpayer/period tuple so the repository does not expose NIF/NIE
    values in cleartext database rows.
    """

    taxpayer_token = taxpayer_nif.strip().upper()
    if not taxpayer_token:
        raise ValueError("taxpayer_nif must be non-empty")
    safe_repository_id(target_period, context="target_period")
    if not 2000 <= target_year <= 2099:
        raise ValueError(f"IVA wallet target_year {target_year} out of supported range [2000, 2099]")
    digest = hashlib.sha256(
        "\x1f".join((taxpayer_token, str(target_year), target_period.strip().upper())).encode("utf-8")
    ).hexdigest()
    return f"iva-wallet-decision:{digest}"


def iva_wallet_decision_event_key(decision: IvaCompensationReconciliationDecision) -> str:
    """Opaque immutable event key for one persisted reconciliation decision."""

    taxpayer_token = decision.taxpayer_nif.strip().upper()
    if not taxpayer_token:
        raise ValueError("decision taxpayer_nif must be non-empty")
    digest = hashlib.sha256(
        "\x1f".join(
            (
                taxpayer_token,
                str(decision.target_year),
                decision.target_period.strip().upper(),
                decision.decided_at.isoformat(),
                decision.wallet_captured_at.isoformat() if decision.wallet_captured_at is not None else "",
                _decision_payload_digest(decision),
            )
        ).encode("utf-8")
    ).hexdigest()
    return f"iva-wallet-decision-event:{digest}"


def _legacy_iva_wallet_decision_key(taxpayer_nif: str, target_year: int, target_period: str) -> str:
    """Pre-hardening cleartext key kept only as a read fallback."""

    safe_repository_id(taxpayer_nif, context="taxpayer_nif")
    safe_repository_id(target_period, context="target_period")
    if not 2000 <= target_year <= 2099:
        raise ValueError(f"IVA wallet target_year {target_year} out of supported range [2000, 2099]")
    return f"{taxpayer_nif}:{target_year}:{target_period}"


class CalculationObservationRepository(SecureBoundRepository[_ObservationEnvelopePayload]):
    """Repository over encrypted SQL-backed past-filing observations."""

    namespace: ClassVar[str] = CALCULATION_OBSERVATIONS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = CALCULATION_OBSERVATIONS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = CALCULATION_OBSERVATIONS_NAMESPACE.schema_version
    payload_type: ClassVar[type[_ObservationEnvelopePayload]] = _ObservationEnvelopePayload

    def extract_identifier(self, payload: _ObservationEnvelopePayload) -> str:
        observation = payload.observation
        return observation_key(observation.modelo, observation.filing_year, observation.period)

    def load_observation(
        self,
        modelo: str,
        filing_year: int,
        period: str,
    ) -> _ObservationEnvelopePayload | None:
        """Return the persisted observation for one (modelo, year, period) or None."""

        return self.load(observation_key(modelo, filing_year, period))

    def save_observation(
        self,
        observation: RegistryModeloObservation,
        *,
        source_kind: str,
        captured_at: datetime | None = None,
    ) -> None:
        """Persist `observation` keyed by its (modelo, filing_year, period)."""

        when = captured_at if captured_at is not None else datetime.now(UTC)
        payload = _ObservationEnvelopePayload(
            observation=observation,
            captured_at=when,
            source_kind=source_kind,
        )
        self.save(payload)

    def delete_observation(
        self,
        modelo: str,
        filing_year: int,
        period: str,
    ) -> bool:
        """Remove the observation for one (modelo, year, period); return whether a row was deleted."""

        return self.delete(observation_key(modelo, filing_year, period))

    def iter_modelo(self, modelo: str) -> Iterator[_ObservationEnvelopePayload]:
        """Yield every persisted observation for `modelo` in unspecified order.

        Used by the multi-year resolver to scan all known prior
        filings for a modelo without per-year/period probing.
        """

        safe_repository_id(modelo, context="modelo")
        for payload in self.iter_records():
            if payload.observation.modelo == modelo:
                yield payload


class IvaWalletDecisionRepository(SecureBoundRepository[_IvaWalletDecisionEnvelopePayload]):
    """Repository over encrypted SQL-backed IVA wallet reconciliation decisions.

    Holds one latest decision per `(taxpayer_nif, target_year, target_period)`
    triple for calculation lookup, and also writes every distinct decision to
    an immutable audit-event namespace. Decisions are AUDIT-class — they record
    the resolved gap between a taxpayer's local IVA compensation recurrence and
    the live AEAT wallet, which downstream calculation chains consult.
    """

    namespace: ClassVar[str] = IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE.namespace
    history_namespace: ClassVar[str] = IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE.schema_version
    payload_type: ClassVar[type[_IvaWalletDecisionEnvelopePayload]] = _IvaWalletDecisionEnvelopePayload

    def extract_identifier(self, payload: _IvaWalletDecisionEnvelopePayload) -> str:
        decision = payload.decision
        return iva_wallet_decision_key(decision.taxpayer_nif, decision.target_year, decision.target_period)

    def save_decision(self, decision: IvaCompensationReconciliationDecision) -> None:
        """Persist `decision` to latest lookup and immutable audit history."""

        payload = _IvaWalletDecisionEnvelopePayload(decision=decision)
        super().save(payload)
        envelope = Envelope[_IvaWalletDecisionEnvelopePayload](
            schema_version=self.schema_version,
            written_at=datetime.now(UTC),
            classification=self.sensitivity,
            payload=payload,
        )
        self._objects.save(
            namespace=self.history_namespace,
            object_key=iva_wallet_decision_event_key(decision),
            classification=self.sensitivity,
            schema_version=self.schema_version,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

    def load_decision(
        self,
        taxpayer_nif: str,
        target_year: int,
        target_period: str,
    ) -> IvaCompensationReconciliationDecision | None:
        """Return the latest persisted IVA wallet reconciliation decision."""

        payload = super().load(iva_wallet_decision_key(taxpayer_nif, target_year, target_period))
        if payload is None:
            payload = super().load(_legacy_iva_wallet_decision_key(taxpayer_nif, target_year, target_period))
        return payload.decision if payload is not None else None

    def list_decisions(self) -> tuple[IvaCompensationReconciliationDecision, ...]:
        """Return the latest persisted IVA wallet decisions in target-period order."""

        return tuple(
            sorted(
                (payload.decision for payload in self.iter_records()),
                key=lambda decision: (
                    decision.target_year,
                    decision.target_period,
                    decision.taxpayer_nif,
                    decision.decided_at,
                ),
            )
        )

    def load_decision_history(
        self,
        taxpayer_nif: str,
        target_year: int,
        target_period: str,
    ) -> tuple[IvaCompensationReconciliationDecision, ...]:
        """Return immutable decision history for one taxpayer and target period."""

        taxpayer_token = taxpayer_nif.strip().upper()
        decisions: list[IvaCompensationReconciliationDecision] = []
        for record in self._objects.list_records(
            self.history_namespace,
            expected_class=self.sensitivity,
            max_supported_version=self.schema_version,
        ):
            envelope = Envelope[_IvaWalletDecisionEnvelopePayload].model_validate_json(
                record.payload.decode("utf-8")
            )
            decision = envelope.payload.decision
            if (
                decision.taxpayer_nif.strip().upper() == taxpayer_token
                and decision.target_year == target_year
                and decision.target_period == target_period
            ):
                decisions.append(decision)
        return tuple(sorted(decisions, key=lambda item: (item.decided_at, item.wallet_captured_at or item.decided_at)))


__all__ = [
    "CalculationObservationRepository",
    "IvaWalletDecisionRepository",
    "iva_wallet_decision_event_key",
    "iva_wallet_decision_key",
    "observation_key",
]
