"""Encrypted persistence for per-perceptor-clave withholding records (Modelo 190).

The DEDICATED store the percepciones-count resolver reads to count percepciones
DISTINCTLY. Modelo 190 casilla ``decl.total-percepciones`` ("Número total de
percepciones … Número de registros de tipo 2", AEAT Diseño de Registros) is the
count of DISTINCT (perceptor NIF, clave, subclave) type-2 records on the annual
declaration — a perceptor paid under two claves files two percepciones — NOT the
distinct-NIF perceptor count (that is RET-1's ``perceptor_count`` for Modelo
180/193) and NOT the sum of the quarterly Modelo 111 perceptor counts. The
validated distinct-count primitive (the ``percepcion_count`` withholding fact)
already exists; what it lacked was a persisted, calc-mesh-readable per-perceptor
source so the calculate path could compute the distinct count instead of falling
back to the wrong quarterly sum. This module is that source: it persists each
clave-bearing :class:`WithholdingObservation` keyed by ``(modelo, filing_year,
period)`` plus the per-perceptor-clave identity, so the pull and calculate
surfaces read ONE store (``one-aggregation-path-pull-equals-calculate``).

Sensitivity is :class:`SensitivityClass` ``FINANCIAL`` — perceptor NIFs are
identity-bearing financial data, stored encrypted at rest through an
:class:`Envelope`-wrapped repository. The plaintext NIF lives only inside the
encrypted payload; the object key carries the sha256 of the NIF (the
iva-wallet-decision key convention), never the cleartext value
(``sensitive-financial-data-secure-storage-only``).

ADR ``2026-06-25-modelo-190-percepciones-count-adr``. Producers (the
pull/aggregate entrypoints) write here through one shared helper; the P03
calc-mesh resolver reads here and calls the distinct-count primitive. This is the
percepciones counterpart of :mod:`._retencion_observations_repository` (the
perceptores store); the two stores are intentionally distinct — different distinct
keys (NIF+clave+subclave vs NIF), different models, different modelos.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime
from typing import ClassVar, override

from pydantic import BaseModel, Field

from ...adapters.persistence.storage import (
    WITHHOLDING_OBSERVATIONS_NAMESPACE,
    SensitivityClass,
    safe_repository_id,
)
from ...adapters.persistence.storage.envelope import SecureBoundRepository
from ...core import STRICT_FROZEN_CONFIG, Period
from ...core.external_constants import UTF_8_ENCODING
from ...core.time import now
from ...domain.calculations.registry import WithholdingObservation
from ._errors import AggregationValidationError, t


class _WithholdingObservationEnvelopePayload(BaseModel):
    """Serialisable wrapper around one per-perceptor-clave :class:`WithholdingObservation`.

    Carries the (modelo, filing_year, period) keying the registry resolver needs
    alongside the validated withholding row, plus capture provenance. Wrapping
    keeps the envelope schema identical to the other repositories' one-``payload``
    shape and leaves room for future per-record metadata without breaking the
    inner record.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=2000, le=2099)
    period: Period
    observation: WithholdingObservation
    captured_at: datetime
    source_kind: str = Field(min_length=1)
    source_metadata: Mapping[str, str] = Field(default_factory=dict)


def _hashed_perceptor_token(perceptor_tax_id: str) -> str:
    token = perceptor_tax_id.strip().upper()
    if not token:
        raise AggregationValidationError(
            t("aggregation.retenciones.errors.perceptor_nif_blank"),
            context={"field": "perceptor_tax_id"},
        )
    return hashlib.sha256(token.encode(UTF_8_ENCODING)).hexdigest()


def withholding_observation_key(
    modelo: str,
    filing_year: int,
    period: Period,
    perceptor_tax_id: str,
    clave: str,
    subclave: str,
) -> str:
    """Opaque per-perceptor-clave object key — the NIF is hashed, never cleartext.

    Secure-object payloads are encrypted, but object keys are storage metadata, so
    the perceptor NIF is sha256-hashed (the iva-wallet-decision key convention).
    Distinct (perceptor NIF, clave, subclave) triples persist as distinct rows so
    a perceptor paid under more than one clave is preserved as the distinct
    percepciones the Diseño counts (registros de tipo 2).
    """
    if not 2000 <= filing_year <= 2099:
        raise AggregationValidationError(
            t("aggregation.retenciones.errors.filing_year_out_of_range"),
            context={"filing_year": str(filing_year), "min_year": "2000", "max_year": "2099"},
        )
    safe_repository_id(modelo, context="modelo")
    period_token = period.registry_token
    safe_repository_id(period_token, context="period")
    safe_repository_id(clave, context="clave")
    subclave_token = subclave or "-"
    safe_repository_id(subclave_token, context="subclave")
    return (
        f"{modelo}:{filing_year}:{period_token}:"
        f"{_hashed_perceptor_token(perceptor_tax_id)}:{clave}:{subclave_token}"
    )


class WithholdingObservationRepository(SecureBoundRepository[_WithholdingObservationEnvelopePayload]):
    """Repository over encrypted SQL-backed per-perceptor-clave withholding observations."""

    namespace: ClassVar[str] = WITHHOLDING_OBSERVATIONS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = WITHHOLDING_OBSERVATIONS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = WITHHOLDING_OBSERVATIONS_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = _WithholdingObservationEnvelopePayload

    @override
    def extract_identifier(self, payload: _WithholdingObservationEnvelopePayload) -> str:
        return withholding_observation_key(
            payload.modelo,
            payload.filing_year,
            payload.period,
            payload.observation.perceptor_tax_id,
            payload.observation.clave,
            payload.observation.subclave,
        )

    def save_observation(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: Period,
        observation: WithholdingObservation,
        source_kind: str,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> None:
        """Persist one per-perceptor-clave row keyed by (modelo, year, period, NIF, clave, subclave)."""
        payload = _WithholdingObservationEnvelopePayload(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            observation=observation,
            captured_at=captured_at if captured_at is not None else now(),
            source_kind=source_kind,
            source_metadata=dict(source_metadata or {}),
        )
        self.save(payload)

    def replace_observations(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: Period,
        observations: Sequence[WithholdingObservation],
        source_kind: str,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> None:
        """Replace the FULL per-perceptor-clave set for one (modelo, filing_year, period).

        SET-REPLACE, not additive upsert: clears any prior rows for the exact
        key-tuple, then writes the supplied set. A re-pull where the operator
        DROPPED a percepción must not leave the stale row behind — otherwise the
        next calculate's distinct count is inflated by a percepción no longer
        declared (a silent over-count). An empty ``observations`` clears the
        window (the operator declared none); the P03 resolver surfaces a
        no-silent advisory when it then reads empty.
        """
        safe_repository_id(modelo, context="modelo")
        when = captured_at if captured_at is not None else now()
        for payload in tuple(self.iter_records()):
            if (
                payload.modelo == modelo
                and payload.filing_year == filing_year
                and payload.period.registry_token == period.registry_token
            ):
                self.delete(self.extract_identifier(payload))
        for observation in observations:
            self.save_observation(
                modelo=modelo,
                filing_year=filing_year,
                period=period,
                observation=observation,
                source_kind=source_kind,
                captured_at=when,
                source_metadata=source_metadata,
            )

    def load_observations(
        self,
        modelo: str,
        period: Period,
    ) -> tuple[WithholdingObservation, ...]:
        """Return persisted per-perceptor-clave :class:`WithholdingObservation` records.

        The result covers one ``(modelo, filing_year, period)`` window.

        The calc-mesh percepciones-count resolver (P03) folds these through the
        validated distinct-count primitive. An empty tuple means no per-perceptor
        records were persisted for the window — the resolver MUST surface a
        no-silent advisory rather than materialising a silent zero.
        """
        safe_repository_id(modelo, context="modelo")
        return tuple(
            payload.observation
            for payload in self.iter_records()
            if payload.modelo == modelo
            and payload.filing_year == period.filing_year
            and payload.period.registry_token == period.registry_token
        )

    def iter_modelo(self, modelo: str) -> Iterator[_WithholdingObservationEnvelopePayload]:
        """Yield every persisted per-perceptor-clave payload for `modelo` in unspecified order."""
        safe_repository_id(modelo, context="modelo")
        for payload in self.iter_records():
            if payload.modelo == modelo:
                yield payload


def persist_withholding_observations(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    observations: Sequence[WithholdingObservation],
    source_kind: str = "aggregate_pull",
) -> None:
    """The ONE shared write path every per-perceptor-clave producer calls.

    Factoring the persist behind a single application helper makes store
    completeness STRUCTURAL rather than per-entrypoint discipline a future
    producer could forget (an unwritten producer -> an incomplete store -> the
    exact pull!=calculate divergence #28 fixes). Writes to the active bucket's
    encrypted store with SET-REPLACE semantics so pull and calculate read one
    source.
    """
    WithholdingObservationRepository().replace_observations(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        observations=observations,
        source_kind=source_kind,
    )


__all__ = [
    "WithholdingObservationRepository",
    "persist_withholding_observations",
    "withholding_observation_key",
]
