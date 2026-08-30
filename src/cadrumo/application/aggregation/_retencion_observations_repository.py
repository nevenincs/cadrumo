"""Encrypted persistence for per-perceptor retención records (Modelo 180/193).

The DEDICATED store the retenciones-summary family reads to count perceptors
DISTINCTLY. Modelo 180 casilla ``decl.total-perceptores`` ("Número total de
perceptores … Número de registros de tipo 2", AEAT Diseño de Registro) is the
count of distinct perceptor NIFs on the annual declaration, NOT the sum of the
quarterly Modelo 115 aggregate counts. The validated distinct-count primitive
``aggregate_retenciones_180`` already exists; what it lacked was a persisted,
calc-mesh-readable per-perceptor source so the calculate path could compute the
distinct count instead of falling back to the wrong quarterly sum. This module is
that source: it persists each :class:`RetencionObservation` (perceptor NIF +
scheme + taxable base + retención) keyed by ``(modelo, filing_year, period)`` plus
the per-perceptor identity, so the pull and calculate surfaces read ONE store.

Sensitivity is :class:`~adapters.persistence.storage.SensitivityClass`
``FINANCIAL`` — perceptor NIFs are identity-bearing financial data, stored
encrypted at rest through a
:class:`~adapters.persistence.storage.SecureBoundRepository` that writes
:class:`~adapters.persistence.storage.Envelope` records. The plaintext NIF
lives only inside the encrypted payload; the object key carries the sha256 of
the NIF (the iva-wallet-decision key convention), never the cleartext value
(``sensitive-financial-data-secure-storage-only``).
The namespace, schema version, object-key grammar, and custody disposition are
declared by
:data:`adapters.persistence.storage.RETENCION_OBSERVATIONS_NAMESPACE`.

Producers (the pull/aggregate entrypoints) write here through one shared
helper; the calc-mesh resolver reads here and calls the distinct-count
primitive.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime
from typing import ClassVar, override

from pydantic import BaseModel, Field

from ...adapters.persistence.storage import (
    RETENCION_OBSERVATIONS_NAMESPACE,
    SecureBoundRepository,
    SensitivityClass,
    safe_repository_id,
)
from ...core import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.aggregation import AggregationCaptureKind
from ...core.filing_year import FilingYear
from ...core.time import UtcInstant, now
from ._observation_window import hashed_tax_id_token, replace_observation_window
from ._retenciones import RetencionObservation, RetencionScheme
from .errors import AggregationValidationError, t


class _RetencionObservationEnvelopePayload(BaseModel):
    """Serialisable wrapper around one per-perceptor :class:`RetencionObservation`.

    Carries the (modelo, filing_year, period) keying the registry resolver needs
    alongside the validated retención row, plus capture provenance. Wrapping keeps
    the envelope schema identical to the other repositories' one-``payload`` shape
    and leaves room for future per-record metadata without breaking the inner
    record.

    ``captured_at`` is the canonical :data:`~core.time.UtcInstant`: a bare
    ``datetime`` admitted a naive value, so a capture instant with no zone
    reached persistence and every later comparison against a UTC-aware instant
    silently answered a different question.

    ``source_kind`` here is CAPTURE provenance (which ingestion path wrote the
    row), deliberately NOT the filed-observation
    :class:`~application.calculations.ObservationSourceKind` taxonomy, which
    classifies whether a FILED observation is official AEAT evidence. The two
    are different value sets on different axes; unifying them would let a
    capture token be read as filing-grade evidence.

    **This store therefore carries no official-evidence displacement guard, and
    that is a consequence of the axis above rather than an omission.** The
    calculation observation store refuses a non-official write onto a slot
    already holding AEAT evidence; the predicate it evaluates is
    ``ObservationSourceKind.is_official_aeat``, and neither this module nor its
    sibling imports that enum -- it appears here only in the sentence above.
    There is no official-evidence state on these rows for a guard to protect,
    so a guard modelled on that one would have no expression to evaluate.

    A second reason makes the same guard actively WRONG here rather than merely
    unnecessary: that store protects a SLOT holding one authoritative row, while
    this one holds a WINDOW that is a SET, written only through whole-window
    set-replace. Clearing a row the operator dropped is the operation this store
    exists to perform, so a per-row displacement refusal would refuse it.

    Both reasons rest on capture provenance staying a distinct axis. It is a
    free-form ``str`` here, so nothing structural holds it apart from the
    filed-observation taxonomy -- only this declaration does.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1, max_length=8)
    filing_year: FilingYear
    period: Period
    observation: RetencionObservation
    captured_at: UtcInstant
    source_kind: AggregationCaptureKind
    source_metadata: Mapping[str, str] = Field(default_factory=dict)


def retencion_observation_key(
    modelo: str,
    filing_year: int,
    period: Period,
    perceptor_nif: str,
    scheme: RetencionScheme,
) -> str:
    """Opaque per-perceptor object key — the NIF is hashed, never cleartext.

    Secure-object payloads are encrypted, but object keys are storage metadata, so
    the perceptor NIF is sha256-hashed (the iva-wallet-decision key convention).
    Distinct (perceptor NIF, scheme) pairs persist as distinct rows so a perceptor
    paid under more than one scheme is preserved while the distinct-NIF count stays
    correct.
    """
    if not 2000 <= filing_year <= 2099:
        raise AggregationValidationError(
            t("aggregation.retenciones.errors.filing_year_out_of_range"),
            context={"filing_year": str(filing_year), "min_year": "2000", "max_year": "2099"},
        )
    safe_repository_id(modelo, context="modelo")
    period_token = period.registry_token
    safe_repository_id(period_token, context="period")
    safe_repository_id(str(scheme.value), context="scheme")
    hashed_token = hashed_tax_id_token(perceptor_nif, field_name="perceptor_nif")
    return f"{modelo}:{filing_year}:{period_token}:{hashed_token}:{scheme.value}"


class RetencionObservationRepository(SecureBoundRepository[_RetencionObservationEnvelopePayload]):
    """Encrypted repository for per-perceptor :class:`RetencionObservation` payloads.

    The :class:`~adapters.persistence.storage.SecureBoundRepository` base
    wraps each payload in a
    :class:`~adapters.persistence.storage.Envelope` under
    :data:`adapters.persistence.storage.RETENCION_OBSERVATIONS_NAMESPACE`
    and enforces the namespace's FINANCIAL
    :class:`~adapters.persistence.storage.SensitivityClass`.

    See Also:
        :data:`adapters.persistence.storage.RETENCION_OBSERVATIONS_NAMESPACE`
            Secure-object namespace and hashed object-key contract.
        :func:`retencion_observation_key`
            Deterministic key builder that keeps the plaintext NIF out of
            storage metadata.
        :func:`persist_retencion_observations`
            Shared producer write path for pull and calculate parity.
    """

    namespace: ClassVar[str] = RETENCION_OBSERVATIONS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = RETENCION_OBSERVATIONS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = RETENCION_OBSERVATIONS_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = _RetencionObservationEnvelopePayload

    @override
    def extract_identifier(self, payload: _RetencionObservationEnvelopePayload) -> str:
        return retencion_observation_key(
            payload.modelo,
            payload.filing_year,
            payload.period,
            payload.observation.perceptor_nif,
            payload.observation.scheme,
        )

    def build_observation_payload(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: Period,
        observation: RetencionObservation,
        source_kind: AggregationCaptureKind,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> _RetencionObservationEnvelopePayload:
        """Return the validated envelope payload for one per-perceptor retención row.

        Construction is separated from persistence so the set-replace path can
        build and validate the whole replacement set before committing any of
        it, and then commit the clear and the write as one transaction.
        """
        return _RetencionObservationEnvelopePayload(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            observation=observation,
            captured_at=captured_at if captured_at is not None else now(),
            source_kind=source_kind,
            source_metadata=dict(source_metadata or {}),
        )

    def save_observation(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: Period,
        observation: RetencionObservation,
        source_kind: AggregationCaptureKind,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> None:
        """Persist one per-perceptor retención row keyed by (modelo, filing_year, period, NIF, scheme)."""
        self.save(
            self.build_observation_payload(
                modelo=modelo,
                filing_year=filing_year,
                period=period,
                observation=observation,
                source_kind=source_kind,
                captured_at=captured_at,
                source_metadata=source_metadata,
            )
        )

    def replace_observations(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: Period,
        observations: Sequence[RetencionObservation],
        source_kind: AggregationCaptureKind,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> None:
        """Replace the FULL per-perceptor set for one (modelo, filing_year, period).

        SET-REPLACE, not additive upsert: clears any prior rows for the exact
        key-tuple, then writes the supplied set, both in ONE transaction. A
        re-pull where the operator DROPPED a perceptor must not leave the stale
        row behind — otherwise the next calculate's distinct count is inflated
        by a perceptor no longer declared (a silent over-count, the inverse of
        the pull≠calculate divergence this store closes). An empty
        ``observations`` clears the window (the operator declared none); the
        resolver raises a no-silent
        :class:`~.errors.AggregationValidationError` when a declaring revision
        then reads an empty store, before a zero perceptor count can be filed.
        """
        replace_observation_window(
            self,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            observations=observations,
            source_kind=source_kind,
            build_payload=self.build_observation_payload,
            captured_at=captured_at,
            source_metadata=source_metadata,
        )

    def load_observations(
        self,
        modelo: str,
        period: Period,
    ) -> tuple[RetencionObservation, ...]:
        """Return every persisted per-perceptor observation for one (modelo, filing_year, period).

        The calc-mesh perceptor-count resolver folds these through the
        validated distinct-count primitive. An empty tuple means no per-perceptor
        records were persisted for the window — the resolver MUST fail loudly
        rather than materialising a zero count.

        The scan verifies each row's identity against the key it is filed under
        before the window filter runs. Filtering on the decrypted payload alone
        trusts the payload to declare its own coordinates, so a record written
        under another row's key would enter this window and inflate the distinct
        perceptor count with a perceptor the declaration never addressed.

        Returns:
            Persisted :class:`RetencionObservation` records for the requested window.

        Raises:
            SecureObjectRowIdentityError: A stored row does not reconstruct the
                key it is filed under.
        """
        safe_repository_id(modelo, context="modelo")
        return tuple(
            payload.observation
            for payload in self.iter_records()
            if payload.modelo == modelo
            and payload.filing_year == period.filing_year
            and payload.period.registry_token == period.registry_token
        )

    def iter_modelo(self, modelo: str) -> Iterator[_RetencionObservationEnvelopePayload]:
        """Yield every persisted per-perceptor payload for `modelo` in unspecified order.

        Verifies each row's identity against its stored key before projecting it,
        for the same reason :meth:`load_observations` does.
        """
        safe_repository_id(modelo, context="modelo")
        for payload in self.iter_records():
            if payload.modelo == modelo:
                yield payload


def persist_retencion_observations(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    observations: Sequence[RetencionObservation],
    source_kind: AggregationCaptureKind = AggregationCaptureKind.AGGREGATE_PULL,
) -> None:
    """The ONE shared write path every per-perceptor producer calls.

    Factoring the persist behind a single application helper makes store
    completeness STRUCTURAL rather than per-entrypoint discipline a future
    producer could forget (an unwritten producer -> an incomplete store -> a
    pull≠calculate divergence). Writes to the active bucket's encrypted
    store with SET-REPLACE semantics so pull and calculate read one source.
    aggregate_per_modelo stays pure — persistence is the entrypoint's job, not the
    aggregator's (aeat-architecture-boundaries).
    """
    RetencionObservationRepository().replace_observations(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        observations=observations,
        source_kind=source_kind,
    )


__all__ = [
    "RetencionObservationRepository",
    "persist_retencion_observations",
    "retencion_observation_key",
]
