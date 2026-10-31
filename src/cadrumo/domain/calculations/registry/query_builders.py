"""Build typed reports from resolved registry query contexts.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.ModeloDefinition`,
:class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from ....core.i18n.render import output_language
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import Period, RegistrySelectorPeriodCode
from ....core.type_adapters import OBJECT_TUPLE_ADAPTER
from .binding_selector_utils import boolean_binding_encoded_values
from .binding_temporal import binding_applies_to_period
from .errors import (
    RegistryFailureClassification,
    RegistryFailureCondition,
    RegistryValidationError,
)
from .form_codes import form_for_role
from .ids import BindingId
from .query_reports import (
    BindingInputChannel,
    ModeloBindingQueryRow,
    ModeloBindingsReport,
    ModeloCasillaDetailReport,
    ModeloCasillaRow,
    ModeloCasillasReport,
    ModeloDescribeReport,
    ModeloFormulaRow,
    ModeloFormulasReport,
)
from .relation_prefill_bindings import RelationPrefillProvider
from .relations import relation_prefill_bindings_for_period
from .runtime_graph import (
    enum_consumed_binding_ids,
    expression_binding_refs,
    expression_casilla_refs,
    expression_parameter_refs,
)
from .schema import BindingDefinition, ModeloDefinition, ModeloRevision
from .schema_base import filing_period_from_scope
from .schema_input_kind import InputKind
from .schema_surfaces import CasillaDefinition

if TYPE_CHECKING:
    pass


_PUBLIC_MAPPING_ADAPTER: TypeAdapter[dict[object, object]] = TypeAdapter(
    dict[object, object],
    config=ConfigDict(strict=True),
)


class ResolvedRegistryQueryContext(BaseModel):
    """One resolved registry query context, returned by both resolution forms.

    ``RegistryQueryService`` reaches a modelo revision by two routes: an
    unscoped lookup that narrows by period token alone, and a scoped lookup
    that resolves a snapshot for an explicit filing year. Both routes return
    this context, so every query method and report builder consumes one typed
    shape instead of two positional tuples whose arity and element meaning
    differed. The unscoped route leaves :attr:`filing_year` unset, which is
    why it stays optional here.

    This is deliberately narrower than a
    :class:`~domain.calculations.registry.schema.RegistrySnapshot`: a snapshot
    requires a filing year and carries the whole legal, source, and
    expectation authority, none of which the unscoped period query has or
    needs to answer a read-only introspection request.
    """

    model_config = STRICT_FROZEN_CONFIG

    definition: ModeloDefinition
    revision: ModeloRevision
    revision_ids: tuple[str, ...] = ()
    filing_year: int | None = None
    registry_period: RegistrySelectorPeriodCode | None = None


def build_modelo_describe_report(context: ResolvedRegistryQueryContext) -> ModeloDescribeReport:
    """Assemble a :class:`ModeloDescribeReport` from a resolved query context."""
    definition = context.definition
    revision = context.revision
    filing_year = context.filing_year
    registry_period = context.registry_period
    return ModeloDescribeReport(
        code=definition.id,
        title=definition.get_title(output_language()),
        official_name=definition.get_official_name(output_language()),
        tax_domain=definition.tax_domain,
        cadence=definition.cadence,
        jurisdiction=definition.jurisdiction,
        revision=revision.id,
        authority_grade=revision.authority_grade,
        revision_ids=context.revision_ids,
        filing_year=filing_year,
        filing_period=_query_filing_period(filing_year, registry_period),
        period=registry_period,
        valid_from=revision.valid_from,
        valid_to=revision.valid_to,
        periods=(
            revision.period_selector.declared_periods
            if filing_year is None
            else revision.period_selector.periods_for_year(filing_year)
        ),
        casilla_count=len(revision.casillas),
        manual_casilla_count=sum(1 for casilla in revision.casillas if casilla.input_kind == InputKind.MANUAL),
        bound_casilla_count=sum(1 for casilla in revision.casillas if casilla.input_kind == InputKind.BOUND),
        computed_casilla_count=sum(1 for casilla in revision.casillas if casilla.input_kind == InputKind.COMPUTED),
        binding_count=len(revision.bindings),
        formula_count=len(revision.formulas),
        legal_refs=tuple(ref for ref in revision.legal_refs),
        source_refs=tuple(ref for ref in revision.source_refs),
    )


def _casilla_row_included(
    casilla: CasillaDefinition,
    *,
    input_kind: InputKind | None,
    required: bool | None,
    form_number: str | None,
) -> bool:
    """Return whether a casilla passes the report's optional kind/required/form filters."""
    return (
        (input_kind is None or casilla.input_kind == input_kind)
        and (required is None or casilla.required is required)
        and (form_number is None or casilla.form_number == form_number)
    )


def build_modelo_casillas_report(
    context: ResolvedRegistryQueryContext,
    *,
    input_kind: InputKind | None,
    required: bool | None,
    form_number: str | None,
) -> ModeloCasillasReport:
    """Assemble a filtered :class:`ModeloCasillasReport` from a resolved query context."""
    definition = context.definition
    revision = context.revision
    rows = [
        ModeloCasillaRow(
            casilla_id=casilla.id,
            number=casilla.number,
            label=casilla.get_label(output_language()),
            help_text=casilla.get_help(output_language()),
            section=tuple(casilla.section),
            data_type=casilla.data_type,
            input_kind=casilla.input_kind,
            required=casilla.required,
            formula=casilla.formula if casilla.formula is not None else None,
            binding=casilla.binding if casilla.binding is not None else None,
            form_number=casilla.form_number,
            legal_refs=tuple(ref for ref in casilla.legal_refs),
            source_refs=tuple(ref for ref in casilla.source_refs),
        )
        for casilla in revision.casillas
        if _casilla_row_included(casilla, input_kind=input_kind, required=required, form_number=form_number)
    ]
    return ModeloCasillasReport(
        code=definition.id,
        revision=revision.id,
        filing_year=context.filing_year,
        filing_period=_query_filing_period(context.filing_year, context.registry_period),
        period=context.registry_period,
        rows=tuple(rows),
    )


def build_modelo_formulas_report(context: ResolvedRegistryQueryContext) -> ModeloFormulasReport:
    """Assemble a :class:`ModeloFormulasReport` from a resolved query context."""
    definition = context.definition
    revision = context.revision
    fold_binding_ids = frozenset(binding.id for binding, _ in relation_prefill_bindings_for_period(revision))
    rows = tuple(
        ModeloFormulaRow(
            formula_id=formula.id,
            target_casilla_id=formula.target_casilla_id,
            input_casilla_ids=tuple(dict.fromkeys(expression_casilla_refs(formula.expression))),
            input_bindings=tuple(dict.fromkeys(expression_binding_refs(formula.expression))),
            input_parameters=tuple(dict.fromkeys(expression_parameter_refs(formula.expression))),
            input_relations=tuple(
                binding_id
                for binding_id in dict.fromkeys(expression_binding_refs(formula.expression))
                if binding_id in fold_binding_ids
            ),
            expression=_public_mapping(formula.expression.model_dump(mode="json")),
            legal_refs=tuple(ref for ref in formula.legal_refs),
            source_refs=tuple(ref for ref in formula.source_refs),
        )
        for formula in revision.formulas
    )
    return ModeloFormulasReport(
        code=definition.id,
        revision=revision.id,
        filing_year=context.filing_year,
        filing_period=_query_filing_period(context.filing_year, context.registry_period),
        period=context.registry_period,
        rows=rows,
    )


def build_modelo_bindings_report(context: ResolvedRegistryQueryContext) -> ModeloBindingsReport:
    """Assemble a :class:`ModeloBindingsReport` from a resolved query context."""
    modelo = context.definition.id
    return ModeloBindingsReport(
        code=modelo,
        revision=context.revision.id,
        filing_year=context.filing_year,
        filing_period=_query_filing_period(context.filing_year, context.registry_period),
        period=context.registry_period,
        rows=_binding_rows(context.revision, modelo=modelo, period=context.registry_period),
    )


def _binding_rows(
    revision: ModeloRevision,
    *,
    modelo: str | None = None,
    period: str | None = None,
) -> tuple[ModeloBindingQueryRow, ...]:
    """Build the typed binding rows for one revision.

    Shared by every ``bindings*`` query so the operator-facing
    ``input_channel`` discriminator is computed once, consistently:
    the channel is ``enum`` only for bindings a dispatch op consumes
    as a string enum key, ``decimal`` for every other binding.
    """
    enum_consumed = enum_consumed_binding_ids(revision)
    fold_binding_ids = frozenset(
        binding.id for binding, _ in relation_prefill_bindings_for_period(revision, period=period)
    )
    operator_required = _operator_input_required_by_binding(revision, modelo=modelo, period=period)
    return tuple(
        ModeloBindingQueryRow(
            binding_id=binding.id,
            typed_enum=binding.value.typed_enum,
            input_channel=(BindingInputChannel.ENUM if binding.id in enum_consumed else BindingInputChannel.DECIMAL),
            provider=binding.provider,
            aggregation={"op": binding.aggregation.op.value} if binding.aggregation is not None else None,
            legal_refs=tuple(binding.legal_refs),
            source_refs=tuple(binding.source_refs),
            borrador_capable=binding.aeat_prefilled is True,
            relation_inputs=(binding.id,) if binding.id in fold_binding_ids else (),
            encoded_options=boolean_binding_encoded_values(binding),
            operator_input_required=operator_required.get(binding.id, True),
        )
        for binding in revision.bindings
    )


def _find_casilla_for_detail(
    context: ResolvedRegistryQueryContext,
    casilla: str,
) -> CasillaDefinition:
    """Resolve a detail query by canonical id first, then by printed number."""
    definition = context.definition
    revision = context.revision
    needle = casilla.strip()
    matched = next(
        (item for item in revision.casillas if item.id == needle or item.number == needle),
        None,
    )
    if matched is not None:
        return matched
    valid_ids = [item.id for item in revision.casillas]
    shown = valid_ids[:20]
    sample = ", ".join(shown)
    overflow = "" if len(valid_ids) == len(shown) else f" (+{len(valid_ids) - len(shown)} more)"
    raise RegistryValidationError(
        f"casilla {casilla!r} is not defined by revision {revision.id} of modelo {definition.id}; "
        f"valid casilla ids include: {sample}{overflow}.",
        registry_failure=RegistryFailureClassification(
            condition=RegistryFailureCondition.QUERY_CASILLA_DECLARED,
            facts={
                "modelo": definition.id,
                "revision": revision.id,
                "casilla": needle,
                "casilla_declared": False,
            },
        ),
    )


def _casilla_formula_expression(
    revision: ModeloRevision,
    casilla: CasillaDefinition,
) -> Mapping[str, object] | None:
    """Return a computed casilla's public formula expression, when present."""
    if casilla.formula is None:
        return None
    formula = next((item for item in revision.formulas if item.id == casilla.formula), None)
    if formula is None:
        return None
    return _public_mapping(formula.expression.model_dump(mode="json"))


def casilla_detail_report(context: ResolvedRegistryQueryContext, casilla: str) -> ModeloCasillaDetailReport:
    """Build the single-casilla detail report, resolving the formula expression.

    The casilla is matched by canonical id first, then by printed ``number``
    (the same dual key the ``casillas --number`` filter accepts). An unknown
    casilla raises a :class:`RegistryValidationError` with its observed
    condition and a bounded sample of valid ids.
    A computed casilla's ``formula`` id is resolved against the revision's
    formulas so the structured expression rides the report.
    """
    definition = context.definition
    revision = context.revision
    matched = _find_casilla_for_detail(context, casilla)
    formula_expression = _casilla_formula_expression(revision, matched)
    return ModeloCasillaDetailReport(
        code=definition.id,
        revision=revision.id,
        filing_year=context.filing_year,
        filing_period=_query_filing_period(context.filing_year, context.registry_period),
        period=context.registry_period,
        casilla_id=matched.id,
        number=matched.number,
        label=matched.get_label(output_language()),
        help_text=matched.get_help(output_language()),
        section=tuple(matched.section),
        data_type=matched.data_type,
        input_kind=matched.input_kind,
        required=matched.required,
        legal_refs=tuple(ref for ref in matched.legal_refs),
        source_refs=tuple(ref for ref in matched.source_refs),
        binding=matched.binding,
        formula_id=matched.formula,
        formula_expression=formula_expression,
    )


def _relation_prefill_is_period_default(
    binding: BindingDefinition,
    *,
    modelo: str,
    period: str,
) -> bool:
    """Return whether a relation-prefill slot is a same-model prior default here.

    The slot is fed by this modelo's own earlier periods and does not apply to
    the target period, so the operator is not expected to supply it: the value
    either arrives from a prior filing or the slot is legitimately out of scope.
    """
    provider = binding.provider
    if not isinstance(provider, RelationPrefillProvider):
        return False
    if binding_applies_to_period(binding.applicability, period):
        return False
    return provider.relation_kind == "previous_period" and str(provider.source_modelo) == modelo


def _operator_input_required_by_binding(
    revision: ModeloRevision,
    *,
    modelo: str | None,
    period: str | None,
) -> dict[BindingId, bool]:
    """Return missing-input visibility for relation slots with period-scoped defaults."""
    required = {binding.id: True for binding in revision.bindings}
    if modelo is None or modelo != form_for_role("sociedades.instalment") or period is None:
        return required
    for binding in revision.bindings:
        if _relation_prefill_is_period_default(binding, modelo=modelo, period=period):
            required[binding.id] = False
    return required


def _query_filing_period(filing_year: int | None, period: str | None) -> Period | None:
    if filing_year is None or period is None:
        return None
    return filing_period_from_scope(filing_year, period)


def _public_mapping(value: object) -> dict[str, object]:
    return {str(key): _public_value(item) for key, item in _public_mapping_items(value).items()}


def _public_mapping_items(value: object) -> dict[object, object]:
    """Validate an untyped mapping before projecting it onto the public query API."""
    mapping = _try_public_mapping(value)
    if mapping is not None:
        return mapping
    raise RegistryValidationError(f"unsupported public mapping value {value!r}")


def _try_public_mapping(value: object) -> dict[object, object] | None:
    """Return a checked public mapping, or ``None`` when the value is not one."""
    if not isinstance(value, Mapping):
        return None
    try:
        return _PUBLIC_MAPPING_ADAPTER.validate_python(value)
    except ValidationError:
        return None


def _public_tuple(value: object) -> tuple[object, ...] | None:
    """Narrow a runtime tuple to object entries for recursive public projection."""
    if not isinstance(value, tuple):
        return None
    return OBJECT_TUPLE_ADAPTER.validate_python(value)


def _public_value(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    tuple_value = _public_tuple(value)
    if tuple_value is not None:
        return tuple(_public_value(item) for item in tuple_value)
    mapping = _try_public_mapping(value)
    if mapping is not None:
        return {str(key): _public_value(item) for key, item in mapping.items()}
    return value
