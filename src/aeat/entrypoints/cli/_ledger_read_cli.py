"""Read, discovery, and reporting commands for ``aeat app ledger``.

Read commands load transactions through :class:`TransactionCatalogueRepository`
and read :class:`BucketEventHistoryRepository` events for history and
review-derived filters.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer

from ...application.export import ExportSerializationFormat
from ...application.ledger import (
    LedgerExportCommand,
    available_llm_providers,
    export_ledger_transactions,
    get_manual_transaction,
    ledger_transaction_payload,
    ledger_transaction_result_payload,
    ledger_transaction_review_status,
    ledger_transaction_tracking_payload,
    summarize_manual_transactions,
)
from ...application.review import FilterParseError
from ...core import LedgerSortField, LedgerSortOrder, Period, resolve_active_bucket_id
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.categories import (
    CATEGORY_FAMILY_MEMBERS,
    SpendingCategory,
    SpendingCategoryFamily,
)
from ...domain.transactions import Transaction, TransactionCatalogueRepository, ledger_irpf_category_catalogue
from ._common import _bad, _canonical_period, _emit_envelope, _optional_canonical_period, _state, _tx_repo
from ._ledger_list import (
    LLM_DECISION_EVENT_TYPES,
    ledger_filter_parse_error_message,
    parse_ledger_list_filter_spec,
    project_ledger_list,
)
from ._ledger_review_cli import register_ledger_review_command
from ._participation_cli import register_participation_commands

ResolveTransactionId = Callable[[Any, str], str]

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
)


def register_read_commands(app: typer.Typer, *, resolve_transaction_id: ResolveTransactionId) -> None:
    """Register ledger read/discovery/reporting commands."""
    _register_ledger_providers_command(app)
    _register_ledger_categories_command(app)
    _register_ledger_check_command(app)
    _register_ledger_preflight_command(app)
    _register_ledger_history_command(app, resolve_transaction_id=resolve_transaction_id)
    _register_ledger_export_command(app)
    _register_ledger_list_command(app)
    _register_ledger_view_command(app, resolve_transaction_id=resolve_transaction_id)
    _register_ledger_status_command(app)
    _register_ledger_track_command(app, resolve_transaction_id=resolve_transaction_id)
    register_ledger_review_command(app, resolve_transaction_id=resolve_transaction_id)
    register_participation_commands(app, resolve_transaction_id=resolve_transaction_id)


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


def _register_ledger_providers_command(app: typer.Typer) -> None:
    @app.command("providers", help=tr("cli.ledger.providers.help"))
    def ledger_providers(ctx: typer.Context) -> None:
        """List the cloud-provider CLIs on PATH and the on-host vision model."""
        from ...application.provisioning import probe_ollama_vision
        from ._ledger_payloads import LedgerProvidersResult

        listings = available_llm_providers()
        vision = probe_ollama_vision()
        result = LedgerProvidersResult.model_validate(
            {
                "providers": [
                    {
                        "provider": item.provider.value,
                        "cli_binary": item.cli_binary,
                        "available": item.available,
                        "resolved_path": item.resolved_path,
                    }
                    for item in listings
                ],
                "vision": {
                    "service": vision.service,
                    "available": vision.available,
                    "detail": vision.detail,
                    "remediation": vision.remediation,
                },
            },
        )
        lines: list[str] = []
        for item in listings:
            status = "available" if item.available else "unavailable"
            location = item.resolved_path or item.cli_binary
            lines.append(f"{item.provider.value}\t{status}\t{location}")
        vision_status = "available" if vision.available else "unavailable"
        vision_tail = f"\t{vision.remediation}" if vision.remediation else ""
        lines.append(f"{vision.service}\t{vision_status}\t{vision.detail}{vision_tail}")
        _emit_envelope(ctx, command="ledger.providers", result=result, lines=lines)


def _register_ledger_categories_command(app: typer.Typer) -> None:
    def _irpf_purpose_label(purpose: str) -> str:
        if purpose == "activity_income_withholding":
            return tr("cli.ledger.categories.irpf_purpose_activity_income_withholding")
        if purpose == "rent_expense_withholding":
            return tr("cli.ledger.categories.irpf_purpose_rent_expense_withholding")
        if purpose == "employment_income":
            return tr("cli.ledger.categories.irpf_purpose_employment_income")
        return purpose

    @app.command("categories", help=tr("cli.ledger.categories.help"))
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
            ],
        )
        for category in irpf_categories:
            lines.append(f"{category['id']}\t{_irpf_purpose_label(str(category['purpose']))}")
        lines.append(
            tr(
                "cli.ledger.categories.irpf_usage_example",
                rent_category="arrendamiento_local",
                activity_category="actividad_economica",
            ),
        )
        from ._ledger_payloads import LedgerCategoriesResult

        _emit_envelope(
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
                },
            ),
            lines=lines,
        )


def _register_ledger_check_command(app: typer.Typer) -> None:
    @app.command(
        "check",
        help=tr(
            "cli.ledger.check.help",
            default=(
                "Probe ledger transactions in the addressed bucket (defaults to the active "
                "profile bucket) and report anomaly rows aggregated across every period a "
                "transaction touches. Local-only; never contacts AEAT."
            ),
        ),
    )
    def ledger_check(
        ctx: typer.Context,
        bucket_id_option: str | None = typer.Option(
            None,
            "--bucket-id",
            help=tr(
                "cli.ledger.check.bucket_id_help",
                default="Bucket id to probe (defaults to the active profile).",
            ),
        ),
        period: str | None = typer.Option(None, "--period", help=tr("cli.ledger.check.period_help")),
        year: int | None = typer.Option(
            None,
            "--year",
            help=tr("cli.ledger.check.year_help", default="Filing year for --period (e.g. 2024)."),
        ),
    ) -> None:
        """Surface ledger anomalies for the addressed bucket without mutating state."""
        from ...application.ledger import LedgerPreflightIssue, preflight_transaction_catalogue
        from ._ledger_payloads import LedgerCheckResult

        if bucket_id_option is not None:
            transaction_repository = TransactionCatalogueRepository(bucket_id=bucket_id_option)
        else:
            transaction_repository = _tx_repo(_state())
        bucket_id = transaction_repository.bucket_id
        catalogue = transaction_repository.load()
        canonical_period = _optional_canonical_period(period, year=year)
        if canonical_period is not None:
            report = preflight_transaction_catalogue(
                bucket_id=bucket_id,
                period=canonical_period,
                transactions=catalogue,
            )
            period_label = f"{canonical_period.registry_token} {canonical_period.year}"
            payload = {
                "bucket_id": bucket_id,
                "periods": [period_label],
                "checked_transaction_count": report.checked_transaction_count,
                "issues": [issue.model_dump(mode="json") for issue in report.issues],
                "ready": report.ready,
            }
            lines = [
                f"bucket\t{bucket_id}",
                f"periods\t{period_label}",
                f"checked\t{report.checked_transaction_count}",
                f"issues\t{len(report.issues)}",
                f"ready\t{str(report.ready).lower()}",
            ]
            for issue in report.issues:
                lines.append(f"issue\t{issue.transaction_id}\t{issue.reason.value}\t{issue.detail}")
            _emit_envelope(
                ctx,
                command="ledger.check",
                result=LedgerCheckResult.model_validate(payload),
                lines=lines,
            )
            return

        years = sorted(
            {
                (tx.raw.value_date or tx.raw.booked_date).year
                for tx in catalogue.values()
                if (tx.raw.value_date or tx.raw.booked_date) is not None
            },
        )

        if not years:
            payload = {
                "bucket_id": bucket_id,
                "periods": [],
                "checked_transaction_count": 0,
                "issues": [],
                "ready": True,
            }
            lines = [
                f"bucket\t{bucket_id}",
                "periods\t",
                "checked\t0",
                "issues\t0",
                "ready\ttrue",
            ]
            _emit_envelope(
                ctx,
                command="ledger.check",
                result=LedgerCheckResult.model_validate(payload),
                lines=lines,
            )
            return

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
            for issue in report.issues:
                aggregated_issues.append(issue)
                aggregated_payload_issues.append(issue.model_dump(mode="json"))

        payload = {
            "bucket_id": bucket_id,
            "periods": [str(year) for year in years],
            "checked_transaction_count": checked_total,
            "issues": aggregated_payload_issues,
            "ready": not aggregated_issues,
        }
        lines = [
            f"bucket\t{bucket_id}",
            f"periods\t{','.join(str(year) for year in years)}",
            f"checked\t{checked_total}",
            f"issues\t{len(aggregated_issues)}",
            f"ready\t{str(not aggregated_issues).lower()}",
        ]
        for issue in aggregated_issues:
            lines.append(f"issue\t{issue.transaction_id}\t{issue.reason.value}\t{issue.detail}")
        _emit_envelope(
            ctx,
            command="ledger.check",
            result=LedgerCheckResult.model_validate(payload),
            lines=lines,
        )


def _register_ledger_preflight_command(app: typer.Typer) -> None:
    @app.command(
        "preflight",
        help=tr(
            "cli.ledger.preflight.help",
            default=(
                "Report missing ledger facts (category, taxable base, IVA amount/rate, "
                "currency, proportionality reference) for the active bucket's transactions "
                "in a given period. Local-only; never contacts AEAT."
            ),
        ),
    )
    def ledger_preflight(
        ctx: typer.Context,
        period: str = typer.Option(
            ...,
            "--period",
            help=tr(
                "cli.ledger.preflight.period_help",
                default=(
                    "Filing period as an AEAT token: 1T-4T (quarters), 0A (annual), "
                    "01-12 (months). Combine with --year to choose the year."
                ),
            ),
        ),
        year: int = typer.Option(
            ...,
            "--year",
            help=tr("cli.ledger.preflight.year_help", default="Filing year (e.g. 2024)."),
        ),
    ) -> None:
        """Surface modelo-readiness gaps for the active bucket without mutating ledger state."""
        from ...application.ledger import preflight_ledger_tax_readiness

        transaction_repository = _tx_repo(_state())
        canonical = _canonical_period(period, year=year)
        report = preflight_ledger_tax_readiness(
            bucket_id=transaction_repository.bucket_id,
            period=canonical,
            transaction_repository=transaction_repository,
        )
        payload = report.model_dump(mode="json")
        lines = [
            f"bucket\t{report.bucket_id}",
            f"period\t{canonical.registry_token} {canonical.year}",
            f"checked\t{report.checked_transaction_count}",
            f"issues\t{len(report.issues)}",
            f"ready\t{str(report.ready).lower()}",
        ]
        notices: list[Notice] = []
        if report.checked_transaction_count == 0 and not report.issues:
            message = tr(
                "cli.ledger.preflight.empty_ledger_advisory",
                default=(
                    "No active ledger transactions were checked for this period. If activity occurred, add or "
                    "import ledger rows before calculating; if there was genuinely no activity, the empty ledger "
                    "can support a zero-activity local filing."
                ),
            )
            suggestion = "aeat app ledger add --help; aeat app ledger import --help"
            notices.append(
                Notice(
                    severity=NoticeSeverity.WARNING,
                    code="ledger.preflight.empty_period",
                    message=message,
                    suggestion=suggestion,
                    context={"period": canonical.registry_token, "year": str(canonical.year)},
                ),
            )
            lines.append(f"advisory\tempty_ledger\t{message}")
            lines.append(f"next\t{suggestion}")
        for issue in report.issues:
            lines.append(f"issue\t{issue.transaction_id}\t{issue.reason.value}\t{issue.detail}")
        from ._ledger_payloads import LedgerPreflightResult

        _emit_envelope(
            ctx,
            command="ledger.preflight",
            result=LedgerPreflightResult.model_validate(payload),
            lines=lines,
            notices=notices,
        )


def _register_ledger_history_command(app: typer.Typer, *, resolve_transaction_id: ResolveTransactionId) -> None:
    @app.command("history", help=tr("cli.ledger.history.help"))
    def ledger_history(
        ctx: typer.Context,
        transaction_id: str = typer.Argument(..., help=tr("cli.ledger.history.id_help")),
        include_split_siblings: bool = typer.Option(
            False,
            "--include-split-siblings",
            help=tr("cli.ledger.history.include_split_siblings_help"),
        ),
    ) -> None:
        """Emit the chronological event chain for one ledger transaction id."""
        transaction_repository = _tx_repo(_state())
        resolved_id = resolve_transaction_id(transaction_repository, transaction_id)
        object_ids = _history_object_ids(
            transaction_repository,
            resolved_id=resolved_id,
            include_split_siblings=include_split_siblings,
        )
        matches = _collect_ledger_history_events(object_ids)
        lines = [
            f"{tr('cli.ledger.labels.bucket')}\t{transaction_repository.bucket_id}",
            f"{tr('cli.ledger.labels.id')}\t{resolved_id}",
            f"{tr('cli.ledger.labels.event_count')}\t{len(matches)}",
        ]
        lines.extend(
            f"{event.occurred_at.isoformat()}\t{event.event_type.value}\t{event.event_id}" for event in matches
        )
        from ._ledger_payloads import LedgerHistoryResult

        _emit_envelope(
            ctx,
            command="ledger.history",
            result=LedgerHistoryResult.model_validate(
                {
                    "bucket_id": transaction_repository.bucket_id,
                    "transaction_id": resolved_id,
                    "event_count": len(matches),
                    "events": [event.model_dump(mode="json") for event in matches],
                },
            ),
            lines=lines,
        )


def _register_ledger_export_command(app: typer.Typer) -> None:
    @app.command("export", help=tr("cli.ledger.export.help"))
    def ledger_export(
        ctx: typer.Context,
        output: Path = typer.Option(..., "--output", help=tr("cli.ledger.export.output_help")),
        export_kind: ExportSerializationFormat = typer.Option(
            ExportSerializationFormat.CSV,
            "--export-format",
            help=tr("cli.ledger.export.format_help"),
        ),
        include_inactive: bool = typer.Option(
            False,
            "--include-inactive",
            help=tr("cli.ledger.export.include_inactive_help"),
        ),
        period: str | None = typer.Option(
            None,
            "--period",
            help=tr(
                "cli.ledger.export.period_help",
                default=(
                    "Restrict the export to one filing period, as an AEAT token: "
                    "1T-4T (quarters), 0A (annual), 01-12 (months). Combine with --year."
                ),
            ),
        ),
        year: int | None = typer.Option(
            None,
            "--year",
            help=tr("cli.ledger.export.year_help", default="Filing year for --period (e.g. 2024)."),
        ),
        actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.export.actor_help")),
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

        _emit_envelope(
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


def _register_ledger_list_command(app: typer.Typer) -> None:
    @app.command("list", help=tr("cli.ledger.list.help"))
    def ledger_list(
        ctx: typer.Context,
        filters: list[str] = typer.Option([], "--filter", help=tr("cli.ledger.list.filter_help")),
        period: str | None = typer.Option(None, "--period", help=tr("cli.ledger.status.period_help")),
        year: int | None = typer.Option(None, "--year", help=tr("cli.ledger.status.year_help")),
        limit: int | None = typer.Option(None, "--limit", min=1, help=tr("cli.ledger.list.limit_help")),
        offset: int = typer.Option(0, "--offset", min=0, help=tr("cli.ledger.list.offset_help")),
        group: str | None = typer.Option(None, "--group", help=tr("cli.ledger.list.group_filter_help")),
        by_group: bool = typer.Option(False, "--by-group", help=tr("cli.ledger.list.by_group_help")),
        sort_by: LedgerSortField | None = typer.Option(
            None,
            "--sort-by",
            help=tr("cli.ledger.list.sort_by_help"),
        ),
        sort_order: LedgerSortOrder = typer.Option(
            LedgerSortOrder.ASC,
            "--sort-order",
            help=tr("cli.ledger.list.sort_order_help"),
        ),
        hide_llm_rejected: bool = typer.Option(
            False,
            "--hide-llm-rejected",
            help=tr("cli.ledger.list.hide_llm_rejected_help"),
        ),
    ) -> None:
        """List bucket-scoped ledger transactions through the backend read service."""
        transaction_repository = _tx_repo(_state())
        resolved_filters = list(filters)
        if period is not None:
            resolved_filters.append(f"period={period}")
        if year is not None:
            resolved_filters.append(f"year={year}")
        try:
            spec = parse_ledger_list_filter_spec(resolved_filters)
        except FilterParseError as exc:
            raise _bad(
                ledger_filter_parse_error_message(
                    exc,
                    year=_ledger_list_pairing_error_year(resolved_filters, year),
                ),
            ) from exc
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

        _emit_envelope(
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
                },
            ),
            lines=projection.lines,
        )


def _register_ledger_view_command(app: typer.Typer, *, resolve_transaction_id: ResolveTransactionId) -> None:
    @app.command("view", help=tr("cli.ledger.view.help"))
    def ledger_view(
        ctx: typer.Context,
        transaction_id: str = typer.Argument(..., help=tr("cli.ledger.view.transaction_id_help")),
    ) -> None:
        """Read one bucket-scoped ledger transaction through the backend read service."""
        transaction_repository = _tx_repo(_state())
        resolved_id = resolve_transaction_id(transaction_repository, transaction_id)
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
            f"{tr('cli.ledger.labels.value_date', default='Value date')}\t{_field(transaction_payload.value_date)}",
            f"{tr('cli.ledger.labels.amount')}\t{transaction_payload.amount}",
            f"{tr('cli.ledger.labels.currency', default='Currency')}\t{_field(transaction_payload.currency)}",
            f"{tr('cli.ledger.labels.direction', default='Direction')}\t{_field(transaction_payload.direction)}",
            f"{tr('cli.ledger.labels.description')}\t{transaction_payload.description}",
            f"{tr('cli.ledger.labels.counterparty', default='Counterparty')}"
            f"\t{_field(transaction_payload.counterparty)}",
            f"{tr('cli.ledger.labels.business_classification', default='Classification')}"
            f"\t{_field(transaction_payload.business_classification)}",
            f"{tr('cli.ledger.labels.business_pct', default='Business %')}\t{_field(transaction_payload.business_pct)}",
            f"{tr('cli.ledger.labels.category_id', default='Category')}\t{_field(transaction_payload.category_id)}",
            f"{tr('cli.ledger.labels.usage_ratio_id', default='Usage ratio id')}"
            f"\t{_field(transaction_payload.usage_ratio_id)}",
            f"{tr('cli.ledger.labels.taxable_base', default='Taxable base')}"
            f"\t{_field(transaction_payload.taxable_base)}",
            f"{tr('cli.ledger.labels.iva_rate', default='IVA rate')}\t{_field(transaction_payload.iva_rate)}",
            f"{tr('cli.ledger.labels.iva_amount', default='IVA amount')}\t{_field(transaction_payload.iva_amount)}",
            f"{tr('cli.ledger.labels.iva_category')}\t{_field(transaction_payload.iva_category)}",
            f"{tr('cli.ledger.labels.counterparty_eu_member_state', default='EU counterparty')}"
            f"\t{_field(transaction_payload.counterparty_eu_member_state)}",
            f"{tr('cli.ledger.labels.irpf_category', default='IRPF category')}"
            f"\t{_field(transaction_payload.irpf_category)}",
            f"{tr('cli.ledger.labels.notes', default='Notes')}\t{_field(transaction_payload.notes)}",
            f"{tr('cli.ledger.labels.purchase_invoice_evidence_id')}"
            f"\t{_field(transaction_payload.purchase_invoice_evidence_id)}",
            f"{tr('cli.ledger.labels.attachment_ids')}\t{_field(', '.join(transaction_payload.attachment_ids))}",
            f"{tr('cli.ledger.labels.lifecycle_state')}\t{_field(transaction_payload.lifecycle_state)}",
            f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
        ]
        from ._ledger_payloads import LedgerViewResult

        notices: list[Notice] = []
        rejection_notice = _latest_llm_rejection_notice(transaction_repository, resolved_id=resolved_id)
        if rejection_notice is not None:
            notices.append(rejection_notice)
            reason = (rejection_notice.context or {}).get("operator_reason", "")
            label = tr("cli.ledger.view.llm_rejected_label", default="LLM suggestion")
            lines.append(f"{label}\t{tr('cli.ledger.classify.llm_rejected_label')}" + (f": {reason}" if reason else ""))

        _emit_envelope(
            ctx,
            command="ledger.view",
            result=LedgerViewResult.model_validate(result_payload.model_dump(mode="json")),
            lines=lines,
            notices=notices,
        )


def _register_ledger_status_command(app: typer.Typer) -> None:
    @app.command("status", help=tr("cli.ledger.status.help"))
    def ledger_status(
        ctx: typer.Context,
        period: str | None = typer.Option(None, "--period", help=tr("cli.ledger.status.period_help")),
        year: int | None = typer.Option(
            None,
            "--year",
            help=tr("cli.ledger.status.year_help", default="Filing year for --period (e.g. 2024)."),
        ),
    ) -> None:
        """Summarize active-bucket ledger state through the backend status service."""
        transaction_repository = _tx_repo(_state())
        report = summarize_manual_transactions(
            bucket_id=transaction_repository.bucket_id,
            period=_optional_canonical_period(period, year=year),
            transaction_repository=transaction_repository,
        )
        transactions = transaction_repository.load()
        lines = [
            f"{tr('cli.ledger.labels.bucket')}\t{report.bucket_id}",
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
                    f"{tr('cli.ledger.labels.period')}\t{report.period.registry_token} {report.period.year}",
                    f"{tr('cli.ledger.labels.checked')}\t{report.checked_transaction_count}",
                    f"{tr('cli.ledger.labels.readiness_issues')}\t{report.readiness_issue_count}",
                    f"{tr('cli.ledger.labels.ready')}\t{report.ready}",
                ],
            )
            from ...application.ledger import preflight_ledger_tax_readiness

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
                    _ledger_status_readiness_issue_line(transaction, reason=issue.reason.value, detail=issue.detail),
                )
        from ...application.aggregation import stale_filed_revisions
        from ...domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
        from ...domain.modelos._repository import WorkUnitCatalogueRepository

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
                    ),
                ),
            )

        from ._ledger_payloads import LedgerStatusResult

        _emit_envelope(
            ctx,
            command="ledger.status",
            result=LedgerStatusResult.model_validate(report.model_dump(mode="json")),
            lines=lines,
        )


def _register_ledger_track_command(app: typer.Typer, *, resolve_transaction_id: ResolveTransactionId) -> None:
    @app.command("track", help=tr("cli.ledger.track.help"))
    def ledger_track(
        ctx: typer.Context,
        transaction_id: str = typer.Argument(..., help=tr("cli.ledger.track.transaction_id_help")),
    ) -> None:
        """Show audit lineage for one bucket-scoped ledger transaction."""
        transaction_repository = _tx_repo(_state())
        resolved_id = resolve_transaction_id(transaction_repository, transaction_id)
        result = get_manual_transaction(
            bucket_id=transaction_repository.bucket_id,
            transaction_id=resolved_id,
            transaction_repository=transaction_repository,
        )
        from ._ledger_payloads import LedgerTrackResult

        participated_in = _ledger_track_participated_in(
            transaction_id=result.ref.transaction_id,
            bucket_id=transaction_repository.bucket_id,
        )

        _emit_envelope(
            ctx,
            command="ledger.track",
            result=LedgerTrackResult.model_validate(
                {
                    "bucket_id": result.ref.bucket_id,
                    "transaction": ledger_transaction_payload(result.transaction).model_dump(mode="json"),
                    "tracking": ledger_transaction_tracking_payload(result.transaction).model_dump(mode="json"),
                    "participated_in": participated_in,
                },
            ),
            lines=_ledger_track_lines(result.ref.transaction_id, result.transaction),
        )


def _ledger_track_participated_in(
    *,
    transaction_id: str,
    bucket_id: str | None,
) -> list[dict[str, object]] | None:
    """Return the finalized-revision participations for ``transaction_id``, or ``None``.

    Surfaces the inverse audit trail on the ``ledger track`` lineage output:
    every finalized modelo revision and filing that consumed this transaction.
    Returns ``None`` when the transaction appears in no finalized revision so the
    field is omitted from the JSON for transactions with no declarations.
    """
    from ...application.ledger import get_transaction_participation
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
    """Return the chronological union of LEDGER-history events across ``object_ids``."""
    event_catalogue = BucketEventHistoryRepository().load()
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
    matches.sort(key=lambda event: event.occurred_at)
    return matches


def _latest_llm_rejection_notice(
    transaction_repository: TransactionCatalogueRepository,
    *,
    resolved_id: str,
) -> Notice | None:
    """Return a notice when the row's most recent LLM decision was a rejection.

    Reads the bucket-event history for the transaction (and its edit lineage) and
    finds the latest LLM-decision event. When that is a rejection — i.e. the
    operator declined an LLM suggestion and has not since accepted one — `view`
    surfaces a one-line advisory carrying the recorded reason, so prior judgement
    is visible without opening `history`
    (``cli-notices-are-the-only-diagnostic-channel``).
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
            default=(
                "The most recent LLM suggestion for this transaction was rejected; classify it manually when ready."
            ),
        ),
        suggestion=f"aeat app ledger classify {resolved_id} --classification BUSINESS --category-id <id>",
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


__all__ = ["register_read_commands"]
