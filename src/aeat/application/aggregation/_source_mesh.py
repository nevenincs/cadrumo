"""Canonical application-layer source resolution contracts.

:class:`CalculationSourceContext` carries the :class:`ModeloRevision` that
the source mesh resolvers consult when projecting binding slots onto
available data sources.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_serializer, field_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import BindingSourceKind, Period
from ...core.errors import CoreValidationError
from ...core.i18n import tr
from ...core.identity import BucketId
from ...core.logging import get_logger
from ...domain.calculations.registry import BindingId, CasillaId, ModeloRevision, RelationId
from ._errors import AggregationValidationError, t


class SourceMeshError(CoreValidationError):
    """Raised when a ``CalculationSourceMesh`` field validator rejects an invariant.

    Replaces bare :exc:`ValueError` at the ``owned_sources`` uniqueness / blank
    guards and the ``source_transaction_ids`` uniqueness / blank guards so
    callers receive a typed, registry-bound, localized error.  Inherits from
    :class:`~aeat.core.errors.CoreValidationError` (which inherits from
    :exc:`ValueError`) so pydantic field validators surface it through
    ``ValidationError`` without special handling.
    """

    def __init__(self, message_key: str) -> None:
        super().__init__(message_key, translated_message=message_key)


_log = get_logger(__name__)

CalculationSourceDiagnosticReason = Literal[
    "duplicate_binding_owner",
    "duplicate_bound_casilla_owner",
    "duplicate_relation_owner",
    "source_issue",
    "storage_degraded",
    "unhandled_binding_source",
    "unrouted_observation",
    "oss_no_live_source",
    "missing_transaction_evidence",
    "official_box_unpopulated",
    "prior_payment_not_deducted",
    "prior_payment_minoracion_not_captured",
]

# Source kinds that are explicitly deferred — no mesh resolver is built yet, but
# they are known to the system and must produce a standing advisory on
# source_diagnostics rather than a silent blank.  Listed here so the S26
# boundary gate (in _calculation_actions) can accept them without flagging
# them as unknown-novel sources, and so the S08 safety net emits the advisory
# while keeping them off the manual_sources allowlist (W02.P06.S10).
DEFERRED_SOURCE_KINDS: frozenset[BindingSourceKind] = frozenset(
    {
        BindingSourceKind.ATRIBUCION_MEMBER,  # M184 — Sheets-pull-only, no live resolver yet
        BindingSourceKind.RELATED_PARTY_OPERATION,  # M232 — Sheets-pull-only
        BindingSourceKind.FOREIGN_ASSET,  # M720 — Sheets-pull-only
        BindingSourceKind.REFUND_OPERATION,  # M360 — Sheets-pull-only
    },
)


class CalculationSourceContext(BaseModel):
    """Context supplied to a calculation source resolver.

    The ``period`` field is the typed :class:`~aeat.core.Period` value
    carrying both the filing year and the bare registry period code.  Consumers
    that need the raw token for a downstream ``str``-typed API should use
    ``context.period.registry_token``; those that need only the year can use
    ``context.period.year`` (which mirrors ``context.filing_year``).
    """

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    modelo: str = Field(min_length=1, max_length=16)
    filing_year: int = Field(ge=2000, le=2099)
    period: Period
    revision: ModeloRevision
    calculated_at: datetime | None = None


class CalculationSourceDiagnostic(BaseModel):
    """Diagnostic emitted while resolving source-backed calculation values."""

    model_config = _STRICT_FROZEN

    reason: CalculationSourceDiagnosticReason
    source_kind: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=512)
    resolver_id: str | None = Field(default=None, min_length=1, max_length=128)
    binding_id: BindingId | None = None
    relation_id: RelationId | None = None
    casilla_id: CasillaId | None = None


class CalculationSourceProvenance(BaseModel):
    """Stable source object provenance produced by a resolver."""

    model_config = _STRICT_FROZEN

    source_kind: str = Field(min_length=1, max_length=64)
    source_ref: str = Field(min_length=1, max_length=256)
    fingerprint: str | None = Field(default=None, min_length=1, max_length=256)


class BorradorSourceProvenance(BaseModel):
    """Typed borrador-snapshot provenance carried on a source resolution.

    The AEAT borrador snapshot is the one source whose downstream consumer
    (``persist_calculation_revision``) needs more than the generic
    :class:`CalculationSourceProvenance` row: it persists the originating
    ``borrador_snapshot_id`` and the sorted ``bindings_sourced_from_borrador``
    trace onto the :class:`CalculationRevision`. Carrying that as ONE typed
    sub-model keeps the generic :class:`CalculationSourceResolution` envelope
    from accreting per-source named fields while preserving the trace as typed
    data the call site reads directly -- never by parsing the
    ``borrador:{id}:binding:{bid}`` provenance ``source_ref`` strings.
    """

    model_config = _STRICT_FROZEN

    snapshot_id: str = Field(min_length=1, max_length=128)
    bindings_sourced: tuple[BindingId, ...] = Field(default_factory=tuple)


class CalculationSourceResolution(BaseModel):
    """Resolved values and provenance returned by one source resolver."""

    model_config = _STRICT_FROZEN

    resolver_id: str = Field(min_length=1, max_length=128)
    owned_sources: tuple[BindingSourceKind, ...] = Field(default_factory=tuple)
    binding_values: Mapping[BindingId, Decimal] = Field(default_factory=dict)
    enum_binding_values: Mapping[BindingId, str] = Field(default_factory=dict)
    date_binding_values: Mapping[BindingId, date] = Field(default_factory=dict)
    relation_values: Mapping[RelationId, Decimal] = Field(default_factory=dict)
    unresolved_relation_ids: tuple[RelationId, ...] = Field(default_factory=tuple)
    bound_inputs_by_casilla_id: Mapping[CasillaId, Decimal] = Field(default_factory=dict)
    source_transaction_ids: Sequence[str] = Field(default_factory=tuple)
    # Typed borrador provenance. Carried only by the borrador resolution
    # (``Modelo100BorradorSourceResolver``); ``merge_source_resolutions``
    # preserves it onto the merged result so the calculate call site reads the
    # snapshot id and sourced-binding set as TYPED data and hands them to
    # ``persist_calculation_revision``. ``None`` for every other resolver.
    borrador_provenance: BorradorSourceProvenance | None = None
    diagnostics: tuple[CalculationSourceDiagnostic, ...] = Field(default_factory=tuple)
    provenance: tuple[CalculationSourceProvenance, ...] = Field(default_factory=tuple)

    @field_validator("owned_sources", mode="before")
    @classmethod
    def _coerce_owned_sources(cls, value: object) -> object:
        """Hydrate known bare source-token strings to their :class:`BindingSourceKind` member.

        The model carries :data:`~aeat.core.STRICT_FROZEN_CONFIG` (``strict=True``),
        which disables string→enum coercion. Resolvers declare their owned source as a
        canonical token and may pass either the member or its bare string value; this
        before-validator maps each KNOWN bare string to its member (the
        ``BindingAggregation._coerce_op`` precedent in :mod:`aeat.core.aggregation`) so
        the field stays strictly typed while a known token still validates. A blank
        string raises :class:`SourceMeshError`; any other non-member value is left
        untouched for the strict field to reject with its standard enum error, so a
        genuine typo is still caught — without minting a new diagnostic locale key.
        """
        if not isinstance(value, (tuple, list)):
            return value
        coerced: list[object] = []
        for item in value:
            if isinstance(item, BindingSourceKind):
                coerced.append(item)
                continue
            if isinstance(item, str):
                stripped = item.strip()
                if not stripped:
                    raise SourceMeshError("aggregation.source_mesh.errors.owned_sources_blank")
                try:
                    coerced.append(BindingSourceKind(stripped))
                except ValueError:
                    # Unknown token: leave it for the strict typed field to reject.
                    coerced.append(item)
                continue
            coerced.append(item)
        return tuple(coerced)

    @field_validator("owned_sources")
    @classmethod
    def _owned_sources_are_unique(cls, value: tuple[BindingSourceKind, ...]) -> tuple[BindingSourceKind, ...]:
        # After the before-coercer, every item is a canonical BindingSourceKind member
        # (no blank/whitespace possible). Guard uniqueness and sort by the stable string
        # value so the carrier is deterministic, preserving members (never downgrading
        # them to bare str).
        if len(value) != len(set(value)):
            raise SourceMeshError("aggregation.source_mesh.errors.owned_sources_duplicate")
        return tuple(sorted(value, key=lambda source: source.value))

    @field_validator("binding_values")
    @classmethod
    def _freeze_binding_values(cls, value: Mapping[BindingId, Decimal]) -> Mapping[BindingId, Decimal]:
        return MappingProxyType(dict(sorted(value.items())))

    @field_validator("enum_binding_values")
    @classmethod
    def _freeze_enum_binding_values(cls, value: Mapping[BindingId, str]) -> Mapping[BindingId, str]:
        return MappingProxyType(dict(sorted(value.items())))

    @field_validator("date_binding_values")
    @classmethod
    def _freeze_date_binding_values(cls, value: Mapping[BindingId, date]) -> Mapping[BindingId, date]:
        return MappingProxyType(dict(sorted(value.items())))

    @field_validator("relation_values")
    @classmethod
    def _freeze_relation_values(cls, value: Mapping[RelationId, Decimal]) -> Mapping[RelationId, Decimal]:
        return MappingProxyType(dict(sorted(value.items())))

    @field_validator("unresolved_relation_ids")
    @classmethod
    def _freeze_unresolved_relation_ids(cls, value: tuple[RelationId, ...]) -> tuple[RelationId, ...]:
        normalized = tuple(item.strip() for item in value)
        if any(not item for item in normalized):
            raise SourceMeshError("aggregation.source_mesh.errors.unresolved_relation_ids_blank")
        if len(normalized) != len(set(normalized)):
            raise SourceMeshError("aggregation.source_mesh.errors.unresolved_relation_ids_duplicate")
        return tuple(sorted(normalized))

    @field_validator("bound_inputs_by_casilla_id")
    @classmethod
    def _freeze_bound_inputs_by_casilla_id(cls, value: Mapping[CasillaId, Decimal]) -> Mapping[CasillaId, Decimal]:
        return MappingProxyType(dict(sorted(value.items())))

    @field_validator("source_transaction_ids")
    @classmethod
    def _freeze_source_transaction_ids(cls, value: Sequence[str]) -> tuple[str, ...]:
        normalized = tuple(item.strip() for item in value)
        if any(not item for item in normalized):
            raise SourceMeshError("aggregation.source_mesh.errors.source_transaction_ids_blank")
        if len(normalized) != len(set(normalized)):
            raise SourceMeshError("aggregation.source_mesh.errors.source_transaction_ids_duplicate")
        return tuple(sorted(normalized))

    @field_serializer("binding_values")
    def _serialize_binding_values(self, value: Mapping[BindingId, Decimal]) -> dict[BindingId, Decimal]:
        return dict(value)

    @field_serializer("enum_binding_values")
    def _serialize_enum_binding_values(self, value: Mapping[BindingId, str]) -> dict[BindingId, str]:
        return dict(value)

    @field_serializer("date_binding_values")
    def _serialize_date_binding_values(self, value: Mapping[BindingId, date]) -> dict[BindingId, date]:
        return dict(value)

    @field_serializer("relation_values")
    def _serialize_relation_values(self, value: Mapping[RelationId, Decimal]) -> dict[RelationId, Decimal]:
        return dict(value)

    @field_serializer("unresolved_relation_ids")
    def _serialize_unresolved_relation_ids(self, value: tuple[RelationId, ...]) -> tuple[RelationId, ...]:
        return tuple(value)

    @field_serializer("bound_inputs_by_casilla_id")
    def _serialize_bound_inputs_by_casilla_id(self, value: Mapping[CasillaId, Decimal]) -> dict[CasillaId, Decimal]:
        return dict(value)

    @field_serializer("source_transaction_ids")
    def _serialize_source_transaction_ids(self, value: Sequence[str]) -> tuple[str, ...]:
        return tuple(value)


@runtime_checkable
class ModeloSourceResolver(Protocol):
    """Application port implemented by one calculation source adapter."""

    @property
    def resolver_id(self) -> str:
        """Stable resolver identifier for diagnostics and provenance."""
        ...

    @property
    def owned_sources(self) -> tuple[BindingSourceKind, ...]:
        """Registry binding source kinds this resolver owns."""
        ...

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve source-backed calculation values for ``context``.

        Returns a :class:`CalculationSourceResolution` carrying resolved
        binding values, provenance, and any source diagnostics.
        """
        ...


def merge_source_resolutions(
    resolutions: Sequence[CalculationSourceResolution],
    *,
    resolver_id: str = "source_mesh",
) -> CalculationSourceResolution:
    """Merge resolver outputs and reject ambiguous ownership.

    Returns a :class:`CalculationSourceResolution`.
    """
    binding_values: dict[BindingId, Decimal] = {}
    enum_binding_values: dict[BindingId, str] = {}
    date_binding_values: dict[BindingId, date] = {}
    relation_values: dict[RelationId, Decimal] = {}
    unresolved_relation_ids: set[RelationId] = set()
    bound_inputs_by_casilla_id: dict[CasillaId, Decimal] = {}
    source_transaction_ids: set[str] = set()
    diagnostics: list[CalculationSourceDiagnostic] = []
    provenance: list[CalculationSourceProvenance] = []
    owned_sources: set[BindingSourceKind] = set()
    binding_owners: dict[BindingId, str] = {}
    relation_owners: dict[RelationId, str] = {}
    casilla_owners: dict[CasillaId, str] = {}
    # The borrador resolution is the sole contributor of the typed borrador
    # provenance; preserve it onto the merged result. Exactly one resolution
    # carries a non-None borrador_provenance (the borrador resolver) so a plain
    # last-writer-wins carry is unambiguous.
    borrador_provenance: BorradorSourceProvenance | None = None

    for resolution in resolutions:
        owned_sources.update(resolution.owned_sources)
        diagnostics.extend(resolution.diagnostics)
        provenance.extend(resolution.provenance)
        source_transaction_ids.update(resolution.source_transaction_ids)
        unresolved_relation_ids.update(resolution.unresolved_relation_ids)
        if resolution.borrador_provenance is not None:
            borrador_provenance = resolution.borrador_provenance
        for binding_id, value in resolution.binding_values.items():
            _claim_binding(binding_owners, binding_id, resolution.resolver_id)
            binding_values[binding_id] = value
        for binding_id, value in resolution.enum_binding_values.items():
            _claim_binding(binding_owners, binding_id, resolution.resolver_id)
            enum_binding_values[binding_id] = value
        for binding_id, value in resolution.date_binding_values.items():
            _claim_binding(binding_owners, binding_id, resolution.resolver_id)
            date_binding_values[binding_id] = value
        for relation_id, value in resolution.relation_values.items():
            _claim_relation(relation_owners, relation_id, resolution.resolver_id)
            relation_values[relation_id] = value
            unresolved_relation_ids.discard(relation_id)
        for casilla_id, value in resolution.bound_inputs_by_casilla_id.items():
            _claim_bound_casilla(casilla_owners, casilla_id, resolution.resolver_id)
            bound_inputs_by_casilla_id[casilla_id] = value

    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=tuple(sorted(owned_sources)),
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        date_binding_values=date_binding_values,
        relation_values=relation_values,
        unresolved_relation_ids=tuple(sorted(unresolved_relation_ids.difference(relation_values))),
        bound_inputs_by_casilla_id=bound_inputs_by_casilla_id,
        source_transaction_ids=tuple(sorted(source_transaction_ids)),
        borrador_provenance=borrador_provenance,
        diagnostics=tuple(diagnostics),
        provenance=tuple(provenance),
    )


def collect_unhandled_source_diagnostics(
    revision: ModeloRevision,
    *,
    handled_sources: frozenset[str],
    manual_sources: frozenset[str] = frozenset({"manual_input"}),
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return :class:`CalculationSourceDiagnostic` entries for revision bindings with no enrolled resolver.

    Args:
        revision: The :class:`ModeloRevision` whose bindings are inspected for missing resolvers.
        handled_sources: Source kind strings already claimed by enrolled resolvers.
        manual_sources: Source kind strings treated as intentionally unresolved.
    """
    diagnostics: list[CalculationSourceDiagnostic] = []
    for binding in revision.bindings:
        source = str(binding.source)
        if source in handled_sources or source in manual_sources:
            continue
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="unhandled_binding_source",
                source_kind=source,
                binding_id=binding.id,
                message=f"binding {binding.id!r} declares source {source!r} with no enrolled resolver",
            ),
        )
    return tuple(diagnostics)


def storage_degradation_resolution(
    *,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
    source_kinds: Sequence[str],
    error: BaseException,
) -> CalculationSourceResolution:
    """Return an empty :class:`CalculationSourceResolution` carrying secure-storage degradation diagnostics."""
    normalized_sources = tuple(sorted({source.strip() for source in source_kinds if source.strip()}))
    _log.debug(
        "source mesh resolver storage degradation resolver_id=%s source_kinds=%s error_type=%s",
        resolver_id,
        ",".join(normalized_sources),
        type(error).__name__,
        exc_info=(type(error), error, error.__traceback__),
    )
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        diagnostics=tuple(
            CalculationSourceDiagnostic(
                reason="storage_degraded",
                source_kind=source_kind,
                resolver_id=resolver_id,
                message=tr("errors.integrity.integrity_storage_secure_object_unreadable"),
            )
            for source_kind in normalized_sources
        ),
    )


def _claim_binding(owners: dict[BindingId, str], binding_id: BindingId, resolver_id: str) -> None:
    existing = owners.get(binding_id)
    if existing is None:
        owners[binding_id] = resolver_id
        return
    raise AggregationValidationError(
        t("aggregation.source_mesh.errors.duplicate_binding_owner"),
        context={"binding_id": binding_id, "first_resolver": existing, "second_resolver": resolver_id},
    )


def _claim_bound_casilla(owners: dict[CasillaId, str], casilla_id: CasillaId, resolver_id: str) -> None:
    existing = owners.get(casilla_id)
    if existing is None:
        owners[casilla_id] = resolver_id
        return
    raise AggregationValidationError(
        t("aggregation.source_mesh.errors.duplicate_bound_casilla_owner"),
        context={"casilla_id": casilla_id, "first_resolver": existing, "second_resolver": resolver_id},
    )


def _claim_relation(owners: dict[RelationId, str], relation_id: RelationId, resolver_id: str) -> None:
    existing = owners.get(relation_id)
    if existing is None:
        owners[relation_id] = resolver_id
        return
    raise AggregationValidationError(
        t("aggregation.source_mesh.errors.duplicate_relation_owner"),
        context={"relation_id": relation_id, "first_resolver": existing, "second_resolver": resolver_id},
    )


__all__ = [
    "DEFERRED_SOURCE_KINDS",
    "BorradorSourceProvenance",
    "CalculationSourceContext",
    "CalculationSourceDiagnostic",
    "CalculationSourceDiagnosticReason",
    "CalculationSourceProvenance",
    "CalculationSourceResolution",
    "ModeloSourceResolver",
    "collect_unhandled_source_diagnostics",
    "merge_source_resolutions",
    "storage_degradation_resolution",
]
