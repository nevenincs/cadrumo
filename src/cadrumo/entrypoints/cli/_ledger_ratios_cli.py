"""Ledger ratios CLI command surface.

Ratio mutations append :class:`BucketEventHistoryRepository` events in the
active bucket so category overrides remain auditable.
"""

from __future__ import annotations

import typer

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...domain.categories.spending_category import SpendingCategory
from ._common import activate_subcommand_output_language as _activate_subcommand_output_language
from ._common import active_bucket_id_or_refuse as _ratios_bucket_id
from ._common import bad, emit_envelope
from ._decimal_parsing import parse_decimal_amount
from ._ledger_support import ledger_cli_no_recovery


def _ratios_bucket_and_profile() -> tuple[str, str | None]:
    """Return ``(bucket_id, active_profile_id)`` from workflow state."""
    from ...core.bucket_pointer import resolve_active_bucket_id

    return _ratios_bucket_id(), resolve_active_bucket_id()


def _resolved_ratio_year(year: int | None) -> int:
    """Return the filing year whose category profiles govern this invocation.

    Defaults to the calendar year the one clock authority reports rather than
    a pinned literal: the statutory multipliers and default ratios these verbs
    read are year-versioned, so a pinned year would apply one year's law to
    every invocation. An operator replaying an earlier year passes ``--year``.
    """
    from ...core.time.clock import today_madrid

    return today_madrid().year if year is None else year


def ratios_list(
    ctx: typer.Context,
    year: int | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """List every per-category proportional-deduction override stored on the active bucket."""
    _activate_subcommand_output_language(ctx, output_language)
    from ...adapters.persistence.profile.usage_ratios import (
        load_usage_ratios_with_censo_guard,
    )
    from ...application.user_profile.censo_sync import CensoSyncService
    from ...domain.usage_ratios.errors import CensoRatioMismatchError
    from ._ledger_payloads import RatiosListResult, RatiosRowPayload

    bucket_id, profile_id = _ratios_bucket_and_profile()
    raw_afectacion = None
    if profile_id is not None:
        raw_afectacion = CensoSyncService(bucket_id=bucket_id).bound_raw_afectacion_ratio(
            profile_id=profile_id,
        )
    try:
        profile = load_usage_ratios_with_censo_guard(
            bucket_id=bucket_id,
            raw_afectacion_ratio=raw_afectacion,
            year=_resolved_ratio_year(year),
        )
    except CensoRatioMismatchError as exc:
        from ...application.cli_exception_preconditions import CliExceptionPrecondition

        raise ledger_cli_no_recovery(
            exc,
            condition=CliExceptionPrecondition.LEDGER_CENSO_RATIO_CONSISTENT,
            facts={"censo_ratio_consistent": False},
        ) from None
    rows = [RatiosRowPayload(category=category, ratio=str(ratio)) for category, ratio in profile.ratios.items()]
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    lines.extend(f"{row.category.value}\t{row.ratio}" for row in rows)
    emit_envelope(
        ctx,
        command="ledger.ratios.list",
        result=RatiosListResult(
            bucket_id=bucket_id,
            rows=rows,
            count=len(rows),
            censo_mismatch=None,
        ),
        lines=lines,
    )


def ratios_set(
    ctx: typer.Context,
    category: SpendingCategory,
    ratio: str,
    year: int | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Set or replace one per-category usage-ratio override on the active bucket."""
    _activate_subcommand_output_language(ctx, output_language)
    from ...application.ledger.ratios import apply_usage_ratio_override
    from ...application.user_profile.censo_sync import CensoSyncService
    from ._ledger_payloads import RatiosSetResult

    parsed = parse_decimal_amount(ratio, label="ratio")
    bucket_id, profile_id = _ratios_bucket_and_profile()
    raw_afectacion = (
        CensoSyncService(bucket_id=bucket_id).bound_raw_afectacion_ratio(profile_id=profile_id)
        if profile_id is not None
        else None
    )
    apply_usage_ratio_override(
        bucket_id=bucket_id,
        category=category,
        ratio=parsed,
        year=_resolved_ratio_year(year),
        profile_id=profile_id,
        raw_afectacion_ratio=raw_afectacion,
    )
    emit_envelope(
        ctx,
        command="ledger.ratios.set",
        result=RatiosSetResult(bucket_id=bucket_id, category=category, ratio=str(parsed)),
        lines=(f"bucket\t{bucket_id}", f"{category.value}\t{parsed}"),
    )


def ratios_unset(
    ctx: typer.Context,
    category: SpendingCategory,
    output_language: OutputLanguage | None = None,
) -> None:
    """Clear one per-category usage-ratio override from the active bucket."""
    _activate_subcommand_output_language(ctx, output_language)
    from ...application.ledger.ratios import clear_usage_ratio_override
    from ...domain.usage_ratios.errors import UsageRatioValidationError
    from ._ledger_payloads import RatiosUnsetResult

    bucket_id = _ratios_bucket_id()
    try:
        clear_usage_ratio_override(bucket_id=bucket_id, category=category)
    except UsageRatioValidationError as exc:
        raise bad(
            tr(
                "cli.app.ledger.ratios.no_override_error",
                category=category.value,
                bucket_id=bucket_id,
            ),
        ) from exc
    emit_envelope(
        ctx,
        command="ledger.ratios.unset",
        result=RatiosUnsetResult(bucket_id=bucket_id, category=category, ratio=""),
        lines=(f"bucket\t{bucket_id}", f"{category.value}\t<unset>"),
    )


def ratios_eligible(
    ctx: typer.Context,
    year: int | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """List every ``SpendingCategory`` that may carry a per-category proportional-deduction override."""
    _activate_subcommand_output_language(ctx, output_language)
    from ...application.ledger.ratios import list_eligible_ratios_for_bucket
    from ._ledger_payloads import RatiosEligibleResult, RatiosEligibleRowPayload

    bucket_id = _ratios_bucket_id()
    rows = list_eligible_ratios_for_bucket(bucket_id=bucket_id, year=_resolved_ratio_year(year))
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for row in rows:
        default = "" if row.default_ratio is None else str(row.default_ratio)
        override_marker = "X" if row.override_present else "."
        kind_text = row.proportionality_kind.value
        lines.append(
            f"{row.category.value}\t{kind_text}\tdefault={default or '-'}\toverride={override_marker}",
        )
    emit_envelope(
        ctx,
        command="ledger.ratios.eligible",
        result=RatiosEligibleResult(
            bucket_id=bucket_id,
            rows=[
                RatiosEligibleRowPayload(
                    category=row.category,
                    proportionality_kind=row.proportionality_kind,
                    default_ratio=None if row.default_ratio is None else str(row.default_ratio),
                    override_present=row.override_present,
                )
                for row in rows
            ],
            count=len(rows),
        ),
        lines=lines,
    )


def ratios_validate(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """Validate per-category usage-ratio overrides against eligibility and bound rules without mutating state."""
    _activate_subcommand_output_language(ctx, output_language)
    from ...application.ledger.ratios import validate_ratios_for_bucket
    from ._ledger_payloads import RatiosValidateFindingPayload, RatiosValidateResult

    bucket_id = _ratios_bucket_id()
    report = validate_ratios_for_bucket(bucket_id=bucket_id)
    lines = [
        f"bucket\t{bucket_id}",
        f"profile_present\t{report.profile_present}",
        f"eligible\t{report.eligible_count}",
        f"overrides\t{report.overrides_count}",
    ]
    if report.missing_overrides:
        lines.append("missing\t" + ",".join(c.value for c in report.missing_overrides))
    for finding in report.findings:
        detail = f"\t{finding.detail}" if finding.detail else ""
        lines.append(f"finding\t{finding.category.value}\t{finding.kind}{detail}")
    emit_envelope(
        ctx,
        command="ledger.ratios.validate",
        result=RatiosValidateResult(
            bucket_id=report.bucket_id,
            profile_present=report.profile_present,
            eligible_count=report.eligible_count,
            overrides_count=report.overrides_count,
            missing_overrides=list(report.missing_overrides),
            findings=[
                RatiosValidateFindingPayload(
                    category=finding.category,
                    kind=finding.kind,
                    detail=finding.detail,
                )
                for finding in report.findings
            ],
        ),
        lines=lines,
    )


__all__ = ["ratios_eligible", "ratios_list", "ratios_set", "ratios_unset", "ratios_validate"]
