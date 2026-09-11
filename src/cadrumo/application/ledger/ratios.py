"""Operator-facing extensions for the ``aeat app ledger ratios`` verb-group.

The existing usage-ratio CRUD verbs (``list``/``set``/``unset``) live in
the application-layer ledger actions backed by the domain
``usage_ratios`` module. This module adds two read-only verbs that
close the discoverability and pre-calculate readiness gaps:

  ``eligible``  enumerate categories that may carry a user ratio,
                annotated with their statutory default ratio
  ``validate``  inspect the persisted profile against eligibility and
                bound rules; report missing categories per modelo
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.identity.bucket import BucketId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.prose_elision import ElidedProse
from ...core.unit_proportion import UnitProportion, is_unit_proportion
from ...domain.buckets.event import BucketEventType
from ...domain.categories.proportionality import ProportionalityKind, ProportionalityRule, effective_usage_ratio
from ...domain.categories.registry import resolve_category_profiles
from ...domain.categories.spending_category import HOME_OFFICE_FAMILIES, SpendingCategory, family_for
from ...domain.usage_ratios.errors import UsageRatioValidationError
from ...domain.usage_ratios.model import ELIGIBLE_USAGE_RATIO_CATEGORIES, UsageRatioProfile
from ...domain.usage_ratios.service import usage_ratio_bucket_lock
from ..bucket_event_repository import bucket_event_history_repository
from .usage_ratio_repository import load_usage_ratio_profile, save_usage_ratio_profile


class EligibleCategoryRow(BaseModel):
    """One row in the ``ratios eligible`` listing.

    ``default_ratio`` is None for eligible categories whose
    proportionality rule does not ship a statutory default; the
    operator must supply an override before the modelo pre-calculate
    readiness check passes.
    """

    model_config = STRICT_FROZEN_CONFIG

    category: SpendingCategory
    proportionality_kind: ProportionalityKind
    default_ratio: Decimal | None = Field(default=None)
    override_present: bool


#: The ratios-finding ``detail`` annotation: elides rather than refusing.
#:
#: The tightest declared prose cap in the tree, and every builder interpolates
#: a category label and two ratios into it. Empty is the documented default, so
#: the lower bound stays open.
_FindingDetail = Annotated[str, ElidedProse(300, min_length=0)]


class RatiosValidationFinding(BaseModel):
    """One issue raised by ``ratios validate`` for an eligible category."""

    model_config = STRICT_FROZEN_CONFIG

    category: SpendingCategory
    kind: str = Field(min_length=1)
    detail: _FindingDetail = ""


class RatiosValidationReport(BaseModel):
    """Result of ``ratios validate``. Read-only, emits no bucket event."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    profile_present: bool
    eligible_count: NonNegativeInt
    overrides_count: NonNegativeInt
    missing_overrides: tuple[SpendingCategory, ...] = Field(default_factory=tuple)
    findings: tuple[RatiosValidationFinding, ...] = Field(default_factory=tuple)


def eligible_ratio_categories(profile: UsageRatioProfile, *, year: int) -> tuple[EligibleCategoryRow, ...]:
    """Return all eligible categories with their default ratio + override flag.

    The output is sorted by canonical category value so callers can
    diff snapshots without ordering noise. Each row is an :class:`EligibleCategoryRow`.

    Args:
        profile: The operator's persisted per-category overrides.
        year: Filing year whose category profiles supply the statutory
            default ratio. Required rather than defaulted: the default ratio
            is year-versioned regulatory data, and a pinned year would apply
            one year's law to every filing.
    """
    rows: list[EligibleCategoryRow] = []
    year_profiles = resolve_category_profiles(year)
    for category in sorted(ELIGIBLE_USAGE_RATIO_CATEGORIES, key=lambda c: c.value):
        category_profile = year_profiles[category]
        rule: ProportionalityRule = category_profile.proportionality
        rows.append(
            EligibleCategoryRow(
                category=category,
                proportionality_kind=rule.kind,
                default_ratio=rule.default_ratio,
                override_present=category in profile.ratios,
            ),
        )
    return tuple(rows)


def validate_ratios_profile(
    *,
    bucket_id: str,
    profile: UsageRatioProfile,
    require_overrides_for: tuple[SpendingCategory, ...] = (),
) -> RatiosValidationReport:
    """Inspect a profile against eligibility and any required overrides.

    ``require_overrides_for`` is the set of categories the caller needs
    explicitly populated (e.g. a modelo's pre-calculate readiness check).
    Categories absent from :data:`ELIGIBLE_USAGE_RATIO_CATEGORIES` raise a
    ``not_eligible`` finding rather than silently passing.

    Returns a :class:`RatiosValidationReport`.
    """
    findings: list[RatiosValidationFinding] = []
    missing: list[SpendingCategory] = []

    for category in require_overrides_for:
        if category not in ELIGIBLE_USAGE_RATIO_CATEGORIES:
            findings.append(
                RatiosValidationFinding(
                    category=category,
                    kind="not_eligible",
                    detail=(
                        f"category {category.value!r} is not eligible for a user ratio override "
                        "(its proportionality rule does not consume USAGE_RATIO_*)"
                    ),
                ),
            )
            continue
        if category not in profile.ratios:
            missing.append(category)

    # The domain-layer profile already rejects out-of-bounds ratios at
    # construction time; surfacing those here is a defensive guard for
    # malformed on-disk records that bypass validation on read.
    for category, ratio in profile.ratios.items():
        if category not in ELIGIBLE_USAGE_RATIO_CATEGORIES:
            findings.append(
                RatiosValidationFinding(
                    category=category,
                    kind="not_eligible_override",
                    detail=f"persisted override on a non-eligible category {category.value!r}",
                ),
            )
            continue
        if not is_unit_proportion(ratio):
            findings.append(
                RatiosValidationFinding(
                    category=category,
                    kind="out_of_bounds",
                    detail=f"persisted ratio {ratio} for {category.value!r} is outside [0, 1]",
                ),
            )

    return RatiosValidationReport(
        bucket_id=bucket_id,
        profile_present=bool(profile.ratios),
        eligible_count=len(ELIGIBLE_USAGE_RATIO_CATEGORIES),
        overrides_count=len(profile.ratios),
        missing_overrides=tuple(missing),
        findings=tuple(findings),
    )


def list_eligible_ratios_for_bucket(*, bucket_id: str, year: int) -> tuple[EligibleCategoryRow, ...]:
    """Convenience: load the bucket's profile and project the eligibility report.

    Each element is an :class:`EligibleCategoryRow` describing one
    spending category's eligibility and configured ratio.

    Args:
        bucket_id: The bucket whose persisted profile is projected.
        year: Filing year whose category profiles supply the statutory
            default ratio.
    """
    profile = load_usage_ratio_profile(bucket_id=bucket_id)
    return eligible_ratio_categories(profile, year=year)


def validate_ratios_for_bucket(
    *,
    bucket_id: str,
    require_overrides_for: tuple[SpendingCategory, ...] = (),
) -> RatiosValidationReport:
    """Load the bucket's profile, run validation, and return a :class:`RatiosValidationReport`."""
    profile = load_usage_ratio_profile(bucket_id=bucket_id)
    return validate_ratios_profile(
        bucket_id=bucket_id,
        profile=profile,
        require_overrides_for=require_overrides_for,
    )


def set_usage_ratio(*, bucket_id: str, category: SpendingCategory, ratio: Decimal) -> Decimal | None:
    """Set or replace one per-category usage-ratio override on the bucket.

    Loads the bucket's :class:`UsageRatioProfile`, applies the override through
    the domain ``with_ratio`` validator, and persists the result. Returns the
    prior override value for the category (``None`` when there was none) so the
    caller can emit a before/after audit event. Application command boundary for
    the CLI ``ledger ratios set`` verb; the CLI no longer calls the domain
    load/save primitives directly.

    The load-modify-save runs under the per-bucket
    :func:`cadrumo.domain.usage_ratios.usage_ratio_bucket_lock` so two concurrent
    writers cannot read the same snapshot and lose one another's override.
    """
    with usage_ratio_bucket_lock(bucket_id):
        profile = load_usage_ratio_profile(bucket_id=bucket_id)
        prior = profile.ratios.get(category)
        save_usage_ratio_profile(profile.with_ratio(category, ratio), bucket_id=bucket_id)
        return prior


def unset_usage_ratio(*, bucket_id: str, category: SpendingCategory) -> Decimal | None:
    """Clear one per-category usage-ratio override on the bucket.

    Returns the cleared value. Raises :class:`UsageRatioValidationError` when
    the category carries no persisted override (so the caller can surface a
    precise "nothing to clear" message). Application command boundary for the
    CLI ``ledger ratios unset`` verb.

    The load-modify-save runs under the per-bucket
    :func:`cadrumo.domain.usage_ratios.usage_ratio_bucket_lock` so a concurrent
    ``set`` on a sibling category cannot be lost by this clear.
    """
    with usage_ratio_bucket_lock(bucket_id):
        profile = load_usage_ratio_profile(bucket_id=bucket_id)
        prior = profile.ratios.get(category)
        if prior is None:
            raise UsageRatioValidationError(
                f"no persisted usage-ratio override for category {category.value!r} on bucket {bucket_id!r}",
            )
        save_usage_ratio_profile(profile.without_ratio(category), bucket_id=bucket_id)
        return prior


class RatiosCensoOverrideWarning(BaseModel):
    """A non-fatal warning that the operator's per-category override deviates from the censo-derived value.

    The censo is the binding legal source of truth for censo-derived
    ratios. Operators may still override (e.g. to model a planned
    afectación change), but the engine emits a typed warning so downstream
    auditors can review the divergence.
    """

    model_config = STRICT_FROZEN_CONFIG

    category: SpendingCategory
    override_ratio: UnitProportion
    censo_derived_ratio: UnitProportion
    raw_afectacion_ratio: UnitProportion


def censo_business_pct_for(
    category: SpendingCategory,
    raw_afectacion_ratio: Decimal | None,
    *,
    year: int,
) -> Decimal | None:
    """Return the legally-effective business_pct for a category from censo.

    The per-category projection of
    :func:`cadrumo.domain.usage_ratios.derive_home_office_ratios_from_censo`:
    given a single :class:`SpendingCategory` and the operator's bound
    censo ``office_m2 / total_m2``, returns the
    ``raw_afectacion_ratio * statutory_multiplier`` value the classify
    and allocate paths should stamp onto ``Transaction.business_pct``
    when no operator override is present. Returns ``None`` for
    categories outside the HOME_OFFICE families or when no censo has
    been applied yet, signalling to the caller that the operator's
    explicit value (or the registry default) governs instead.
    """
    if raw_afectacion_ratio is None:
        return None
    if family_for(category) not in HOME_OFFICE_FAMILIES:
        return None
    rule = resolve_category_profiles(year)[category].proportionality
    return effective_usage_ratio(rule, raw_afectacion_ratio)


class BusinessSharePctOutcome(StrEnum):
    """Why a row did or did not receive a censo-derived business share.

    Five members because the four ways of NOT deriving one are different
    facts about the taxpayer, and a caller that could only see ``None`` had
    to guess which. Only two of them are anything the operator can act on.
    """

    #: The operator supplied a share; no profile fact is consulted.
    STATED = "stated"
    #: The censo fact and the category's statutory rule produced one.
    DERIVED_FROM_CENSO = "derived_from_censo"
    #: No category, so there is nothing to apportion against.
    NO_CATEGORY = "no_category"
    #: No censo has been applied yet, so the afectación ratio is unknown.
    NO_CENSO_APPLIED = "no_censo_applied"
    #: The category is outside the home-office families and is never
    #: apportioned by censo, whatever the taxpayer declared.
    CATEGORY_NOT_APPORTIONED = "category_not_apportioned"


#: The outcomes that carry a share. Derived once so the model below and any
#: reader agree on which they are.
_OUTCOMES_CARRYING_A_SHARE = frozenset(
    {BusinessSharePctOutcome.STATED, BusinessSharePctOutcome.DERIVED_FROM_CENSO},
)


class BusinessSharePctResolution(BaseModel):
    """One resolution: what decided the share, and the share if there is one."""

    model_config = STRICT_FROZEN_CONFIG

    outcome: BusinessSharePctOutcome
    business_pct: Decimal | None = None

    @model_validator(mode="after")
    def _a_share_exists_exactly_when_the_outcome_produces_one(self) -> Self:
        """Refuse a resolution whose share disagrees with its own outcome.

        A "no share" outcome carrying a number invites a caller to stamp a
        proportion nothing derived; a deriving outcome carrying none leaves
        the caller with a success it cannot use.
        """
        carries = self.outcome in _OUTCOMES_CARRYING_A_SHARE
        if carries != (self.business_pct is not None):
            raise ValueError("business share resolution disagrees with its own outcome")
        return self


def resolve_business_share_pct(
    *,
    operator_supplied: Decimal | None,
    category: SpendingCategory | None,
    censo_afectacion_ratio: Decimal | None,
    year: int,
) -> BusinessSharePctResolution:
    """Decide the business share a row is stamped with, and say why.

    The legal arithmetic is :func:`censo_business_pct_for`; this is the
    precedence around it, which was a chain of early returns at a command
    boundary and is therefore the half a second frontend had to reproduce.

    The order is the rule. An operator statement wins over every profile
    fact, because it is the specific claim and the censo is only ever a
    default. Absence of a category is asked before absence of a censo: a row
    with no category has nothing to apportion whether or not a censo exists,
    and reporting the censo as the obstacle would send the operator to fix
    the wrong thing.

    ``censo_afectacion_ratio`` is passed in rather than read here so this
    stays a decision about facts. WHICH profile is active, and whether one is
    active at all, is a session question the caller already answers.

    Args:
        operator_supplied: The share the operator stated, or ``None``.
        category: The row's spending category, or ``None`` when unset.
        censo_afectacion_ratio: The bound ``office_m2 / total_m2`` from the
            applied censo, or ``None`` when none has been applied.
        year: The filing year whose category profiles supply the statutory
            multiplier. Year-versioned regulatory data, so it comes from the
            row's own booked date rather than a pinned literal.

    Returns:
        The resolution, carrying a share only where one was decided.
    """
    if operator_supplied is not None:
        return BusinessSharePctResolution(
            outcome=BusinessSharePctOutcome.STATED,
            business_pct=operator_supplied,
        )
    if category is None:
        return BusinessSharePctResolution(outcome=BusinessSharePctOutcome.NO_CATEGORY)
    if censo_afectacion_ratio is None:
        return BusinessSharePctResolution(outcome=BusinessSharePctOutcome.NO_CENSO_APPLIED)
    derived = censo_business_pct_for(category, censo_afectacion_ratio, year=year)
    if derived is None:
        return BusinessSharePctResolution(outcome=BusinessSharePctOutcome.CATEGORY_NOT_APPORTIONED)
    return BusinessSharePctResolution(
        outcome=BusinessSharePctOutcome.DERIVED_FROM_CENSO,
        business_pct=derived,
    )


def censo_override_warning(
    *,
    category: SpendingCategory,
    override_ratio: Decimal,
    raw_afectacion_ratio: Decimal,
    year: int,
) -> RatiosCensoOverrideWarning | None:
    """Return a typed warning when an override deviates from the censo.

    The check is silent for non-HOME_OFFICE categories: only the
    suministros and ownership home-office families are legally bound
    to the censo-derived afectación ratio (LIRPF Art. 30.2 rule 5,
    Ley 6/2017 BOE-A-2017-12544). For HOME_OFFICE categories the
    helper computes the legally-effective ratio (raw afectación times
    the rule's ``statutory_multiplier``) and compares it against
    ``override_ratio`` for exact equality. A non-equal pair returns a
    :class:`RatiosCensoOverrideWarning`; equal values (and
    non-home-office categories) return ``None``.

    Args:
        category: The category being overridden via ``ratios set``.
        override_ratio: The operator-supplied override.
        raw_afectacion_ratio: ``office_m2 / total_m2`` from the bound
            censo snapshot.
        year: Registry year whose proportionality rule drives the
            derivation.

    Returns:
        A :class:`RatiosCensoOverrideWarning` if a warning should be
        emitted, otherwise ``None``.
    """
    if family_for(category) not in HOME_OFFICE_FAMILIES:
        return None
    rule = resolve_category_profiles(year)[category].proportionality
    derived = effective_usage_ratio(rule, raw_afectacion_ratio)
    if derived == override_ratio:
        return None
    return RatiosCensoOverrideWarning(
        category=category,
        override_ratio=override_ratio,
        censo_derived_ratio=derived,
        raw_afectacion_ratio=raw_afectacion_ratio,
    )


__all__ = [
    "BusinessSharePctOutcome",
    "BusinessSharePctResolution",
    "EligibleCategoryRow",
    "RatiosCensoOverrideWarning",
    "RatiosValidationFinding",
    "RatiosValidationReport",
    "censo_business_pct_for",
    "censo_override_warning",
    "eligible_ratio_categories",
    "list_eligible_ratios_for_bucket",
    "resolve_business_share_pct",
    "set_usage_ratio",
    "unset_usage_ratio",
    "validate_ratios_for_bucket",
    "validate_ratios_profile",
]


class UsageRatioMutationOutcomeV1(BaseModel):
    """What one ratio mutation changed, and what it raised against the Censo."""

    model_config = STRICT_FROZEN_CONFIG

    category: SpendingCategory
    prior_ratio: Decimal | None
    new_ratio: Decimal | None
    censo_override_warning: RatiosCensoOverrideWarning | None = None


def _emit_ratio_event(
    *,
    bucket_id: str,
    event_type: BucketEventType,
    object_id: str,
    payload: dict[str, str],
) -> None:
    """Append one ratios audit event to the bucket-event history.

    The event's type, object class, actor and payload shape are the audit
    record's contract, not a display choice, so they are decided here rather
    than by whichever surface performed the mutation.
    """
    from ...core.time.clock import now
    from ...domain.buckets.event import BucketEventObjectType
    from ...domain.buckets.event_repository import emit_bucket_event

    emit_bucket_event(
        repository=bucket_event_history_repository(bucket_id=bucket_id),
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=now(),
        actor="operator",
        object_type=BucketEventObjectType.PROFILE,
        object_id=object_id,
        payload=payload,
        payload_version=1,
    )


def _ratio_change_payload(*, category: SpendingCategory, prior: Decimal | None, new: Decimal | None) -> dict[str, str]:
    """Render a before/after pair, with an absent value as the empty string."""
    return {
        "category": category.value,
        "prior": "" if prior is None else str(prior),
        "new": "" if new is None else str(new),
    }


def apply_usage_ratio_override(
    *,
    bucket_id: str,
    category: SpendingCategory,
    ratio: Decimal,
    year: int,
    profile_id: str | None = None,
    raw_afectacion_ratio: Decimal | None = None,
) -> UsageRatioMutationOutcomeV1:
    """Persist one override, record it, and check it against the Censo.

    Three things that had to happen together and were composed by the caller:
    the write, its audit event, and the comparison against the afectación ratio
    the operator declared to the AEAT. A surface that performed the write and
    forgot the comparison would let an override silently contradict the Censo.

    NOT ATOMIC, and deliberately reported rather than papered over: the ratio
    store and the event history are separate secure objects with no shared
    commit, so a failure after the write leaves a persisted override with no
    audit event. Making it atomic needs the co-commit treatment the invoice
    link writer uses; this function does not invent one.

    Args:
        bucket_id: The owning profile bucket.
        category: The spending category being overridden.
        ratio: The override to store.
        year: The filing year the Censo comparison is made for.
        profile_id: The active profile, when one is bound.
        raw_afectacion_ratio: The Censo-declared afectación ratio, when known.

    Returns:
        The prior and new values, plus any Censo override warning raised.
    """
    prior = set_usage_ratio(bucket_id=bucket_id, category=category, ratio=ratio)
    _emit_ratio_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_RATIOS_SET,
        object_id=category.value,
        payload=_ratio_change_payload(category=category, prior=prior, new=ratio),
    )
    warning = (
        censo_override_warning(
            category=category,
            override_ratio=ratio,
            raw_afectacion_ratio=raw_afectacion_ratio,
            year=year,
        )
        if profile_id is not None and raw_afectacion_ratio is not None
        else None
    )
    if warning is not None:
        _emit_ratio_event(
            bucket_id=bucket_id,
            event_type=BucketEventType.LEDGER_RATIOS_CENSO_OVERRIDE_WARNING,
            object_id=warning.category.value,
            payload={
                "category": warning.category.value,
                "override_ratio": str(warning.override_ratio),
                "censo_derived_ratio": str(warning.censo_derived_ratio),
                "raw_afectacion_ratio": str(warning.raw_afectacion_ratio),
            },
        )
    return UsageRatioMutationOutcomeV1(
        category=category,
        prior_ratio=prior,
        new_ratio=ratio,
        censo_override_warning=warning,
    )


def clear_usage_ratio_override(*, bucket_id: str, category: SpendingCategory) -> UsageRatioMutationOutcomeV1:
    """Clear one override and record the clearance.

    Carries the same non-atomicity as :func:`apply_usage_ratio_override`.

    Args:
        bucket_id: The owning profile bucket.
        category: The category whose override is cleared.

    Returns:
        The cleared value as ``prior_ratio``, with ``new_ratio`` absent.

    Raises:
        UsageRatioValidationError: When the category carries no override.
    """
    prior = unset_usage_ratio(bucket_id=bucket_id, category=category)
    _emit_ratio_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_RATIOS_UNSET,
        object_id=category.value,
        payload=_ratio_change_payload(category=category, prior=prior, new=None),
    )
    return UsageRatioMutationOutcomeV1(category=category, prior_ratio=prior, new_ratio=None)
