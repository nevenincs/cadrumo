"""JSON-contract payloads for the ``aeat app ledger ratios`` subgroup.

Each result is a strict :class:`~aeat.entrypoints.cli._schemas.OutputSchema`
registered through :func:`~aeat.entrypoints.cli._schemas.register_schema` and
emitted inside :class:`~aeat.entrypoints.cli._schemas.SchemaEnvelope` via
:func:`~aeat.entrypoints.cli._common._emit_envelope`. The parent
:mod:`~aeat.entrypoints.cli._ledger_payloads` module re-exports these split
schemas so ledger ratio handlers keep the existing payload import surface.

The application layer remains authoritative for
:class:`~aeat.application.ledger.EligibleCategoryRow`,
:class:`~aeat.application.ledger.RatiosValidationReport`,
:func:`~aeat.application.ledger.set_usage_ratio`, and
:func:`~aeat.application.ledger.unset_usage_ratio`; the domain
:class:`~aeat.domain.usage_ratios.UsageRatioProfile` owns persisted
per-category override validation. This module only pins the CLI transport
shape for list, set, unset, eligible, and validate results.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema


class RatiosRowPayload(OutputSchema):
    """One per-category usage-ratio row."""

    category: str
    ratio: str


class RatiosEligibleRowPayload(OutputSchema):
    """One ``ledger ratios eligible`` row (D2)."""

    category: str
    proportionality_kind: str
    default_ratio: str | None = None
    override_present: bool


class RatiosValidateFindingPayload(OutputSchema):
    """One ``ledger ratios validate`` finding row (D2)."""

    category: str
    kind: str
    detail: str = ""


@register_schema("ledger.ratios.list")
class RatiosListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger ratios list``."""

    bucket_id: str
    rows: list[RatiosRowPayload]
    count: int
    censo_mismatch: str | None = None


@register_schema("ledger.ratios.set")
class RatiosSetResult(OutputSchema):
    """JSON envelope for ``aeat app ledger ratios set``."""

    bucket_id: str
    category: str
    ratio: str


@register_schema("ledger.ratios.unset")
class RatiosUnsetResult(OutputSchema):
    """JSON envelope for ``aeat app ledger ratios unset``."""

    bucket_id: str
    category: str
    ratio: str = ""


@register_schema("ledger.ratios.eligible")
class RatiosEligibleResult(OutputSchema):
    """JSON envelope for ``aeat app ledger ratios eligible``."""

    bucket_id: str
    rows: list[RatiosEligibleRowPayload]
    count: int


@register_schema("ledger.ratios.validate")
class RatiosValidateResult(OutputSchema):
    """JSON envelope for ``aeat app ledger ratios validate``.

    Mirrors ``RatiosValidationReport.model_dump(mode='json')`` produced by
    :func:`~aeat.application.ledger.validate_ratios_for_bucket`.
    """

    bucket_id: str
    profile_present: bool
    eligible_count: int
    overrides_count: int
    missing_overrides: list[str] = []
    findings: list[RatiosValidateFindingPayload] = []
