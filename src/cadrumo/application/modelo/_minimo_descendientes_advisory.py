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
from typing import NamedTuple

from ...core.casilla_id import CasillaId
from ...core.modelo import Modelo
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.contribuyente.descendant import DescendantInfo
from ...domain.contribuyente.descendant_facts import descendant_list_from_facts
from ...domain.contribuyente.family_fact_context import FamilyFactResolutionContext
from ...domain.user_profile.errors import ProfileNotFoundError
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from .semantic_role_resolution import casilla_id_for_unambiguous_revision_semantic_role

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

#: The Art. 81.2 guardería increase (Modelo 100 casilla 0613).
_INCREMENTO_GUARDERIA_SEMANTIC_ROLE = "irpf_incremento_maternidad_guarderia"


class _GuarderiaContext(NamedTuple):
    """The shared source facts an Art. 81.3 advisory reads."""

    casilla_id: CasillaId
    filing_year: int
    descendants: tuple[DescendantInfo, ...]
    facts: dict[str, str]
    family_context: FamilyFactResolutionContext


# fact-relocation: selected M100 descendant verification/detail declarations are consumed through RegistryQueryService
def _registry_minimo_descendientes_diagnostics(
    revision: ModeloRevision,
    *,
    modelo: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Leave revision-specific descendant declarations to the registry boundary."""
    report = RegistryQueryService(bundled_authority()).bindings(modelo)
    del revision, report
    raise NotImplementedError("registry-selected descendant verification declarations are unresolved")


def _registry_minimo_descendientes_count_diagnostics() -> tuple[CalculationSourceDiagnostic, ...]:
    """Leave count consistency declarations to the registry boundary."""
    raise NotImplementedError("registry-selected descendant count declarations are unresolved")


def _registry_named_descendant_limit() -> int:
    """Read the message cardinality from the selected registry revision."""
    raise NotImplementedError("registry-selected descendant cardinality is unresolved")


def _family_fact_context(filing_year: int) -> FamilyFactResolutionContext:
    """Compose the advisory's explicit family fact coordinates."""
    coordinate = date(filing_year, 12, 31)
    return FamilyFactResolutionContext(authority=bundled_authority(), filing_period=coordinate, devengo_date=coordinate)


def collect_minimo_descendientes_undeclared_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Delegate descendant verification declarations to the selected revision."""
    del casilla_values, bucket_id
    return _registry_minimo_descendientes_diagnostics(revision, modelo=modelo)


def _profile_fact_strings(bucket_id: str) -> dict[str, str] | None:
    """Return every non-null profile fact as a ``{path: str-value}`` map, or ``None``."""
    from ..user_profile.profile_record_repository import ProfileRecordRepository

    try:
        record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return None
    return {fact.path: str(fact.value) for fact in record.facts if fact.value is not None}


def collect_minimo_descendientes_prorrata_inferred_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Delegate inferred-proration verification declarations to the registry."""
    del casilla_values, bucket_id
    return _registry_minimo_descendientes_diagnostics(revision, modelo=modelo)


def _name_indices(indices: list[int]) -> str:
    """Render generic descendant labels using the registry-selected cardinality."""
    limit = _registry_named_descendant_limit()
    shown = ", ".join(f"descendant[{index}]" for index in indices[:limit])
    remainder = len(indices) - limit
    return f"{shown} and {remainder} more" if remainder > 0 else shown


def _guarderia_shape_advisory(indices: list[int], casilla_id: CasillaId) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_GUARDERIA_SHAPE_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} counts no guardería spend for {_name_indices(indices)}: the "
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


def _segundo_ciclo_month_advisory(indices: list[int], casilla_id: CasillaId) -> CalculationSourceDiagnostic:
    """The turning-three window is withheld until the operator declares the month."""
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_SEGUNDO_CICLO_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} counts no guardería spend for {_name_indices(indices)}: the "
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


def _guarderia_madre_meses_advisory(indices: list[int], casilla_id: CasillaId) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_GUARDERIA_MADRE_MESES_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} is zero despite declared guardería spend for "
            f"{_name_indices(indices)}: Art. 81.2 LIRPF raises the maternidad deducción, so it "
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
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Delegate descendant income verification declarations to the registry."""
    del casilla_values, bucket_id
    return _registry_minimo_descendientes_diagnostics(revision, modelo=modelo)


def collect_minimo_descendientes_entry_date_missing_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Delegate entry-date verification declarations to the registry."""
    del casilla_values, bucket_id
    return _registry_minimo_descendientes_diagnostics(revision, modelo=modelo)


def collect_guarderia_spend_shape_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    bucket_id: str,
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
        bucket_id: Bucket whose profile carries the descendant facts.

    Returns:
        A one-element tuple carrying the advisory, or an empty tuple.
    """
    context = _guarderia_descendants(revision, modelo=modelo, bucket_id=bucket_id)
    if context is None:
        return ()
    return _guarderia_spend_shape_diagnostics(context)


def _guarderia_descendants(revision: ModeloRevision, *, modelo: str, bucket_id: str) -> _GuarderiaContext | None:
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
    facts = _profile_fact_strings(bucket_id)
    if facts is None:
        return None
    descendant_facts = facts
    return _GuarderiaContext(
        casilla_id=casilla_id,
        filing_year=revision.valid_to.year,
        descendants=tuple(descendant_list_from_facts(descendant_facts)),
        facts=facts,
        family_context=_family_fact_context(revision.valid_to.year),
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
        diagnostics.append(_guarderia_shape_advisory(affected, context.casilla_id))
    if needs_month:
        diagnostics.append(_segundo_ciclo_month_advisory(needs_month, context.casilla_id))
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
    bucket_id: str,
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
        bucket_id: Bucket whose profile carries the descendant facts.

    Returns:
        A one-element tuple carrying the advisory, or an empty tuple.
    """
    context = _guarderia_descendants(revision, modelo=modelo, bucket_id=bucket_id)
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
    return (_guarderia_madre_meses_advisory(affected, context.casilla_id),)


def collect_minimo_descendientes_dependencia_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Delegate dependency verification declarations to the registry."""
    del casilla_values, bucket_id
    return _registry_minimo_descendientes_diagnostics(revision, modelo=modelo)


def collect_descendientes_count_desync_diagnostics(
    *,
    modelo: str,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Delegate descendant-count verification declarations to the registry."""
    del modelo, bucket_id
    return _registry_minimo_descendientes_count_diagnostics()
