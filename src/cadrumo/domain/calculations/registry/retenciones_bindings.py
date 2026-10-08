"""Retenciones-aggregation registry binding helpers (RET-1).

The per-family module for the ``retenciones_aggregation`` binding source — the
calc-mesh source that materialises retenciones-family scalars from the dedicated
per-perceptor retención store.
Extracted as its own family module per ``aeat-architecture-boundaries``;
the cross-family validator dispatch in :mod:`.bindings` registers this family's
``validate(binding) -> list[str]`` entry.

The materialisation depends on a :class:`_RetencionesAggregationProtocol` rather
than the application-layer ``RetencionesAggregation``, so the domain layer stays
independent of the application aggregation service.

The resolver walks the declared :class:`ModeloRevision` bindings and emits only
canonical binding values for this source family.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal, Protocol

from pydantic import BaseModel, BeforeValidator, Field

from ....core.aggregation import BindingAggregationOp, BindingSourceKind, RetencionScheme
from ....core.casilla_id import CasillaId
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import provider_member, selector_against_model
from .errors import RegistryValidationError
from .facts.resolution import ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, require_governed_fact_authority
from .ids import BindingId
from .schema_base import coerce_enum_member, coerce_enum_tuple
from .schema_exports import ExportFieldDataType

if TYPE_CHECKING:
    from ....core.period import Period
    from .schema import BindingDefinition, ModeloRevision


class RetencionesAggregationFact(StrEnum):
    """A figure a retenciones aggregation binding totals across matched rows."""

    PERCEPTOR_COUNT_DISTINCT = "perceptor_count_distinct"
    TYPE2_RECORD_COUNT = "type2_record_count"
    TAXABLE_BASE_SUM = "taxable_base_sum"
    RETENCION_AMOUNT_SUM = "retencion_amount_sum"
    ROW_FIELD = "row_field"


RetencionesAggregationFactField = Annotated[
    RetencionesAggregationFact, BeforeValidator(coerce_enum_member(RetencionesAggregationFact))
]
"""Registry token hydrated into a RetencionesAggregationFact member."""


# The selected Modelo 180 revision owns the fields of its official type-2
# design.  This provider only needs a stable token to ask its one canonical
# type-2 materialization for a field; membership is refused if the materializer
# does not expose the requested field.
_Modelo180Type2RowField = str
Modelo180Type2RowGrouping = Literal["per_type2_record"]


class _RetencionesAggregationProtocol(Protocol):
    """The scalar and Modelo 180 row outputs the source materialises."""

    @property
    def modelo(self) -> str: ...

    @property
    def period(self) -> Period: ...

    @property
    def rollups(self) -> tuple[_RetencionesRollupProtocol, ...]: ...

    @property
    def total_perceptors(self) -> int: ...

    @property
    def total_taxable_base(self) -> Decimal: ...

    @property
    def total_retencion(self) -> Decimal: ...

    @property
    def type2_rows(self) -> tuple[_Modelo180Type2RowProtocol, ...]: ...

    @property
    def type2_record_count(self) -> int: ...


class _RetencionesRollupProtocol(Protocol):
    """One per-perceptor/scheme rollup row exposed by the retenciones source."""

    @property
    def perceptor_nif(self) -> str: ...

    @property
    def scheme(self) -> RetencionScheme: ...

    @property
    def total_taxable_base(self) -> Decimal: ...

    @property
    def total_retencion(self) -> Decimal: ...


class _Modelo180StructuredAddressProtocol(Protocol):
    """Address fields that the selected type-2 record design admits."""

    @property
    def province_code(self) -> str: ...

    @property
    def municipality_code(self) -> str: ...

    @property
    def municipality(self) -> str: ...

    @property
    def locality(self) -> str: ...

    @property
    def postal_code(self) -> str: ...

    @property
    def street_type(self) -> str: ...

    @property
    def street_name(self) -> str: ...

    @property
    def number_type(self) -> str: ...

    @property
    def house_number(self) -> str: ...

    @property
    def number_qualifier(self) -> str: ...

    @property
    def block(self) -> str: ...

    @property
    def portal(self) -> str: ...

    @property
    def staircase(self) -> str: ...

    @property
    def floor(self) -> str: ...

    @property
    def door(self) -> str: ...

    @property
    def complement(self) -> str: ...


class _Modelo180PropertyDetailProtocol(Protocol):
    """Property evidence carried by the canonical Modelo 180 type-2 row."""

    @property
    def representative_nif(self) -> str | None: ...

    @property
    def recipient_province_code(self) -> str: ...

    @property
    def modality(self) -> str: ...

    @property
    def accrual_year(self) -> int: ...

    @property
    def situation(self) -> str: ...

    @property
    def cadastral_reference(self) -> str | None: ...

    @property
    def address(self) -> _Modelo180StructuredAddressProtocol | None: ...


class _Modelo180Type2RowProtocol(Protocol):
    """The one canonical emitted-row materialization consumed by M180 bindings."""

    @property
    def perceptor_nif(self) -> str: ...

    @property
    def perceptor_name(self) -> str: ...

    @property
    def property_detail(self) -> _Modelo180PropertyDetailProtocol: ...

    @property
    def taxable_base(self) -> Decimal: ...

    @property
    def withholding_percentage(self) -> Decimal: ...

    @property
    def retencion_amount(self) -> Decimal: ...


class RetencionesAggregationProvider(BaseModel):
    """Validated form of a ``retenciones_aggregation`` binding selector.

    Carries the target casilla id and the scalar fact this source serves. Annual
    summary modelos still keep their monetary totals on relation-prefill
    bindings; Modelo 115 uses the same per-perceptor store directly for its
    quarterly perceptor count and taxable base.  Modelo 180 additionally
    exposes its already-materialized official type-2 rows through the generic
    row-binding/export path.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.RETENCIONES_AGGREGATION] = BindingSourceKind.RETENCIONES_AGGREGATION

    target_casilla_id: CasillaId
    schemes: Annotated[tuple[RetencionScheme, ...], BeforeValidator(coerce_enum_tuple(RetencionScheme))] = ()
    fact: RetencionesAggregationFactField = RetencionesAggregationFact.PERCEPTOR_COUNT_DISTINCT
    row_field: _Modelo180Type2RowField | None = None
    grouping: Modelo180Type2RowGrouping | None = None
    record: str | None = Field(default=None, min_length=1, max_length=64)
    data_type: ExportFieldDataType | None = None


def validate_retenciones_aggregation_binding(binding: BindingDefinition) -> list[str]:
    """Accumulating registry-build validator for a ``retenciones_aggregation`` binding.

    Validates the selector shape against :class:`RetencionesAggregationProvider`
    (the single build-time contract per ``aeat-registry-bindings``),
    preserving the underlying pydantic field message in the diagnostic.
    """
    diagnostics = selector_against_model(binding, RetencionesAggregationProvider)
    if diagnostics:
        return diagnostics
    try:
        _validated_retenciones_aggregation_selector(binding)
    except RegistryValidationError as exc:
        return [f"binding {binding.id!r} (source={binding.source!r}) retenciones invariants violated: {exc}"]
    return []


def _validated_retenciones_aggregation_selector(binding: BindingDefinition) -> RetencionesAggregationProvider:
    """Return a selector only when its scalar/row shape is coherent."""
    selector = provider_member(binding, RetencionesAggregationProvider)
    op = binding_aggregation_op(binding)
    if selector.fact is RetencionesAggregationFact.ROW_FIELD:
        _validate_retenciones_row_selector(binding, selector, op)
        return selector
    _validate_retenciones_scalar_selector(binding, selector, op)
    return selector


def _validate_retenciones_row_selector(
    binding: BindingDefinition,
    selector: RetencionesAggregationProvider,
    op: BindingAggregationOp,
) -> None:
    if op is not BindingAggregationOp.ROWS:
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires aggregation op 'rows'")
    _require_row_selector_key(binding, selector.row_field, "row_field")
    _require_row_selector_key(binding, selector.grouping, "grouping")
    _require_row_selector_key(binding, selector.record, "record")
    _require_row_selector_key(binding, selector.data_type, "data_type")
    if selector.schemes:
        raise RegistryValidationError(f"binding {binding.id!r} Modelo 180 type-2 row binding cannot filter schemes")


def _require_row_selector_key(binding: BindingDefinition, value: object, key: str) -> None:
    if value is None:
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires a {key!r} selector key")


def _validate_retenciones_scalar_selector(
    binding: BindingDefinition,
    selector: RetencionesAggregationProvider,
    op: BindingAggregationOp,
) -> None:
    if op is BindingAggregationOp.ROWS:
        raise RegistryValidationError(
            f"binding {binding.id!r} scalar retenciones fact cannot use aggregation op 'rows'"
        )
    if any(value is not None for value in (selector.row_field, selector.grouping, selector.record, selector.data_type)):
        raise RegistryValidationError(
            f"binding {binding.id!r} scalar retenciones fact cannot declare row selector keys"
        )
    if selector.fact is RetencionesAggregationFact.TYPE2_RECORD_COUNT and selector.schemes:
        raise RegistryValidationError(f"binding {binding.id!r} type-2 record count cannot filter schemes")


def resolve_retenciones_aggregation_binding_values(
    revision: ModeloRevision,
    aggregation: _RetencionesAggregationProtocol,
    *,
    authority: GovernedFactSource | None = None,
) -> dict[BindingId, Decimal]:
    """Materialise scalar ``retenciones_aggregation`` bindings on a :class:`ModeloRevision`.

    Returns a binding value for every binding whose ``source`` is
    :attr:`BindingSourceKind.RETENCIONES_AGGREGATION`, keyed by the selector's
    declared fact.
    """
    resolved: dict[BindingId, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.RETENCIONES_AGGREGATION:
            continue
        selector = _validated_retenciones_aggregation_selector(binding)
        if selector.fact is RetencionesAggregationFact.ROW_FIELD:
            continue
        resolved[binding.id] = _retenciones_selector_value(selector, aggregation, authority=authority)
    return resolved


def resolve_retenciones_aggregation_binding_row_values(
    revision: ModeloRevision,
    aggregation: _RetencionesAggregationProtocol,
) -> dict[tuple[BindingId, int], Decimal | str | int | bool]:
    """Materialise the selected Modelo 180 type-2 record fields by stable row index.

    The aggregation has already applied the official grouping and selected the
    last withholding percentage for each row.  This resolver only projects that
    canonical result into the generic repeated-record channel; it does not
    regroup observations or calculate an alternative annual total.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    row_bindings = _retenciones_type2_row_bindings(revision)
    if not row_bindings:
        return {}
    _require_modelo_180_row_bindings(aggregation.modelo)
    resolved: dict[tuple[BindingId, int], Decimal | str | int | bool] = {}
    for binding, selector in row_bindings:
        resolved.update(_retenciones_type2_binding_row_values(binding, selector, aggregation.type2_rows))
    return resolved


def _retenciones_type2_row_bindings(
    revision: ModeloRevision,
) -> list[tuple[BindingDefinition, RetencionesAggregationProvider]]:
    return [
        (binding, selector)
        for binding in revision.bindings
        if binding.source is BindingSourceKind.RETENCIONES_AGGREGATION
        and (selector := _validated_retenciones_aggregation_selector(binding)).fact
        is RetencionesAggregationFact.ROW_FIELD
    ]


def _require_modelo_180_row_bindings(modelo: str) -> None:
    if modelo != "180":
        raise RegistryValidationError("retenciones type-2 row bindings are only supported for Modelo 180")


def _retenciones_type2_binding_row_values(
    binding: BindingDefinition,
    selector: RetencionesAggregationProvider,
    rows: tuple[_Modelo180Type2RowProtocol, ...],
) -> dict[tuple[BindingId, int], Decimal | str | int | bool]:
    if selector.row_field is None:  # pragma: no cover - protected by selector validation
        raise RegistryValidationError(f"binding {binding.id!r} is missing its Modelo 180 type-2 row field")
    resolved: dict[tuple[BindingId, int], Decimal | str | int | bool] = {}
    for row_index, row in enumerate(rows, start=1):
        value = _modelo_180_type2_row_value(row, selector.row_field, binding_id=binding.id)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        resolved[(binding.id, row_index)] = value
    return resolved


def _registry_schemes_for_modelo(
    aggregation: _RetencionesAggregationProtocol,
    *,
    authority: GovernedFactSource | None = None,
) -> frozenset[RetencionScheme]:
    """Resolve the selected modelo's allowed scheme tokens from fact authority."""
    from .facts.resolution import MappingFactQuery
    from .schema_base import DateAxis

    selected_authority = require_governed_fact_authority(authority, subject="retenciones scheme lookup")
    resolved = selected_authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="m111-m115-m123-withholding-scheme-catalogue",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=aggregation.period.end_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("withholding scheme catalogue did not resolve as a mapping fact")
    target_key = f"modelo.{aggregation.modelo}.schemes"
    declaration = _withholding_scheme_declaration(resolved, target_key)
    tokens = _withholding_scheme_tokens(declaration, target_key)
    return _validated_withholding_schemes(tokens, target_key)


def _withholding_scheme_declaration(resolved: ResolvedMappingFact, target_key: str) -> str:
    declarations = [entry.value for entry in resolved.payload.entries if entry.key == target_key]
    if len(declarations) != 1 or not isinstance(declarations[0], str):
        raise RegistryValidationError(
            f"withholding scheme catalogue must declare exactly one {target_key!r} entry",
        )
    return declarations[0]


def _withholding_scheme_tokens(declaration: str, target_key: str) -> tuple[str, ...]:
    tokens = tuple(token.strip() for token in declaration.split(",") if token.strip())
    if not tokens:
        raise RegistryValidationError(f"withholding scheme catalogue entry {target_key!r} is empty")
    return tokens


def _validated_withholding_schemes(tokens: tuple[str, ...], target_key: str) -> frozenset[RetencionScheme]:
    try:
        schemes = frozenset(RetencionScheme(token) for token in tokens)
    except ValueError as exc:
        raise RegistryValidationError(f"withholding scheme catalogue entry {target_key!r} is malformed") from exc
    if len(schemes) != len(tokens):
        raise RegistryValidationError(f"withholding scheme catalogue entry {target_key!r} contains duplicates")
    return schemes


def _retenciones_selector_value(
    selector: RetencionesAggregationProvider,
    aggregation: _RetencionesAggregationProtocol,
    *,
    authority: GovernedFactSource | None = None,
) -> Decimal:
    if not selector.schemes:
        return _unfiltered_retenciones_value(selector.fact, aggregation)
    declared_schemes = _registry_schemes_for_modelo(aggregation, authority=authority)
    unknown_schemes = frozenset(selector.schemes).difference(declared_schemes)
    if unknown_schemes:
        rendered = ", ".join(sorted(scheme.value for scheme in unknown_schemes))
        raise RegistryValidationError(
            f"retenciones binding declares scheme token(s) outside the selected registry catalogue: {rendered}",
        )
    selected = tuple(row for row in aggregation.rollups if row.scheme in selector.schemes)
    return _filtered_retenciones_value(selector.fact, selected)


def _unfiltered_retenciones_value(
    fact: RetencionesAggregationFact,
    aggregation: _RetencionesAggregationProtocol,
) -> Decimal:
    values: dict[RetencionesAggregationFact, Decimal] = {
        RetencionesAggregationFact.PERCEPTOR_COUNT_DISTINCT: Decimal(aggregation.total_perceptors),
        RetencionesAggregationFact.TYPE2_RECORD_COUNT: Decimal(aggregation.type2_record_count),
        RetencionesAggregationFact.TAXABLE_BASE_SUM: aggregation.total_taxable_base,
        RetencionesAggregationFact.RETENCION_AMOUNT_SUM: aggregation.total_retencion,
    }
    try:
        return values[fact]
    except KeyError as exc:  # pragma: no cover - protected by selector validation
        raise RegistryValidationError(f"retenciones scalar binding declares unsupported fact {fact!r}") from exc


def _filtered_retenciones_value(
    fact: RetencionesAggregationFact,
    selected: tuple[_RetencionesRollupProtocol, ...],
) -> Decimal:
    if fact is RetencionesAggregationFact.PERCEPTOR_COUNT_DISTINCT:
        return Decimal(len({row.perceptor_nif for row in selected}))
    if fact is RetencionesAggregationFact.TAXABLE_BASE_SUM:
        return sum((row.total_taxable_base for row in selected), Decimal("0"))
    if fact is RetencionesAggregationFact.RETENCION_AMOUNT_SUM:
        return sum((row.total_retencion for row in selected), Decimal("0"))
    raise RegistryValidationError(f"retenciones scheme-filtered binding declares unsupported fact {fact!r}")


def _modelo_180_type2_row_value(
    row: _Modelo180Type2RowProtocol,
    row_field: str,
    *,
    binding_id: BindingId,
) -> Decimal | str | int | bool | None:
    """Return one selected-layout field from the canonical Modelo 180 type-2 row.

    These names mirror the selected layout's ``row_field_casilla_ids`` map.  A
    new layout field must be deliberately added here, so a registry typo or an
    unsupported layout extension cannot turn into a blank official record.
    """
    detail = row.property_detail
    values: dict[str, Decimal | str | int | bool | None] = {
        "perceptor_nif": str(row.perceptor_nif),
        "representative_nif": None if detail.representative_nif is None else str(detail.representative_nif),
        "perceptor_name": row.perceptor_name,
        "recipient_province_code": detail.recipient_province_code,
        "modality": detail.modality,
        "taxable_base": row.taxable_base,
        "withholding_percentage": row.withholding_percentage,
        "retencion_amount": row.retencion_amount,
        "accrual_year": detail.accrual_year,
        "situation": detail.situation,
        "cadastral_reference": detail.cadastral_reference,
    }
    values.update(_modelo_180_structured_address_values(detail.address))
    try:
        return values[row_field]
    except KeyError as exc:
        raise RegistryValidationError(
            f"binding {binding_id!r} row_field {row_field!r} is not produced for Modelo 180 type-2 rows",
        ) from exc


def _modelo_180_structured_address_values(
    address: _Modelo180StructuredAddressProtocol | None,
) -> dict[str, str | None]:
    return {
        **_modelo_180_address_street_values(address),
        **_modelo_180_address_unit_values(address),
        **_modelo_180_address_locality_values(address),
    }


def _modelo_180_address_street_values(
    address: _Modelo180StructuredAddressProtocol | None,
) -> dict[str, str | None]:
    return {
        "street_type": None if address is None else address.street_type,
        "street_name": None if address is None else address.street_name,
        "number_type": None if address is None else address.number_type,
        "house_number": None if address is None else address.house_number,
        "number_qualifier": None if address is None else address.number_qualifier,
        "block": None if address is None else address.block,
    }


def _modelo_180_address_unit_values(
    address: _Modelo180StructuredAddressProtocol | None,
) -> dict[str, str | None]:
    return {
        "portal": None if address is None else address.portal,
        "staircase": None if address is None else address.staircase,
        "floor": None if address is None else address.floor,
        "door": None if address is None else address.door,
        "complement": None if address is None else address.complement,
    }


def _modelo_180_address_locality_values(
    address: _Modelo180StructuredAddressProtocol | None,
) -> dict[str, str | None]:
    return {
        "locality": None if address is None else address.locality,
        "municipality": None if address is None else address.municipality,
        "municipality_code": None if address is None else address.municipality_code,
        "province_code": None if address is None else address.province_code,
        "postal_code": None if address is None else address.postal_code,
    }


__all__ = [
    "RetencionesAggregationFact",
    "RetencionesAggregationProvider",
    "resolve_retenciones_aggregation_binding_row_values",
    "resolve_retenciones_aggregation_binding_values",
    "validate_retenciones_aggregation_binding",
]


RetencionesAggregationProvider = RetencionesAggregationProvider
