"""Relative temporal, applicability, and authorship members for binding declarations.

Three closed unions live here, each replacing a set of loosely coupled optional
fields whose legal combinations were previously enforced by mutual-exclusion
validators rather than by the type.

:data:`BindingTemporalSelector` is the provider-agnostic lift of the
previous-filing period grammar: the six field combinations that grammar actually
admitted become six named members, so a combination it refused is now
unspellable rather than merely rejected. Every member is *relative* to the
target filing context. No member carries an absolute year or a revision
identifier, which is the point: a declaration states timeless intent, and the
concrete source coordinate is derived at resolve time from the target context.

:data:`BindingApplicability` states which revision contexts a binding applies
to, including the explicit non-calculation disposition that keeps an export-only
binding from reading as an unreferenced declaration.

:data:`BindingAuthorship` distinguishes a hand-authored row from a generated one
and, for the generated case, requires the generator identity and run digest that
make the row reproducible.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, field_validator, model_validator

from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.frozen_mapping import FROZEN_MAPPING
from ....core.period import RegistrySelectorPeriodCode
from ....core.type_guards import is_object_list
from .errors import RegistryValidationError
from .ids import RevisionId
from .period_offset_math import apply_period_offset, same_ejercicio_prior_quarter_anchors
from .schema_base import RegistryModel

__all__ = [
    "AllRevisionContexts",
    "AuthoredBinding",
    "BindingApplicability",
    "BindingApplicabilityKind",
    "BindingAuthorship",
    "BindingAuthorshipKind",
    "BindingTemporalKind",
    "BindingTemporalSelector",
    "FiledCurrentPeriod",
    "FilingYearOffset",
    "FilingYearOffsetByTargetPeriod",
    "GeneratedBinding",
    "NonCalculation",
    "NonCalculationReason",
    "PriorQuarterExpandingSpan",
    "SameFilingYearPeriods",
    "SameTargetContext",
    "TargetPeriodOffset",
    "TargetPeriods",
    "binding_applies_to_period",
    "temporal_max_year_delta",
    "temporal_period_anchors",
]


@pydantic_validation_boundary
def _coerce_period_sequence(value: object) -> object:
    """Accept the JSON array form of a period tuple.

    Registry models validate under ``strict=True``, which refuses a list for a
    tuple-typed field. A binding declaration is serialised into the published
    authority artifact and read back from it, so the JSON array a period tuple
    dumps to must validate back to the same member rather than to a refusal.
    """
    if is_object_list(value):
        return tuple(value)
    return value


_SourcePeriods = Annotated[
    tuple[RegistrySelectorPeriodCode, ...],
    BeforeValidator(_coerce_period_sequence),
    Field(min_length=1),
]
_GeneratorToken = Annotated[str, Field(min_length=1, max_length=200)]


def _reject_duplicate_periods(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(set(value)) != len(value):
        raise RegistryValidationError(
            "binding temporal source periods must be unique",
            context={"source_periods": ",".join(value)},
        )
    return value


class BindingTemporalKind(StrEnum):
    """Discriminator tokens for the closed temporal-selector union."""

    SAME_TARGET_CONTEXT = "same_target_context"
    SAME_FILING_YEAR_PERIODS = "same_filing_year_periods"
    FILING_YEAR_OFFSET = "filing_year_offset"
    FILING_YEAR_OFFSET_BY_TARGET_PERIOD = "filing_year_offset_by_target_period"
    TARGET_PERIOD_OFFSET = "target_period_offset"
    PRIOR_QUARTER_EXPANDING_SPAN = "prior_quarter_expanding_span"
    FILED_CURRENT_PERIOD = "filed_current_period"


class SameTargetContext(RegistryModel):
    """The source shares the target's filing year and period exactly.

    The default for providers with no cross-period coordinate at all: ledger
    aggregations, profile fields, operator input, and design constants.
    """

    kind: Literal[BindingTemporalKind.SAME_TARGET_CONTEXT] = BindingTemporalKind.SAME_TARGET_CONTEXT


class SameFilingYearPeriods(RegistryModel):
    """Named periods of the target's own filing year."""

    kind: Literal[BindingTemporalKind.SAME_FILING_YEAR_PERIODS] = BindingTemporalKind.SAME_FILING_YEAR_PERIODS
    source_periods: _SourcePeriods

    @field_validator("source_periods")
    @classmethod
    @pydantic_validation_boundary
    def _unique_periods(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _reject_duplicate_periods(value)


class FilingYearOffset(RegistryModel):
    """Named periods of a filing year a fixed, non-zero number of years away.

    ``max_years`` bounds how far the resolver may reach when the offset is
    applied repeatedly (the bounded carry-forward case); it is an absolute
    bound, so it is never negative.
    """

    kind: Literal[BindingTemporalKind.FILING_YEAR_OFFSET] = BindingTemporalKind.FILING_YEAR_OFFSET
    years: int
    source_periods: _SourcePeriods
    max_years: int | None = None

    @field_validator("source_periods")
    @classmethod
    @pydantic_validation_boundary
    def _unique_periods(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _reject_duplicate_periods(value)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_offset(self) -> FilingYearOffset:
        if self.years == 0:
            raise RegistryValidationError(
                "filing_year_offset years must be non-zero; declare same_filing_year_periods instead",
            )
        if self.max_years is not None and self.max_years < 0:
            raise RegistryValidationError(
                "filing_year_offset max_years must be non-negative",
                context={"max_years": self.max_years},
            )
        if self.max_years is not None and self.max_years < abs(self.years):
            # The bound is applied to the offset's own reach, so a bound below
            # one step filters out every anchor the member could produce. The
            # declaration would then resolve to nothing while still LOOKING like
            # a live cross-period coordinate, which is exactly the silent
            # absence a filing-bound member must not be able to declare.
            raise RegistryValidationError(
                "filing_year_offset max_years must admit at least one step of years",
                context={"max_years": self.max_years, "years": self.years},
            )
        return self


class FilingYearOffsetByTargetPeriod(RegistryModel):
    """Named periods of a filing year whose distance depends on the target period.

    The uniform :class:`FilingYearOffset` states one distance for every target
    period. Some instalment regimes cannot: modelo 202's modalidad 40.2 bases
    each pago fraccionado on the last período impositivo whose declaration
    deadline has already elapsed, and that is two filing years back for the
    April instalment and one year back for the October and December ones,
    because the source modelo 200's July deadline falls between them.

    The distance is therefore declared per target period rather than once.
    ``offsets`` is total over the target periods this member covers: a target
    period the mapping does not name produces NO anchor at all, which is a
    scope-out, not a fallback onto a neighbouring year. An offset chain that
    reached for an adjacent year whenever the declared one was absent would
    silently substitute a filing whose deadline had not elapsed, which is
    precisely the condition the law keys on.
    """

    kind: Literal[BindingTemporalKind.FILING_YEAR_OFFSET_BY_TARGET_PERIOD] = (
        BindingTemporalKind.FILING_YEAR_OFFSET_BY_TARGET_PERIOD
    )
    offsets: Annotated[Mapping[RegistrySelectorPeriodCode, int], FROZEN_MAPPING]
    source_periods: _SourcePeriods

    @field_validator("source_periods")
    @classmethod
    @pydantic_validation_boundary
    def _unique_periods(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _reject_duplicate_periods(value)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_offsets(self) -> FilingYearOffsetByTargetPeriod:
        if not self.offsets:
            raise RegistryValidationError(
                "filing_year_offset_by_target_period must declare at least one target-period offset",
            )
        zero_periods = sorted(period for period, years in self.offsets.items() if years == 0)
        if zero_periods:
            raise RegistryValidationError(
                "filing_year_offset_by_target_period offsets must be non-zero; declare "
                "same_filing_year_periods for a same-year source window",
                context={"target_periods": ",".join(zero_periods)},
            )
        return self


class TargetPeriodOffset(RegistryModel):
    """The period a fixed, non-zero number of periods from the target period.

    ``within_filing_year`` confines the offset to the target's own filing year:
    the modelo 130/131 carry-forward pattern offsets one period back but must
    not reach across the year boundary, so a 1T target resolves to no source
    anchor at all. That emptiness is a scope-out, not a missing observation, and
    it is declared here rather than inferred, because an offset that silently
    crossed into the prior year would carry a foreign year's quota forward.
    """

    kind: Literal[BindingTemporalKind.TARGET_PERIOD_OFFSET] = BindingTemporalKind.TARGET_PERIOD_OFFSET
    periods: int
    within_filing_year: bool = False

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_offset(self) -> TargetPeriodOffset:
        if self.periods == 0:
            raise RegistryValidationError(
                "target_period_offset periods must be non-zero; declare same_target_context instead",
            )
        return self


class PriorQuarterExpandingSpan(RegistryModel):
    """Every quarter of the target's filing year preceding the target quarter.

    The span expands with the target quarter rather than naming a fixed period
    set, which is why it carries no period fields and is mutually exclusive with
    every axis that does.
    """

    kind: Literal[BindingTemporalKind.PRIOR_QUARTER_EXPANDING_SPAN] = BindingTemporalKind.PRIOR_QUARTER_EXPANDING_SPAN


class FiledCurrentPeriod(RegistryModel):
    """One literal already-filed period of the target's own filing year."""

    kind: Literal[BindingTemporalKind.FILED_CURRENT_PERIOD] = BindingTemporalKind.FILED_CURRENT_PERIOD
    source_period: RegistrySelectorPeriodCode


BindingTemporalSelector = Annotated[
    SameTargetContext
    | SameFilingYearPeriods
    | FilingYearOffset
    | FilingYearOffsetByTargetPeriod
    | TargetPeriodOffset
    | PriorQuarterExpandingSpan
    | FiledCurrentPeriod,
    Field(discriminator="kind"),
]


def temporal_max_year_delta(temporal: BindingTemporalSelector) -> int | None:
    """Return the absolute bound on anchor year deltas the member declares.

    ``None`` means unbounded. :class:`FilingYearOffset` carries the bound
    explicitly; a period offset confined to the filing year is the bound ``0``.
    :class:`FilingYearOffsetByTargetPeriod` is deliberately unbounded: its
    offsets ARE the declaration, and filtering them through a second bound
    would silently drop the farther of two authored distances.
    """
    if isinstance(temporal, FilingYearOffset):
        return temporal.max_years
    if isinstance(temporal, TargetPeriodOffset) and temporal.within_filing_year:
        return 0
    return None


def temporal_period_anchors(
    temporal: BindingTemporalSelector,
    *,
    target_period: str,
) -> tuple[tuple[int, str], ...]:
    """Return the ``(year_delta, source_period)`` anchors a member names for a target.

    The single derivation every provider carrying a temporal member resolves
    through, so a member added to the union reaches the previous-filing and
    relation-prefill folds at once instead of being interpreted twice. The
    result is already bounded by :func:`temporal_max_year_delta`; an empty
    tuple means the member names no source window for this target period,
    which is a scope-out the caller must preserve rather than fill.

    Args:
        temporal: The closed temporal member the provider declares.
        target_period: The period token being calculated.

    Returns:
        Anchors in declaration order, each a year delta relative to the target
        filing year paired with the source period token.
    """
    anchors = _unbounded_temporal_anchors(temporal, target_period=target_period)
    bound = temporal_max_year_delta(temporal)
    if bound is None:
        return anchors
    return tuple(anchor for anchor in anchors if abs(anchor[0]) <= bound)


def _unbounded_temporal_anchors(
    temporal: BindingTemporalSelector,
    *,
    target_period: str,
) -> tuple[tuple[int, str], ...]:
    """Return the anchor set a member produces before the year bound applies."""
    if isinstance(temporal, PriorQuarterExpandingSpan):
        try:
            return same_ejercicio_prior_quarter_anchors(target_period)
        except RegistryValidationError as exc:
            raise RegistryValidationError(
                "prior_quarter_expanding_span cannot interpret the target period; "
                "only quarterly codes 1T..4T or pago-fraccionado codes 1P..3P are supported",
                context={"target_period": target_period},
            ) from exc
    if isinstance(temporal, TargetPeriodOffset):
        try:
            return (apply_period_offset(temporal.periods, target_period=target_period),)
        except RegistryValidationError as exc:
            raise RegistryValidationError(
                "target_period_offset cannot interpret the target period",
                context={"target_period": target_period, "periods": temporal.periods},
            ) from exc
    if isinstance(temporal, SameTargetContext):
        return ((0, target_period),)
    if isinstance(temporal, FilingYearOffsetByTargetPeriod):
        years = temporal.offsets.get(target_period)
        if years is None:
            return ()
        return tuple((years, period) for period in temporal.source_periods)
    if isinstance(temporal, FilingYearOffset):
        return tuple((temporal.years, period) for period in temporal.source_periods)
    if isinstance(temporal, SameFilingYearPeriods):
        return tuple((0, period) for period in temporal.source_periods)
    return ((0, temporal.source_period),)


class BindingApplicabilityKind(StrEnum):
    """Discriminator tokens for the closed applicability union."""

    ALL_REVISION_CONTEXTS = "all_revision_contexts"
    TARGET_PERIODS = "target_periods"
    NON_CALCULATION = "non_calculation"


class AllRevisionContexts(RegistryModel):
    """The binding applies in every filing context its revision covers."""

    kind: Literal[BindingApplicabilityKind.ALL_REVISION_CONTEXTS] = BindingApplicabilityKind.ALL_REVISION_CONTEXTS


class TargetPeriods(RegistryModel):
    """The binding applies only when the target period is one of these."""

    kind: Literal[BindingApplicabilityKind.TARGET_PERIODS] = BindingApplicabilityKind.TARGET_PERIODS
    periods: _SourcePeriods

    @field_validator("periods")
    @classmethod
    @pydantic_validation_boundary
    def _unique_periods(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _reject_duplicate_periods(value)


NonCalculationReason = Literal[
    "informational_total",
    "profile_input",
    "rate_band_reserved",
    "application_calculation_handoff",
]
"""The classes of declaration that legitimately have no typed calculation consumer.

Each member is a class the authored corpus actually contains, not a speculative
slot:

``informational_total``
    A total the official design reports for information only. Modelo 303's
    criterio-de-caja entregas and adquisiciones totals are this: the printed
    casillas left the form, and the total is still declared and handed off.
``profile_input``
    A taxpayer-profile fact declared as a binding for a downstream consumer
    rather than for a casilla of its own revision.
``rate_band_reserved``
    A rate-band declaration kept for a band the revision's form does not print,
    so the band stays declarable without claiming a box.
``application_calculation_handoff``
    A value an application-layer calculation reads directly, rather than a
    formula or casilla of the revision.
"""


class NonCalculation(RegistryModel):
    """The binding is not consumed by calculation, and that is declared intent.

    An export-only binding has no typed calculation consumer, which is
    indistinguishable from an orphaned declaration unless the author says so.
    This member is that statement, so the compiler can refuse every *other*
    unreferenced binding instead of tolerating all of them.

    The statement is not a bare flag: :attr:`reason` classes WHY the row has no
    calculation consumer, and :attr:`consumed_by` names WHAT does read it. A
    disposition that named neither would be indistinguishable from an author
    silencing an orphan, which is the failure this member exists to prevent --
    hence the refusal of a blank ``consumed_by``. :attr:`box_retired_in` records
    the revision from which the printed casilla is absent, so a retired box is
    traceable to the edition that retired it rather than inferred from the
    casilla's absence.
    """

    kind: Literal[BindingApplicabilityKind.NON_CALCULATION] = BindingApplicabilityKind.NON_CALCULATION
    reason: NonCalculationReason
    box_retired_in: RevisionId | None = None
    consumed_by: Annotated[str, Field(min_length=1, max_length=300)]

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_disposition(self) -> NonCalculation:
        if not self.consumed_by.strip():
            raise RegistryValidationError(
                "non_calculation applicability must name a non-blank consumed_by",
                context={"reason": self.reason},
            )
        if self.box_retired_in is not None and not self.box_retired_in.strip():
            raise RegistryValidationError(
                "non_calculation box_retired_in must be a non-blank revision id when declared",
                context={"reason": self.reason},
            )
        return self


BindingApplicability = Annotated[
    AllRevisionContexts | TargetPeriods | NonCalculation,
    Field(discriminator="kind"),
]


def binding_applies_to_period(applicability: BindingApplicability, period: str | None) -> bool:
    """Return whether a binding's applicability admits one target period.

    A ``non_calculation`` binding admits none: it is declared as having no
    typed calculation consumer, so admitting it into a calculation scan would
    reintroduce exactly the ambiguity the member exists to remove. ``period``
    of ``None`` means "every context this revision covers", which only the
    period-scoped member narrows.
    """
    if isinstance(applicability, NonCalculation):
        return False
    if period is None or isinstance(applicability, AllRevisionContexts):
        return True
    return period in applicability.periods


class BindingAuthorshipKind(StrEnum):
    """Discriminator tokens for the closed authorship union."""

    AUTHORED = "authored"
    GENERATED = "generated"


class AuthoredBinding(RegistryModel):
    """The row was written by hand and is owned by its author."""

    kind: Literal[BindingAuthorshipKind.AUTHORED] = BindingAuthorshipKind.AUTHORED


class GeneratedBinding(RegistryModel):
    """The row was emitted by a named generator run and is reproducible from it."""

    kind: Literal[BindingAuthorshipKind.GENERATED] = BindingAuthorshipKind.GENERATED
    generator_id: _GeneratorToken
    run_digest: _GeneratorToken

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_identity(self) -> GeneratedBinding:
        if not self.generator_id.strip():
            raise RegistryValidationError("generated binding generator_id must be non-blank")
        if not self.run_digest.strip():
            raise RegistryValidationError(
                "generated binding run_digest must be non-blank",
                context={"generator_id": self.generator_id},
            )
        return self


BindingAuthorship = Annotated[
    AuthoredBinding | GeneratedBinding,
    Field(discriminator="kind"),
]
