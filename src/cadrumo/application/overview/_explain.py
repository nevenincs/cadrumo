"""Overview explain: per-(modelo, year) applicability decomposition.

:func:`build_overview_explain` is the application service backing
``aeat app overview explain MODELO [--year YYYY]``. The ``applicable``
verdict is DERIVED from the three-axis
:class:`~domain.deadlines.TaxpayerProfile` taxpayer model through
the registry-grounded
:func:`~domain.calculations.registry.derive_modelo_applicability`
rule table, never assumed from an autónomo default. An undeclared taxpayer
model yields an explicit ``incomplete`` verdict: the service
reports "declare your taxpayer type first" rather than a confident
wrong obligation.

The deadline-engine ``explain`` text is still surfaced as the
*scheduling* rationale (when the modelo's filing windows are
registered for the year), but it no longer drives the applicability
flag. The service also enumerates the profile keys the answer depends
on so the operator can audit them. Local-only: never contacts AEAT.

See Also:
    :class:`ModeloRevision`
        Compiled revision whose deadline windows are matched against the
        taxpayer profile to build the scheduling rationale.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import UNMODELED_OBLIGATIONS as _UNMODELED_OBLIGATIONS
from ...core.time import now, today_madrid
from ...domain.calculations.registry import (
    ApplicabilityVerdict,
    LegalRefId,
    derive_modelo_applicability,
)
from ...domain.deadlines import (
    DeadlineEngine,
    DeadlineValidationError,
    NoDeadlineWindowsError,
    TaxpayerProfile,
    twelve_month_anniversary,
)
from ...domain.retention import TAX_RECORD_RETENTION_FLOOR_YEARS, add_prescription_years
from .errors import OverviewExplainError

if TYPE_CHECKING:
    from ...domain.calculations.registry import DeadlineWindowDefinition, ModeloRevision

_ProfileFactValue = str | bool | int
"""Closed value type for the explain payload's ``profile_facts`` map.

The deadline-engine-relevant fields surfaced through
:func:`_extract_profile_facts` are all JSON-serialisable scalars:
booleans (most applicability gates), strings (tax_id, enum values
coerced via ``.value``), and integers (numeric thresholds). Widening
this union is a contract change; keep it tight so the boundary
remains a typed surface rather than a ``dict[str, Any]`` escape hatch.
"""


_UNMODELED_MODELO_DESCRIPTIONS: dict[str, str] = {str(code): desc for code, desc in _UNMODELED_OBLIGATIONS.items()}
"""Recognized-but-unmodeled obligations keyed by bare modelo code.

Derived once from :data:`~core.UNMODELED_OBLIGATIONS` so ``explain`` can
tell an operator that a code like ``"216"`` is a real AEAT obligation the app
does not model yet — distinct from an unknown-identifier typo.
"""


class DeadlineExplanationEngine(Protocol):
    """Protocol for the deadline engine's scheduling-rationale method."""

    def explain(self, profile: TaxpayerProfile, modelo: str, *, year: int | None = None) -> str: ...


class OverviewExplain(BaseModel):
    """Outcome of ``build_overview_explain``.

    The model separates the registry-applicability verdict from the optional
    deadline-engine scheduling rationale. That keeps
    :class:`ApplicabilityVerdict` authoritative even when a known modelo has no
    registered filing window for the requested year.

    Attributes:
        modelo: AEAT modelo identifier the explanation is for.
        year: The fiscal year the applicability was evaluated against.
        applicable: Whether the modelo positively applies to the
            profile this year. Only an
            :attr:`ApplicabilityVerdict.APPLICABLE`
            verdict is ``True``; ``NOT_APPLICABLE`` and ``INCOMPLETE``
            are both ``False`` — the operator is never told a modelo
            applies unless the taxpayer model positively justifies it.
        verdict: The three-state
            :class:`ApplicabilityVerdict` derived from
            the taxpayer model. ``INCOMPLETE`` means the operator must
            declare their taxpayer type first.
        rationale: Operator-facing prose explaining the verdict,
            derived from the registry-grounded applicability rule.
        legal_refs: Opaque BOE / AEAT citation keys grounding the
            applicability rule. Always at least one entry.
        scheduling_rationale: The deadline engine's registry-backed
            scheduling text, when the modelo's filing windows are
            registered for the year. ``None`` when no deadline-window
            data exists (registry-track gap R1) — the applicability
            ``verdict`` is independent of it.
        out_of_plazo_warning: Warning text when the matching registry
            filing window closed more than twelve months before the
            reference date. The warning annotates the voluntary-deadline
            state and the ordinary four-year LGT prescription horizon
            without changing the applicability verdict.
        profile_facts: Subset of the operator's
            :class:`~domain.deadlines.TaxpayerProfile` fields the answer
            depends on. Keys are stable field names; values are
            JSON-serialisable scalars.
        generated_at: UTC timestamp of when the aggregator ran.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    year: int = Field(ge=1990, le=2200)
    applicable: bool
    verdict: ApplicabilityVerdict
    rationale: str = Field(min_length=1)
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    scheduling_rationale: str | None = None
    out_of_plazo_warning: str | None = None
    profile_facts: dict[str, _ProfileFactValue] = Field(default_factory=dict)
    generated_at: datetime


_DEADLINE_RELEVANT_FIELDS: tuple[str, ...] = (
    "tax_id",
    "entity_type",
    "legal_entity_form",
    "irpf_estimation_regime",
    "iva_regime",
    "has_employees",
    "pays_professionals_with_retencion",
    "art109_activity_income_withholding_ge_70pct",
    "pays_rent_with_retencion",
    "pays_capital_income_with_retencion",
    "does_intracomunitario",
    "third_party_transactions_above_347_threshold",
    "bienes_extranjero_above_threshold",
    "monedas_virtuales_extranjero_above_threshold",
)


def _extract_profile_facts(profile: TaxpayerProfile) -> dict[str, _ProfileFactValue]:
    """Return the applicability-relevant profile fields as a plain dict.

    The applicability verdict is derived from the three-axis taxpayer
    model — entity type, IRPF income categories, estimation regime —
    plus the flat deadline facts. Surfacing them here lets the operator
    see which facts the answer depends on.
    """
    facts: dict[str, _ProfileFactValue] = {}
    for field_name in _DEADLINE_RELEVANT_FIELDS:
        if not hasattr(profile, field_name):
            continue
        value = getattr(profile, field_name)
        # Coerce enums to their string value for JSON-serialisable output.
        if hasattr(value, "value"):
            value = value.value
        # An undeclared optional axis (entity_type / regime) is None;
        # surface it as an explicit empty string so the operator sees
        # the gap rather than a missing key.
        facts[field_name] = "" if value is None else value
    # The IRPF income-category set is the gate for natural persons;
    # surface it as a stable comma-joined token.
    facts["irpf_income_categories"] = ",".join(sorted(category.value for category in profile.irpf_income_categories))
    # The nested IVA + enrolment sub-models also gate applicability.
    iva = getattr(profile, "iva", None)
    if iva is not None:
        facts["iva.roi_enrolled"] = iva.roi_enrolled
        facts["iva.oss_enrolled"] = iva.oss_enrolled
        facts["iva.group_member_enrolled"] = iva.group_member_enrolled
        facts["iva.group_dominant_entity_enrolled"] = iva.group_dominant_entity_enrolled
        facts["iva.intracommunity_operations_exceed_50000_eur"] = iva.intracommunity_operations_exceed_50000_eur
    return facts


def _modelo_is_registered(modelo: str) -> bool:
    """Return whether ``modelo`` is a known modelo in the calculation registry.

    Distinguishes a genuinely unknown modelo identifier from a real
    modelo whose registry entry simply has no deadline-window data for
    the requested year. The former is an operator error; the latter is
    a registry-data gap the CLI should degrade gracefully around rather
    than crash on.
    """
    from ...core.resources import ResourceNotFoundError, resources

    try:
        resources().modelos.get(modelo)
    except ResourceNotFoundError:
        return False
    return True


def build_overview_explain(
    profile: TaxpayerProfile,
    *,
    modelo: str,
    year: int | None = None,
    engine: DeadlineExplanationEngine | None = None,
    today: date | None = None,
) -> OverviewExplain:
    """Decompose a modelo's applicability against the operator's profile.

    The ``applicable`` flag and the ``verdict`` are DERIVED from the
    three-axis taxpayer model through
    :func:`~domain.calculations.registry.derive_modelo_applicability`
    — never from an autónomo default. An undeclared taxpayer
    model yields an ``INCOMPLETE`` verdict: the service
    reports "declare your taxpayer type first" instead of a confident
    wrong obligation.

    The deadline engine's ``explain`` text is still surfaced as
    ``scheduling_rationale`` when the modelo's filing windows are
    registered for the year. When the modelo is a known registry modelo
    but no deadline windows are registered (registry-track gap R1), the
    scheduling rationale is left ``None``; the applicability ``verdict``
    is unaffected. A genuinely unknown modelo identifier still raises
    :class:`OverviewExplainError`.

    Args:
        profile: The :class:`~domain.deadlines.TaxpayerProfile` whose
            attributes determine applicability.
        modelo: Modelo identifier to explain (e.g. ``"130"``).
        year: Optional calendar year. Defaults to the current year.
        engine: Optional :class:`DeadlineExplanationEngine` override.
        today: Optional reference date for out-of-plazo annotation.
            Defaults to today. Tests pass this explicitly; the CLI uses
            the real current date.

    Returns:
        An :class:`OverviewExplain` carrying the applicability verdict,
        optional scheduling rationale, and profile facts used by the verdict.

    Raises:
        OverviewExplainError: When the modelo identifier is blank or
            unknown to the registry, or when the deadline engine fails
            for a reason other than a missing deadline-window dataset.
    """
    modelo_id = modelo.strip()
    if not modelo_id:
        raise OverviewExplainError(
            translated_message="application.overview.explain.errors.modelo_blank",
        )
    reference_today = today or today_madrid()
    resolved_year = year or reference_today.year

    if not _modelo_is_registered(modelo_id):
        unmodeled_description = _UNMODELED_MODELO_DESCRIPTIONS.get(modelo_id)
        if unmodeled_description is not None:
            # A recognized AEAT obligation the registry does not model: it is a
            # real obligation, not an operator typo, so distinguish it from an
            # unknown identifier. The coverage reconciliation advises it as
            # ``registry_unmodeled``; explain says the same in prose.
            raise OverviewExplainError(
                translated_message="errors.fail.overview_explain",
                context={
                    "modelo": str(modelo_id),
                    "unmodeled_description": unmodeled_description,
                    "coverage": "registry_unmodeled",
                    "recognized_aeat_obligation": True,
                    "registry_models_it": False,
                },
            )
        # Refuse operator typos before calling the domain applicability
        # model: the domain schema validates known ModeloId shape and
        # must not leak a Pydantic error through the overview boundary.
        raise OverviewExplainError(
            translated_message="errors.fail.overview_explain",
            context={
                "modelo": str(modelo_id),
                "filing_year": str(resolved_year),
                "modelo_registered": False,
            },
        )

    applicability = derive_modelo_applicability(profile, modelo_id)
    # The scheduling rationale is independent of the applicability
    # verdict: it explains the filing window, not whether the taxpayer
    # owes the modelo. It is only meaningful when the registry carries
    # deadline windows for the modelo/year.
    scheduling_rationale = _scheduling_rationale(
        profile,
        modelo=modelo_id,
        year=resolved_year,
        engine=engine,
    )
    out_of_plazo_warning = _out_of_plazo_warning(
        profile,
        modelo=modelo_id,
        year=resolved_year,
        today=reference_today,
    )

    return OverviewExplain(
        modelo=modelo_id,
        year=resolved_year,
        applicable=applicability.applicable,
        verdict=applicability.verdict,
        rationale=applicability.reason,
        legal_refs=applicability.legal_refs,
        scheduling_rationale=scheduling_rationale,
        out_of_plazo_warning=out_of_plazo_warning,
        profile_facts=_extract_profile_facts(profile),
        generated_at=now(),
    )


def _scheduling_rationale(
    profile: TaxpayerProfile,
    *,
    modelo: str,
    year: int,
    engine: DeadlineExplanationEngine | None,
) -> str | None:
    """Return the deadline engine's scheduling text, or ``None``.

    ``None`` is returned when the registry has no deadline windows for
    the modelo/year (registry-track gap R1) — a data gap the CLI
    degrades gracefully around. A genuinely unknown modelo identifier
    is left for :func:`build_overview_explain` to refuse. Other
    :class:`~domain.deadlines.DeadlineValidationError` failures remain
    typed :class:`OverviewExplainError` refusals.
    """
    deadline_engine = engine or DeadlineEngine()
    try:
        return deadline_engine.explain(profile, modelo, year=year)
    except NoDeadlineWindowsError:
        # The benign no-windows data gap (registry-track R1): no
        # deadline windows registered for this modelo/year. Degrade
        # gracefully. The narrow ``NoDeadlineWindowsError`` catch lets a
        # genuine registry-integrity fault (the bare
        # ``ScheduleComputationError``) propagate instead of being
        # swallowed as a missing-data state.
        return None
    except DeadlineValidationError as exc:
        raise OverviewExplainError(
            translated_message="errors.fail.overview_explain",
            context={
                "modelo": str(modelo),
                "filing_year": str(year),
                "evaluation_error_type": type(exc).__name__,
            },
        ) from exc


def _out_of_plazo_warning(
    profile: TaxpayerProfile,
    *,
    modelo: str,
    year: int,
    today: date,
) -> str | None:
    """Return an old-deadline warning for ``overview explain``.

    Applicability answers the taxpayer-model question ("does this
    modelo apply?"). This helper adds a separate timing warning: a
    historical return can still be applicable while its
    voluntary filing window closed long ago.
    """
    deadline_engine = DeadlineEngine()
    try:
        windows = deadline_engine.deadline_windows(year)
    except NoDeadlineWindowsError:
        return None
    matching_windows = tuple(
        window
        for code, revision, window in windows
        if code == modelo and _deadline_window_matches(deadline_engine, profile, revision, window)
    )
    if not matching_windows:
        return None
    closes_on = max(window.closes_on for window in matching_windows)
    twelve_month_boundary = twelve_month_anniversary(closes_on)
    if today < twelve_month_boundary:
        return None
    days_late = (today - closes_on).days
    prescription_boundary = add_prescription_years(closes_on, TAX_RECORD_RETENTION_FLOOR_YEARS)
    prescription_state = (
        "inside the ordinary four-year LGT arts. 66-67 prescription horizon"
        if today <= prescription_boundary
        else "after the ordinary four-year LGT arts. 66-67 prescription horizon"
    )
    return (
        f"out_of_plazo: voluntary filing window closed on {closes_on.isoformat()}; "
        f"as of {today.isoformat()} the return is {days_late} days past the "
        f"deadline and is {prescription_state} "
        f"(ordinary boundary {prescription_boundary.isoformat()})."
    )


def _deadline_window_matches(
    deadline_engine: DeadlineEngine,
    profile: TaxpayerProfile,
    revision: ModeloRevision,
    window: DeadlineWindowDefinition,
) -> bool:
    if not deadline_engine.schedule_applies(profile, revision, window):
        return False
    condition_text = deadline_engine.evaluate_conditions(
        profile,
        window.applicability_conditions,
        mode=window.applicability_condition_mode,
    )
    return condition_text is not None


__all__ = [
    "DeadlineExplanationEngine",
    "OverviewExplain",
    "build_overview_explain",
]
