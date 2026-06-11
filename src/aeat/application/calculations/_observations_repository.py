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

Sensitivity is :class:`SensitivityClass` ``AUDIT`` — these records
reconstruct exactly what was filed and so are identity-bearing tax
substrate. They are stored encrypted at rest through an
:class:`Envelope`-wrapped repository.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import datetime
from typing import ClassVar, override

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.storage import (
    CALCULATION_OBSERVATIONS_NAMESPACE,
    IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE,
    IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE,
    Envelope,
    SensitivityClass,
    safe_repository_id,
)
from ...adapters.persistence.storage.envelope import SecureBoundRepository
from ...core import Period
from ...core.external_constants import UTF_8_ENCODING
from ...core.time import now
from ...domain.calculations.registry import RegistryModeloObservation
from ...domain.iva_compensation._reconciliation import IvaCompensationReconciliationDecision
from ._errors import ObservationKeyError


class _ObservationEnvelopePayload(BaseModel):
    """Serialisable wrapper around a `RegistryModeloObservation`.

    The runtime model lives in `_bindings.py` and is itself frozen
    pydantic v2 with `extra="forbid"`. We wrap it to keep the
    envelope schema identical to other repositories' shape (one
    `payload` field) and to leave room for future per-observation
    metadata (e.g., `captured_from`, `captured_at`, evidence
    pointer) without breaking the inner record.

    The ``stamped_revision_id`` field is the registry revision id the
    source filing resolved to at capture time (ADR
    ``2026-06-10-period-revision-resolution-adr``, Ruling 3 / R2).
    It is ``None`` for legacy records persisted before this field
    was introduced; carry-read code MUST treat a missing stamp as a
    non-blocking advisory rather than a blocker so historical data
    degrades loudly rather than being silently refused or silently
    accepted. New records MUST stamp the revision id from the
    :class:`RegistrySnapshot` the producer already holds at write
    time.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    observation: RegistryModeloObservation
    captured_at: datetime
    source_kind: str = Field(
        min_length=1,
        max_length=64,
        description="Where this observation came from: app_filing | aeat_sede_justificante | operator_manual",
    )
    member_nif: str | None = Field(
        default=None,
        max_length=16,
        description=(
            "Optional grupo-de-entidades member NIF. When set, the storage "
            "identifier is widened so distinct members' filings for the same "
            "(modelo, filing_year, period) persist as separate rows rather than "
            "overwriting one another — the cross-member fan-in the 353<-322 "
            "per_grupo_member aggregation enumerates. None preserves the "
            "single-filer (modelo, filing_year, period) key bit-for-bit."
        ),
    )
    stamped_revision_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description=(
            "Registry revision id the source filing resolved to at capture time "
            "(ADR 2026-06-10-period-revision-resolution-adr, Ruling 3 / R2). "
            "None for legacy records — carry-read must surface a non-blocking "
            "advisory rather than blocking or silently accepting unstamped records."
        ),
    )


class _IvaWalletDecisionEnvelopePayload(BaseModel):
    """Serialisable wrapper for an IVA wallet reconciliation decision."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    decision: IvaCompensationReconciliationDecision


def _decision_payload_digest(decision: IvaCompensationReconciliationDecision) -> str:
    return hashlib.sha256(decision.model_dump_json().encode(UTF_8_ENCODING)).hexdigest()


def _require_observation_period(period: Period) -> Period:
    if not isinstance(period, Period):
        raise ObservationKeyError("observation period must be an aeat.core.Period")
    return period


def observation_key(modelo: str, period: Period) -> str:
    """Stable repository key for a `(modelo, Period)` pair.

    Validated through `safe_repository_id` so each component is
    constrained to the SecureObjectRepository's id contract before
    composition.
    """
    filing_period = _require_observation_period(period)
    filing_year = filing_period.filing_year
    period_token = filing_period.registry_token
    safe_repository_id(modelo, context="modelo")
    safe_repository_id(period_token, context="period")
    if not 2000 <= filing_year <= 2099:
        raise ObservationKeyError(f"observation filing_year {filing_year} out of supported range [2000, 2099]")
    return f"{modelo}:{filing_year}:{period_token}"


def member_observation_key(modelo: str, period: Period, member_nif: str | None) -> str:
    """Storage key for an observation, widened by a grupo member NIF when present.

    When ``member_nif`` is ``None`` the key is the single-filer
    ``observation_key`` unchanged, so every existing consumer (the default
    previous_filing path, the multi-year resolver) keys identically. When set,
    the member NIF is appended so two members' filings for the same
    ``(modelo, filing_year, period)`` persist as distinct rows — the cross-member
    fan-in the 353<-322 ``per_grupo_member`` aggregation enumerates and sums.
    """
    base = observation_key(modelo, period)
    if member_nif is None:
        return base
    safe_repository_id(member_nif, context="member_nif")
    return f"{base}:{member_nif}"


def iva_wallet_decision_key(taxpayer_nif: str, target_year: int, target_period: str) -> str:
    """Opaque latest-decision key for one taxpayer and Modelo 303 target period.

    Secure-object payloads are encrypted, but object keys are storage metadata.
    Hash the taxpayer/period tuple so the repository does not expose NIF/NIE
    values in cleartext database rows.
    """
    taxpayer_token = taxpayer_nif.strip().upper()
    if not taxpayer_token:
        raise ObservationKeyError("taxpayer_nif must be non-empty")
    safe_repository_id(target_period, context="target_period")
    if not 2000 <= target_year <= 2099:
        raise ObservationKeyError(f"IVA wallet target_year {target_year} out of supported range [2000, 2099]")
    digest = hashlib.sha256(
        "\x1f".join((taxpayer_token, str(target_year), target_period.strip().upper())).encode(UTF_8_ENCODING),
    ).hexdigest()
    return f"iva-wallet-decision:{digest}"


def iva_wallet_decision_event_key(decision: IvaCompensationReconciliationDecision) -> str:
    """Opaque immutable event key for one persisted reconciliation decision."""
    taxpayer_token = decision.taxpayer_nif.strip().upper()
    if not taxpayer_token:
        raise ObservationKeyError("decision taxpayer_nif must be non-empty")
    digest = hashlib.sha256(
        "\x1f".join(
            (
                taxpayer_token,
                str(decision.target_year),
                decision.target_period.strip().upper(),
                decision.decided_at.isoformat(),
                decision.wallet_captured_at.isoformat() if decision.wallet_captured_at is not None else "",
                _decision_payload_digest(decision),
            ),
        ).encode(UTF_8_ENCODING),
    ).hexdigest()
    return f"iva-wallet-decision-event:{digest}"


class CalculationObservationRepository(SecureBoundRepository[_ObservationEnvelopePayload]):
    """Repository over encrypted SQL-backed past-filing observations."""

    namespace: ClassVar[str] = CALCULATION_OBSERVATIONS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = CALCULATION_OBSERVATIONS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = CALCULATION_OBSERVATIONS_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = _ObservationEnvelopePayload

    @override
    def extract_identifier(self, payload: _ObservationEnvelopePayload) -> str:
        observation = payload.observation
        period = Period.from_year_and_code(observation.filing_year, observation.period)
        return member_observation_key(
            observation.modelo,
            period,
            payload.member_nif,
        )

    def load_observation(
        self,
        modelo: str,
        filing_year: int,
        period: str,
    ) -> _ObservationEnvelopePayload | None:
        """Return the persisted observation for one (modelo, year, period token) or None."""
        filing_period = Period.from_year_and_code(filing_year, period)
        return self.load(observation_key(modelo, filing_period))

    def save_observation(
        self,
        observation: RegistryModeloObservation,
        *,
        source_kind: str,
        captured_at: datetime | None = None,
        member_nif: str | None = None,
        stamped_revision_id: str | None = None,
    ) -> None:
        """Persist `observation` keyed by its (modelo, filing_year, period).

        ``member_nif`` is an optional grupo-de-entidades member NIF. When
        supplied, the storage identifier is widened (see
        :func:`member_observation_key`) so distinct members' filings for the
        same (modelo, filing_year, period) persist as separate rows instead of
        overwriting — the cross-member fan-in the 353<-322 ``per_grupo_member``
        aggregation enumerates. When ``None`` the single-filer key is unchanged.

        ``stamped_revision_id`` is the registry revision id the source filing
        resolved to at capture time (ADR 2026-06-10-period-revision-resolution-adr,
        Ruling 3 / R2). Producers that hold a :class:`RegistrySnapshot` MUST
        pass ``snapshot.revision.id`` here. Legacy callers that do not yet have
        access to the revision id should leave this ``None``; the carry-read gate
        will surface a non-blocking advisory rather than blocking silently.
        """
        when = captured_at if captured_at is not None else now()
        payload = _ObservationEnvelopePayload(
            observation=observation,
            captured_at=when,
            source_kind=source_kind,
            member_nif=member_nif,
            stamped_revision_id=stamped_revision_id,
        )
        self.save(payload)

    def delete_observation(
        self,
        modelo: str,
        filing_year: int,
        period: str,
    ) -> bool:
        """Remove the observation for one (modelo, year, period token); return whether a row was deleted."""
        filing_period = Period.from_year_and_code(filing_year, period)
        return self.delete(observation_key(modelo, filing_period))

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
    payload_type: ClassVar[type[BaseModel]] = _IvaWalletDecisionEnvelopePayload

    @override
    def extract_identifier(self, payload: _IvaWalletDecisionEnvelopePayload) -> str:
        decision = payload.decision
        return iva_wallet_decision_key(decision.taxpayer_nif, decision.target_year, decision.target_period)

    def save_decision(self, decision: IvaCompensationReconciliationDecision) -> None:
        """Persist `decision` to latest lookup and immutable audit history."""
        payload = _IvaWalletDecisionEnvelopePayload(decision=decision)
        super().save(payload)
        envelope = Envelope[_IvaWalletDecisionEnvelopePayload](
            schema_version=self.schema_version,
            written_at=now(),
            classification=self.sensitivity,
            payload=payload,
        )
        self._objects.save(
            namespace=self.history_namespace,
            object_key=iva_wallet_decision_event_key(decision),
            classification=self.sensitivity,
            schema_version=self.schema_version,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode(UTF_8_ENCODING),
        )

    def load_decision(
        self,
        taxpayer_nif: str,
        target_year: int,
        target_period: str,
    ) -> IvaCompensationReconciliationDecision | None:
        """Return the latest persisted :class:`IvaCompensationReconciliationDecision` for the given period."""
        payload = super().load(iva_wallet_decision_key(taxpayer_nif, target_year, target_period))
        return payload.decision if payload is not None else None

    def list_decisions(self) -> tuple[IvaCompensationReconciliationDecision, ...]:
        """Return the latest persisted IVA wallet decisions in target-period order.

        Each element is an :class:`IvaCompensationReconciliationDecision` sorted
        by ``(target_year, target_period, taxpayer_nif, decided_at)``.
        """
        return tuple(
            sorted(
                (payload.decision for payload in self.iter_records()),
                key=lambda decision: (
                    decision.target_year,
                    decision.target_period,
                    decision.taxpayer_nif,
                    decision.decided_at,
                ),
            ),
        )

    def load_decision_history(
        self,
        taxpayer_nif: str,
        target_year: int,
        target_period: str,
    ) -> tuple[IvaCompensationReconciliationDecision, ...]:
        """Return decision history for one taxpayer and target period.

        Returns an immutable tuple of :class:`IvaCompensationReconciliationDecision`.
        """
        taxpayer_token = taxpayer_nif.strip().upper()
        decisions: list[IvaCompensationReconciliationDecision] = []
        for record in self._objects.list_records(
            self.history_namespace,
            expected_class=self.sensitivity,
            max_supported_version=self.schema_version,
        ):
            envelope = Envelope[_IvaWalletDecisionEnvelopePayload].model_validate_json(
                record.payload.decode(UTF_8_ENCODING),
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
    "member_observation_key",
    "observation_key",
]
