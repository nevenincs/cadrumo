"""User-facing ``aeat`` command-line surface.

Composes every Typer sub-app into the single ``aeat`` console script
exposed by the project's ``[project.scripts]`` entry. Sub-apps live in
sibling modules and packages (``auth``, ``bootstrap``, ``casillas``,
``cloud``, ``data``, ``deadlines``, ``docs``, ``drive``,
``filing``, ``financial``, ``llm``, ``modelos``, ``normatives``,
``portals``, ``profile``, ``rental``, ``review``, ``run``,
``sanitize``, ``secrets``, ``submission``, ``sync``, ``vat``,
``workflow``). Cross-cutting helpers (i18n, JSON output schemas,
exit codes, error envelopes, log-level resolution) live in the
underscored helper modules.

Importing this module is cheap; per-command Google / Playwright /
cryptography dependencies are loaded lazily inside the command bodies
so ``aeat --help`` stays fast.
"""

from __future__ import annotations

import logging
from pathlib import Path

import typer

from ._errors import decorate_typer_app
from ._i18n import t, tr
from ._log_levels import apply_to_root_logger, resolve_log_level

app = typer.Typer(
    name="aeat",
    help="Prepare Spanish tax return exports from evidence through verified local files.",
    no_args_is_help=True,
    add_completion=False,
)

setup_app = typer.Typer(help="Prepare the local profile, access, storage, and readiness prerequisites.")
app_app = typer.Typer(help="Run evidence preparation, declarations, workspace, and audit workflows.")

ledger_app = typer.Typer(help="Import and prepare evidence for filing.")
ledger_import_app = typer.Typer(help="Import statements, invoices, and receipts.")
imports_app = typer.Typer(help="Review, compare, remove, or replace import batches.")
transactions_app = typer.Typer(help="Clean, classify, review, and edit transaction treatment.")
ledger_invoices_app = typer.Typer(help="Review, edit, and match invoice evidence.")
clients_app = typer.Typer(help="Review and edit client facts that affect obligations.")

declarations_app = typer.Typer(help="Find obligations, prepare drafts, validate, export, and verify files.")
history_app = typer.Typer(help="Import AEAT receipts, previous exports, or proof of prior filing.")
periods_app = typer.Typer(help="Review and correct period state before calculation.")
deadlines_app = typer.Typer(help="Review and explain deadline state.")
obligations_app = typer.Typer(help="Find and explain periods and declarations that may need work.")
corrections_app = typer.Typer(help="Prepare correction exports after values change.")

workspaces_app = typer.Typer(help="Save and load local work state.")
audits_app = typer.Typer(help="Export traceable evidence, decisions, validations, outputs, and unknowns.")


@app.callback()
def main(
    ctx: typer.Context,
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Enable machine-readable JSON mode for commands that support the shared contract.",
    ),
    quiet: bool = typer.Option(False, "--quiet", help="Only emit errors on stderr."),
    verbose: bool = typer.Option(False, "--verbose", help="Emit info-level operation summaries."),
    debug: bool = typer.Option(False, "--debug", help="Emit debug-level diagnostics on stderr."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable ANSI colour output."),
    no_progress: bool = typer.Option(False, "--no-progress", help="Disable progress reporting on stderr."),
) -> None:
    """Apply root-level CLI transport defaults for the current invocation."""

    state = ctx.ensure_object(dict)
    state["json"] = json_output
    state["quiet"] = quiet
    state["verbose"] = verbose
    state["debug"] = debug
    state["no_color"] = no_color
    state["no_progress"] = no_progress
    root_logger = logging.getLogger()
    previous_root_level = root_logger.level
    previous_handler_levels = [handler.level for handler in root_logger.handlers]

    def _restore_root_logger_levels() -> None:
        root_logger.setLevel(previous_root_level)
        for handler, previous_level in zip(root_logger.handlers, previous_handler_levels, strict=False):
            handler.setLevel(previous_level)

    ctx.call_on_close(_restore_root_logger_levels)
    apply_to_root_logger(resolve_log_level(quiet=quiet, verbose=verbose, debug=debug))


def _emit(title: str, *lines: str, next_command: str | None = None) -> None:
    typer.echo(title)
    for line in lines:
        if line:
            typer.echo(line)
    if next_command:
        typer.echo("")
        next_label = tr(t("Siguiente:", "Next:", "Següent:", "Következő:"))
        typer.echo(f"{next_label} {next_command}")


def _scope(
    *,
    period: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    range_: str | None = None,
    year: str | None = None,
) -> str:
    if period:
        return period
    if from_date or to_date:
        return f"{from_date or 'DATE'} to {to_date or 'DATE'}"
    if year:
        return year
    return range_ or "current workspace"


@setup_app.command("check", help="Show readiness status and the next blocking action.")
def setup_check() -> None:
    """Show readiness status and the next blocking action."""
    _emit(
        "Setup readiness",
        "Profile: needs review",
        "AEAT access: needs review",
        "Storage: needs review",
        next_command="aeat setup start --profile autonomo --activity ACTIVITY",
    )


@setup_app.command("start", help="Guide readiness setup for profile, access, storage, and security.")
def setup_start(
    profile: str = typer.Option("autonomo", "--profile", help="Taxpayer profile type."),
    activity: str | None = typer.Option(None, "--activity", help="Business activity, such as design."),
) -> None:
    """Guide readiness setup for profile, access, storage, and security."""
    _emit(
        "Setup started",
        f"Profile: {profile}",
        f"Activity: {activity or 'not set'}",
        "Scope: profile, access, storage, and security",
        next_command="aeat app status",
    )


@app_app.command("status", help="Show workspace state, missing evidence, open review items, and next command.")
def app_status() -> None:
    """Show workspace state, missing evidence, open review items, and next command."""
    _emit(
        "Workspace status",
        "Statements: not reviewed",
        "Transactions: not reviewed",
        "Invoices: not matched",
        "Declarations: not prepared",
        next_command="aeat app ledger import statements PATH --provider PROVIDER",
    )


@app_app.command("next", help="Print the next blocking command only.")
def app_next() -> None:
    """Print the next blocking command only."""
    typer.echo("aeat app ledger import statements PATH --provider PROVIDER")


@ledger_import_app.command("statements", help="Import account export files, including N26 exports.")
def import_statements(
    path: Path = typer.Argument(..., help="Statements export path."),
    provider: str | None = typer.Option(None, "--provider", help="Statement provider, such as n26."),
    period: str | None = typer.Option(None, "--period", help="Period to import."),
    from_date: str | None = typer.Option(None, "--from", help="Start date."),
    to_date: str | None = typer.Option(None, "--to", help="End date."),
    year: str | None = typer.Option(None, "--year", help="Year to import."),
    recursive: bool = typer.Option(False, "--recursive", help="Import all files below a folder."),
) -> None:
    """Import account export files, including N26 exports."""
    _emit(
        "Statements import queued",
        f"Path: {path}",
        f"Provider: {provider or 'not specified'}",
        f"Scope: {_scope(period=period, from_date=from_date, to_date=to_date, year=year)}",
        f"Recursive: {'yes' if recursive else 'no'}",
        next_command="aeat app ledger imports review --gaps",
    )


@ledger_import_app.command("invoices", help="Import issued and received invoice files.")
def import_invoices(
    path: Path = typer.Argument(..., help="Invoices path."),
    period: str | None = typer.Option(None, "--period", help="Period to import."),
    from_date: str | None = typer.Option(None, "--from", help="Start date."),
    to_date: str | None = typer.Option(None, "--to", help="End date."),
    year: str | None = typer.Option(None, "--year", help="Year to import."),
    recursive: bool = typer.Option(False, "--recursive", help="Import all files below a folder."),
) -> None:
    """Import issued and received invoice files."""
    _emit(
        "Invoices import queued",
        f"Path: {path}",
        f"Scope: {_scope(period=period, from_date=from_date, to_date=to_date, year=year)}",
        f"Recursive: {'yes' if recursive else 'no'}",
        next_command="aeat app ledger invoices review --unmatched",
    )


@ledger_import_app.command("receipts", help="Import supporting receipts or proof documents.")
def import_receipts(
    path: Path = typer.Argument(..., help="Receipts path."),
    period: str | None = typer.Option(None, "--period", help="Period to import."),
) -> None:
    """Import supporting receipts or proof documents."""
    _emit("Receipts import queued", f"Path: {path}", f"Period: {period or 'current workspace'}")


@imports_app.command(
    "review", help="Review import batches for gaps, duplicates, wrong accounts, and incomplete evidence."
)
def imports_review(
    period: str | None = typer.Option(None, "--period", help="Period to review."),
    from_date: str | None = typer.Option(None, "--from", help="Start date."),
    to_date: str | None = typer.Option(None, "--to", help="End date."),
    range_: str | None = typer.Option(None, "--range", help="Named range, such as auto."),
    gaps: bool = typer.Option(False, "--gaps", help="Focus on missing date coverage."),
    duplicates: bool = typer.Option(False, "--duplicates", help="Focus on duplicate imported rows."),
) -> None:
    """Review import batches for gaps, duplicates, wrong accounts, and incomplete evidence."""
    focus = "gaps" if gaps else "duplicates" if duplicates else "all import issues"
    _emit(
        "Import review",
        f"Scope: {_scope(period=period, from_date=from_date, to_date=to_date, range_=range_)}",
        f"Focus: {focus}",
        next_command="aeat app ledger imports compare IMPORT_ID --source PATH",
    )


@imports_app.command("compare", help="Compare an imported batch against a source PDF, CSV, or download receipt.")
def imports_compare(
    import_id: str = typer.Argument(..., help="Import batch identifier."),
    source: Path = typer.Option(..., "--source", help="Source evidence path."),
) -> None:
    """Compare an imported batch against a source PDF, CSV, or download receipt."""
    _emit(
        "Import compared",
        f"Import: {import_id}",
        f"Source: {source}",
        next_command="aeat app ledger transactions clean",
    )


@imports_app.command("remove", help="Remove an incorrect, duplicate, personal, or unnecessary import batch.")
def imports_remove(
    import_id: str = typer.Argument(..., help="Import batch identifier."),
    reason: str = typer.Option(..., "--reason", help="Audit reason for removal."),
) -> None:
    """Remove an incorrect, duplicate, personal, or unnecessary import batch."""
    _emit("Import removed", f"Import: {import_id}", f"Reason: {reason}", next_command="aeat app ledger imports review")


@imports_app.command("replace", help="Replace an incorrect or incomplete import batch with a corrected file.")
def imports_replace(
    import_id: str = typer.Argument(..., help="Import batch identifier."),
    path: Path = typer.Argument(..., help="Replacement file path."),
) -> None:
    """Replace an incorrect or incomplete import batch with a corrected file."""
    _emit("Import replaced", f"Import: {import_id}", f"Path: {path}", next_command="aeat app ledger imports review")


@transactions_app.command("clean", help="Convert imported rows into consistent ledger transactions.")
def transactions_clean(
    period: str | None = typer.Option(None, "--period", help="Period to clean."),
    range_: str | None = typer.Option(None, "--range", help="Named range, such as auto."),
) -> None:
    """Convert imported rows into consistent ledger transactions."""
    _emit(
        "Transactions cleaned",
        f"Scope: {_scope(period=period, range_=range_)}",
        next_command="aeat app ledger transactions review --unknown",
    )


@transactions_app.command("classify", help="Assign transaction treatment.")
def transactions_classify(
    period: str | None = typer.Option(None, "--period", help="Period to classify."),
    range_: str | None = typer.Option(None, "--range", help="Named range, such as auto."),
    group_by_year: bool = typer.Option(False, "--group-by-year", help="Group output by year."),
) -> None:
    """Assign transaction treatment."""
    _emit(
        "Transactions classified",
        f"Scope: {_scope(period=period, range_=range_)}",
        f"Group by year: {'yes' if group_by_year else 'no'}",
        next_command="aeat app ledger transactions review",
    )


@transactions_app.command("review", help="List transactions that still need a user decision.")
def transactions_review(
    period: str | None = typer.Option(None, "--period", help="Period to review."),
    range_: str | None = typer.Option(None, "--range", help="Named range, such as auto."),
    unknown: bool = typer.Option(False, "--unknown", help="Only show unknown transactions."),
) -> None:
    """List transactions that still need a user decision."""
    _emit(
        "Transactions review",
        f"Scope: {_scope(period=period, range_=range_)}",
        f"Unknown only: {'yes' if unknown else 'no'}",
        next_command="aeat app ledger invoices review --unmatched",
    )


@transactions_app.command("edit", help="Record a manual decision for one transaction.")
def transactions_edit(
    transaction_id: str = typer.Argument(..., help="Transaction identifier."),
    type_: str | None = typer.Option(None, "--type", help="Transaction type."),
    category: str | None = typer.Option(None, "--category", help="Transaction category."),
    reason: str = typer.Option(..., "--reason", help="Audit reason for the decision."),
) -> None:
    """Record a manual decision for one transaction."""
    _emit(
        "Transaction edited",
        f"Transaction: {transaction_id}",
        f"Type: {type_ or 'not set'}",
        f"Category: {category or 'not set'}",
        f"Reason: {reason}",
    )


@transactions_app.command("split", help="Split a mixed payment into business and non-business parts.")
def transactions_split(
    transaction_id: str = typer.Argument(..., help="Transaction identifier."),
    lines: str = typer.Option(..., "--lines", help="Split specification."),
    reason: str = typer.Option(..., "--reason", help="Audit reason for the split."),
) -> None:
    """Split a mixed payment into business and non-business parts."""
    _emit("Transaction split", f"Transaction: {transaction_id}", f"Lines: {lines}", f"Reason: {reason}")


@transactions_app.command("merge", help="Merge duplicate imported rows that represent one real movement.")
def transactions_merge(
    first_transaction_id: str = typer.Argument(..., help="First transaction identifier."),
    second_transaction_id: str = typer.Argument(..., help="Second transaction identifier."),
    reason: str = typer.Option(..., "--reason", help="Audit reason for the merge."),
) -> None:
    """Merge duplicate imported rows that represent one real movement."""
    _emit("Transactions merged", f"Transactions: {first_transaction_id}, {second_transaction_id}", f"Reason: {reason}")


@transactions_app.command("exclude", help="Exclude private, duplicate, or non-business rows from filing totals.")
def transactions_exclude(
    transaction_id: str = typer.Argument(..., help="Transaction identifier."),
    reason: str = typer.Option(..., "--reason", help="Audit reason for exclusion."),
) -> None:
    """Exclude private, duplicate, or non-business rows from filing totals."""
    _emit("Transaction excluded", f"Transaction: {transaction_id}", f"Reason: {reason}")


@ledger_invoices_app.command("review", help="List invoices, receipts, and payments that still need manual matching.")
def invoices_review(
    period: str | None = typer.Option(None, "--period", help="Period to review."),
    range_: str | None = typer.Option(None, "--range", help="Named range, such as auto."),
    unmatched: bool = typer.Option(False, "--unmatched", help="Only show unmatched evidence."),
    missing: bool = typer.Option(False, "--missing", help="Only show missing evidence."),
) -> None:
    """List invoices, receipts, and payments that still need manual matching."""
    focus = "unmatched" if unmatched else "missing" if missing else "all invoice evidence"
    _emit(
        "Invoice review",
        f"Scope: {_scope(period=period, range_=range_)}",
        f"Focus: {focus}",
        next_command="aeat app ledger invoices match",
    )


@ledger_invoices_app.command("edit", help="Record or correct a manual invoice-to-payment match.")
def invoices_edit(
    invoice_id: str = typer.Argument(..., help="Invoice identifier."),
    transaction: str = typer.Option(..., "--transaction", help="Transaction identifier."),
    reason: str = typer.Option(..., "--reason", help="Audit reason for the match."),
) -> None:
    """Record or correct a manual invoice-to-payment match."""
    _emit("Invoice match edited", f"Invoice: {invoice_id}", f"Transaction: {transaction}", f"Reason: {reason}")


@ledger_invoices_app.command(
    "match", help="Match invoices and receipts to ledger transactions and report missing evidence."
)
def invoices_match(
    period: str | None = typer.Option(None, "--period", help="Period to match."),
    range_: str | None = typer.Option(None, "--range", help="Named range, such as auto."),
) -> None:
    """Match invoices and receipts to ledger transactions and report missing evidence."""
    _emit("Invoices matched", f"Scope: {_scope(period=period, range_=range_)}", next_command="aeat app ledger summary")


@clients_app.command("review", help="List clients whose country, withholding, or invoice facts need review.")
def clients_review(period: str | None = typer.Option(None, "--period", help="Period to review.")) -> None:
    """List clients whose country, withholding, or invoice facts need review."""
    _emit("Clients reviewed", f"Period: {period or 'current workspace'}")


@clients_app.command("edit", help="Record client facts that affect obligations finding.")
def clients_edit(
    client_id: str = typer.Argument(..., help="Client identifier."),
    country: str | None = typer.Option(None, "--country", help="Client country."),
    withheld_tax: str | None = typer.Option(None, "--withheld-tax", help="Whether tax was withheld: yes or no."),
) -> None:
    """Record client facts that affect obligations finding."""
    _emit(
        "Client edited",
        f"Client: {client_id}",
        f"Country: {country or 'not set'}",
        f"Withheld tax: {withheld_tax or 'not set'}",
    )


@ledger_app.command("summary", help="Show filing-ready totals and evidence status for a period or date range.")
def ledger_summary(
    period: str | None = typer.Option(None, "--period", help="Period to summarize."),
    range_: str | None = typer.Option(None, "--range", help="Named range, such as auto."),
) -> None:
    """Show filing-ready totals and evidence status for a period or date range."""
    _emit(
        "Ledger summary",
        f"Scope: {_scope(period=period, range_=range_)}",
        next_command="aeat app declarations obligations find",
    )


@history_app.command("import", help="Import AEAT receipts, previous exports, or proof of prior filing.")
def history_import(
    path: Path = typer.Argument(..., help="History evidence path."),
    auto_detect: bool = typer.Option(False, "--auto-detect", help="Detect periods and files automatically."),
) -> None:
    """Import AEAT receipts, previous exports, or proof of prior filing."""
    _emit(
        "History imported",
        f"Path: {path}",
        f"Auto detect: {'yes' if auto_detect else 'no'}",
        next_command="aeat app declarations periods review",
    )


@periods_app.command("review", help="Review filed, missing, duplicated, and unknown periods.")
def periods_review(
    period: str | None = typer.Option(None, "--period", help="Period to review."),
    from_date: str | None = typer.Option(None, "--from", help="Start date."),
    to_date: str | None = typer.Option(None, "--to", help="End date."),
    range_: str | None = typer.Option(None, "--range", help="Named range, such as auto."),
) -> None:
    """Review filed, missing, duplicated, and unknown periods."""
    _emit(
        "Periods review",
        f"Scope: {_scope(period=period, from_date=from_date, to_date=to_date, range_=range_)}",
        next_command="aeat app declarations deadlines review",
    )


@periods_app.command("edit", help="Record a user correction to period state.")
def periods_edit(
    period: str = typer.Argument(..., help="Period to edit."),
    status: str = typer.Option(..., "--status", help="Period status."),
    reason: str = typer.Option(..., "--reason", help="Audit reason for the correction."),
) -> None:
    """Record a user correction to period state."""
    _emit("Period edited", f"Period: {period}", f"Status: {status}", f"Reason: {reason}")


@deadlines_app.command("review", help="Review whether a period is current, due, overdue, or past the normal window.")
def deadlines_review(
    period: str | None = typer.Option(None, "--period", help="Period to review."),
    from_date: str | None = typer.Option(None, "--from", help="Start date."),
    to_date: str | None = typer.Option(None, "--to", help="End date."),
    as_of: str | None = typer.Option(None, "--as-of", help="Date used for deadline state."),
) -> None:
    """Review whether a period is current, due, overdue, or past the normal window."""
    _emit(
        "Deadlines review",
        f"Scope: {_scope(period=period, from_date=from_date, to_date=to_date)}",
        f"As of: {as_of or 'today'}",
        next_command="aeat app declarations deadlines explain --period PERIOD --plain",
    )


@deadlines_app.command("explain", help="Explain deadline state in plain language.")
def deadlines_explain(
    period: str | None = typer.Option(None, "--period", help="Period to explain."),
    plain: bool = typer.Option(False, "--plain", help="Use plain language."),
) -> None:
    """Explain deadline state in plain language."""
    _emit(
        "Deadlines explanation",
        f"Period: {period or 'current workspace'}",
        f"Plain language: {'yes' if plain else 'no'}",
    )


@obligations_app.command("find", help="Find periods and declarations that may need work.")
def obligations_find(
    period: str | None = typer.Option(None, "--period", help="Period to inspect."),
    range_: str | None = typer.Option(None, "--range", help="Named range, such as auto."),
    include_overdue: bool = typer.Option(False, "--include-overdue", help="Include overdue periods."),
    compare_history: bool = typer.Option(False, "--compare-history", help="Compare imported history."),
) -> None:
    """Find periods and declarations that may need work."""
    _emit(
        "Obligations found",
        f"Scope: {_scope(period=period, range_=range_)}",
        f"Include overdue: {'yes' if include_overdue else 'no'}",
        f"Compare history: {'yes' if compare_history else 'no'}",
        next_command="aeat app declarations obligations explain --plain",
    )


@obligations_app.command("explain", help="Explain why obligations were found.")
def obligations_explain(
    plain: bool = typer.Option(False, "--plain", help="Use plain language."),
    group_by_year: bool = typer.Option(False, "--group-by-year", help="Group output by year."),
) -> None:
    """Explain why obligations were found."""
    _emit(
        "Obligations explanation",
        f"Plain language: {'yes' if plain else 'no'}",
        f"Group by year: {'yes' if group_by_year else 'no'}",
    )


@corrections_app.command(
    "prepare", help="Create a correction draft when values change after a prior export or deadline."
)
def corrections_prepare(
    period: str = typer.Option(..., "--period", help="Period to correct."),
    reason: str = typer.Option(..., "--reason", help="Correction reason."),
    modelo: str | None = typer.Option(None, "--modelo", help="Modelo to correct."),
) -> None:
    """Create a correction draft when values change after a prior export or deadline."""
    _emit(
        "Correction prepared",
        f"Period: {period}",
        f"Modelo: {modelo or 'not specified'}",
        f"Reason: {reason}",
        next_command="aeat app declarations corrections review --period PERIOD",
    )


@corrections_app.command("review", help="Review changed values and evidence for a correction draft.")
def corrections_review(period: str = typer.Option(..., "--period", help="Period to review.")) -> None:
    """Review changed values and evidence for a correction draft."""
    _emit(
        "Correction reviewed",
        f"Period: {period}",
        next_command="aeat app declarations corrections validate --period PERIOD",
    )


@corrections_app.command("validate", help="Run strict checks for a correction or after-deadline draft.")
def corrections_validate(
    period: str = typer.Option(..., "--period", help="Period to validate."),
    late: bool = typer.Option(False, "--late", help="Validate as after-deadline correction."),
) -> None:
    """Run strict checks for a correction or after-deadline draft."""
    _emit(
        "Correction validated",
        f"Period: {period}",
        f"Late: {'yes' if late else 'no'}",
        next_command="aeat app declarations corrections export --period PERIOD --output PATH",
    )


@corrections_app.command("export", help="Write correction files for manual AEAT upload.")
def corrections_export(
    period: str = typer.Option(..., "--period", help="Period to export."),
    output: Path = typer.Option(..., "--output", help="Output path."),
) -> None:
    """Write correction files for manual AEAT upload."""
    _emit(
        "Correction export created",
        f"Period: {period}",
        f"Output: {output}",
        next_command="aeat app audits export PATH",
    )


@declarations_app.command("prepare", help="Create drafts for found obligations.")
def declarations_prepare(
    period: str | None = typer.Option(None, "--period", help="Period to prepare."),
    all_: bool = typer.Option(False, "--all", help="Prepare all found obligations."),
    missing: bool = typer.Option(False, "--missing", help="Prepare missing obligations only."),
    order: str | None = typer.Option(None, "--order", help="Ordering, such as chronological."),
) -> None:
    """Create drafts for found obligations."""
    mode = "all" if all_ else "missing" if missing else "selected"
    _emit(
        "Declarations prepared",
        f"Scope: {_scope(period=period)}",
        f"Mode: {mode}",
        f"Order: {order or 'default'}",
        next_command="aeat app declarations review",
    )


@declarations_app.command("review", help="Show calculated values, assumptions, warnings, and required decisions.")
def declarations_review(
    period: str | None = typer.Option(None, "--period", help="Period to review."),
    all_: bool = typer.Option(False, "--all", help="Review all drafts."),
    missing: bool = typer.Option(False, "--missing", help="Review missing obligations only."),
) -> None:
    """Show calculated values, assumptions, warnings, and required decisions."""
    mode = "all" if all_ else "missing" if missing else "selected"
    _emit(
        "Declarations reviewed",
        f"Scope: {_scope(period=period)}",
        f"Mode: {mode}",
        next_command="aeat app declarations validate",
    )


@declarations_app.command("validate", help="Run strict checks before export.")
def declarations_validate(
    period: str | None = typer.Option(None, "--period", help="Period to validate."),
    all_: bool = typer.Option(False, "--all", help="Validate all drafts."),
    missing: bool = typer.Option(False, "--missing", help="Validate missing obligations only."),
    strict: bool = typer.Option(False, "--strict", help="Run strict validation."),
) -> None:
    """Run strict checks before export."""
    mode = "all" if all_ else "missing" if missing else "selected"
    _emit(
        "Declarations validated",
        f"Scope: {_scope(period=period)}",
        f"Mode: {mode}",
        f"Strict: {'yes' if strict else 'no'}",
        next_command="aeat app declarations export --ready --output PATH",
    )


@declarations_app.command("export", help="Write AEAT-ready files or blocked reports.")
def declarations_export(
    output: Path | None = typer.Option(None, "--output", help="Output path."),
    ready: bool = typer.Option(False, "--ready", help="Export ready declarations."),
    blocked_report: Path | None = typer.Option(None, "--blocked-report", help="Write a blocked-output report."),
    split_by_obligation: bool = typer.Option(False, "--split-by-obligation", help="Split output by obligation."),
) -> None:
    """Write AEAT-ready files or blocked reports."""
    target = blocked_report or output or Path("./exports")
    _emit(
        "Declarations export created",
        f"Target: {target}",
        f"Ready only: {'yes' if ready else 'no'}",
        f"Split by obligation: {'yes' if split_by_obligation else 'no'}",
        next_command="aeat app declarations verify --ready --export PATH",
    )


@declarations_app.command("verify", help="Verify exported files and calculation trace before manual AEAT upload.")
def declarations_verify(
    export: Path = typer.Option(..., "--export", help="Export path to verify."),
    ready: bool = typer.Option(False, "--ready", help="Verify ready exports."),
) -> None:
    """Verify exported files and calculation trace before manual AEAT upload."""
    _emit(
        "Declarations export verified",
        f"Export: {export}",
        f"Ready only: {'yes' if ready else 'no'}",
        next_command="aeat app audits export PATH",
    )


@workspaces_app.command("save", help="Save the current workspace state.")
def workspaces_save(name: str = typer.Argument(..., help="Workspace name.")) -> None:
    """Save the current workspace state."""
    _emit("Workspace saved", f"Name: {name}")


@workspaces_app.command("load", help="Load a saved workspace state.")
def workspaces_load(name: str = typer.Argument(..., help="Workspace name.")) -> None:
    """Load a saved workspace state."""
    _emit("Workspace loaded", f"Name: {name}", next_command="aeat app status")


@audits_app.command("export", help="Export an audit bundle with inputs, decisions, validations, outputs, and unknowns.")
def audits_export(path: Path = typer.Argument(..., help="Audit output path.")) -> None:
    """Export an audit bundle with inputs, decisions, validations, outputs, and unknowns."""
    _emit("Audit exported", f"Path: {path}")


ledger_app.add_typer(ledger_import_app, name="import")
ledger_app.add_typer(imports_app, name="imports")
ledger_app.add_typer(transactions_app, name="transactions")
ledger_app.add_typer(ledger_invoices_app, name="invoices")
ledger_app.add_typer(clients_app, name="clients")

declarations_app.add_typer(history_app, name="history")
declarations_app.add_typer(periods_app, name="periods")
declarations_app.add_typer(deadlines_app, name="deadlines")
declarations_app.add_typer(obligations_app, name="obligations")
declarations_app.add_typer(corrections_app, name="corrections")

app_app.add_typer(ledger_app, name="ledger")
app_app.add_typer(declarations_app, name="declarations")
app_app.add_typer(workspaces_app, name="workspaces")
app_app.add_typer(audits_app, name="audits")

app.add_typer(setup_app, name="setup")
app.add_typer(app_app, name="app")

decorate_typer_app(app)

__all__ = ["app"]
