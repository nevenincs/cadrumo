"""JSON-contract payloads for the ``aeat app ledger ratios`` subgroup.

Each result is a strict :class:`OutputSchema` registered through
CommandSpec schema authority and emitted inside :class:`SchemaEnvelope` via
:func:`_emit_envelope`. The parent :mod:`_ledger_payloads` module re-exports
these split schemas so ledger ratio handlers keep the existing payload import
surface.

The application layer remains authoritative for
:class:`EligibleCategoryRow`, :class:`RatiosValidationReport`,
:func:`set_usage_ratio`, and :func:`unset_usage_ratio`; the domain
:class:`UsageRatioProfile` owns persisted per-category override validation. This
module only pins the CLI transport shape for list, set, unset, eligible, and
validate results.
"""

from __future__ import annotations

from pydantic import Field, field_validator

from ...core.decimal import try_parse_canonical_decimal
from ...core.identity import BucketId
from ...core.json_contract import OutputSchema
from ...domain.categories import ProportionalityKind, SpendingCategory
from ...domain.usage_ratios import UsageRatioValidationError, validate_usage_ratio_bound


def _validated_ratio_text(value: str, *, field: str) -> str:
    """Return ``value`` when it is a decimal inside the canonical ``[0, 1]`` band.

    The ratio crosses the wire as text so the exact operator-entered scale
    survives JSON, but the band itself is not re-stated here: the check
    routes through
    :func:`~domain.usage_ratios.validate_usage_ratio_bound`, the one
    authority the persisted :class:`UsageRatioProfile` also uses.
    """
    parsed = try_parse_canonical_decimal(value)
    if parsed is None:
        raise ValueError(f"{field} must be a decimal string (got {value!r})")
    try:
        validate_usage_ratio_bound(parsed, label=field)
    except UsageRatioValidationError as exc:
        raise ValueError(str(exc)) from exc
    return value


class RatiosRowPayload(OutputSchema):
    """One per-category usage-ratio row.

    ``category`` reuses the canonical
    :class:`~domain.categories.SpendingCategory` closed set and ``ratio``
    is bound to ``[0, 1]`` through the domain authority, so an unknown
    category or an out-of-band ratio is refused at the transport edge
    instead of crossing it.
    """

    category: SpendingCategory
    ratio: str

    @field_validator("ratio")
    @classmethod
    def _check_ratio(cls, value: str) -> str:
        return _validated_ratio_text(value, field="ratio")


class RatiosEligibleRowPayload(OutputSchema):
    """One ``ledger ratios eligible`` row (D2).

    ``proportionality_kind`` reuses the canonical
    :class:`~domain.categories.ProportionalityKind` enum rather than
    restating the rule vocabulary as free text.
    """

    category: SpendingCategory
    proportionality_kind: ProportionalityKind
    default_ratio: str | None = None
    override_present: bool

    @field_validator("default_ratio")
    @classmethod
    def _check_default_ratio(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return value
        return _validated_ratio_text(value, field="default_ratio")


class RatiosValidateFindingPayload(OutputSchema):
    """One ``ledger ratios validate`` finding row (D2).

    A finding exists to name a problem, so ``kind`` and ``detail`` must
    both carry text; an empty finding is indistinguishable from no
    finding at all.
    """

    category: SpendingCategory
    kind: str = Field(min_length=1)
    detail: str = Field(min_length=1)


class RatiosListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger ratios list``."""

    bucket_id: BucketId
    rows: list[RatiosRowPayload]
    count: int
    censo_mismatch: str | None = None


class RatiosSetResult(OutputSchema):
    """JSON envelope for ``aeat app ledger ratios set``."""

    bucket_id: BucketId
    category: SpendingCategory
    ratio: str

    @field_validator("ratio")
    @classmethod
    def _check_ratio(cls, value: str) -> str:
        return _validated_ratio_text(value, field="ratio")


class RatiosUnsetResult(OutputSchema):
    """JSON envelope for ``aeat app ledger ratios unset``."""

    bucket_id: BucketId
    category: SpendingCategory
    #: Empty after a successful unset — the override no longer exists.
    ratio: str = ""


class RatiosEligibleResult(OutputSchema):
    """JSON envelope for ``aeat app ledger ratios eligible``."""

    bucket_id: BucketId
    rows: list[RatiosEligibleRowPayload]
    count: int


class RatiosValidateResult(OutputSchema):
    """JSON envelope for ``aeat app ledger ratios validate``.

    Mirrors :meth:`RatiosValidationReport.model_dump` output produced by
    :func:`validate_ratios_for_bucket`.
    """

    bucket_id: BucketId
    profile_present: bool
    eligible_count: int
    overrides_count: int
    missing_overrides: list[SpendingCategory] = []
    findings: list[RatiosValidateFindingPayload] = []
