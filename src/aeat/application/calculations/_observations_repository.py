"""Encrypted persistence for past-filing casilla observations.

Stores `RegistryFilingObservation` records — `(modelo, filing_year,
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

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.storage import (
    Envelope,
    SensitivityClass,
    safe_repository_id,
)
from ...adapters.persistence.storage.errors import (
    ClassificationError,
    EnvelopeVersionError,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...domain.calculations.registry._bindings import RegistryFilingObservation
from ._iva_wallet_reconciliation import IvaCompensationReconciliationDecision

_OBSERVATION_NAMESPACE: Final[str] = "aeat.calculations.observations"
_OBSERVATION_ENVELOPE_VERSION: Final[int] = 1
_IVA_WALLET_DECISION_NAMESPACE: Final[str] = "aeat.calculations.iva_wallet.reconciliation_decisions"
_IVA_WALLET_DECISION_ENVELOPE_VERSION: Final[int] = 1


class _ObservationEnvelopePayload(BaseModel):
    """Serialisable wrapper around a `RegistryFilingObservation`.

    The runtime model lives in `_bindings.py` and is itself frozen
    pydantic v2 with `extra="forbid"`. We wrap it to keep the
    envelope schema identical to other repositories' shape (one
    `payload` field) and to leave room for future per-observation
    metadata (e.g., `captured_from`, `captured_at`, evidence
    pointer) without breaking the inner record.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    observation: RegistryFilingObservation
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
    """Stable latest-decision key for one taxpayer and Modelo 303 target period."""

    safe_repository_id(taxpayer_nif, context="taxpayer_nif")
    safe_repository_id(target_period, context="target_period")
    if not 2000 <= target_year <= 2099:
        raise ValueError(f"IVA wallet target_year {target_year} out of supported range [2000, 2099]")
    return f"{taxpayer_nif}:{target_year}:{target_period}"


class CalculationObservationRepository:
    """Repository over encrypted SQL-backed past-filing observations."""

    def __init__(self) -> None:
        self._objects = SecureObjectRepository()

    @property
    def store_dir(self) -> Path:
        return Path("db://secure_objects") / _OBSERVATION_NAMESPACE

    def envelope_path_for(self, modelo: str, filing_year: int, period: str) -> Path:
        return self.store_dir / observation_key(modelo, filing_year, period)

    def load(
        self,
        modelo: str,
        filing_year: int,
        period: str,
    ) -> _ObservationEnvelopePayload | None:
        """Return the persisted observation for one (modelo, year, period) or None."""

        key = observation_key(modelo, filing_year, period)
        record = self._objects.load(
            _OBSERVATION_NAMESPACE,
            key,
            expected_class=SensitivityClass.AUDIT,
            max_supported_version=_OBSERVATION_ENVELOPE_VERSION,
        )
        if record is None:
            return None
        envelope = Envelope[_ObservationEnvelopePayload].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.AUDIT:
            raise ClassificationError(
                f"observation {key} has classification {envelope.classification}; "
                f"consumer expected {SensitivityClass.AUDIT}",
            )
        if envelope.schema_version > _OBSERVATION_ENVELOPE_VERSION:
            raise EnvelopeVersionError(
                f"observation {key} is at version {envelope.schema_version}; "
                f"consumer supports up to {_OBSERVATION_ENVELOPE_VERSION}",
            )
        return envelope.payload

    def save(
        self,
        observation: RegistryFilingObservation,
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
        envelope = Envelope[_ObservationEnvelopePayload](
            schema_version=_OBSERVATION_ENVELOPE_VERSION,
            written_at=when,
            classification=SensitivityClass.AUDIT,
            payload=payload,
        )
        self._objects.save(
            namespace=_OBSERVATION_NAMESPACE,
            object_key=observation_key(observation.modelo, observation.filing_year, observation.period),
            classification=SensitivityClass.AUDIT,
            schema_version=_OBSERVATION_ENVELOPE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

    def iter_modelo(self, modelo: str) -> Iterator[_ObservationEnvelopePayload]:
        """Yield every persisted observation for `modelo` in unspecified order.

        Used by the multi-year resolver to scan all known prior
        filings for a modelo without per-year/period probing.
        """

        safe_repository_id(modelo, context="modelo")
        prefix = f"{modelo}:".encode()
        for raw_row in self._objects.iter_all_records_raw():
            if raw_row.namespace != _OBSERVATION_NAMESPACE:
                continue
            object_key_bytes = (
                raw_row.object_key if isinstance(raw_row.object_key, bytes) else str(raw_row.object_key).encode("utf-8")
            )
            if not object_key_bytes.startswith(prefix):
                continue
            payload_bytes = (
                raw_row.payload if isinstance(raw_row.payload, bytes) else str(raw_row.payload).encode("utf-8")
            )
            envelope = Envelope[_ObservationEnvelopePayload].model_validate_json(payload_bytes.decode("utf-8"))
            if envelope.classification is not SensitivityClass.AUDIT:
                continue
            if envelope.schema_version > _OBSERVATION_ENVELOPE_VERSION:
                continue
            yield envelope.payload

    def delete(self, modelo: str, filing_year: int, period: str) -> bool:
        return self._objects.delete(
            _OBSERVATION_NAMESPACE,
            observation_key(modelo, filing_year, period),
        )

    def save_iva_wallet_decision(
        self,
        decision: IvaCompensationReconciliationDecision,
    ) -> None:
        """Persist the latest IVA wallet reconciliation decision for a target period."""

        payload = _IvaWalletDecisionEnvelopePayload(decision=decision)
        envelope = Envelope[_IvaWalletDecisionEnvelopePayload](
            schema_version=_IVA_WALLET_DECISION_ENVELOPE_VERSION,
            written_at=decision.decided_at,
            classification=SensitivityClass.AUDIT,
            payload=payload,
        )
        self._objects.save(
            namespace=_IVA_WALLET_DECISION_NAMESPACE,
            object_key=iva_wallet_decision_key(decision.taxpayer_nif, decision.target_year, decision.target_period),
            classification=SensitivityClass.AUDIT,
            schema_version=_IVA_WALLET_DECISION_ENVELOPE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

    def load_iva_wallet_decision(
        self,
        taxpayer_nif: str,
        target_year: int,
        target_period: str,
    ) -> IvaCompensationReconciliationDecision | None:
        """Return the latest persisted IVA wallet reconciliation decision."""

        key = iva_wallet_decision_key(taxpayer_nif, target_year, target_period)
        record = self._objects.load(
            _IVA_WALLET_DECISION_NAMESPACE,
            key,
            expected_class=SensitivityClass.AUDIT,
            max_supported_version=_IVA_WALLET_DECISION_ENVELOPE_VERSION,
        )
        if record is None:
            return None
        envelope = Envelope[_IvaWalletDecisionEnvelopePayload].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.AUDIT:
            raise ClassificationError(
                f"IVA wallet decision {key} has classification {envelope.classification}; "
                f"consumer expected {SensitivityClass.AUDIT}",
            )
        if envelope.schema_version > _IVA_WALLET_DECISION_ENVELOPE_VERSION:
            raise EnvelopeVersionError(
                f"IVA wallet decision {key} is at version {envelope.schema_version}; "
                f"consumer supports up to {_IVA_WALLET_DECISION_ENVELOPE_VERSION}",
            )
        return envelope.payload.decision


__all__ = [
    "CalculationObservationRepository",
    "iva_wallet_decision_key",
    "observation_key",
]
