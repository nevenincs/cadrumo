"""Overview explain: per-(modelo, year) applicability decomposition.

`build_overview_explain` is the application service backing
``aeat app overview explain MODELO [--year YYYY]``. It composes the
existing :meth:`DeadlineEngine.applies_to` and
:meth:`DeadlineEngine.explain` over the operator's profile to surface
the binary applicability decision plus the registry-backed rationale
text that explains why the modelo does or does not apply this year.

The service also enumerates the profile keys the deadline engine
actually read (whose values gated the applicability decision) so the
operator can audit which facts the answer depends on. Local-only:
never contacts AEAT.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from pydantic import BaseModel, ConfigDict, Field

_ProfileFactValue = str | bool | int
"""Closed value type for the explain payload's ``profile_facts`` map.

The deadline-engine-relevant fields surfaced through
:func:`_extract_profile_facts` are all JSON-serialisable scalars:
booleans (most applicability gates), strings (tax_id, enum values
coerced via ``.value``), and integers (numeric thresholds). Widening
this union is a contract change; keep it tight so the boundary
remains a typed surface rather than a ``dict[str, Any]`` escape hatch.
"""

from ...core.i18n import tr
from ...domain.deadlines import AutonomoProfile, DeadlineEngine
from ...domain.deadlines._errors import DeadlineValidationError, ScheduleComputationError
from ._errors import OverviewExplainError

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class OverviewExplain(BaseModel):
    """Outcome of ``build_overview_explain``.

    Attributes:
        modelo: AEAT modelo identifier the explanation is for.
        year: The fiscal year the applicability was evaluated against.
        applicable: Whether the modelo applies to the profile this year.
        rationale: Registry-backed prose describing why the modelo does
            or does not apply. Sourced from
            :meth:`DeadlineEngine.explain`.
        profile_facts: Subset of the operator's :class:`AutonomoProfile`
            fields the deadline engine reads when evaluating
            applicability for this modelo. Keys are stable field names;
            values are JSON-serialisable scalars.
        generated_at: UTC timestamp of when the aggregator ran.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    year: int = Field(ge=1990, le=2200)
    applicable: bool
    rationale: str = Field(min_length=1)
    profile_facts: dict[str, _ProfileFactValue] = Field(default_factory=dict)
    generated_at: datetime


_DEADLINE_RELEVANT_FIELDS: tuple[str, ...] = (
    "tax_id",
    "iva_regime",
    "has_employees",
    "pays_professionals_with_retencion",
    "professional_income_withholding_ge_70pct",
    "pays_rent_with_retencion",
    "pays_capital_income_with_retencion",
    "uses_objective_estimation_irpf",
    "does_intracomunitario",
    "third_party_transactions_above_347_threshold",
    "bienes_extranjero_above_threshold",
)


def _extract_profile_facts(profile: AutonomoProfile) -> dict[str, _ProfileFactValue]:
    """Return the deadline-engine-consumed fields as a plain dict.

    The deadline engine's applicability conditions are written against
    these AutonomoProfile attributes; surfacing them here lets the
    operator see which facts the answer depends on without having to
    re-derive the engine's introspection.
    """

    facts: dict[str, _ProfileFactValue] = {}
    for field_name in _DEADLINE_RELEVANT_FIELDS:
        if not hasattr(profile, field_name):
            continue
        value = getattr(profile, field_name)
        # Coerce enums to their string value for JSON-serialisable output.
        if hasattr(value, "value"):
            value = value.value
        facts[field_name] = value
    # The nested IVA + enrolment sub-models also gate applicability.
    iva = getattr(profile, "iva", None)
    if iva is not None:
        facts["iva.roi_enrolled"] = iva.roi_enrolled
        facts["iva.oss_enrolled"] = iva.oss_enrolled
        facts["iva.intracommunity_operations_exceed_50000_eur"] = (
            iva.intracommunity_operations_exceed_50000_eur
        )
    return facts


def build_overview_explain(
    profile: AutonomoProfile,
    *,
    modelo: str,
    year: int | None = None,
    engine: DeadlineEngine | None = None,
) -> OverviewExplain:
    """Decompose a modelo's applicability against the operator's profile.

    Composes :meth:`DeadlineEngine.applies_to` and
    :meth:`DeadlineEngine.explain` to produce a typed envelope the CLI
    can render as a single answer. The applicability flag is the same
    value the calendar / agenda use when deciding whether to surface
    obligations for this modelo, so explain and the operational views
    cannot diverge.

    Raises:
        OverviewExplainError: When the deadline engine cannot find any
            registry windows for the modelo in the supplied year
            (typically because the modelo is unknown or the year
            predates the registry's earliest revision).
    """

    if not modelo.strip():
        raise OverviewExplainError(tr("application.overview.explain.errors.modelo_blank"))
    resolved_year = year or date.today().year
    deadline_engine = engine or DeadlineEngine()
    try:
        applicable = deadline_engine.applies_to(profile, modelo, year=resolved_year)
        rationale = deadline_engine.explain(profile, modelo, year=resolved_year)
    except (ScheduleComputationError, DeadlineValidationError) as exc:
        raise OverviewExplainError(
            f"could not evaluate modelo {modelo!r} for year {resolved_year}: {exc}",
        ) from exc

    return OverviewExplain(
        modelo=modelo,
        year=resolved_year,
        applicable=applicable,
        rationale=rationale,
        profile_facts=_extract_profile_facts(profile),
        generated_at=datetime.now(UTC),
    )


__all__ = [
    "OverviewExplain",
    "build_overview_explain",
]
