"""Generic advisory seams for registry-selected family declarations.

Revision-specific descendant predicates, profile identifiers, legal
references, and bounded-detail policy belong to the selected Modelo 100
registry revision. This module retains generic diagnostic mechanics and the
unrelated childcare advisory helpers.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, NamedTuple

from ...core.casilla_id import CasillaId
from ...core.modelo import Modelo
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.formula_runtime_ops import resolve_dated_value
from ...domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.contribuyente.descendant import DescendantInfo
from ...domain.contribuyente.descendant_facts import descendant_list_from_facts
from ...domain.contribuyente.family_fact_context import FamilyFactResolutionContext
from ...domain.user_profile.errors import ProfileNotFoundError
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from .semantic_role_resolution import casilla_id_for_unambiguous_revision_semantic_role

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from .work_profile import ModeloWorkProfile

__all__ = [
    "collect_descendientes_count_desync_diagnostics",
    "collect_guarderia_madre_meses_undeclared_diagnostics",
    "collect_guarderia_spend_shape_diagnostics",
    "collect_minimo_descendientes_dependencia_diagnostics",
    "collect_minimo_descendientes_entry_date_missing_diagnostics",
    "collect_minimo_descendientes_prorrata_inferred_diagnostics",
    "collect_minimo_descendientes_rentas_undeclared_diagnostics",
    "collect_minimo_descendientes_undeclared_diagnostics",
]

_GUARDERIA_SHAPE_SOURCE_KIND = "guarderia_spend_needs_monthly_detail"
_SEGUNDO_CICLO_SOURCE_KIND = "guarderia_segundo_ciclo_month_undeclared"
_COTIZACIONES_FACT_KEY = "renta_family.cotizaciones_ss_madre_2024"
_COTIZACIONES_CEILING_SOURCE_KIND = "guarderia_cotizaciones_ceiling_unbounded"
_GUARDERIA_MADRE_MESES_SOURCE_KIND = "guarderia_madre_meses_undeclared"
_MINIMO_ESTATAL_SEMANTIC_ROLE = "irpf_minimo_descendientes_estatal"
_DESCENDANT_FACT_PREFIX = "renta_family.descendiente."
_DESCENDANTS_COUNT_PATH = "renta_family.descendientes_count"
_UNDECLARED_SOURCE_KIND = "minimo_descendientes_undeclared"
_RENTAS_UNDECLARED_SOURCE_KIND = "minimo_descendientes_rentas_undeclared"

#: The Art. 81.2 guardería increase (Modelo 100 casilla 0613).
_INCREMENTO_GUARDERIA_SEMANTIC_ROLE = "irpf_incremento_maternidad_guarderia"


class _GuarderiaContext(NamedTuple):
    """The shared source facts an Art. 81.3 advisory reads."""

    casilla_id: CasillaId
    filing_year: int
    descendants: tuple[DescendantInfo, ...]
    facts: dict[str, str]
    family_context: FamilyFactResolutionContext
    registry_scope: _RegistryScope


class _RegistryScope(NamedTuple):
    """The typed registry declarations selected for one calculation scope."""

    revision: ModeloRevision
    bindings: tuple[BindingDefinition, ...]
    filing_year: int
    period_token: str


def _registry_minimo_descendientes_diagnostics(
    revision: ModeloRevision,
    *,
    modelo: str,
    filing_year: int,
    period_token: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Resolve the selected revision's typed verification declarations.

    The advisory predicates themselves remain generic mechanics. Their
    revision-specific profile, formula and legal/source declarations are read
    from the scope selected by the calculation, so a latest-revision lookup
    cannot accidentally author a historical filing.
    """
    scope = _selected_registry_scope(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        period_token=period_token,
    )
    if scope is None:
        return ()
    _validate_binding_report(scope)
    return ()


def _registry_minimo_descendientes_count_diagnostics(
    revision: ModeloRevision,
    *,
    modelo: str,
    filing_year: int,
    period_token: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Resolve the selected revision before checking count consistency."""
    scope = _selected_registry_scope(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        period_token=period_token,
    )
    if scope is None:
        return ()
    _validate_binding_report(scope)
    return ()


def _selected_registry_scope(
    revision: ModeloRevision,
    *,
    modelo: str,
    filing_year: int,
    period_token: str,
) -> _RegistryScope | None:
    """Select one validated registry revision using the live filing scope."""
    if modelo != Modelo("100").value:
        return None
    if type(filing_year) is not int or filing_year <= 0 or not period_token.strip():
        raise RegistryValidationError("descendant advisory registry scope is incomplete")
    return _RegistryScope(
        revision=revision,
        bindings=tuple(revision.bindings),
        filing_year=filing_year,
        period_token=period_token,
    )


def _validate_binding_report(scope: _RegistryScope) -> None:
    """Require the query report to carry every typed, grounded binding row."""
    declared_ids = {str(binding.id) for binding in scope.revision.bindings}
    reported_ids = {str(binding.id) for binding in scope.bindings}
    if declared_ids != reported_ids:
        raise RegistryValidationError(
            "selected descendant advisory binding report does not match the revision declarations",
        )
    if any(not binding.legal_refs or not binding.source_refs for binding in scope.bindings):
        raise RegistryValidationError(
            "selected descendant advisory binding report contains an ungrounded declaration",
        )


def _registry_named_descendant_limit(scope: _RegistryScope) -> int:
    """Read the message cardinality from the selected registry revision."""
    candidates = tuple(
        parameter
        for parameter in scope.revision.parameters
        if str(parameter.data_type) == "integer" and parameter.unit == "diagnostic_items"
    )
    if len(candidates) != 1:
        raise RegistryValidationError(
            "selected descendant advisory revision must declare exactly one integer diagnostic_items parameter",
        )
    selected = resolve_dated_value(
        candidates[0],
        {DateAxis.FILING_PERIOD.value: date(scope.filing_year, 12, 31)},
    )
    if selected.date_axis is not DateAxis.FILING_PERIOD:
        raise RegistryValidationError(
            "selected descendant advisory cardinality must use the filing_period axis",
        )
    value = selected.value
    if value != value.to_integral_value() or value <= 0:
        raise RegistryValidationError(
            "selected descendant advisory cardinality must be a positive integer",
        )
    return int(value)


def _family_fact_context(
    filing_year: int,
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> FamilyFactResolutionContext:
    """Compose the advisory's explicit family fact coordinates."""
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return _family_fact_context(filing_year, operation=indexed_operation)
    coordinate = date(filing_year, 12, 31)
    return FamilyFactResolutionContext(
        authority=operation,
        filing_period=coordinate,
        devengo_date=coordinate,
    )


def collect_minimo_descendientes_undeclared_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    filing_year: int,
    period_token: str,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None = None,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Disclose the ambiguous zero for the selected :class:`ModeloRevision`."""
    scope = _selected_registry_scope(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        period_token=period_token,
    )
    if scope is None:
        return ()
    _validate_binding_report(scope)
    casilla_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _MINIMO_ESTATAL_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    if casilla_id is None or casilla_values.get(casilla_id, Decimal("0")) != 0:
        return ()
    facts = _profile_fact_strings(bucket_id, operation=operation, profile=profile)
    if facts is None:
        return ()
    if any(key.startswith(_DESCENDANT_FACT_PREFIX) or key == _DESCENDANTS_COUNT_PATH for key in facts):
        return ()
    return (
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind=_UNDECLARED_SOURCE_KIND,
            message=(
                f"casilla {casilla_id!r} (mínimo por descendientes, parte estatal) resolved to zero and "
                "the active profile declares no descendant facts"
            ),
            remedy="Declare the family situation with `descendiente add --descendiente NACIMIENTO=YYYY-MM-DD`.",
            casilla_id=casilla_id,
        ),
    )


def _profile_fact_strings(
    bucket_id: str,
    *,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None,
) -> dict[str, str] | None:
    """Return every non-null profile fact as a ``{path: str-value}`` map, or ``None``."""
    if profile is not None:
        record = profile.record
    else:
        from ..user_profile.profile_record_repository import ProfileRecordRepository

        try:
            record = ProfileRecordRepository.for_current_session(
                bucket_id,
                profile_decode_context=operation.profile_decode_context(),
            ).load(bucket_id)
        except ProfileNotFoundError:
            return None
    return {fact.path: str(fact.value) for fact in record.facts if fact.value is not None}


def collect_minimo_descendientes_prorrata_inferred_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    filing_year: int,
    period_token: str,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Delegate inferred-proration verification declarations to the registry.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    del casilla_values, bucket_id
    return _registry_minimo_descendientes_diagnostics(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        period_token=period_token,
    )


def _name_indices(indices: list[int], scope: _RegistryScope) -> str:
    """Render generic descendant labels using the registry-selected cardinality."""
    limit = _registry_named_descendant_limit(scope)
    shown = ", ".join(f"descendant[{index}]" for index in indices[:limit])
    remainder = len(indices) - limit
    return f"{shown} and {remainder} more" if remainder > 0 else shown


def _guarderia_shape_advisory(
    indices: list[int],
    casilla_id: CasillaId,
    scope: _RegistryScope,
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_GUARDERIA_SHAPE_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} counts no guardería spend for {_name_indices(indices, scope)}: the "
            "child turns three in this period, so Art. 81.2 LIRPF admits only spend after the "
            "birthday and an annual total cannot be split across it"
        ),
        remedy=(
            "Restate it month by month with `descendiente add --descendiente "
            "GASTOS_GUARDERIA_MENSUAL=MM:N;MM-MM:N`. The eligible months are the ones your centre "
            "reported, so your certificate is the authority."
        ),
        casilla_id=casilla_id,
    )


def _cotizaciones_ceiling_is_unbounded(
    descendants: Sequence[DescendantInfo],
    facts: Mapping[str, str],
    filing_year: int,
    *,
    context: FamilyFactResolutionContext,
) -> bool:
    """Whether an unbounded cotizaciones ceiling can change this filing's outcome.

    Reads the household cotizaciones fact directly rather than through a profile
    object, because this collector already holds the fact strings and rebuilding a
    profile to ask one question would be a second reader of the same data.

    Silent unless a figure is actually declared: with none the ceiling binds at zero
    and the increment is already nil for a reason the operator can see, so the
    advisory would add nothing but noise.
    """
    raw = facts.get(_COTIZACIONES_FACT_KEY, "").strip()
    if not raw:
        return False
    try:
        declared = int(raw)
    except ValueError:
        return False
    if declared <= 0:
        return False
    return any(
        descendant.convive_con_contribuyente
        and descendant.age_at_year_end(filing_year) == context.integer("lirpf-art-58-under-three-maximum-age")
        and bool(descendant.gastos_guarderia_mensuales)
        for descendant in descendants
    )


def _segundo_ciclo_month_advisory(
    indices: list[int],
    casilla_id: CasillaId,
    scope: _RegistryScope,
) -> CalculationSourceDiagnostic:
    """The turning-three window is withheld until the operator declares the month."""
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_SEGUNDO_CICLO_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} counts no guardería spend for {_name_indices(indices, scope)}: the "
            "child turns three in this period, so Art. 81.2 LIRPF admits spend only up to the "
            "month before the second cycle of educación infantil may begin, and that month is "
            "not declared"
        ),
        remedy=(
            "Declare it with `descendiente add --descendiente SEGUNDO_CICLO_INFANTIL_INICIO_MES=MM`. "
            "The month is the one the second cycle may start for this child, which your región "
            "and centre determine; your centre reports it on the modelo 233."
        ),
        casilla_id=casilla_id,
    )


def _cotizaciones_ceiling_advisory(casilla_id: CasillaId) -> CalculationSourceDiagnostic:
    """The cotizaciones limb is bounded by the same month, and is NOT applied here.

    Disclosed rather than computed: the declared figure is a household annual total
    while the ceiling is per child, and AEAT states no rule for apportioning one
    across several. Computing one would invent the arithmetic this advisory exists
    to keep out of the engine.
    """
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_COTIZACIONES_CEILING_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} caps the guardería increment with the declared cotizaciones "
            "total as supplied. For a child turning three, Art. 81 counts only the cotizaciones "
            "devengadas up to the month before the second cycle may begin, and this application "
            "does not apply that bound: the figure is a household annual total while the ceiling "
            "is per child"
        ),
        remedy=(
            "Supply the already-bounded figure — the cotizaciones devengadas up to the month "
            "before the second cycle may begin — rather than the full annual total, if the two "
            "differ for this filing."
        ),
        casilla_id=casilla_id,
    )


def _guarderia_madre_meses_advisory(
    indices: list[int],
    casilla_id: CasillaId,
    scope: _RegistryScope,
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_GUARDERIA_MADRE_MESES_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} is zero despite declared guardería spend for "
            f"{_name_indices(indices, scope)}: Art. 81.2 LIRPF raises the maternidad deducción, so it "
            "needs the months the mother met the Art. 81.1 requirement, and none are on record"
        ),
        remedy=(
            "Declare them with `descendiente add --descendiente MESES_TRABAJO=MM-MM`, or leave "
            "the zero if she met it in no month of this period."
        ),
        casilla_id=casilla_id,
    )


def collect_minimo_descendientes_rentas_undeclared_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    filing_year: int,
    period_token: str,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None = None,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Disclose an absent rentas figure for the selected :class:`ModeloRevision`."""
    scope = _selected_registry_scope(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        period_token=period_token,
    )
    if scope is None:
        return ()
    _validate_binding_report(scope)
    casilla_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _MINIMO_ESTATAL_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    if casilla_id is None or casilla_values.get(casilla_id, Decimal("0")) == 0:
        return ()
    facts = _profile_fact_strings(bucket_id, operation=operation, profile=profile)
    if facts is None:
        return ()
    context = _family_fact_context(filing_year, operation=operation)
    undeclared = [
        index
        for index, descendant in enumerate(descendant_list_from_facts(facts))
        if descendant.rentas_anuales_euros is None
        and descendant.meets_non_income_conditions(filing_year, context=context)
    ]
    if not undeclared:
        return ()
    return (
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind=_RENTAS_UNDECLARED_SOURCE_KIND,
            message=(
                f"casilla {casilla_id!r} claims a mínimo por descendientes for "
                f"{_name_indices(undeclared, scope)} with no annual-rentas figure on record"
            ),
            remedy="Declare the figure with `descendiente add --descendiente RENTAS=N`; RENTAS=0 is explicit.",
            casilla_id=casilla_id,
        ),
    )


def collect_minimo_descendientes_entry_date_missing_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    filing_year: int,
    period_token: str,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Delegate entry-date verification declarations to the registry.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    del casilla_values, bucket_id
    return _registry_minimo_descendientes_diagnostics(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        period_token=period_token,
    )


def collect_guarderia_spend_shape_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    filing_year: int,
    period_token: str,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None = None,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise when a declared guardería figure contributes nothing because of its SHAPE.

    Art. 81.2 extends the increase into the period the child turns three, but
    only for spend "incurridos con posterioridad al cumplimiento de dicha edad".
    An ANNUAL total spans that birthday and cannot be apportioned across it, so
    a child in that period whose spend is on record only as an annual figure
    contributes zero.

    That is the one state where a taxpayer declared real spend, sees it stored,
    and receives nothing — and nothing about the computed value says why. It is
    not a withheld window: the operator can replace the annual figure with the
    month-by-month detail their childcare centre already certified, and the
    months on that certificate are exactly the eligible ones, because the centre
    determines them and reports them to the authority on its own informative
    return. So the advisory points at the document that settles the question
    rather than at a rule this application cannot state (`no-silent-under-declaration`).

    Args:
        revision: The :class:`ModeloRevision` being calculated. Its ``valid_to``
            supplies the devengo year the turning-three test is anchored to.
        casilla_values: The computed engine values keyed by :class:`CasillaId`.
        modelo: The modelo identifier of the filing being calculated.
        filing_year: Filing year used to select the descendant fact coordinate.
        period_token: Registry period token used to confirm the selected scope.
        bucket_id: Bucket whose profile carries the descendant facts.
        operation: Authority operation supplying the profile and registry reads.
        profile: The bucket's profile when the caller already loaded it; when
            omitted, the facts are read from the bucket.

    Returns:
        A one-element tuple carrying the advisory, or an empty tuple.
    """
    context = _guarderia_descendants(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        period_token=period_token,
        bucket_id=bucket_id,
        operation=operation,
        profile=profile,
    )
    if context is None:
        return ()
    return _guarderia_spend_shape_diagnostics(context)


def _guarderia_descendants(
    revision: ModeloRevision,
    *,
    modelo: str,
    filing_year: int,
    period_token: str,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None,
) -> _GuarderiaContext | None:
    """Resolve the shared preconditions the two Art. 81.3 collectors below need.

    Both ask about the same population against the same casilla and the same
    devengo year, and both are silent for the same three reasons: a different
    modelo, a revision that fixes no devengo date, or an unreadable profile.
    Assembled once so the two cannot drift into disagreeing about when they
    apply.
    """
    if modelo != Modelo("100").value:
        return None
    casilla_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _INCREMENTO_GUARDERIA_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    if casilla_id is None:
        return None
    if revision.valid_to is None:
        return None
    registry_scope = _selected_registry_scope(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        period_token=period_token,
    )
    if registry_scope is None:
        return None
    facts = _profile_fact_strings(bucket_id, operation=operation, profile=profile)
    if facts is None:
        return None
    descendant_facts = facts
    return _GuarderiaContext(
        casilla_id=casilla_id,
        filing_year=registry_scope.filing_year,
        descendants=tuple(descendant_list_from_facts(descendant_facts)),
        facts=facts,
        family_context=_family_fact_context(registry_scope.filing_year, operation=operation),
        registry_scope=registry_scope,
    )


def _guarderia_spend_shape_diagnostics(
    context: _GuarderiaContext,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Classify every declared guardería shape issue in stable diagnostic order."""
    affected = [
        index
        for index, descendant in enumerate(context.descendants)
        if descendant.guarderia_needs_monthly_detail(context.filing_year, context=context.family_context)
    ]
    needs_month = [
        index
        for index, descendant in enumerate(context.descendants)
        if descendant.guarderia_needs_segundo_ciclo_month(context.filing_year, context=context.family_context)
    ]
    diagnostics: list[CalculationSourceDiagnostic] = []
    if affected:
        diagnostics.append(_guarderia_shape_advisory(affected, context.casilla_id, context.registry_scope))
    if needs_month:
        diagnostics.append(_segundo_ciclo_month_advisory(needs_month, context.casilla_id, context.registry_scope))
    if _cotizaciones_ceiling_is_unbounded(
        context.descendants,
        context.facts,
        context.filing_year,
        context=context.family_context,
    ):
        diagnostics.append(_cotizaciones_ceiling_advisory(context.casilla_id))
    return tuple(diagnostics)


def collect_guarderia_madre_meses_undeclared_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    filing_year: int,
    period_token: str,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None = None,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise when declared guardería spend yields nothing for want of the mother's months.

    Art. 81.2 increases the maternidad deducción, so it is available only where
    the Art. 81.1 requirement is met, and Art. 81.3 prorates it by the months
    both hold at once. A filer who never recorded the mother's qualifying months
    carries a zero on that side, and zero months of overlap is zero increase.

    The arithmetic is right and the outcome is still a trap, because the record
    cannot tell a mother who declared no qualifying months from one who was
    never asked: the field simply defaults to zero. So a taxpayer can declare
    real nursery spend, watch it stored and listed back, and receive nothing,
    with no computed value able to say which of the two happened
    (`no-silent-under-declaration`).

    Fires only where spend is actually on record for a child the article admits.
    A filer with no guardería spend at all is not in this state, and telling
    them about the mother's months would be noise.

    Args:
        revision: The :class:`ModeloRevision` being calculated; its ``valid_to``
            supplies the devengo year.
        casilla_values: Computed engine values keyed by :class:`CasillaId`. The
            advisory is scoped to the zero, since a positive increase means the
            months were declared.
        modelo: The modelo identifier of the filing being calculated.
        filing_year: Filing year used to select the descendant fact coordinate.
        period_token: Registry period token used to confirm the selected scope.
        bucket_id: Bucket whose profile carries the descendant facts.
        operation: Authority operation supplying the profile and registry reads.
        profile: The bucket's profile when the caller already loaded it; when
            omitted, the facts are read from the bucket.

    Returns:
        A one-element tuple carrying the advisory, or an empty tuple.
    """
    context = _guarderia_descendants(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        period_token=period_token,
        bucket_id=bucket_id,
        operation=operation,
        profile=profile,
    )
    if context is None:
        return ()
    if casilla_values.get(context.casilla_id, Decimal("0")) != 0:
        return ()
    affected = [
        index
        for index, descendant in enumerate(context.descendants)
        if not descendant.meses_madre_trabajo
        and descendant.guarderia_qualifying_meses(context.filing_year, context=context.family_context) > 0
        and descendant.guarderia_contributing_spend(context.filing_year, context=context.family_context) > 0
    ]
    if not affected:
        return ()
    return (_guarderia_madre_meses_advisory(affected, context.casilla_id, context.registry_scope),)


def collect_minimo_descendientes_dependencia_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    filing_year: int,
    period_token: str,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Delegate dependency verification declarations to the registry.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    del casilla_values, bucket_id
    return _registry_minimo_descendientes_diagnostics(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        period_token=period_token,
    )


def collect_descendientes_count_desync_diagnostics(
    revision: ModeloRevision,
    *,
    modelo: str,
    filing_year: int,
    period_token: str,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Delegate descendant-count verification declarations to the registry.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    del bucket_id
    return _registry_minimo_descendientes_count_diagnostics(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        period_token=period_token,
    )
