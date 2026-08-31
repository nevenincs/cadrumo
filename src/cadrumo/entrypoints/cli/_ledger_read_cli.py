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

from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...application.export.tabular import ExportSerializationFormat
from ...application.ledger.actions_export import export_ledger_transactions
from ...application.ledger.actions_manual import (
    get_manual_transaction,
    ledger_transaction_payload,
    ledger_transaction_result_payload,
    ledger_transaction_tracking_payload,
    summarize_manual_transactions,
)
from ...application.ledger.models import LedgerExportCommand
from ...application.ledger.review_projection import ledger_transaction_review_status
from ...application.operator_actions._models import ActionReference
from ...application.review.errors import FilterParseError
from ...application.review.filter import LedgerReviewFilterSpec
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.decimal._coerce import coerce_decimal_strict
from ...core.i18n._render import tr
from ...core.json_contract import (
    Notice,
    NoticeSeverity,
    ResolvedActionArgument,
    strict_round_trip,
)
from ...core.ledger_sort import LedgerSortField, LedgerSortOrder
from ...core.operator_action_enums import ActionArgumentSource, ActionArgumentStatus
from ...core.period import Period
from ...core.unit_proportion import is_unit_proportion
from ...domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType
from ...domain.categories.spending_category import CATEGORY_FAMILY_MEMBERS, SpendingCategory, SpendingCategoryFamily
from ...domain.invoices.service import LinkInconsistency
from ...domain.transactions.irpf_categories import ledger_irpf_category_catalogue
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ._common import _bad, _state, _tx_repo, active_profile_label, emit_envelope, resolve_notice_action
from ._decimal_parsing import optional_decimal_text
from ._ledger_list import (
    LLM_DECISION_EVENT_TYPES,
    project_ledger_list,
)
from ._ledger_support import _ledger_cli_no_recovery
from ._period_parsing import _canonical_period, _optional_canonical_period

if TYPE_CHECKING:
    from ...application.ledger.llm_diagnostics import (
        LlmConfidenceProviderMetrics,
        LlmDiagnosticsReport,
        LlmUsageCostProviderMetrics,
    )
    from ...application.ledger.preflight import LedgerPreflightIssue, LedgerPreflightReport
    from ._ledger_payloads import LedgerLinkInconsistencyPayload
    from ._ledger_rule_payloads import LedgerLlmDiagnosticsResult

ResolveTransactionId = Callable[[Any, str], str]


def resolve_ledger_transaction_id(
    transaction_repository: TransactionCatalogueRepository,
    prefix: str,
) -> str:
    """Resolve a read-side transaction id while following stable edit lineage."""
    from ...application.cli_exception_preconditions import CliExceptionPrecondition
    from ...application.ledger.id_resolution import resolve_lineage_transaction_id
    from ...domain.transactions.errors import TransactionIdPrefixError

    catalogue = transaction_repository.load()
    try:
        return resolve_lineage_transaction_id(prefix, catalogue)
    except TransactionIdPrefixError as exc:
        raise _ledger_cli_no_recovery(
            exc,
            condition=CliExceptionPrecondition.LEDGER_TRANSACTION_ID_RESOLVES,
            facts={"transaction_id_resolves": False},
        ) from None


_LEDGER_HISTORY_EVENT_TYPES: tuple[BucketEventType, ...] = (
    BucketEventType.LEDGER_TRANSACTION_CREATED,
    BucketEventType.LEDGER_TRANSACTION_IMPORTED,
    BucketEventType.LEDGER_TRANSACTION_UPDATED,
    BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,
    BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED,
    BucketEventType.LEDGER_TRANSACTION_ALLOCATED,
    BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
    BucketEventType.LEDGER_TRANSACTION_STASHED,
    BucketEventType.LEDGER_TRANSACTION_RESTORED,
    BucketEventType.LEDGER_TRANSACTION_REMOVED,
    BucketEventType.LEDGER_TRANSACTION_EXPORTED,
    BucketEventType.LEDGER_TRANSACTION_SPLIT,
    BucketEventType.LEDGER_TRANSACTION_MERGED,
    BucketEventType.LEDGER_TRANSACTION_INVOICE_LINKED,
)
_LEDGER_EVIDENCE_HISTORY_EVENT_TYPES: tuple[BucketEventType, ...] = (
    BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED,
    BucketEventType.PURCHASE_INVOICE_EVIDENCE_REPLACED,
    BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
    BucketEventType.ATTACHMENT_LINKED,
    BucketEventType.ATTACHMENT_REMOVED,
)


def _ledger_list_pairing_error_year(filters: list[str], option_year: int | None) -> int | None:
    """Return a safe year to include in period/year pairing guidance."""
    if option_year is not None:
        return option_year
    for raw_filter in filters:
        key, separator, value = raw_filter.partition("=")
        if separator and key.strip().lower() == "year":
            stripped = value.strip()
            if stripped.isdecimal():
                return int(stripped)
    return None


def ledger_llm_diagnostics(
    ctx: typer.Context, since: str | None = None, until: str | None = None, low_confidence_below: float = 0.5
) -> None:
    """Report existing LLM usage, cost, and classification-confidence metrics."""
    from ...application.ledger.llm_diagnostics import build_llm_diagnostics_report

    since_date = _parse_iso_date(since, "--since")
    until_date = _parse_iso_date(until, "--until")
    threshold = coerce_decimal_strict(low_confidence_below)
    if not is_unit_proportion(threshold):
        raise _bad(tr("cli.ledger.llm_diagnostics.threshold_range"))
    report = build_llm_diagnostics_report(since=since_date, until=until_date, low_confidence_threshold=threshold)
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


def ledger_categories(ctx: typer.Context) -> None:
    """List the recognised `--category-id` spending-category catalogue."""
    families: list[dict[str, object]] = []
    lines: list[str] = [
        tr("cli.ledger.categories.header"),
        f"{tr('cli.ledger.categories.id_column')}\t{tr('cli.ledger.categories.family_column')}",
    ]
    first_category_id: str | None = None
    for family in SpendingCategoryFamily:
        members = CATEGORY_FAMILY_MEMBERS.get(family, ())
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
    irpf_categories = [
        {
            "id": category.id,
            "purpose": category.purpose,
            "directions": [direction.value for direction in category.directions],
            "net_paid_invoice": category.net_paid_invoice,
            "related_category_ids": list(category.related_category_ids),
        }
        for category in ledger_irpf_category_catalogue()
    ]
    lines.extend(
        [
            "",
            tr("cli.ledger.categories.irpf_header"),
            f"{tr('cli.ledger.categories.irpf_id_column')}\t{tr('cli.ledger.categories.irpf_use_column')}",
        ]
    )
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
    from ._ledger_payloads import LedgerCategoriesResult

    emit_envelope(
        ctx,
        command="ledger.categories",
        result=LedgerCategoriesResult.model_validate(
            {
                "families": families,
                "category_ids": [category.value for category in SpendingCategory],
                "irpf_categories": irpf_categories,
                "irpf_category_ids": [category["id"] for category in irpf_categories],
                "net_paid_withholding_irpf_category_ids": [
                    category["id"] for category in irpf_categories if category["net_paid_invoice"]
                ],
                "income_requires_category": False,
            }
        ),
        lines=lines,
    )


def _link_inconsistency_notices(rows: tuple[LinkInconsistency, ...]) -> list[Notice]:
    """Return the warning notice for one-sided invoice links, or nothing.

    Takes the typed :class:`~cadrumo.domain.invoices.LinkInconsistency` rows
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
    from ...application.invoices._queries import verify_invoice_repository_links
    from ._ledger_payloads import LedgerLinkInconsistencyPayload

    if bucket_id_option is not None:
        transaction_repository = TransactionCatalogueRepository(bucket_id=bucket_id_option)
    else:
        transaction_repository = _tx_repo(_state())
    bucket_id = transaction_repository.bucket_id
    catalogue = transaction_repository.load()
    link_inconsistencies = verify_invoice_repository_links(bucket_id=bucket_id)
    link_rows = [
        LedgerLinkInconsistencyPayload(
            invoice_id=row.invoice_id, transaction_id=row.transaction_id, direction=row.direction
        )
        for row in link_inconsistencies
    ]
    link_lines = [
        f"link_inconsistency\t{row.invoice_id}\t{row.transaction_id}\t{row.direction.value}"
        for row in link_inconsistencies
    ]
    link_notices = _link_inconsistency_notices(link_inconsistencies)
    canonical_period = _optional_canonical_period(period, year=year)
    if canonical_period is not None:
        _emit_ledger_check_period(
            ctx,
            bucket_id=bucket_id,
            period=canonical_period,
            catalogue=catalogue,
            link_rows=link_rows,
            link_lines=link_lines,
            link_notices=link_notices,
        )
        return
    years = sorted(
        {
            (tx.raw.value_date or tx.raw.booked_date).year
            for tx in catalogue.values()
            if (tx.raw.value_date or tx.raw.booked_date) is not None
        }
    )
    if not years:
        _emit_ledger_check_empty(
            ctx, bucket_id=bucket_id, link_rows=link_rows, link_lines=link_lines, link_notices=link_notices
        )
        return
    _emit_ledger_check_all_periods(
        ctx,
        bucket_id=bucket_id,
        years=years,
        catalogue=catalogue,
        link_rows=link_rows,
        link_lines=link_lines,
        link_notices=link_notices,
    )


def _emit_ledger_check_period(
    ctx: typer.Context,
    *,
    bucket_id: str,
    period: Period,
    catalogue: TransactionCatalogue,
    link_rows: list[LedgerLinkInconsistencyPayload],
    link_lines: list[str],
    link_notices: list[Notice],
) -> None:
    from ...application.ledger.preflight import preflight_transaction_catalogue
    from ._ledger_payloads import LedgerCheckResult

    report = preflight_transaction_catalogue(
        bucket_id=bucket_id,
        period=period,
        transactions=catalogue,
    )
    period_label = str(period)
    ready = report.ready and not link_rows
    payload = {
        "bucket_id": bucket_id,
        "periods": [period_label],
        "checked_transaction_count": report.checked_transaction_count,
        "issues": [issue.model_dump(mode="json") for issue in report.issues],
        "link_inconsistencies": link_rows,
        "ready": ready,
    }
    lines = [
        f"bucket\t{bucket_id}",
        f"periods\t{period_label}",
        f"checked\t{report.checked_transaction_count}",
        f"issues\t{len(report.issues)}",
        f"link_inconsistencies\t{len(link_rows)}",
        f"ready\t{str(ready).lower()}",
    ]
    lines.extend(_ledger_check_issue_lines(report))
    lines.extend(link_lines)
    emit_envelope(
        ctx,
        command="ledger.check",
        result=LedgerCheckResult.model_validate(payload),
        lines=lines,
        notices=link_notices,
    )


def _emit_ledger_check_empty(
    ctx: typer.Context,
    *,
    bucket_id: str,
    link_rows: list[LedgerLinkInconsistencyPayload],
    link_lines: list[str],
    link_notices: list[Notice],
) -> None:
    from ._ledger_payloads import LedgerCheckResult

    ready = not link_rows
    payload = {
        "bucket_id": bucket_id,
        "periods": [],
        "checked_transaction_count": 0,
        "issues": [],
        "link_inconsistencies": link_rows,
        "ready": ready,
    }
    lines = [
        f"bucket\t{bucket_id}",
        "periods\t",
        "checked\t0",
        "issues\t0",
        f"link_inconsistencies\t{len(link_rows)}",
        f"ready\t{str(ready).lower()}",
        *link_lines,
    ]
    emit_envelope(
        ctx,
        command="ledger.check",
        result=LedgerCheckResult.model_validate(payload),
        lines=lines,
        notices=link_notices,
    )


def _emit_ledger_check_all_periods(
    ctx: typer.Context,
    *,
    bucket_id: str,
    years: list[int],
    catalogue: TransactionCatalogue,
    link_rows: list[LedgerLinkInconsistencyPayload],
    link_lines: list[str],
    link_notices: list[Notice],
) -> None:
    from ...application.ledger.preflight import preflight_transaction_catalogue
    from ._ledger_payloads import LedgerCheckResult

    aggregated_issues: list[LedgerPreflightIssue] = []
    aggregated_payload_issues: list[dict[str, object]] = []
    checked_total = 0
    for year in years:
        report = preflight_transaction_catalogue(
            bucket_id=bucket_id,
            period=Period.from_year_and_code(year, "0A"),
            transactions=catalogue,
        )
        checked_total += report.checked_transaction_count
        aggregated_issues.extend(report.issues)
        aggregated_payload_issues.extend(issue.model_dump(mode="json") for issue in report.issues)

    ready = not aggregated_issues and not link_rows
    payload = {
        "bucket_id": bucket_id,
        "periods": [str(year) for year in years],
        "checked_transaction_count": checked_total,
        "issues": aggregated_payload_issues,
        "link_inconsistencies": link_rows,
        "ready": ready,
    }
    lines = [
        f"bucket\t{bucket_id}",
        f"periods\t{','.join(str(year) for year in years)}",
        f"checked\t{checked_total}",
        f"issues\t{len(aggregated_issues)}",
        f"link_inconsistencies\t{len(link_rows)}",
        f"ready\t{str(ready).lower()}",
        *(_ledger_check_issue_lines_from_items(aggregated_issues)),
        *link_lines,
    ]
    emit_envelope(
        ctx,
        command="ledger.check",
        result=LedgerCheckResult.model_validate(payload),
        lines=lines,
        notices=link_notices,
    )


def _ledger_check_issue_lines(report: LedgerPreflightReport) -> list[str]:
    return _ledger_check_issue_lines_from_items(report.issues)


def _ledger_check_issue_lines_from_items(issues: Sequence[LedgerPreflightIssue]) -> list[str]:
    return [f"issue\t{issue.transaction_id}\t{issue.reason.value}\t{issue.detail}" for issue in issues]


def ledger_preflight(ctx: typer.Context, period: str, year: int) -> None:
    """Surface modelo-readiness gaps for the active bucket without mutating ledger state."""
    from ...application.ledger.preflight import preflight_ledger_tax_readiness

    transaction_repository = _tx_repo(_state())
    canonical = _canonical_period(period, year=year)
    report = preflight_ledger_tax_readiness(
        bucket_id=transaction_repository.bucket_id, period=canonical, transaction_repository=transaction_repository
    )
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
    transaction_repository = _tx_repo(_state())
    resolved_id = resolve_ledger_transaction_id(transaction_repository, transaction_id)
    object_ids = _history_object_ids(
        transaction_repository, resolved_id=resolved_id, include_split_siblings=include_split_siblings
    )
    matches = _collect_ledger_history_events(object_ids)
    lines = [
        f"{tr('cli.ledger.labels.bucket')}\t{transaction_repository.bucket_id}",
        f"{tr('cli.ledger.labels.id')}\t{resolved_id}",
        f"{tr('cli.ledger.labels.event_count')}\t{len(matches)}",
    ]
    lines.extend(f"{event.occurred_at.isoformat()}\t{event.event_type.value}\t{event.event_id}" for event in matches)
    from ._ledger_payloads import LedgerHistoryResult

    emit_envelope(
        ctx,
        command="ledger.history",
        result=LedgerHistoryResult.model_validate(
            {
                "bucket_id": transaction_repository.bucket_id,
                "transaction_id": resolved_id,
                "event_count": len(matches),
                "events": [event.model_dump(mode="json") for event in matches],
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
    """Export canonical bucket-scoped ledger rows through the backend."""
    transaction_repository = _tx_repo(_state())
    result = export_ledger_transactions(
        LedgerExportCommand(
            bucket_id=transaction_repository.bucket_id,
            export_format=export_kind,
            include_inactive=include_inactive,
            output_path=output,
            period=_optional_canonical_period(period, year=year),
            actor=actor or resolve_active_bucket_id() or "operator",
            source_command="aeat app ledger export",
        ),
        transaction_repository=transaction_repository,
    )
    from ._ledger_payloads import LedgerExportPayload

    emit_envelope(
        ctx,
        command="ledger.export",
        result=LedgerExportPayload.from_result(result, output_path=str(output)),
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
) -> None:
    """List bucket-scoped ledger rows through :func:`~cadrumo.entrypoints.cli._ledger_list.project_ledger_list`."""
    transaction_repository = _tx_repo(_state())
    resolved_filters = list(filters)
    if period is not None:
        resolved_filters.append(f"period={period}")
    if year is not None:
        resolved_filters.append(f"year={year}")
    try:
        spec = LedgerReviewFilterSpec.from_strings(resolved_filters)
    except FilterParseError as exc:
        from ...application.cli_exception_preconditions import CliExceptionPrecondition

        raise _ledger_cli_no_recovery(
            exc,
            condition=CliExceptionPrecondition.LEDGER_FILTER_VALID,
            facts={"ledger_filter_valid": False, "reason": exc.reason},
        ) from None
    projection = project_ledger_list(
        transaction_repository=transaction_repository,
        spec=spec,
        group=group,
        by_group=by_group,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
        exclude_llm_rejected=hide_llm_rejected,
    )
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
    transaction_repository = _tx_repo(_state())
    resolved_id = resolve_ledger_transaction_id(transaction_repository, transaction_id)
    result = get_manual_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        transaction_repository=transaction_repository,
    )
    result_payload = ledger_transaction_result_payload(result)
    transaction_payload = result_payload.transaction
    review_status = ledger_transaction_review_status(result.transaction)

    def _field(value: object) -> str:
        return "-" if value is None or value == "" else str(value)

    lines = [
        f"{tr('cli.ledger.labels.id')}\t{result.ref.transaction_id}",
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
    rejection_notice = _latest_llm_rejection_notice(transaction_repository, resolved_id=resolved_id)
    if rejection_notice is not None:
        notices.append(rejection_notice)
        reason = (rejection_notice.context or {}).get("operator_reason", "")
        label = tr("cli.ledger.view.llm_rejected_label")
        lines.append(f"{label}\t{tr('cli.ledger.classify.llm_rejected_label')}" + (f": {reason}" if reason else ""))
    emit_envelope(
        ctx,
        command="ledger.view",
        result=strict_round_trip(LedgerViewResult, result_payload),
        lines=lines,
        notices=notices,
    )


def ledger_status(ctx: typer.Context, period: str | None = None, year: int | None = None) -> None:
    """Summarize active-bucket ledger state through the backend status service."""
    transaction_repository = _tx_repo(_state())
    report = summarize_manual_transactions(
        bucket_id=transaction_repository.bucket_id,
        period=_optional_canonical_period(period, year=year),
        transaction_repository=transaction_repository,
    )
    transactions = transaction_repository.load()
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
    if report.period is not None:
        lines.extend(
            [
                f"{tr('cli.ledger.labels.period')}\t{report.period}",
                f"{tr('cli.ledger.labels.checked')}\t{report.checked_transaction_count}",
                f"{tr('cli.ledger.labels.readiness_issues')}\t{report.readiness_issue_count}",
                f"{tr('cli.ledger.labels.ready')}\t{report.ready}",
            ]
        )
        from ...application.ledger.preflight import preflight_ledger_tax_readiness

        preflight = preflight_ledger_tax_readiness(
            bucket_id=transaction_repository.bucket_id,
            period=report.period,
            transaction_repository=transaction_repository,
        )
        for issue in preflight.issues:
            transaction = transactions.get(issue.transaction_id)
            if transaction is None:
                continue
            lines.append(
                _ledger_status_readiness_issue_line(transaction, reason=issue.reason.value, detail=issue.detail)
            )
    from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ...application.aggregation import stale_filed_revisions

    revisions = CalculationRevisionCatalogueRepository().load().revisions
    work_units = WorkUnitCatalogueRepository().load()
    for revision, verdict in stale_filed_revisions(revisions=revisions, catalogue=transactions):
        work_unit = work_units.get(revision.work_unit_id)
        if work_unit is None or work_unit.bucket_id != transaction_repository.bucket_id:
            continue
        lines.append(
            "\t".join(
                (
                    "ledger_filing_stale",
                    f"modelo={work_unit.modelo}",
                    f"year={work_unit.filing_year}",
                    f"period={work_unit.period.registry_token}",
                    f"revision={revision.calculation_revision_id}",
                    f"changed={len(verdict.changed)}",
                    f"removed={len(verdict.removed)}",
                )
            )
        )
    from ._ledger_payloads import LedgerStatusResult

    emit_envelope(ctx, command="ledger.status", result=strict_round_trip(LedgerStatusResult, report), lines=lines)


def ledger_track(ctx: typer.Context, transaction_id: str) -> None:
    """Show audit lineage for one transaction.

    Emits a :class:`~cadrumo.entrypoints.cli._ledger_payloads.LedgerTrackResult`.
    """
    transaction_repository = _tx_repo(_state())
    resolved_id = resolve_ledger_transaction_id(transaction_repository, transaction_id)
    result = get_manual_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        transaction_repository=transaction_repository,
    )
    from ._ledger_payloads import LedgerTrackResult

    participated_in = _ledger_track_participated_in(
        transaction_id=result.ref.transaction_id, bucket_id=transaction_repository.bucket_id
    )
    emit_envelope(
        ctx,
        command="ledger.track",
        result=LedgerTrackResult.model_validate(
            {
                "bucket_id": result.ref.bucket_id,
                "transaction": ledger_transaction_payload(result.transaction).model_dump(mode="json"),
                "tracking": ledger_transaction_tracking_payload(result.transaction).model_dump(mode="json"),
                "participated_in": participated_in,
            }
        ),
        lines=_ledger_track_lines(result.ref.transaction_id, result.transaction),
    )


def _ledger_track_participated_in(
    *,
    transaction_id: str,
    bucket_id: str | None,
) -> list[dict[str, object]] | None:
    """Return the finalized-revision participations for ``transaction_id``, or ``None``.

    Wraps :func:`~cadrumo.application.ledger.participation_read.get_transaction_participation`, whose
    :class:`~TransactionRevisionParticipationIndex` is the
    rebuildable inverse index from ledger rows to finalized revisions.
    Surfaces the inverse audit trail on the ``ledger track`` lineage output:
    every finalized modelo revision and filing that consumed this transaction.
    Returns ``None`` when the transaction appears in no finalized revision so the
    field is omitted from the JSON for transactions with no declarations.
    """
    from ...application.ledger.participation_read import get_transaction_participation
    from ._ledger_payloads import LedgerTransactionParticipationEntryPayload

    index = get_transaction_participation(transaction_id=transaction_id, bucket_id=bucket_id)
    if not index.participations:
        return None
    return [
        LedgerTransactionParticipationEntryPayload.model_validate(
            {
                "calculation_revision_id": participation.calculation_revision_id,
                "work_unit_id": participation.work_unit_id,
                "modelo": str(participation.modelo),
                "filing_year": participation.filing_year,
                "period": participation.period,
                "revision_state": participation.revision_state,
                "filing_record_id": participation.filing_record_id,
                "justificante_reference": participation.justificante_reference,
            },
        ).model_dump(mode="json")
        for participation in index.participations
    ]


def _history_object_ids(
    transaction_repository: TransactionCatalogueRepository,
    *,
    resolved_id: str,
    include_split_siblings: bool,
) -> list[str]:
    """Return every event-anchor id whose events belong to ``resolved_id``.

    Always includes ``resolved_id`` plus every prior id in its edit-lineage
    chain. An ``update`` that edits an id-affecting fact anchors the pre-edit
    events (create, import) on the *old* id and the post-edit events on the
    *new* id; walking the lineage means an operator who wrote down an old id
    before the correction still sees the full chronological chain, and the
    superseded id resolves to (and surfaces) the lineage rather than failing
    with id-not-found. Split siblings are added only when the operator opts in.

    The content-addressed id stays authoritative; this is a read-side
    lineage lookup over the same edit-lineage chain the finalized-modelo
    guard walks.
    """
    catalogue = transaction_repository.load()
    transaction = catalogue.get(resolved_id)
    object_ids: list[str] = [resolved_id]
    if transaction is not None:
        for entry in transaction.edit_lineage:
            if entry.previous_transaction_id not in object_ids:
                object_ids.append(entry.previous_transaction_id)
    if not include_split_siblings:
        return object_ids
    if transaction is None or transaction.split_lineage is None:
        return object_ids
    for sibling in transaction.split_lineage.sibling_transaction_ids:
        if sibling not in object_ids:
            object_ids.append(sibling)
    return object_ids


def _collect_ledger_history_events(object_ids: list[str]) -> list[BucketEvent]:
    """Return the chronological union of :class:`~cadrumo.domain.buckets.BucketEvent` rows across ``object_ids``."""
    event_catalogue = BucketEventHistoryRepository().load()
    object_id_set = set(object_ids)
    matches: list[BucketEvent] = []
    for object_id in object_ids:
        matches.extend(
            event
            for event in event_catalogue.for_object(
                object_type=BucketEventObjectType.LEDGER_TRANSACTION,
                object_id=object_id,
            )
            if event.event_type in _LEDGER_HISTORY_EVENT_TYPES
        )
    matches.extend(
        event
        for event in event_catalogue.values()
        if event.event_type in _LEDGER_EVIDENCE_HISTORY_EVENT_TYPES
        and event.payload.get("transaction_id") in object_id_set
    )
    matches.sort(key=lambda event: event.occurred_at)
    return matches


def _latest_llm_rejection_notice(
    transaction_repository: TransactionCatalogueRepository,
    *,
    resolved_id: str,
) -> Notice | None:
    """Return a notice when the row's most recent LLM decision was a rejection.

    Returns a :class:`~cadrumo.core.json_contract.Notice` derived from
    :data:`~cadrumo.entrypoints.cli._ledger_list.LLM_DECISION_EVENT_TYPES`.
    Reads the bucket-event history for the transaction (and its edit lineage) and
    finds the latest LLM-decision event. When that is a rejection — i.e. the
    operator declined an LLM suggestion and has not since accepted one — `view`
    surfaces a one-line advisory carrying the recorded reason, so prior judgement
    is visible without opening `history`
    (``aeat-cli-contract``).
    """
    object_ids = _history_object_ids(transaction_repository, resolved_id=resolved_id, include_split_siblings=False)
    decisions = [
        event for event in _collect_ledger_history_events(object_ids) if event.event_type in LLM_DECISION_EVENT_TYPES
    ]
    if not decisions:
        return None
    latest = decisions[-1]  # chronological order from _collect_ledger_history_events
    if latest.event_type is not BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED:
        return None
    reason = latest.payload.get("operator_reason", "")
    context = {"transaction_id": resolved_id, "occurred_at": latest.occurred_at.isoformat()}
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


def _ledger_status_readiness_issue_line(transaction: Transaction, *, reason: str, detail: str) -> str:
    def _value(value: object) -> str:
        return "-" if value is None or value == "" else str(value)

    return "\t".join(
        (
            "readiness_issue",
            transaction.transaction_id,
            f"classification={transaction.business_classification.value}",
            f"category_id={_value(transaction.category_id)}",
            f"taxable_base={_value(transaction.taxable_base)}",
            f"iva_rate={_value(transaction.iva_rate)}",
            f"iva_amount={_value(transaction.iva_amount)}",
            f"reason={reason}",
            f"detail={detail}",
        ),
    )


def _ledger_track_lines(transaction_id: str, transaction: Transaction) -> list[str]:
    """Track lines, naming the import-batch provenance for imported rows."""
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{transaction_id}",
        f"{tr('cli.ledger.labels.lifecycle_state')}\t{transaction.lifecycle_state.value}",
        f"{tr('cli.ledger.labels.created_event_id')}\t{transaction.created_event_id or '-'}",
    ]
    if transaction.created_event_id is None:
        provenance = transaction.raw.provenance
        lines.append(f"import_provider\t{provenance.provider_name}")
        lines.append(f"import_source\t{provenance.source_path.name}")
        lines.append(f"import_ingested_at\t{provenance.ingested_at.isoformat()}")
        lines.append(f"import_fingerprint\t{transaction.import_fingerprint or '-'}")
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
    "resolve_ledger_transaction_id",
]
