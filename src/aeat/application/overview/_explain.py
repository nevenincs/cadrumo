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

from ...core.i18n import tr
from ...domain.deadlines import DeadlineEngine, TaxpayerProfile
from ...domain.deadlines._errors import DeadlineValidationError, ScheduleComputationError
from ._errors import OverviewExplainError

_ProfileFactValue = str | bool | int
"""Closed value type for the explain payload's ``profile_facts`` map.

The deadline-engine-relevant fields surfaced through
:func:`_extract_profile_facts` are all JSON-serialisable scalars:
booleans (most applicability gates), strings (tax_id, enum values
coerced via ``.value``), and integers (numeric thresholds). Widening
this union is a contract change; keep it tight so the boundary
remains a typed surface rather than a ``dict[str, Any]`` escape hatch.
"""

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
        profile_facts: Subset of the operator's :class:`TaxpayerProfile`
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


def _extract_profile_facts(profile: TaxpayerProfile) -> dict[str, _ProfileFactValue]:
    """Return the deadline-engine-consumed fields as a plain dict.

    The deadline engine's applicability conditions are written against
    these TaxpayerProfile attributes; surfacing them here lets the
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


def _modelo_is_registered(modelo: str) -> bool:
    """Return whether ``modelo`` is a known modelo in the calculation registry.

    Distinguishes a genuinely unknown modelo identifier from a real
    modelo whose registry entry simply has no deadline-window data for
    the requested year. The former is an operator error; the latter is
    a registry-data gap the CLI should degrade gracefully around rather
    than crash on.
    """

    from ...core.resources import resources
    from ...core.resources._errors import ResourceNotFoundError

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
    engine: DeadlineEngine | None = None,
) -> OverviewExplain:
    """Decompose a modelo's applicability against the operator's profile.

    Composes :meth:`DeadlineEngine.applies_to` and
    :meth:`DeadlineEngine.explain` to produce a typed envelope the CLI
    can render as a single answer. The applicability flag is the same
    value the calendar / agenda use when deciding whether to surface
    obligations for this modelo, so explain and the operational views
    cannot diverge.

    When the modelo is a known registry modelo but no deadline windows
    are registered for the requested year, the service degrades
    gracefully: it still reports the (necessarily ``False``)
    applicability flag and substitutes an informational rationale
    rather than raising. A genuinely unknown modelo identifier still
    raises :class:`OverviewExplainError`.

    Raises:
        OverviewExplainError: When the modelo identifier is blank or
            unknown to the registry, or when the deadline engine fails
            for a reason other than a missing deadline-window dataset.
    """

    if not modelo.strip():
        raise OverviewExplainError(tr("application.overview.explain.errors.modelo_blank"))
    resolved_year = year or date.today().year
    deadline_engine = engine or DeadlineEngine()
    try:
        applicable = deadline_engine.applies_to(profile, modelo, year=resolved_year)
    except (ScheduleComputationError, DeadlineValidationError) as exc:
        raise OverviewExplainError(
            f"could not evaluate modelo {modelo!r} for year {resolved_year}: {exc}",
        ) from exc
    try:
        rationale = deadline_engine.explain(profile, modelo, year=resolved_year)
    except ScheduleComputationError as exc:
        # A known modelo with no registered deadline windows for this
        # year is a registry-data gap, not an operator error: degrade
        # to an informational rationale instead of crashing.
        if _modelo_is_registered(modelo):
            rationale = tr(
                "application.overview.explain.no_deadline_windows",
                modelo=modelo,
                year=resolved_year,
            )
        else:
            raise OverviewExplainError(
                f"could not evaluate modelo {modelo!r} for year {resolved_year}: {exc}",
            ) from exc
    except DeadlineValidationError as exc:
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
