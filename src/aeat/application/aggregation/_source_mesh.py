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
from ...core import Period
from ...core.errors import CoreValidationError
from ...core.i18n import tr
from ...core.identity import BucketId
from ...core.logging import get_logger
from ...domain.calculations.registry import ModeloRevision
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
    "oss_no_live_source",
    "missing_transaction_evidence",
    "official_box_unpopulated",
]

# Source kinds that are explicitly deferred — no mesh resolver is built yet, but
# they are known to the system and must produce a standing advisory on
# source_diagnostics rather than a silent blank.  Listed here so the S26
# boundary gate (in _calculation_actions) can accept them without flagging
# them as unknown-novel sources, and so the S08 safety net emits the advisory
# while keeping them off the manual_sources allowlist (W02.P06.S10).
DEFERRED_SOURCE_KINDS: frozenset[str] = frozenset(
    {
        "withholding",  # M190/M193 per-perceptor detalle — no live source; defer-with-advisory (S27)
        "atribucion_member",  # M184 — Sheets-pull-only, no live resolver yet
        "related_party_operation",  # M232 — Sheets-pull-only
        "foreign_asset",  # M720 — Sheets-pull-only
        "refund_operation",  # M360 — Sheets-pull-only
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
    binding_id: str | None = Field(default=None, min_length=1, max_length=256)
    relation_id: str | None = Field(default=None, min_length=1, max_length=256)
    casilla_id: str | None = Field(default=None, min_length=1, max_length=256)


class CalculationSourceProvenance(BaseModel):
    """Stable source object provenance produced by a resolver."""

    model_config = _STRICT_FROZEN

    source_kind: str = Field(min_length=1, max_length=64)
    source_ref: str = Field(min_length=1, max_length=256)
    fingerprint: str | None = Field(default=None, min_length=1, max_length=256)


class CalculationSourceResolution(BaseModel):
    """Resolved values and provenance returned by one source resolver."""

    model_config = _STRICT_FROZEN

    resolver_id: str = Field(min_length=1, max_length=128)
    owned_sources: tuple[str, ...] = Field(default_factory=tuple)
    binding_values: Mapping[str, Decimal] = Field(default_factory=dict)
    enum_binding_values: Mapping[str, str] = Field(default_factory=dict)
    date_binding_values: Mapping[str, date] = Field(default_factory=dict)
    relation_values: Mapping[str, Decimal] = Field(default_factory=dict)
    unresolved_relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    bound_casilla_inputs: Mapping[str, Decimal] = Field(default_factory=dict)
    source_transaction_ids: Sequence[str] = Field(default_factory=tuple)
    diagnostics: tuple[CalculationSourceDiagnostic, ...] = Field(default_factory=tuple)
    provenance: tuple[CalculationSourceProvenance, ...] = Field(default_factory=tuple)

    @field_validator("owned_sources")
    @classmethod
    def _owned_sources_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(source.strip() for source in value)
        if any(not source for source in normalized):
            raise SourceMeshError("aggregation.source_mesh.errors.owned_sources_blank")
        if len(normalized) != len(set(normalized)):
            raise SourceMeshError("aggregation.source_mesh.errors.owned_sources_duplicate")
        return tuple(sorted(normalized))

    @field_validator("binding_values")
    @classmethod
    def _freeze_binding_values(cls, value: Mapping[str, Decimal]) -> Mapping[str, Decimal]:
        return MappingProxyType(dict(sorted(value.items())))

    @field_validator("enum_binding_values")
    @classmethod
    def _freeze_enum_binding_values(cls, value: Mapping[str, str]) -> Mapping[str, str]:
        return MappingProxyType(dict(sorted(value.items())))

    @field_validator("relation_values")
    @classmethod
    def _freeze_relation_values(cls, value: Mapping[str, Decimal]) -> Mapping[str, Decimal]:
        return MappingProxyType(dict(sorted(value.items())))

    @field_validator("unresolved_relation_ids")
    @classmethod
    def _freeze_unresolved_relation_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(item.strip() for item in value)
        if any(not item for item in normalized):
            raise SourceMeshError("aggregation.source_mesh.errors.unresolved_relation_ids_blank")
        if len(normalized) != len(set(normalized)):
            raise SourceMeshError("aggregation.source_mesh.errors.unresolved_relation_ids_duplicate")
        return tuple(sorted(normalized))

    @field_validator("bound_casilla_inputs")
    @classmethod
    def _freeze_bound_casilla_inputs(cls, value: Mapping[str, Decimal]) -> Mapping[str, Decimal]:
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
    def _serialize_binding_values(self, value: Mapping[str, Decimal]) -> dict[str, Decimal]:
        return dict(value)

    @field_serializer("enum_binding_values")
    def _serialize_enum_binding_values(self, value: Mapping[str, str]) -> dict[str, str]:
        return dict(value)

    @field_serializer("relation_values")
    def _serialize_relation_values(self, value: Mapping[str, Decimal]) -> dict[str, Decimal]:
        return dict(value)

    @field_serializer("unresolved_relation_ids")
    def _serialize_unresolved_relation_ids(self, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(value)

    @field_serializer("bound_casilla_inputs")
    def _serialize_bound_casilla_inputs(self, value: Mapping[str, Decimal]) -> dict[str, Decimal]:
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
    def owned_sources(self) -> tuple[str, ...]:
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
    binding_values: dict[str, Decimal] = {}
    enum_binding_values: dict[str, str] = {}
    relation_values: dict[str, Decimal] = {}
    unresolved_relation_ids: set[str] = set()
    bound_casilla_inputs: dict[str, Decimal] = {}
    source_transaction_ids: set[str] = set()
    diagnostics: list[CalculationSourceDiagnostic] = []
    provenance: list[CalculationSourceProvenance] = []
    owned_sources: set[str] = set()
    binding_owners: dict[str, str] = {}
    relation_owners: dict[str, str] = {}
    casilla_owners: dict[str, str] = {}

    for resolution in resolutions:
        owned_sources.update(resolution.owned_sources)
        diagnostics.extend(resolution.diagnostics)
        provenance.extend(resolution.provenance)
        source_transaction_ids.update(resolution.source_transaction_ids)
        unresolved_relation_ids.update(resolution.unresolved_relation_ids)
        for binding_id, value in resolution.binding_values.items():
            _claim_binding(binding_owners, binding_id, resolution.resolver_id)
            binding_values[binding_id] = value
        for binding_id, value in resolution.enum_binding_values.items():
            _claim_binding(binding_owners, binding_id, resolution.resolver_id)
            enum_binding_values[binding_id] = value
        for relation_id, value in resolution.relation_values.items():
            _claim_relation(relation_owners, relation_id, resolution.resolver_id)
            relation_values[relation_id] = value
            unresolved_relation_ids.discard(relation_id)
        for casilla_id, value in resolution.bound_casilla_inputs.items():
            _claim_bound_casilla(casilla_owners, casilla_id, resolution.resolver_id)
            bound_casilla_inputs[casilla_id] = value

    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=tuple(sorted(owned_sources)),
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        relation_values=relation_values,
        unresolved_relation_ids=tuple(sorted(unresolved_relation_ids.difference(relation_values))),
        bound_casilla_inputs=bound_casilla_inputs,
        source_transaction_ids=tuple(sorted(source_transaction_ids)),
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
    owned_sources: tuple[str, ...],
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


def _claim_binding(owners: dict[str, str], binding_id: str, resolver_id: str) -> None:
    existing = owners.get(binding_id)
    if existing is None:
        owners[binding_id] = resolver_id
        return
    raise AggregationValidationError(
        t("aggregation.source_mesh.errors.duplicate_binding_owner"),
        context={"binding_id": binding_id, "first_resolver": existing, "second_resolver": resolver_id},
    )


def _claim_bound_casilla(owners: dict[str, str], casilla_id: str, resolver_id: str) -> None:
    existing = owners.get(casilla_id)
    if existing is None:
        owners[casilla_id] = resolver_id
        return
    raise AggregationValidationError(
        t("aggregation.source_mesh.errors.duplicate_bound_casilla_owner"),
        context={"casilla_id": casilla_id, "first_resolver": existing, "second_resolver": resolver_id},
    )


def _claim_relation(owners: dict[str, str], relation_id: str, resolver_id: str) -> None:
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
