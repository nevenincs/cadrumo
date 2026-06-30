"""Encrypted persistence for past-filing casilla observations.

Stores :class:`~aeat.domain.calculations.registry.RegistryModeloObservation`
records — ``(modelo, filing_year, period, casilla_values)`` — as encrypted audit
envelopes in the
:class:`~aeat.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`.
The records are the substrate read by
:class:`~._multi_year.PreviousFilingSourceResolver` and
:class:`~._relation_prefill.RelationPrefillSourceResolver` so annual modelos
can roll up prior quarterlies, IVA prorrata can compute its four-year backward
mean, IS BIN carryforward can replay prior-year bases imponibles negativas, and
IVA regularización inversiones can apply its 5/10 year straight-line schedule.

Producers are out of scope for this module: the modelo filing flow
will write here when an operator successfully files via the app,
and the live-AEAT capture path will write here when justificantes
are parsed. This module exposes only the typed read/write surface.

Sensitivity is :class:`~aeat.adapters.persistence.storage.SensitivityClass`
``AUDIT`` — these records reconstruct exactly what was filed and so are
identity-bearing tax substrate. They are stored encrypted at rest through an
:class:`~aeat.adapters.persistence.storage.Envelope`-wrapped repository.

The store is value-centric. Clean-state proof still has to join these rows with
filing records, verification reports, and justificante evidence through
:func:`~._cross_period_clean_state.evaluate_cross_period_clean_state`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping
from datetime import datetime
from typing import ClassVar, override

from pydantic import BaseModel, Field

from ...adapters.persistence.storage import (
    CALCULATION_OBSERVATIONS_NAMESPACE,
    IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE,
    IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE,
    Envelope,
    SensitivityClass,
    safe_repository_id,
)
from ...adapters.persistence.storage.envelope import SecureBoundRepository
from ...core import STRICT_FROZEN_CONFIG, Period
from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import sha256_hex
from ...core.resources import resources
from ...core.time import now
from ...domain.calculations.registry import RegistryModeloObservation, RegistrySnapshotError, undeclared_casilla_ids
from ...domain.iva_compensation._reconciliation import IvaCompensationReconciliationDecision
from ._errors import ObservationCasillaReferenceError, ObservationKeyError


class _ObservationEnvelopePayload(BaseModel):
    """Serialisable wrapper around a :class:`RegistryModeloObservation`.

    The registry model is pure calculation evidence. This wrapper keeps the
    envelope schema identical to other repositories' shape and carries the
    application-side capture metadata — ``captured_at``, ``source_kind``,
    ``member_nif``, ``stamped_revision_id``, and ``source_metadata`` — without
    adding persistence concerns to the inner registry record.

    The ``stamped_revision_id`` field is the registry revision id the
    source filing resolved to at capture time. It is mandatory in the stored
    envelope so every carry-read can re-confirm the source value against the
    law-determined registry revision before trusting it.
    """

    model_config = STRICT_FROZEN_CONFIG

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
    stamped_revision_id: str = Field(
        min_length=1,
        max_length=128,
        description=(
            "Registry revision id the source filing resolved to at capture time "
            "so carry-read code can re-confirm the value against the law-determined "
            "registry revision."
        ),
    )
    source_metadata: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Encrypted source-specific provenance for the observation. Live AEAT "
            "filed observations use this for register status, expediente id, and "
            "authenticated identity so downstream readers can audit what official "
            "register row produced the calculation history."
        ),
    )


class _IvaWalletDecisionEnvelopePayload(BaseModel):
    """Serialisable wrapper for an IVA wallet reconciliation decision."""

    model_config = STRICT_FROZEN_CONFIG

    decision: IvaCompensationReconciliationDecision


def _decision_payload_digest(decision: IvaCompensationReconciliationDecision) -> str:
    return sha256_hex(decision.model_dump_json().encode(UTF_8_ENCODING))


def _require_observation_period(period: Period) -> Period:
    if not isinstance(period, Period):
        raise ObservationKeyError("observation period must be an aeat.core.Period")
    return period


def observation_key_for_token(modelo: str, filing_year: int, period_token: str) -> str:
    """Stable repository key for a modelo/year/raw registry-period token triple.

    Censo modelos can declare non-date registry tokens such as ``alta`` or
    ``modificacion`` that are not valid :class:`Period` codes. The encrypted
    observation store still keys them by the same logical triple.
    """
    safe_repository_id(modelo, context="modelo")
    safe_repository_id(period_token, context="period")
    if not 2000 <= filing_year <= 2099:
        raise ObservationKeyError(f"observation filing_year {filing_year} out of supported range [2000, 2099]")
    return f"{modelo}:{filing_year}:{period_token}"


def observation_key(modelo: str, period: Period) -> str:
    """Stable repository key for a ``(modelo, Period)`` pair.

    Validated through :func:`~aeat.adapters.persistence.storage.safe_repository_id`
    so each component is constrained to the
    :class:`~aeat.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`
    id contract before composition.
    """
    filing_period = _require_observation_period(period)
    return observation_key_for_token(modelo, filing_period.filing_year, filing_period.registry_token)


def member_observation_key_for_token(
    modelo: str,
    filing_year: int,
    period_token: str,
    member_nif: str | None,
) -> str:
    """Storage key for an observation keyed by a raw registry period token."""
    base = observation_key_for_token(modelo, filing_year, period_token)
    if member_nif is None:
        return base
    safe_repository_id(member_nif, context="member_nif")
    return f"{base}:{member_nif}"


def member_observation_key(modelo: str, period: Period, member_nif: str | None) -> str:
    """Storage key for an observation, widened by a grupo member NIF when present.

    When ``member_nif`` is ``None`` the key is the single-filer
    ``observation_key`` unchanged, so every existing consumer (the default
    previous_filing path, the multi-year resolver) keys identically. When set,
    the member NIF is appended so two members' filings for the same
    ``(modelo, filing_year, period)`` persist as distinct rows — the cross-member
    fan-in the 353<-322 ``per_grupo_member`` aggregation enumerates and sums.
    """
    filing_period = _require_observation_period(period)
    return member_observation_key_for_token(
        modelo,
        filing_period.filing_year,
        filing_period.registry_token,
        member_nif,
    )


def iva_wallet_decision_key(taxpayer_nif: str, target_period: Period) -> str:
    """Opaque latest-decision key for one taxpayer and Modelo 303 target period.

    Secure-object payloads are encrypted, but object keys are storage metadata.
    Hash the taxpayer/period tuple so the repository does not expose NIF/NIE
    values in cleartext database rows.
    """
    filing_period = _require_observation_period(target_period)
    target_year = filing_period.filing_year
    target_period_token = filing_period.registry_token
    taxpayer_token = taxpayer_nif.strip().upper()
    if not taxpayer_token:
        raise ObservationKeyError("taxpayer_nif must be non-empty")
    safe_repository_id(target_period_token, context="target_period")
    if not 2000 <= target_year <= 2099:
        raise ObservationKeyError(f"IVA wallet target_year {target_year} out of supported range [2000, 2099]")
    digest = hashlib.sha256(
        "\x1f".join((taxpayer_token, str(target_year), target_period_token)).encode(UTF_8_ENCODING),
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
                decision.target_period.registry_token,
                decision.decided_at.isoformat(),
                decision.wallet_captured_at.isoformat() if decision.wallet_captured_at is not None else "",
                _decision_payload_digest(decision),
            ),
        ).encode(UTF_8_ENCODING),
    ).hexdigest()
    return f"iva-wallet-decision-event:{digest}"


def _validate_observation_casilla_ids(observation: RegistryModeloObservation) -> str:
    observed_casilla_ids = frozenset(observation.casilla_values)
    operand_casilla_refs = frozenset(
        operand_ref for item in observation.observations for operand_ref in item.operand_casilla_refs
    )
    referenced_casilla_ids = observed_casilla_ids | operand_casilla_refs
    try:
        snapshot = resources().modelos.authority.snapshot(
            observation.modelo,
            filing_year=observation.filing_year,
            period=observation.period,
        )
    except RegistrySnapshotError as exc:
        raise ObservationCasillaReferenceError(
            "calculation observation casilla ids cannot be validated because the registry snapshot is missing",
            context={
                "modelo": observation.modelo,
                "filing_year": observation.filing_year,
                "period": observation.period,
            },
        ) from exc

    invalid = undeclared_casilla_ids(snapshot.revision, referenced_casilla_ids) if referenced_casilla_ids else ()
    if not invalid:
        return str(snapshot.revision.id)
    raise ObservationCasillaReferenceError(
        "calculation observations must use canonical casilla.id values declared by the registry snapshot",
        context={
            "modelo": observation.modelo,
            "filing_year": observation.filing_year,
            "period": observation.period,
            "revision_id": snapshot.revision.id,
            "casilla_ids": invalid,
            "observation_casilla_ids": undeclared_casilla_ids(snapshot.revision, observed_casilla_ids),
            "operand_casilla_refs": undeclared_casilla_ids(snapshot.revision, operand_casilla_refs),
        },
    )


class CalculationObservationRepository(SecureBoundRepository[_ObservationEnvelopePayload]):
    """Repository over encrypted SQL-backed past-filing observations.

    Stores :class:`RegistryModeloObservation` rows for
    :func:`~._binding_prefill.resolve_bindings_from_local_store`,
    :func:`~._relation_prefill.resolve_relations_from_local_store`, and
    :func:`~._cross_period_clean_state.evaluate_cross_period_clean_state`.
    It owns encrypted value history only; filing-grade source proof is assembled
    by the clean-state service from this repository plus filing, verification,
    and justificante repositories.
    """

    namespace: ClassVar[str] = CALCULATION_OBSERVATIONS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = CALCULATION_OBSERVATIONS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = CALCULATION_OBSERVATIONS_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = _ObservationEnvelopePayload

    @override
    def extract_identifier(self, payload: _ObservationEnvelopePayload) -> str:
        observation = payload.observation
        period = observation.filing_period
        if period is None:
            return member_observation_key_for_token(
                observation.modelo,
                observation.filing_year,
                observation.period,
                payload.member_nif,
            )
        return member_observation_key(
            observation.modelo,
            period,
            payload.member_nif,
        )

    def load_observation(
        self,
        modelo: str,
        period: Period,
    ) -> _ObservationEnvelopePayload | None:
        """Return the persisted observation for one (modelo, year, period token) or None."""
        filing_period = _require_observation_period(period)
        return self.load(observation_key(modelo, filing_period))

    def save_observation(
        self,
        observation: RegistryModeloObservation,
        *,
        source_kind: str,
        captured_at: datetime | None = None,
        member_nif: str | None = None,
        stamped_revision_id: str | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> None:
        """Persist ``observation`` keyed by its ``(modelo, filing_year, period)``.

        ``member_nif`` is an optional grupo-de-entidades member NIF. When
        supplied, the storage identifier is widened (see
        :func:`member_observation_key`) so distinct members' filings for the
        same (modelo, filing_year, period) persist as separate rows instead of
        overwriting — the cross-member fan-in the 353<-322 ``per_grupo_member``
        aggregation enumerates. When ``None`` the single-filer key is unchanged.

        ``stamped_revision_id`` is the registry revision id the source filing
        resolved to at capture time. Producers that hold a
        :class:`~aeat.domain.calculations.registry.RegistrySnapshot` MUST pass
        ``snapshot.revision.id`` here. If omitted, the repository resolves the
        law-determined revision from the observation's ``(modelo, filing_year,
        period)`` before persisting.

        ``source_metadata`` is source-specific encrypted provenance. It is never
        part of repository keys and must only contain data that belongs inside
        the AUDIT-class secure payload; live AEAT captures use it for register
        status, expediente identity, and authenticated taxpayer/member identity
        consumed by the cross-period clean-state proof.
        """
        law_revision_id = _validate_observation_casilla_ids(observation)
        when = captured_at if captured_at is not None else now()
        payload = _ObservationEnvelopePayload(
            observation=observation,
            captured_at=when,
            source_kind=source_kind,
            member_nif=member_nif,
            stamped_revision_id=law_revision_id if stamped_revision_id is None else stamped_revision_id,
            source_metadata=dict(source_metadata or {}),
        )
        self.save(payload)

    def iter_modelo(self, modelo: str) -> Iterator[_ObservationEnvelopePayload]:
        """Yield every persisted observation for ``modelo`` in unspecified order.

        Used by grouped previous-filing and clean-state readers to enumerate all
        known source rows for a modelo, including member-widened keys.
        """
        safe_repository_id(modelo, context="modelo")
        for payload in self.iter_records():
            if payload.observation.modelo == modelo:
                yield payload


class IvaWalletDecisionRepository(SecureBoundRepository[_IvaWalletDecisionEnvelopePayload]):
    """Repository over encrypted SQL-backed IVA wallet reconciliation decisions.

    Holds one latest decision per ``(taxpayer_nif, target_year, target_period)``
    triple for calculation lookup, and also writes every distinct decision to
    an immutable audit-event namespace. Decisions are AUDIT-class — they record
    the resolved gap between a taxpayer's local IVA compensation recurrence and
    the live AEAT wallet, which downstream calculation chains consult through
    :class:`~._iva_wallet_reconciliation.IvaWalletDecisionSourceResolver`.
    """

    namespace: ClassVar[str] = IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE.namespace
    history_namespace: ClassVar[str] = IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = _IvaWalletDecisionEnvelopePayload

    @override
    def extract_identifier(self, payload: _IvaWalletDecisionEnvelopePayload) -> str:
        decision = payload.decision
        return iva_wallet_decision_key(decision.taxpayer_nif, decision.target_period)

    def save_decision(self, decision: IvaCompensationReconciliationDecision) -> None:
        """Persist ``decision`` to latest lookup and immutable audit history."""
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
        target_period: Period,
    ) -> IvaCompensationReconciliationDecision | None:
        """Return the latest persisted :class:`IvaCompensationReconciliationDecision` for the given period."""
        payload = super().load(iva_wallet_decision_key(taxpayer_nif, target_period))
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
                    decision.target_period.registry_token,
                    decision.taxpayer_nif,
                    decision.decided_at,
                ),
            ),
        )

    def load_decision_history(
        self,
        taxpayer_nif: str,
        target_period: Period,
    ) -> tuple[IvaCompensationReconciliationDecision, ...]:
        """Return decision history for one taxpayer and target period.

        Returns an immutable tuple of :class:`IvaCompensationReconciliationDecision`.
        """
        filing_period = _require_observation_period(target_period)
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
            if decision.taxpayer_nif.strip().upper() == taxpayer_token and decision.target_period == filing_period:
                decisions.append(decision)
        return tuple(sorted(decisions, key=lambda item: (item.decided_at, item.wallet_captured_at or item.decided_at)))


__all__ = [
    "CalculationObservationRepository",
    "IvaWalletDecisionRepository",
    "iva_wallet_decision_event_key",
    "iva_wallet_decision_key",
    "member_observation_key",
    "member_observation_key_for_token",
    "observation_key",
    "observation_key_for_token",
]
