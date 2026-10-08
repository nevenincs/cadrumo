"""Ledger ratios CLI command surface.

Ratio mutations append :class:`BucketEventHistoryRepository` events in the
active bucket so category overrides remain auditable.
"""

from __future__ import annotations

import typer

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ._decimal_parsing import parse_decimal_amount
from ._ledger_support import ledger_cli_no_recovery
from .common import activate_subcommand_output_language as _activate_subcommand_output_language
from .common import bad, emit_envelope
from .runtime_ledger_ratios import list_eligible_ratios, list_ratios, set_ratio, unset_ratio, validate_ratios


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
    from ...domain.usage_ratios.errors import CensoRatioMismatchError
    from ._ledger_ratios_payloads import RatiosListResult, RatiosRowPayload

    completion = list_ratios(ctx, year=_resolved_ratio_year(year))
    projection = completion.projection
    if projection.outcome == "censo_mismatch":
        from ...application.cli_exception_preconditions import CliExceptionPrecondition

        raise ledger_cli_no_recovery(
            CensoRatioMismatchError("persisted HOME_OFFICE ratio overrides conflict with the bound censo"),
            condition=CliExceptionPrecondition.LEDGER_CENSO_RATIO_CONSISTENT,
            facts={"censo_ratio_consistent": False},
        ) from None
    bucket_id = str(projection.profile_id)
    rows = [RatiosRowPayload(category=row.category, ratio=row.ratio) for row in projection.rows]
    lines = [f"bucket\t{bucket_id}", f"count\t{projection.count}"]
    lines.extend(f"{row.category}\t{row.ratio}" for row in rows)
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
    category: str,
    ratio: str,
    year: int | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Set or replace one per-category usage-ratio override on the active bucket."""
    _activate_subcommand_output_language(ctx, output_language)
    from ...domain.usage_ratios.model import validate_usage_ratio_bound
    from ._ledger_ratios_payloads import RatiosSetResult

    parsed = parse_decimal_amount(ratio, label="ratio")
    validate_usage_ratio_bound(parsed, label="ratio")
    completion = set_ratio(
        ctx,
        category=category,
        ratio=str(parsed),
        year=_resolved_ratio_year(year),
    )
    projection = completion.projection
    bucket_id = str(projection.profile_id)
    emit_envelope(
        ctx,
        command="ledger.ratios.set",
        result=RatiosSetResult(bucket_id=bucket_id, category=projection.category, ratio=projection.ratio),
        lines=(f"bucket\t{bucket_id}", f"{projection.category}\t{projection.ratio}"),
    )


def ratios_unset(
    ctx: typer.Context,
    category: str,
    output_language: OutputLanguage | None = None,
) -> None:
    """Clear one per-category usage-ratio override from the active bucket."""
    _activate_subcommand_output_language(ctx, output_language)
    from ._ledger_ratios_payloads import RatiosUnsetResult

    completion = unset_ratio(ctx, category=category)
    projection = completion.projection
    bucket_id = str(projection.profile_id)
    if projection.outcome == "no_override":
        raise bad(
            tr(
                "cli.app.ledger.ratios.no_override_error",
                category=projection.category,
                bucket_id=bucket_id,
            ),
        )
    emit_envelope(
        ctx,
        command="ledger.ratios.unset",
        result=RatiosUnsetResult(bucket_id=bucket_id, category=projection.category, ratio=""),
        lines=(f"bucket\t{bucket_id}", f"{projection.category}\t<unset>"),
    )


def ratios_eligible(
    ctx: typer.Context,
    year: int | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """List every ``SpendingCategory`` that may carry a per-category proportional-deduction override."""
    _activate_subcommand_output_language(ctx, output_language)
    from ._ledger_ratios_payloads import RatiosEligibleResult, RatiosEligibleRowPayload

    completion = list_eligible_ratios(ctx, year=_resolved_ratio_year(year))
    projection = completion.projection
    bucket_id = str(projection.profile_id)
    lines = [f"bucket\t{bucket_id}", f"count\t{projection.count}"]
    for row in projection.rows:
        default = "" if row.default_ratio is None else row.default_ratio
        override_marker = "X" if row.override_present else "."
        kind_text = row.proportionality_kind
        lines.append(
            f"{row.category}\t{kind_text}\tdefault={default or '-'}\toverride={override_marker}",
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
                    default_ratio=row.default_ratio,
                    override_present=row.override_present,
                )
                for row in projection.rows
            ],
            count=projection.count,
        ),
        lines=lines,
    )


def ratios_validate(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """Validate per-category usage-ratio overrides against eligibility and bound rules without mutating state."""
    _activate_subcommand_output_language(ctx, output_language)
    from ._ledger_ratios_payloads import RatiosValidateFindingPayload, RatiosValidateResult

    completion = validate_ratios(ctx)
    projection = completion.projection
    bucket_id = str(projection.profile_id)
    lines = [
        f"bucket\t{bucket_id}",
        f"profile_present\t{projection.profile_present}",
        f"eligible\t{projection.eligible_count}",
        f"overrides\t{projection.overrides_count}",
    ]
    if projection.missing_overrides:
        lines.append("missing\t" + ",".join(projection.missing_overrides))
    for finding in projection.findings:
        detail = f"\t{finding.detail}" if finding.detail else ""
        lines.append(f"finding\t{finding.category}\t{finding.kind}{detail}")
    emit_envelope(
        ctx,
        command="ledger.ratios.validate",
        result=RatiosValidateResult(
            bucket_id=bucket_id,
            profile_present=projection.profile_present,
            eligible_count=projection.eligible_count,
            overrides_count=projection.overrides_count,
            missing_overrides=list(projection.missing_overrides),
            findings=[
                RatiosValidateFindingPayload(
                    category=finding.category,
                    kind=finding.kind,
                    detail=finding.detail,
                )
                for finding in projection.findings
            ],
        ),
        lines=lines,
    )


__all__ = ["ratios_eligible", "ratios_list", "ratios_set", "ratios_unset", "ratios_validate"]
