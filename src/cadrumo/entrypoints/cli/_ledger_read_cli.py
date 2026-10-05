"""Read, discovery, and reporting commands for ``aeat app ledger``.

Read commands load transactions through :class:`TransactionCatalogueRepository`
and read :class:`BucketEventHistoryRepository` events for history and
review-derived filters.

List and view commands delegate row projection to
:func:`~cadrumo.entrypoints.cli._ledger_list.project_ledger_list` and emit typed
payloads such as :class:`~cadrumo.entrypoints.cli._ledger_payloads.LedgerViewResult`
and :class:`~cadrumo.entrypoints.cli._ledger_payloads.LedgerTrackResult`.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from ...application.export.tabular import ExportSerializationFormat
from ...application.operator_actions.models import ActionReference
from ...core.decimal.coercion import coerce_decimal_strict
from ...core.i18n.render import tr
from ...core.json_contract import (
    Notice,
    NoticeSeverity,
    ResolvedActionArgument,
    strict_round_trip,
)
from ...core.ledger_sort import LedgerSortField, LedgerSortOrder
from ...core.operator_action_enums import ActionArgumentSource, ActionArgumentStatus
from ._decimal_parsing import optional_decimal_text
from .common import (
    active_profile_label,
    bad,
    emit_envelope,
    resolve_notice_action,
)
from .period_parsing import _canonical_period, _optional_canonical_period
from .state_projection_support import authority_operation

if TYPE_CHECKING:
    from ...application.ledger.llm_diagnostics import (
        LlmConfidenceProviderMetrics,
        LlmDiagnosticsReport,
        LlmUsageCostProviderMetrics,
    )
    from ...application.ledger.preflight import LedgerPreflightIssue
    from ...application.ledger.readiness_query import LedgerReadinessIssueV1
    from ...application.ledger.track_operation import LedgerTrackProjection
    from ...application.ledger.view_operation import LedgerViewProjection
    from ...domain.invoices.service import LinkInconsistency
    from ._ledger_rule_payloads import LedgerLlmDiagnosticsResult


def ledger_llm_diagnostics(
    ctx: typer.Context, since: str | None = None, until: str | None = None, low_confidence_below: float = 0.5
) -> None:
    """Report existing LLM usage, cost, and classification-confidence metrics."""
    from ...core.unit_proportion import is_unit_proportion
    from .runtime_ledger_llm_diagnostics import read_ledger_llm_diagnostics_for_cli

    since_date = _parse_iso_date(since, "--since")
    until_date = _parse_iso_date(until, "--until")
    threshold = coerce_decimal_strict(low_confidence_below)
    if not is_unit_proportion(threshold):
        raise bad(tr("cli.ledger.llm_diagnostics.threshold_range"))
    report = read_ledger_llm_diagnostics_for_cli(
        ctx,
        since=since_date,
        until=until_date,
        low_confidence_threshold=threshold,
    )
    result = _llm_diagnostics_result(report, since=since_date, until=until_date)
    lines, notices = _llm_diagnostics_lines_and_notices(report)
    emit_envelope(ctx, command="ledger.llm_diagnostics", result=result, lines=lines, notices=notices)


def _llm_diagnostics_result(
    report: LlmDiagnosticsReport,
    *,
    since: date | None,
    until: date | None,
) -> LedgerLlmDiagnosticsResult:
    from ._ledger_rule_payloads import LedgerLlmDiagnosticsResult

    return LedgerLlmDiagnosticsResult.model_validate(
        {
            "since": since.isoformat() if since is not None else None,
            "until": until.isoformat() if until is not None else None,
            "low_confidence_threshold": format(report.low_confidence_threshold, "f"),
            "usage_providers": [_llm_usage_provider_payload(row) for row in report.usage_providers],
            "total_calls": report.total_calls,
            "total_cache_hits": report.total_cache_hits,
            "total_input_tokens": report.total_input_tokens,
            "total_output_tokens": report.total_output_tokens,
            "total_cost_estimate_usd": (
                None if report.total_cost_estimate_usd is None else format(report.total_cost_estimate_usd, "f")
            ),
            "total_unpriced_calls": report.total_unpriced_calls,
            "confidence_providers": [_llm_confidence_provider_payload(row) for row in report.confidence_providers],
            "total_classified": report.total_classified,
            "total_low_confidence": report.total_low_confidence,
            "has_data": report.has_data,
        },
    )


def _llm_usage_provider_payload(row: LlmUsageCostProviderMetrics) -> dict[str, object]:
    return {
        "provider": row.provider,
        "calls": row.calls,
        "cache_hits": row.cache_hits,
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "total_tokens": row.total_tokens,
        "cost_estimate_usd": None if row.cost_estimate_usd is None else format(row.cost_estimate_usd, "f"),
        "unpriced_calls": row.unpriced_calls,
    }


def _llm_confidence_provider_payload(row: LlmConfidenceProviderMetrics) -> dict[str, object]:
    return {
        "provider": row.provider,
        "classified_count": row.classified_count,
        "low_confidence_count": row.low_confidence_count,
        "high_confidence_count": row.high_confidence_count,
        "medium_confidence_count": row.medium_confidence_count,
        "min_confidence": optional_decimal_text(row.min_confidence),
        "max_confidence": optional_decimal_text(row.max_confidence),
        "mean_confidence": optional_decimal_text(row.mean_confidence),
    }


def _llm_diagnostics_lines_and_notices(report: LlmDiagnosticsReport) -> tuple[list[str], list[Notice]]:
    lines = [
        f"{row.provider}\tcalls={row.calls}\tcache_hits={row.cache_hits}"
        f"\ttokens={row.total_tokens}\tcost_usd="
        f"{'unpriced' if row.cost_estimate_usd is None else format(row.cost_estimate_usd, 'f')}"
        for row in report.usage_providers
    ]
    lines.extend(
        f"{row.provider}\tclassified={row.classified_count}"
        f"\tlow_confidence={row.low_confidence_count}\tmean={optional_decimal_text(row.mean_confidence) or '-'}"
        for row in report.confidence_providers
    )
    if report.has_data:
        return lines, []
    notice = Notice(
        severity=NoticeSeverity.INFO,
        code="ledger.llm_diagnostics.no_data",
        message=tr("cli.ledger.llm_diagnostics.no_data_message"),
        context={},
    )
    return [*lines, notice.message], [notice]


def _parse_iso_date(value: str | None, option: str) -> date | None:
    if value is None:
        return None
    from ._date_parsing import _parse_iso_date as _parse_required_iso_date

    return _parse_required_iso_date(
        value,
        label=option,
        translation_key="cli.ledger.llm_diagnostics.bad_date",
    )


def _irpf_purpose_label(purpose: str) -> str:
    if purpose == "activity_income_withholding":
        return tr("cli.ledger.categories.irpf_purpose_activity_income_withholding")
    if purpose == "rent_expense_withholding":
        return tr("cli.ledger.categories.irpf_purpose_rent_expense_withholding")
    if purpose == "employment_income":
        return tr("cli.ledger.categories.irpf_purpose_employment_income")
    return purpose


def _spending_category_projection() -> tuple[list[dict[str, object]], list[str], list[str]]:
    from ...domain.categories.spending_category import SpendingCategoryFamily, categories_for_family
    from ...domain.categories.spending_category_catalogue import spending_category_tokens

    families: list[dict[str, object]] = []
    lines: list[str] = [
        tr("cli.ledger.categories.header"),
        f"{tr('cli.ledger.categories.id_column')}\t{tr('cli.ledger.categories.family_column')}",
    ]
    first_category_id: str | None = None
    for family in SpendingCategoryFamily:
        members = categories_for_family(family)
        if not members:
            continue
        category_ids = tuple(member.value for member in members)
        families.append({"family": family.value, "category_ids": list(category_ids)})
        for category_id in category_ids:
            if first_category_id is None:
                first_category_id = category_id
            lines.append(f"{category_id}\t{family.value}")
    if first_category_id is not None:
        lines.append(tr("cli.ledger.categories.usage_example", example=first_category_id))
    lines.append(tr("cli.ledger.categories.income_note"))
    return families, [category.value for category in spending_category_tokens()], lines


def _irpf_category_projection() -> tuple[list[dict[str, object]], list[str]]:
    from ...domain.transactions.irpf_categories import ledger_irpf_category_catalogue

    irpf_categories: list[dict[str, object]] = [
        {
            "id": category.id,
            "purpose": category.purpose,
            "directions": [direction.value for direction in category.directions],
            "net_paid_invoice": category.net_paid,
            "related_category_ids": list(category.related_ids),
        }
        for category in ledger_irpf_category_catalogue()
    ]
    lines = [
        "",
        tr("cli.ledger.categories.irpf_header"),
        f"{tr('cli.ledger.categories.irpf_id_column')}\t{tr('cli.ledger.categories.irpf_use_column')}",
    ]
    for category in irpf_categories:
        lines.append(f"{category['id']}\t{_irpf_purpose_label(str(category['purpose']))}")
    lines.append(
        tr(
            "cli.ledger.categories.irpf_usage_example",
            rent_category="arrendamiento_local",
            professional_category="asesoria_fiscal",
            activity_category="actividad_economica",
        )
    )
    return irpf_categories, lines


def _ledger_categories_payload(
    families: list[dict[str, object]],
    category_ids: list[str],
    irpf_categories: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "families": families,
        "category_ids": category_ids,
        "irpf_categories": irpf_categories,
        "irpf_category_ids": [category["id"] for category in irpf_categories],
        "net_paid_withholding_irpf_category_ids": [
            category["id"] for category in irpf_categories if category["net_paid_invoice"]
        ],
        "income_requires_category": False,
    }


def ledger_categories(ctx: typer.Context) -> None:
    """List the recognised `--category-id` spending-category catalogue."""
    # The category catalogue is registry authority, read under the command's lease.
    authority_operation(ctx)
    families, category_ids, spending_lines = _spending_category_projection()
    irpf_categories, irpf_lines = _irpf_category_projection()
    lines = [*spending_lines, *irpf_lines]
    from ._ledger_payloads import LedgerCategoriesResult

    emit_envelope(
        ctx,
        command="ledger.categories",
        result=LedgerCategoriesResult.model_validate(
            _ledger_categories_payload(families, category_ids, irpf_categories),
        ),
        lines=lines,
    )


def _link_inconsistency_notices(rows: tuple[LinkInconsistency, ...]) -> list[Notice]:
    """Return the warning notice for one-sided invoice links, or nothing.

    Takes the typed :class:`~cadrumo.domain.invoices.service.LinkInconsistency` rows
    rather than a serialised mapping, so the closed ``direction`` axis and the
    identifiers stay typed up to the envelope, mirroring how the readiness
    issues are carried alongside them.

    The rows themselves are primary result data on the check payload; this is
    the incidental diagnostic that tells the operator the association is
    untrustworthy and names the verb that repairs it. Re-running ``link`` for
    the reported pair rewrites both sides in one commit.
    """
    if not rows:
        return []
    context = {"link_inconsistency_count": str(len(rows))}
    action = None
    if len(rows) == 1:
        row = rows[0]
        action = resolve_notice_action(
            action=ActionReference(action_id="operator.ledger.link"),
            argument_bindings=(
                ResolvedActionArgument(
                    argument_name="transaction_id",
                    status=ActionArgumentStatus.RESOLVED,
                    value=row.transaction_id,
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="transaction_id",
                ),
                ResolvedActionArgument(
                    argument_name="invoice_id",
                    status=ActionArgumentStatus.RESOLVED,
                    value=row.invoice_id,
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="invoice_id",
                ),
            ),
        )
    return [
        Notice(
            severity=NoticeSeverity.WARNING,
            code="ledger.check.link_inconsistency",
            message=tr(
                "cli.ledger.check.link_inconsistency_notice",
                link_count=len(rows),
            ),
            action=action,
            context=context,
        ),
    ]


def ledger_check(
    ctx: typer.Context, bucket_id_option: str | None = None, period: str | None = None, year: int | None = None
) -> None:
    """Surface ledger anomalies and broken invoice links without mutating state."""
    from ._ledger_payloads import LedgerCheckResult, LedgerLinkInconsistencyPayload
    from .runtime_ledger_check import read_ledger_check_for_cli

    check = read_ledger_check_for_cli(
        ctx,
        period=_optional_canonical_period(period, year=year),
        bucket_id_option=bucket_id_option,
    ).to_check()
    link_rows = [
        LedgerLinkInconsistencyPayload(
            invoice_id=row.invoice_id, transaction_id=row.transaction_id, direction=row.direction
        )
        for row in check.link_inconsistencies
    ]
    lines = [
        f"bucket	{check.bucket_id}",
        f"periods	{','.join(check.periods)}",
        f"checked	{check.checked_transaction_count}",
        f"issues	{len(check.issues)}",
        f"link_inconsistencies	{len(link_rows)}",
        f"ready	{str(check.ready).lower()}",
        *_ledger_check_issue_lines_from_items(check.issues),
        *(
            f"link_inconsistency	{row.invoice_id}	{row.transaction_id}	{row.direction.value}"
            for row in check.link_inconsistencies
        ),
    ]
    emit_envelope(
        ctx,
        command="ledger.check",
        result=LedgerCheckResult.model_validate(
            {
                "bucket_id": check.bucket_id,
                "periods": list(check.periods),
                "checked_transaction_count": check.checked_transaction_count,
                "issues": [issue.model_dump(mode="json") for issue in check.issues],
                "link_inconsistencies": link_rows,
                "ready": check.ready,
            }
        ),
        lines=lines,
        notices=_link_inconsistency_notices(check.link_inconsistencies),
    )


def _ledger_check_issue_lines_from_items(issues: Sequence[LedgerPreflightIssue]) -> list[str]:
    return [f"issue\t{issue.transaction_id}\t{issue.reason.value}\t{issue.detail}" for issue in issues]


def ledger_preflight(ctx: typer.Context, period: str, year: int) -> None:
    """Surface modelo-readiness gaps for the active bucket without mutating ledger state."""
    from .runtime_ledger_preflight import read_ledger_preflight_for_cli

    canonical = _canonical_period(period, year=year)
    report = read_ledger_preflight_for_cli(ctx, period=canonical).to_report()
    payload = report.model_dump(mode="json")
    lines = [
        f"bucket\t{report.bucket_id}",
        f"period\t{canonical}",
        f"checked\t{report.checked_transaction_count}",
        f"issues\t{len(report.issues)}",
        f"ready\t{str(report.ready).lower()}",
    ]
    notices: list[Notice] = []
    if report.checked_transaction_count == 0 and (not report.issues):
        message = tr("cli.ledger.preflight.empty_ledger_advisory")
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.preflight.empty_period",
                message=message,
                context={"period": canonical.registry_token, "year": str(canonical.filing_year)},
            )
        )
        lines.append(f"advisory\tempty_ledger\t{message}")
    for issue in report.issues:
        lines.append(f"issue\t{issue.transaction_id}\t{issue.reason.value}\t{issue.detail}")
    from ._ledger_payloads import LedgerPreflightResult

    emit_envelope(
        ctx,
        command="ledger.preflight",
        result=LedgerPreflightResult.model_validate(payload),
        lines=lines,
        notices=notices,
    )


def ledger_history(ctx: typer.Context, transaction_id: str, include_split_siblings: bool = False) -> None:
    """Emit the chronological event chain for one ledger transaction id."""
    from .runtime_ledger_history import read_ledger_history_for_cli

    history = read_ledger_history_for_cli(
        ctx, transaction_id=transaction_id, include_split_siblings=include_split_siblings
    ).to_history()
    lines = [
        f"{tr('cli.ledger.labels.bucket')}	{history.bucket_id}",
        f"{tr('cli.ledger.labels.id')}	{history.transaction_id}",
        f"{tr('cli.ledger.labels.event_count')}	{history.event_count}",
    ]
    lines.extend(
        f"{event.occurred_at.isoformat()}	{event.event_type.value}	{event.event_id}" for event in history.events
    )
    from ._ledger_payloads import LedgerHistoryResult

    emit_envelope(
        ctx,
        command="ledger.history",
        result=LedgerHistoryResult.model_validate(
            {
                "bucket_id": history.bucket_id,
                "transaction_id": history.transaction_id,
                "event_count": history.event_count,
                "events": [event.model_dump(mode="json") for event in history.events],
            }
        ),
        lines=lines,
    )


def ledger_export(
    ctx: typer.Context,
    output: Path,
    export_kind: ExportSerializationFormat = ExportSerializationFormat.CSV,
    include_inactive: bool = False,
    period: str | None = None,
    year: int | None = None,
    actor: str | None = None,
) -> None:
    """Export canonical exact-profile ledger rows through the authenticated worker."""
    from .runtime_ledger_export_link import export_ledger_for_cli

    projection = export_ledger_for_cli(
        ctx,
        output=output,
        export_format=export_kind,
        include_inactive=include_inactive,
        period=_optional_canonical_period(period, year=year),
        actor=actor,
    )
    from ._ledger_payloads import LedgerExportPayload

    result = LedgerExportPayload.model_validate(
        {
            **projection.model_dump(mode="json", exclude={"profile_id", "output_path"}),
            "output_path": str(output),
        }
    )
    emit_envelope(
        ctx,
        command="ledger.export",
        result=result,
        lines=[
            f"{tr('cli.ledger.labels.bucket')}\t{result.bucket_id}",
            f"{tr('cli.ledger.labels.export_id')}\t{result.export_id}",
            f"{tr('cli.ledger.labels.rows')}\t{result.row_count}",
            f"{tr('cli.ledger.labels.sha256')}\t{result.sha256}",
            f"{tr('cli.ledger.labels.output')}\t{output}",
        ],
    )


def ledger_list(
    ctx: typer.Context,
    filters: tuple[str, ...] = (),
    period: str | None = None,
    year: int | None = None,
    limit: int | None = None,
    offset: int = 0,
    group: str | None = None,
    by_group: bool = False,
    sort_by: LedgerSortField | None = None,
    sort_order: LedgerSortOrder = LedgerSortOrder.ASC,
    hide_llm_rejected: bool = False,
    account: str | None = None,
) -> None:
    """List bucket-scoped ledger rows through :func:`~cadrumo.entrypoints.cli._ledger_list.project_ledger_list`."""
    from ...application.review.errors import FilterParseError
    from ...application.review.filter import LedgerReviewFilterSpec
    from ._ledger_list import project_ledger_list
    from ._ledger_support import ledger_cli_no_recovery
    from .runtime_ledger_list import read_ledger_list_for_cli

    resolved_filters = list(filters)
    if period is not None:
        resolved_filters.append(f"period={period}")
    if year is not None:
        resolved_filters.append(f"year={year}")
    if account is not None:
        resolved_filters.append(f"account={account}")
    try:
        spec = LedgerReviewFilterSpec.from_strings(resolved_filters)
    except FilterParseError as exc:
        from ...application.cli_exception_preconditions import CliExceptionPrecondition

        raise ledger_cli_no_recovery(
            exc,
            condition=CliExceptionPrecondition.LEDGER_FILTER_VALID,
            facts={"ledger_filter_valid": False, "reason": exc.reason},
        ) from None
    snapshot = read_ledger_list_for_cli(
        ctx,
        spec=spec,
        group=group,
        by_group=by_group,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
        exclude_llm_rejected=hide_llm_rejected,
    )
    projection = project_ledger_list(snapshot)
    from ._ledger_payloads import LedgerListResult

    emit_envelope(
        ctx,
        command="ledger.list",
        result=LedgerListResult.model_validate(
            {
                "bucket_id": projection.bucket_id,
                "rows": projection.rows,
                "total": projection.total,
                "shown": projection.shown,
                "offset": projection.offset,
                "limit": projection.limit,
                "truncated": projection.truncated,
            }
        ),
        lines=projection.lines,
    )


def ledger_view(ctx: typer.Context, transaction_id: str) -> None:
    """Read one bucket-scoped ledger transaction.

    Emits a :class:`~cadrumo.entrypoints.cli._ledger_payloads.LedgerViewResult`.
    """
    from .runtime_ledger_view import read_ledger_view_for_cli

    projection = read_ledger_view_for_cli(ctx, transaction_id=transaction_id)
    transaction_payload = projection.transaction
    review_status = projection.review_status

    def _field(value: object) -> str:
        return "-" if value is None or value == "" else str(value)

    lines = [
        f"{tr('cli.ledger.labels.id')}\t{transaction_payload.transaction_id}",
        f"{tr('cli.ledger.labels.date')}\t{transaction_payload.date}",
        f"{tr('cli.ledger.labels.value_date')}\t{_field(transaction_payload.value_date)}",
        f"{tr('cli.ledger.labels.amount')}\t{transaction_payload.amount}",
        f"{tr('cli.ledger.labels.currency')}\t{_field(transaction_payload.currency)}",
        f"{tr('cli.ledger.labels.direction')}\t{_field(transaction_payload.direction)}",
        f"{tr('cli.ledger.labels.description')}\t{transaction_payload.description}",
        f"{tr('cli.ledger.labels.counterparty')}\t{_field(transaction_payload.counterparty)}",
        f"{tr('cli.ledger.labels.business_classification')}\t{_field(transaction_payload.business_classification)}",
        f"{tr('cli.ledger.labels.business_pct')}\t{_field(transaction_payload.business_pct)}",
        f"{tr('cli.ledger.labels.category_id')}\t{_field(transaction_payload.category_id)}",
        f"{tr('cli.ledger.labels.usage_ratio_id')}\t{_field(transaction_payload.usage_ratio_id)}",
        f"{tr('cli.ledger.labels.taxable_base')}\t{_field(transaction_payload.taxable_base)}",
        f"{tr('cli.ledger.labels.iva_rate')}\t{_field(transaction_payload.iva_rate)}",
        f"{tr('cli.ledger.labels.iva_amount')}\t{_field(transaction_payload.iva_amount)}",
        f"{tr('cli.ledger.labels.iva_category')}\t{_field(transaction_payload.iva_category)}",
        f"{tr('cli.ledger.labels.counterparty_country')}\t{_field(transaction_payload.counterparty_country)}",
        f"{tr('cli.ledger.labels.counterparty_identification_state')}\t{_field(transaction_payload.counterparty_identification_state)}",
        f"{tr('cli.ledger.labels.irpf_category')}\t{_field(transaction_payload.irpf_category)}",
        f"{tr('cli.ledger.labels.notes')}\t{_field(transaction_payload.notes)}",
        f"{tr('cli.ledger.labels.purchase_invoice_evidence_id')}\t{_field(transaction_payload.purchase_invoice_evidence_id)}",
        f"{tr('cli.ledger.labels.attachment_ids')}\t{_field(', '.join(transaction_payload.attachment_ids))}",
        f"{tr('cli.ledger.labels.lifecycle_state')}\t{_field(transaction_payload.lifecycle_state)}",
        f"{tr('cli.ledger.labels.classified_by')}\t{_field(transaction_payload.classified_by)}",
        f"{tr('cli.ledger.labels.classified_at')}\t{_field(transaction_payload.classified_at)}",
        f"{tr('cli.ledger.labels.classification_confidence')}\t{_field(transaction_payload.classification_confidence)}",
        f"{tr('cli.ledger.labels.classification_reason')}\t{_field(transaction_payload.classification_reason)}",
        f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
    ]
    from ._ledger_payloads import LedgerViewResult

    notices: list[Notice] = []
    rejection_notice = _latest_llm_rejection_notice(projection)
    if rejection_notice is not None:
        notices.append(rejection_notice)
        reason = (rejection_notice.context or {}).get("operator_reason", "")
        label = tr("cli.ledger.view.llm_rejected_label")
        lines.append(f"{label}\t{tr('cli.ledger.classify.llm_rejected_label')}" + (f": {reason}" if reason else ""))
    emit_envelope(
        ctx,
        command="ledger.view",
        result=LedgerViewResult.model_validate(
            {
                "bucket_id": str(projection.profile_id),
                "transaction_id": transaction_payload.transaction_id,
                "review_status": review_status.value,
                "transaction": transaction_payload.model_dump(mode="json"),
            }
        ),
        lines=lines,
        notices=notices,
    )


def ledger_status(ctx: typer.Context, period: str | None = None, year: int | None = None) -> None:
    """Summarize active-bucket ledger state through the backend status service."""
    from .runtime_ledger_status import read_ledger_status_for_cli

    projection = read_ledger_status_for_cli(ctx, period=_optional_canonical_period(period, year=year))
    report = projection.to_report()
    lines = [
        f"{tr('cli.ledger.labels.profile')}\t{active_profile_label() or '<none>'}",
        f"business_income_total\t{report.business_income_total}",
        f"business_expense_total\t{report.business_expense_total}",
        f"business_net_total\t{report.business_net_total}",
        f"{tr('cli.ledger.labels.rows')}\t{report.total_count}",
        f"{tr('cli.ledger.labels.active')}\t{report.active_count}",
        f"{tr('cli.ledger.labels.archived')}\t{report.archived_count}",
        f"{tr('cli.ledger.labels.stashed')}\t{report.stashed_count}",
        f"{tr('cli.ledger.labels.pending')}\t{report.pending_review_count}",
        f"{tr('cli.ledger.labels.reviewed')}\t{report.reviewed_count}",
        f"{tr('cli.ledger.labels.skipped')}\t{report.skipped_count}",
    ]
    readiness_issues = tuple(issue.to_issue() for issue in projection.readiness_issues)
    if report.period is not None:
        lines.extend(
            [
                f"{tr('cli.ledger.labels.period')}\t{report.period}",
                f"{tr('cli.ledger.labels.checked')}\t{report.checked_transaction_count}",
                f"{tr('cli.ledger.labels.readiness_issues')}\t{report.readiness_issue_count}",
                f"{tr('cli.ledger.labels.ready')}\t{report.ready}",
            ]
        )
        lines.extend(_ledger_status_readiness_issue_line(issue) for issue in readiness_issues)
    stale_filings = projection.stale_filings
    lines.extend(
        "	".join(
            (
                "ledger_filing_stale",
                f"modelo={finding.modelo}",
                f"year={finding.filing_year}",
                f"period={finding.period}",
                f"revision={finding.calculation_revision_id}",
                f"changed={finding.changed_count}",
                f"removed={finding.removed_count}",
                # Always emitted, so the line keeps a fixed arity for a reader
                # that splits it. `false` says the comparison behind the counts
                # was sound but narrower than today's fact set, not that
                # anything additional drifted.
                f"covers_current_fact_set={str(finding.covers_current_fact_set).lower()}",
            )
        )
        for finding in stale_filings
    )

    from ._ledger_payloads import LedgerReadinessIssuePayload, LedgerStaleFilingPayload, LedgerStatusResult

    # The counts round-trip from the report; the two finding lists do not live
    # on it, so they are attached here from the same values the lines above
    # rendered. Each element is validated on the way in, so the payload is not
    # trusted merely because it was built locally.
    result = strict_round_trip(LedgerStatusResult, report).model_copy(
        update={
            "readiness_issues": [strict_round_trip(LedgerReadinessIssuePayload, issue) for issue in readiness_issues],
            "stale_filings": [strict_round_trip(LedgerStaleFilingPayload, finding) for finding in stale_filings],
        },
    )
    emit_envelope(ctx, command="ledger.status", result=result, lines=lines)


def ledger_track(ctx: typer.Context, transaction_id: str) -> None:
    """Render admitted audit lineage without opening frontend profile custody."""
    from ._ledger_payloads import LedgerTrackResult
    from .runtime_ledger_track import read_ledger_track_for_cli

    projection = read_ledger_track_for_cli(ctx, transaction_id=transaction_id)
    provenance = projection.imported_provenance
    emit_envelope(
        ctx,
        command="ledger.track",
        result=LedgerTrackResult.model_validate(
            {
                "bucket_id": str(projection.profile_id),
                "transaction": projection.transaction.model_dump(mode="json"),
                "tracking": projection.tracking.model_dump(mode="json"),
                "source_filename": provenance.source_filename if provenance is not None else None,
                "source_row_index": provenance.source_row_index if provenance is not None else None,
                "participated_in": (
                    [row.model_dump(mode="json") for row in projection.participated_in]
                    if projection.participated_in is not None
                    else None
                ),
            }
        ),
        lines=_ledger_track_lines(projection),
    )


def _latest_llm_rejection_notice(projection: LedgerViewProjection) -> Notice | None:
    """Render the standing rejection already resolved inside worker custody."""
    latest = projection.latest_llm_rejection
    if latest is None:
        return None
    reason = latest.operator_reason
    context = {"transaction_id": projection.transaction.transaction_id, "occurred_at": latest.occurred_at.isoformat()}
    if reason:
        context["operator_reason"] = reason
    return Notice(
        severity=NoticeSeverity.INFO,
        code="ledger.view.llm_suggestion_rejected",
        message=tr(
            "cli.ledger.view.llm_rejected_notice",
        ),
        context=context,
    )


def _ledger_status_readiness_issue_line(issue: LedgerReadinessIssueV1) -> str:
    """Render one readiness issue, marking a row the catalogue no longer holds."""

    def _value(value: object) -> str:
        return "-" if value is None or value == "" else str(value)

    fields = (
        "readiness_issue",
        issue.transaction_id,
        f"classification={_value(issue.business_classification)}",
        f"category_id={_value(issue.category_id)}",
        f"taxable_base={_value(issue.taxable_base)}",
        f"iva_rate={_value(issue.iva_rate)}",
        f"iva_amount={_value(issue.iva_amount)}",
        f"reason={issue.reason}",
        f"detail={issue.detail}",
    )
    if issue.transaction_present:
        return "	".join(fields)
    # The row named by the issue is gone. Dropping the issue here would make the
    # printed issues fewer than the count reported above them, with nothing said.
    return "	".join((*fields, "transaction=absent"))


def _ledger_track_lines(projection: LedgerTrackProjection) -> list[str]:
    """Render the canonical lineage and imported provenance supplied by custody."""
    tracking = projection.tracking
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{tracking.transaction_id}",
        f"{tr('cli.ledger.labels.lifecycle_state')}\t{tracking.lifecycle_state}",
        f"{tr('cli.ledger.labels.created_event_id')}\t{tracking.created_event_id or '-'}",
    ]
    provenance = projection.imported_provenance
    if provenance is not None:
        lines.append(f"import_provider\t{provenance.provider_name}")
        lines.append(f"import_source\t{provenance.source_filename}")
        lines.append(f"import_source_row\t{provenance.source_row_index}")
        lines.append(f"import_ingested_at\t{provenance.ingested_at}")
        lines.append(f"import_fingerprint\t{provenance.import_fingerprint or '-'}")
    return lines


__all__ = [
    "ledger_categories",
    "ledger_check",
    "ledger_export",
    "ledger_history",
    "ledger_list",
    "ledger_llm_diagnostics",
    "ledger_preflight",
    "ledger_status",
    "ledger_track",
    "ledger_view",
]
