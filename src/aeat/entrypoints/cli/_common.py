"""Shared CLI transport helpers used across all ``aeat`` command groups.

Provides output helpers, period normalisation, and repository accessors
used by the ledger, modelo, and config command groups. The repository
accessors return typed domain objects: :class:`TransactionCatalogue` and
:class:`TransactionCatalogueRepository` for transaction ledger access,
:class:`InvoiceCatalogue` and :class:`InvoiceCatalogueRepository` for
invoice data, :class:`ModeloDraft` for in-progress modelo drafts, and
:class:`TaxpayerProfile` for deadline and period calculations.

Application-layer and domain symbols are imported lazily inside each
helper to avoid pulling the registry parse into fast-path commands such
as ``aeat --version``.
"""

from __future__ import annotations

import re as _re
from collections.abc import Iterable
from datetime import date as _date
from decimal import Decimal
from typing import TYPE_CHECKING, NoReturn

import typer

from ...core import Modelo
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ...core.output_rendering import render_command_output

# The application- and domain-layer symbols below are imported lazily,
# inside the helpers that use them at runtime. A module-level import
# would pull the application layer — and transitively the registry
# parse — into every consumer of this transport module, including the
# ``aeat --version`` / ``aeat --help`` fast paths that import ``_emit``
# but never reach a registry-backed helper. ``from __future__ import
# annotations`` keeps the type annotations valid as strings without a
# runtime import; the ``TYPE_CHECKING`` block keeps static checkers
# resolving them.
if TYPE_CHECKING:
    from ...application.auth import AuthProviderListing
    from ...application.workflow import WorkflowState
    from ...domain.calculations.registry import ModeloRevision
    from ...domain.contribuyente import ProfileKey
    from ...domain.deadlines import TaxpayerProfile
    from ...domain.filing import ModeloDraft, ModeloDraftRepository
    from ...domain.invoices import InvoiceCatalogue, InvoiceCatalogueRepository
    from ...domain.transactions import TransactionCatalogue, TransactionCatalogueRepository

# ---------------------------------------------------------------------
# Transport helpers
# ---------------------------------------------------------------------

_FORMAT_TEXT = "text"
_FORMAT_JSON = "json"
_FORMAT_TABLE = "table"


def _format_of(ctx: typer.Context) -> str:
    state = ctx.ensure_object(dict)
    return state.get("format", _FORMAT_TEXT)


def _emit(ctx: typer.Context, payload: object, lines: Iterable[str]) -> None:
    """Render the result either as JSON or as line-formatted text."""
    rendered = render_command_output(format_name=_format_of(ctx), payload=payload, lines=lines)
    if rendered.text:
        typer.echo(rendered.text)


def _emit_envelope(
    ctx: typer.Context,
    *,
    command: str,
    result: object,
    lines: Iterable[str],
) -> None:
    """Render a typed result through :class:`SchemaEnvelope` for JSON or as text lines.

    JSON mode goes through :func:`emit_json_success` so the payload is
    wrapped in ``{"schema_version": ..., "command": ..., "result": ...,
    "warnings": ...}``; text mode keeps the existing line iterator
    unchanged so terminal output is unaffected.

    Args:
        ctx: Typer context (used to discover the requested output format).
        command: Stable command path string (matches the
            ``@register_schema(...)`` argument on the result model).
        result: The strict-validated payload model to surface as
            ``envelope.result``. Must be a pydantic model registered
            under ``command`` in :data:`SCHEMA_REGISTRY`; the CLI
            conformance gate enforces this at test time.
        lines: Iterable of pre-formatted text lines (used unchanged
            for text mode).
    """
    from ...core.json_contract import emit_json_success

    format_name = _format_of(ctx)
    if format_name == _FORMAT_JSON:
        emit_json_success(command, result)
        return
    # Route non-JSON paths through render_command_output so unsupported
    # ``--format`` values (e.g. ``xml``) raise the same refusal contract
    # that the bare ``_emit`` path enforces. ``render_command_output``
    # ignores ``payload`` outside JSON mode and emits the line iterator.
    rendered = render_command_output(format_name=format_name, payload=result, lines=lines)
    if rendered.text:
        typer.echo(rendered.text)


def _bad(message: str) -> typer.BadParameter:
    return typer.BadParameter(message)


def _no_active_profile_refusal() -> Exception:
    """Return the canonical no-active-profile refusal exception.

    A missing active profile is a workflow-state refusal, not a
    user-input error: it must read as ``Refused. No active profile…``
    rather than be wrapped in a Click ``Invalid value:`` header. Every
    cold-start command path — ledger, modelo work, overview — raises
    this same translated refusal so first-contact guidance is
    consistent across the CLI surface.
    """
    from ._errors import CliRefusedBoundaryError

    return CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))


def _exit(code: int) -> NoReturn:
    raise typer.Exit(code=code)


def _state() -> WorkflowState:
    from ...application.workflow import workflow_state_repository
    from ...core import resolve_active_bucket_id

    # Without an active profile there is no bucket database to open;
    # workflow_state_repository().load() would raise a raw StorageError
    # ("aeat_database_url is empty") that leaks internal plumbing to the
    # operator. Refuse early with the operator-facing no-active-profile
    # message instead.
    if resolve_active_bucket_id() is None:
        raise _no_active_profile_refusal()
    return workflow_state_repository().load()


def _active_profile_or_exit(ctx: typer.Context) -> tuple[WorkflowState, str]:
    """Return (state, active_profile_name) or exit code 2 with a typed payload."""
    from ...core import resolve_active_bucket_id

    active = resolve_active_bucket_id()
    if active is None:
        _error_value = tr("cli.common.errors.no_active_profile_error_value")
        _next_value = tr("cli.common.next.create_profile_command")
        _emit(
            ctx,
            {"error": _error_value, "next": _next_value},
            [f"error\t{_error_value}", f"next\t{_next_value}"],
        )
        _exit(2)
    return _state(), active


def _description_for(entry: AuthProviderListing | ProfileKey) -> str:
    return _translate(entry.description)


def _label_for(listing: AuthProviderListing) -> str:
    return _translate(listing.label)


def _translate(translatable: str) -> str:
    """Render a str in the operator's preferred locale (Spanish first)."""
    from ...core.i18n import tr

    return tr(translatable)


def _fmt_decimal(value: Decimal | None) -> str:
    if value is None:
        return "0"
    normalized = value.normalize()
    return format(normalized, "f")


# ---------------------------------------------------------------------
# Period normaliser
# ---------------------------------------------------------------------

_PERIOD_RE = _re.compile(r"^(?P<year>\d{4})(?:[-]?Q(?P<quarter>[1-4])|-(?P<month>0[1-9]|1[0-2]))?$", _re.IGNORECASE)


def _canonical_period(raw: str) -> str:
    """Return the upper-case, un-hyphenated period ID or raise _bad."""
    if not raw.strip():
        raise _bad(tr("cli.common.errors.period_empty"))
    match = _PERIOD_RE.fullmatch(raw.strip())
    if match is None:
        raise _bad(tr("cli.common.errors.period_unrecognised", raw=raw))
    year = match.group("year")
    quarter = match.group("quarter")
    month = match.group("month")
    if quarter is not None:
        return f"{year}Q{quarter}"
    if month is not None:
        return f"{year}-{month}"
    return year


def _parse_iso_date(raw: str, *, label: str) -> _date:
    try:
        return _date.fromisoformat(raw.strip())
    except ValueError as exc:
        raise _bad(tr("cli.common.errors.invalid_iso_date", label=label, raw=raw)) from exc


def _profile_to_taxpayer(state: WorkflowState) -> TaxpayerProfile:
    from ...application.user_profile import projection_for_taxpayer

    record = state.active_profile_record()
    if record is None:
        return projection_for_taxpayer({}, tax_id_default="00000000T")
    return projection_for_taxpayer(record, tax_id_default="00000000T")


# ---------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------


def _active_bucket_id_or_bad(state: WorkflowState) -> str:
    """Return the active profile bucket id or raise the CLI 'bad' error."""
    from ...core import require_active_bucket_id
    from ...core.errors import NoActiveProfileError

    try:
        return require_active_bucket_id()
    except NoActiveProfileError as exc:
        raise _no_active_profile_refusal() from exc


def _tx_repo(state: WorkflowState) -> TransactionCatalogueRepository:
    from ...application.workflow import active_transaction_catalogue_repository
    from ...domain.transactions import LedgerNoActiveBucketError

    try:
        return active_transaction_catalogue_repository(state)
    except LedgerNoActiveBucketError as exc:
        raise _no_active_profile_refusal() from exc


def _invoice_repo(*, bucket_id: str | None = None) -> InvoiceCatalogueRepository:
    from ...domain.invoices import InvoiceCatalogueRepository

    return InvoiceCatalogueRepository(bucket_id=bucket_id)


def _draft_repo(*, bucket_id: str | None = None) -> ModeloDraftRepository:
    from ...domain.filing import ModeloDraftRepository

    return ModeloDraftRepository(bucket_id=bucket_id)


def _load_transactions(state: WorkflowState) -> TransactionCatalogue:
    return _tx_repo(state).load()


def _load_invoices() -> InvoiceCatalogue:
    return _invoice_repo().load()


def _load_drafts() -> tuple[ModeloDraft, ...]:
    repo = _draft_repo()
    return tuple(repo.iter_drafts())


def _draft_by_id(draft_id: str) -> ModeloDraft:
    for draft in _load_drafts():
        if draft.draft_id == draft_id:
            return draft
    raise _bad(tr("cli.common.errors.draft_id_not_found", draft_id=draft_id))


def _aggregate_filing_inputs(modelo: str, period: str, state: WorkflowState) -> dict[str, object]:
    """Return filing inputs aggregated from registry-approved sources.

    Returns casilla-id → Decimal binding dict consumed directly as
    ``binding_overrides`` by the calculation engine. dict[str, object] is
    intentional: callers may merge or extend the result before passing it
    downstream. Mapping would block that mutation.
    """
    if modelo.strip() == Modelo.M100 and _annual_filing_year(period) is not None:
        filing_year = _annual_filing_year(period)
        assert filing_year is not None
        bucket_id = _active_bucket_id_or_bad(state)
        return _aggregate_renta_filing_inputs(
            bucket_id=bucket_id,
            filing_year=filing_year,
            transaction_repository=_tx_repo(state),
            invoice_repository=_invoice_repo(bucket_id=bucket_id),
        )
    return {}


def _aggregate_renta_filing_inputs(
    *,
    bucket_id: str,
    filing_year: int,
    transaction_repository: TransactionCatalogueRepository,
    invoice_repository: InvoiceCatalogueRepository,
) -> dict[str, object]:
    from ...application.aggregation import resolve_modelo_ledger_binding_values_from_repositories
    from ...core.resources import resources

    authority = resources().modelos.authority
    snapshot = authority.snapshot(Modelo.M100.value, filing_year=filing_year, period="0A")
    aggregation = resolve_modelo_ledger_binding_values_from_repositories(
        bucket_id=bucket_id,
        modelo=Modelo.M100.value,
        revision=snapshot.revision,
        filing_year=filing_year,
        period="0A",
        transaction_repository=transaction_repository,
        invoice_repository=invoice_repository,
    )
    return _bound_inputs_from_available_bindings(snapshot.revision, dict(aggregation.binding_values))


def _bound_inputs_from_available_bindings(
    revision: ModeloRevision,
    binding_values: dict[str, Decimal],
) -> dict[str, object]:
    """Map each bound casilla in a :class:`ModeloRevision` to its supplied value.

    Reads the revision's casillas and keeps those whose ``input_kind`` is
    ``BOUND`` and whose binding selector has a value in ``binding_values``.
    """
    from ...domain.calculations.registry import InputKind

    return {
        casilla.id: binding_values[casilla.binding]
        for casilla in revision.casillas
        if casilla.input_kind == InputKind.BOUND and casilla.binding is not None and casilla.binding in binding_values
    }


def _annual_filing_year(period: str) -> int | None:
    text = period.strip().upper()
    if _re.fullmatch(r"\d{4}", text):
        return int(text)
    if _re.fullmatch(r"\d{4}A", text):
        return int(text[:4])
    return None


# ---------------------------------------------------------------------
# Output-language override
# ---------------------------------------------------------------------


def activate_subcommand_output_language(ctx: typer.Context, language: OutputLanguage | None) -> None:
    """Apply a subcommand-supplied ``--output-language`` to the render path.

    ``--output-language`` on a subcommand short-circuits the root
    callback's ``--language`` flow; rather than re-parsing, override the
    Settings field directly and drop the cached language so any ``tr()``
    fired during the verb body resolves to the requested locale.
    """
    if language is None:
        return
    from ...core.config import override_settings
    from ...core.i18n._render import clear_output_language_cache

    ctx.with_resource(override_settings(aeat_output_language=language))
    clear_output_language_cache()
