"""Operator-facing extensions for the ``aeat app ledger ratios`` verb-group.

The existing usage-ratio CRUD verbs (``list``/``set``/``unset``) live in
the application-layer ledger actions backed by the domain
``usage_ratios`` module. This module adds two read-only verbs that
close the discoverability and pre-calculate readiness gaps:

  ``eligible``  enumerate categories that may carry a user ratio, each with
                its registry label, notes and proportionality kind
  ``validate``  inspect the persisted profile against eligibility and
                bound rules; report missing categories per modelo
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import DEFAULT_OUTPUT_LANGUAGE, OutputLanguage
from ...core.i18n.render import tr
from ...core.identity.bucket import BucketId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.prose_elision import ElidedProse
from ...core.text_bounds import NonEmptyStr
from ...core.time.clock import now
from ...core.unit_proportion import UnitProportion, is_unit_proportion
from ...domain.buckets.event import BucketEvent, BucketEventType
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.categories.proportionality import ProportionalityKind, ProportionalityRule, effective_usage_ratio
from ...domain.categories.registry import resolve_category_profiles
from ...domain.categories.spending_category import HOME_OFFICE_FAMILIES, SpendingCategory, family_for
from ...domain.usage_ratios.errors import UsageRatioValidationError
from ...domain.usage_ratios.model import ELIGIBLE_USAGE_RATIO_CATEGORIES, UsageRatioProfile
from ...domain.usage_ratios.service import usage_ratio_bucket_lock
from ..bucket_event_repository import bucket_event_history_repository
from .persistence_ports import LedgerPersistenceConflictError
from .usage_ratio_repository import (
    load_usage_ratio_profile,
    save_usage_ratio_profile_with_writes,
)


class EligibleCategoryRow(BaseModel):
    """One row in the ``ratios eligible`` listing.

    No category ships a statutory ratio: the operator must supply an
    override, or the censo must declare the area, before the modelo
    pre-calculate readiness check passes.

    ``label`` and ``notes`` are the registry's wording for the category, said
    in the requested language: every frontend shows these rather than keeping
    a vocabulary of its own.
    """

    model_config = STRICT_FROZEN_CONFIG

    category: SpendingCategory
    proportionality_kind: ProportionalityKind
    label: NonEmptyStr
    notes: NonEmptyStr
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


def eligible_ratio_categories(
    profile: UsageRatioProfile,
    *,
    year: int,
    operation: PinnedAuthorityOperation,
    language: OutputLanguage = DEFAULT_OUTPUT_LANGUAGE,
) -> tuple[EligibleCategoryRow, ...]:
    """Return all eligible categories with their registry wording, kind + override flag.

    The output is sorted by canonical category value so callers can
    diff snapshots without ordering noise. Each row is an :class:`EligibleCategoryRow`.

    Args:
        profile: The operator's persisted per-category overrides.
        year: Filing year whose category profiles supply the proportionality
            kind. Required rather than defaulted: the rule is year-versioned
            regulatory data, and a pinned year would apply one year's law to
            every filing.
        operation: The caller-owned authority generation used for every
            category and governed-fact query in this projection.
        language: The language the registry's label and notes keys are said in.
    """
    rows: list[EligibleCategoryRow] = []
    year_profiles = resolve_category_profiles(year, operation=operation)
    with validating_governed_facts(operation):
        eligible_categories = tuple(sorted(ELIGIBLE_USAGE_RATIO_CATEGORIES, key=lambda c: c.value))
    for category in eligible_categories:
        category_profile = year_profiles[category]
        rule: ProportionalityRule = category_profile.proportionality
        rows.append(
            EligibleCategoryRow(
                category=category,
                proportionality_kind=rule.kind,
                label=tr(str(category_profile.display_label), locale=language.value),
                notes=tr(str(rule.notes), locale=language.value),
                override_present=category in profile.ratios,
            ),
        )
    return tuple(rows)


def validate_ratios_profile(
    *,
    bucket_id: str,
    profile: UsageRatioProfile,
    operation: PinnedAuthorityOperation,
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
    with validating_governed_facts(operation):
        eligible_categories = frozenset(ELIGIBLE_USAGE_RATIO_CATEGORIES)

    for category in require_overrides_for:
        if category not in eligible_categories:
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
        if category not in eligible_categories:
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
        eligible_count=len(eligible_categories),
        overrides_count=len(profile.ratios),
        missing_overrides=tuple(missing),
        findings=tuple(findings),
    )


def list_eligible_ratios_for_bucket(
    *,
    bucket_id: str,
    year: int,
    operation: PinnedAuthorityOperation,
    language: OutputLanguage = DEFAULT_OUTPUT_LANGUAGE,
) -> tuple[EligibleCategoryRow, ...]:
    """Convenience: load the bucket's profile and project the eligibility report.

    Each element is an :class:`EligibleCategoryRow` describing one
    spending category's eligibility and configured ratio.

    Args:
        bucket_id: The bucket whose persisted profile is projected.
        year: Filing year whose category profiles supply the proportionality
            kind.
        operation: The caller-owned authority generation used to decode the
            stored profile.
        language: The language the registry's label and notes keys are said in.
    """
    profile = load_usage_ratio_profile(bucket_id=bucket_id, operation=operation)
    return eligible_ratio_categories(profile, year=year, operation=operation, language=language)


def validate_ratios_for_bucket(
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    require_overrides_for: tuple[SpendingCategory, ...] = (),
) -> RatiosValidationReport:
    """Load the bucket's profile, run validation, and return a :class:`RatiosValidationReport`."""
    profile = load_usage_ratio_profile(bucket_id=bucket_id, operation=operation)
    return validate_ratios_profile(
        bucket_id=bucket_id,
        profile=profile,
        operation=operation,
        require_overrides_for=require_overrides_for,
    )


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
    operation: PinnedAuthorityOperation,
) -> Decimal | None:
    """Return the censo-derived degree of use a row's ``business_pct`` is stamped with.

    ``Transaction.business_pct`` is the degree of use of the expense in the
    activity, which is what IVA deducts (LIVA art. 95, read as the TEAC
    unified criterion of 19-07-2023 reads it). For the home-office families
    the censo default is the raw afectación ``office_m2 / total_m2`` with no
    statutory factor. The IRPF factor of LIRPF art. 30.2, regla 5.ª b) is
    applied only by the Renta category rule over the usage-ratio store
    (:func:`cadrumo.domain.usage_ratios.service.derive_home_office_ratios_from_censo`),
    so it never reaches the IVA cuota.

    Returns ``None`` for categories outside the HOME_OFFICE families or when
    no censo has been applied yet, signalling to the caller that the
    operator's explicit value governs instead.
    """
    if raw_afectacion_ratio is None:
        return None
    if family_for(category, effective_date=date(year, 12, 31), authority=operation) not in HOME_OFFICE_FAMILIES:
        return None
    return raw_afectacion_ratio


class BusinessSharePctOutcome(StrEnum):
    """Why a row did or did not receive a censo-derived business share.

    Five members because the four ways of NOT deriving one are different
    facts about the taxpayer, and a caller that could only see ``None`` had
    to guess which. Only two of them are anything the operator can act on.
    """

    #: The operator supplied a share; no profile fact is consulted.
    STATED = "stated"
    #: The censo afectación supplied the degree of use.
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
    @pydantic_validation_boundary
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
    operation: PinnedAuthorityOperation,
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
        year: The filing year whose category families decide which
            categories the censo apportions. Year-versioned regulatory data,
            so it comes from the row's own booked date rather than a pinned
            literal.
        operation: The caller-owned authority generation used for category
            family resolution.

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
    derived = censo_business_pct_for(category, censo_afectacion_ratio, year=year, operation=operation)
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
    operation: PinnedAuthorityOperation,
) -> RatiosCensoOverrideWarning | None:
    """Return a typed warning when a usage-ratio override deviates from the censo.

    The override is a value of the Renta usage-ratio store, which holds the
    IRPF-effective ratio, so it is compared against the IRPF derivation: raw
    afectación times the rule's ``statutory_multiplier`` (LIRPF art. 30.2,
    regla 5.ª b), for the suministros family; the raw afectación for the
    ownership family). It says nothing about IVA, which deducts a row's degree
    of use (see :func:`censo_business_pct_for`). The check is silent for
    non-HOME_OFFICE categories. A non-equal pair returns a
    :class:`RatiosCensoOverrideWarning`; equal values (and non-home-office
    categories) return ``None``.

    Args:
        category: The category being overridden via ``ratios set``.
        override_ratio: The operator-supplied override.
        raw_afectacion_ratio: ``office_m2 / total_m2`` from the bound
            censo snapshot.
        year: Registry year whose proportionality rule drives the
            derivation.
        operation: The caller-owned authority generation used for category
            family and proportionality resolution.

    Returns:
        A :class:`RatiosCensoOverrideWarning` if a warning should be
        emitted, otherwise ``None``.
    """
    if family_for(category, authority=operation) not in HOME_OFFICE_FAMILIES:
        return None
    rule = resolve_category_profiles(year, operation=operation)[category].proportionality
    if not rule.kind.is_usage_ratio:
        return None
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


def _ratio_event(
    *,
    bucket_id: str,
    event_type: BucketEventType,
    object_id: str,
    payload: dict[str, str],
    actor: str,
    occurred_at: datetime,
) -> BucketEvent:
    """Derive one ratios audit event without persisting it.

    The event's type, object class, actor and payload shape are the audit
    record's contract, not a display choice, so they are decided here rather
    than by whichever surface performed the mutation.
    """
    from ...domain.buckets.event import BucketEventObjectType
    from ...domain.buckets.event_repository import build_bucket_event

    return build_bucket_event(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.PROFILE,
        object_id=object_id,
        payload=payload,
        payload_version=1,
    )


_RATIO_COMMIT_ATTEMPTS = 4


def _commit_ratio_change(*, bucket_id: str, profile: UsageRatioProfile, events: tuple[BucketEvent, ...]) -> None:
    """Persist ``profile`` and its audit ``events`` in one secure-object batch.

    Both rows live in the bucket's one encrypted database, so the batch commits
    them together or not at all. The event write carries the revision the
    history was read at; when another writer appended in between, the batch is
    refused whole and re-composed against the newly current history. Re-running
    is safe: the profile is a value computed before this call and the events are
    content-addressed, so a retry collapses onto the same entries.
    """
    from ...domain.buckets.event_repository import bucket_event_history_write

    repository = bucket_event_history_repository(bucket_id=bucket_id)
    last_conflict: LedgerPersistenceConflictError | None = None
    for _attempt in range(_RATIO_COMMIT_ATTEMPTS):
        try:
            save_usage_ratio_profile_with_writes(
                profile,
                (bucket_event_history_write(repository, events),),
                bucket_id=bucket_id,
            )
        except LedgerPersistenceConflictError as conflict:
            last_conflict = conflict
            continue
        return
    if last_conflict is not None:
        raise last_conflict
    raise AssertionError("ratio co-commit exhausted without a conflict")


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
    actor: str = "operator",
    operation: PinnedAuthorityOperation,
) -> UsageRatioMutationOutcomeV1:
    """Persist one override, record it, and check it against the Censo.

    Three things that had to happen together and were composed by the caller:
    the write, its audit event, and the comparison against the afectación ratio
    the operator declared to the AEAT. A surface that performed the write and
    forgot the comparison would let an override silently contradict the Censo.

    The profile row and the audit events commit in one secure-object batch
    (see :func:`_commit_ratio_change`), so a failure leaves neither an override
    without its event nor an event without its override. The Censo comparison is
    computed before the batch, so its warning event joins it.

    Args:
        bucket_id: The owning profile bucket.
        category: The spending category being overridden.
        ratio: The override to store.
        year: The filing year the Censo comparison is made for.
        profile_id: The active profile, when one is bound.
        raw_afectacion_ratio: The Censo-declared afectación ratio, when known.
        actor: The label recorded on the audit events.
        operation: The caller-owned authority generation used to decode the
            stored profile.

    Returns:
        The prior and new values, plus any Censo override warning raised.
    """
    occurred_at = now()
    warning = (
        censo_override_warning(
            category=category,
            override_ratio=ratio,
            raw_afectacion_ratio=raw_afectacion_ratio,
            year=year,
            operation=operation,
        )
        if profile_id is not None and raw_afectacion_ratio is not None
        else None
    )
    with usage_ratio_bucket_lock(bucket_id):
        profile = load_usage_ratio_profile(bucket_id=bucket_id, operation=operation)
        prior = profile.ratios.get(category)
        with validating_governed_facts(operation):
            updated = profile.with_ratio(category, ratio)
        events = [
            _ratio_event(
                bucket_id=bucket_id,
                event_type=BucketEventType.LEDGER_RATIOS_SET,
                object_id=category.value,
                payload=_ratio_change_payload(category=category, prior=prior, new=ratio),
                actor=actor,
                occurred_at=occurred_at,
            )
        ]
        if warning is not None:
            events.append(
                _ratio_event(
                    bucket_id=bucket_id,
                    event_type=BucketEventType.LEDGER_RATIOS_CENSO_OVERRIDE_WARNING,
                    object_id=warning.category.value,
                    payload={
                        "category": warning.category.value,
                        "override_ratio": str(warning.override_ratio),
                        "censo_derived_ratio": str(warning.censo_derived_ratio),
                        "raw_afectacion_ratio": str(warning.raw_afectacion_ratio),
                    },
                    actor=actor,
                    occurred_at=occurred_at,
                )
            )
        _commit_ratio_change(bucket_id=bucket_id, profile=updated, events=tuple(events))
    return UsageRatioMutationOutcomeV1(
        category=category,
        prior_ratio=prior,
        new_ratio=ratio,
        censo_override_warning=warning,
    )


def clear_usage_ratio_override(
    *, bucket_id: str, category: SpendingCategory, actor: str = "operator", operation: PinnedAuthorityOperation
) -> UsageRatioMutationOutcomeV1:
    """Clear one override and record the clearance.

    Commits the clearance and its event together, as :func:`apply_usage_ratio_override` does.

    Args:
        bucket_id: The owning profile bucket.
        category: The category whose override is cleared.
        actor: The label recorded on the audit event.
        operation: The caller-owned authority generation used to decode the
            stored profile.

    Returns:
        The cleared value as ``prior_ratio``, with ``new_ratio`` absent.

    Raises:
        UsageRatioValidationError: When the category carries no override.
    """
    occurred_at = now()
    with usage_ratio_bucket_lock(bucket_id):
        profile = load_usage_ratio_profile(bucket_id=bucket_id, operation=operation)
        prior = profile.ratios.get(category)
        if prior is None:
            raise UsageRatioValidationError(
                f"no persisted usage-ratio override for category {category.value!r} on bucket {bucket_id!r}",
            )
        with validating_governed_facts(operation):
            updated = profile.without_ratio(category)
        event = _ratio_event(
            bucket_id=bucket_id,
            event_type=BucketEventType.LEDGER_RATIOS_UNSET,
            object_id=category.value,
            payload=_ratio_change_payload(category=category, prior=prior, new=None),
            actor=actor,
            occurred_at=occurred_at,
        )
        _commit_ratio_change(bucket_id=bucket_id, profile=updated, events=(event,))
    return UsageRatioMutationOutcomeV1(category=category, prior_ratio=prior, new_ratio=None)
