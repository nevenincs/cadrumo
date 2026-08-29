"""Encrypted persistence for per-perceptor-clave percepciones records (Modelo 190).

The DEDICATED store the percepciones-count resolver reads to count percepciones
DISTINCTLY. Modelo 190 casilla ``decl.total-percepciones`` ("Número total de
percepciones … Número de registros de tipo 2", AEAT Diseño de Registros) is the
count of DISTINCT (perceptor NIF, clave, subclave) type-2 records on the annual
declaration — a perceptor paid under two claves files two percepciones — NOT the
distinct-NIF perceptor count (that is the ``perceptor_count`` for Modelo
180/193) and NOT the sum of the quarterly Modelo 111 perceptor counts. The
validated distinct-count primitive (the ``percepcion_count`` withholding fact)
already exists; what it lacked was a persisted, calc-mesh-readable per-perceptor
source so the calculate path could compute the distinct count instead of falling
back to the wrong quarterly sum. This module is that source: it persists each
clave-bearing :class:`WithholdingObservation` keyed by ``(modelo, filing_year,
period)`` plus the per-perceptor-clave identity, so the pull and calculate
surfaces read ONE store (``aeat-calculation-aggregation``).

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
:data:`adapters.persistence.storage.WITHHOLDING_OBSERVATIONS_NAMESPACE`.

Producers (the pull/aggregate entrypoints) write here through one shared
helper; the calc-mesh resolver reads here and calls the distinct-count
primitive. This is the percepciones counterpart of
:mod:`._retencion_observations_repository` (the perceptores store); the two
stores are intentionally distinct — different distinct keys (NIF+clave+subclave
vs NIF), different models, different modelos.

This module follows the ``percepciones`` stem rather than ``withholding``: the
"withholding" stem collided with the project's Spanish-stem naming convention
(``retencion`` already names the sibling Modelo 180/193 store), so this module
— and the repository symbols it owns locally — use the ``percepciones`` stem
instead. The :class:`~domain.calculations.registry.WithholdingObservation`
domain type it wraps is an unrelated, widely shared registry taxonomy type and
is out of scope for that naming choice.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime
from typing import ClassVar, override

from pydantic import BaseModel, Field

from ...adapters.persistence.storage import (
    WITHHOLDING_OBSERVATIONS_NAMESPACE,
    SecureBoundRepository,
    SensitivityClass,
    safe_repository_id,
)
from ...core import STRICT_FROZEN_CONFIG, AggregationCaptureKind, Period
from ...core.filing_year import FilingYear
from ...core.time import UtcInstant, now
from ...domain.calculations.registry.withholding_bindings import WithholdingObservation
from ._observation_window import hashed_tax_id_token, replace_observation_window
from .errors import AggregationValidationError, t


class _PercepcionObservationEnvelopePayload(BaseModel):
    """Serialisable wrapper around one per-perceptor-clave :class:`WithholdingObservation`.

    Carries the (modelo, filing_year, period) keying the registry resolver needs
    alongside the validated withholding row, plus capture provenance. Wrapping
    keeps the envelope schema identical to the other repositories' one-``payload``
    shape and leaves room for future per-record metadata without breaking the
    inner record.

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
    observation: WithholdingObservation
    captured_at: UtcInstant
    source_kind: AggregationCaptureKind
    source_metadata: Mapping[str, str] = Field(default_factory=dict)


def percepcion_observation_key(
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
    hashed_token = hashed_tax_id_token(perceptor_tax_id, field_name="perceptor_tax_id")
    return f"{modelo}:{filing_year}:{period_token}:{hashed_token}:{clave}:{subclave_token}"


class PercepcionObservationRepository(SecureBoundRepository[_PercepcionObservationEnvelopePayload]):
    """Encrypted repository for per-perceptor-clave :class:`WithholdingObservation` payloads.

    The :class:`~adapters.persistence.storage.SecureBoundRepository` base
    wraps each payload in a
    :class:`~adapters.persistence.storage.Envelope` under
    :data:`adapters.persistence.storage.WITHHOLDING_OBSERVATIONS_NAMESPACE`
    and enforces the namespace's FINANCIAL
    :class:`~adapters.persistence.storage.SensitivityClass`.

    See Also:
        :data:`adapters.persistence.storage.WITHHOLDING_OBSERVATIONS_NAMESPACE`
            Secure-object namespace and hashed object-key contract.
        :func:`percepcion_observation_key`
            Deterministic key builder that hashes the NIF and preserves
            clave/subclave identity.
        :func:`persist_percepcion_observations`
            Shared producer write path for pull and calculate parity.
    """

    namespace: ClassVar[str] = WITHHOLDING_OBSERVATIONS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = WITHHOLDING_OBSERVATIONS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = WITHHOLDING_OBSERVATIONS_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = _PercepcionObservationEnvelopePayload

    @override
    def extract_identifier(self, payload: _PercepcionObservationEnvelopePayload) -> str:
        return percepcion_observation_key(
            payload.modelo,
            payload.filing_year,
            payload.period,
            payload.observation.perceptor_tax_id,
            payload.observation.clave,
            payload.observation.subclave,
        )

    def build_observation_payload(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: Period,
        observation: WithholdingObservation,
        source_kind: AggregationCaptureKind,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> _PercepcionObservationEnvelopePayload:
        """Return the validated envelope payload for one per-perceptor-clave row.

        Construction is separated from persistence so the set-replace path can
        build and validate the whole replacement set before committing any of
        it, and then commit the clear and the write as one transaction.
        """
        return _PercepcionObservationEnvelopePayload(
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
        observation: WithholdingObservation,
        source_kind: AggregationCaptureKind,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> None:
        """Persist one per-perceptor-clave row keyed by (modelo, year, period, NIF, clave, subclave)."""
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
        observations: Sequence[WithholdingObservation],
        source_kind: AggregationCaptureKind,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> None:
        """Replace the FULL per-perceptor-clave set for one (modelo, filing_year, period).

        SET-REPLACE, not additive upsert: clears any prior rows for the exact
        key-tuple, then writes the supplied set, both in ONE transaction. A
        re-pull where the operator DROPPED a percepción must not leave the stale
        row behind — otherwise the next calculate's distinct count is inflated
        by a percepción no longer declared (a silent over-count). An empty
        ``observations`` clears the window (the operator declared none); the
        resolver surfaces a no-silent advisory when it then reads empty.
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
    ) -> tuple[WithholdingObservation, ...]:
        """Return persisted per-perceptor-clave :class:`WithholdingObservation` records.

        The result covers one ``(modelo, filing_year, period)`` window.

        The calc-mesh percepciones-count resolver folds these through the
        validated distinct-count primitive. An empty tuple means no per-perceptor
        records were persisted for the window — the resolver MUST surface a
        no-silent advisory rather than materialising a silent zero.

        The scan verifies each row's identity against the key it is filed under
        before the window filter runs. Filtering on the decrypted payload alone
        trusts the payload to declare its own coordinates, so a record written
        under another row's key would enter this window and distort the distinct
        percepciones count with a record the declaration never addressed.

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

    def iter_modelo(self, modelo: str) -> Iterator[_PercepcionObservationEnvelopePayload]:
        """Yield every persisted per-perceptor-clave payload for `modelo` in unspecified order.

        Verifies each row's identity against its stored key before projecting it,
        for the same reason :meth:`load_observations` does.
        """
        safe_repository_id(modelo, context="modelo")
        for payload in self.iter_records():
            if payload.modelo == modelo:
                yield payload


def persist_percepcion_observations(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    observations: Sequence[WithholdingObservation],
    source_kind: AggregationCaptureKind = AggregationCaptureKind.AGGREGATE_PULL,
) -> None:
    """The ONE shared write path every per-perceptor-clave producer calls.

    Factoring the persist behind a single application helper makes store
    completeness STRUCTURAL rather than per-entrypoint discipline a future
    producer could forget (an unwritten producer -> an incomplete store -> a
    pull!=calculate divergence). Writes to the active bucket's
    encrypted store with SET-REPLACE semantics so pull and calculate read one
    source.
    """
    PercepcionObservationRepository().replace_observations(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        observations=observations,
        source_kind=source_kind,
    )


__all__ = [
    "PercepcionObservationRepository",
    "percepcion_observation_key",
    "persist_percepcion_observations",
]
