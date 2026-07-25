"""Shared CLI transport helpers used across all ``cadrumo`` command groups.

Provides output helpers, period normalisation, and repository accessors
used by the ledger, modelo, and config command groups. The repository
accessors return typed domain objects:
:class:`TransactionCatalogue` and
:class:`TransactionCatalogueRepository` for transaction
ledger access, :class:`InvoiceCatalogue` and
:class:`InvoiceCatalogueRepository` for invoice data,
:class:`ModeloDraft` for in-progress modelo drafts, and
:class:`TaxpayerProfile` for deadline and period
calculations.

The output boundary is :func:`_emit_envelope`. It routes every JSON result
through :class:`SchemaEnvelope`, requires a registered result schema, and
carries typed :class:`Notice` diagnostics while preserving the text line
iterator unchanged.

Application-layer and domain symbols are imported lazily inside each
helper to avoid pulling the registry parse into fast-path commands such
as ``aeat --version``.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Sequence
from datetime import date as _date
from decimal import Decimal
from typing import TYPE_CHECKING

import typer

from ...core.decimal import try_parse_canonical_decimal
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ...core.output_rendering import render_command_output

# The application- and domain-layer symbols below are imported lazily,
# inside the helpers that use them at runtime. A module-level import
# would pull the application layer — and transitively the registry
# parse — into every consumer of this transport module, including the
# ``aeat --version`` / ``aeat --help`` fast paths that import ``_emit_envelope``
# but never reach a registry-backed helper. ``from __future__ import
# annotations`` keeps the type annotations valid as strings without a
# runtime import; the ``TYPE_CHECKING`` block keeps static checkers
# resolving them.
if TYPE_CHECKING:
    from ...adapters.persistence.profile.filing_drafts import ModeloDraftRepository
    from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ...application.auth import AuthProviderListing
    from ...application.workflow import WorkflowState
    from ...core import Period
    from ...core.json_contract import Notice
    from ...domain.deadlines import TaxpayerProfile
    from ...domain.filing import ModeloDraft
    from ...domain.invoices import InvoiceCatalogue
    from ...domain.transactions import TransactionCatalogue

__all__ = [
    "emit_help_text",
    "parse_decimal_amount",
    "parse_optional_decimal_amount",
]

# ---------------------------------------------------------------------
# Transport helpers
# ---------------------------------------------------------------------

_FORMAT_TEXT = "text"
_FORMAT_JSON = "json"
_FORMAT_TABLE = "table"


def _is_metadata_invocation() -> bool:
    """Return whether the arguments request help or version metadata."""
    return any(argument in {"--help", "-h", "--version", "-V"} for argument in sys.argv[1:])


def _format_of(ctx: typer.Context) -> str:
    state = ctx.ensure_object(dict)
    return state.get("format", _FORMAT_TEXT)


def emit_help_text(ctx: typer.Context) -> None:
    """Emit Click/Typer help text through the shared CLI output boundary."""
    typer.echo(ctx.get_help())


def _emit_envelope(
    ctx: typer.Context,
    *,
    command: str,
    result: object,
    lines: Iterable[str],
    notices: Sequence[Notice] | None = None,
) -> None:
    """Render a typed result through JSON or text output.

    JSON mode goes through :func:`emit_json_success`
    so the payload is wrapped in the shared
    :class:`SchemaEnvelope` spine
    ``{"schema_version": ..., "command": ..., "status": ..., "result": ...,
    "notices": ...}``; ``status`` is derived from the supplied notice
    severities. Text mode keeps the existing line iterator unchanged so
    terminal output is unaffected.

    When the active profile bucket is a sandbox
    (:func:`~cadrumo.application.bucket_maintenance.is_sandbox_label`), a
    persistent info :class:`Notice` naming the sandbox is prepended to
    ``notices`` (JSON mode) and a matching banner line is prepended ahead
    of ``lines`` (text mode), so an operator can never mistake a sandbox
    run for a run against the real profile. The indicator is added here,
    once, rather than by each of the ~100 command handlers that call this
    helper — see :func:`_active_sandbox_notice`.

    Args:
        ctx: Typer context (used to discover the requested output format).
        command: Stable command path string (matches the
            ``@register_schema(...)`` argument on the result model).
        result: The strict-validated payload model to surface as
            ``envelope.result``. Must be a pydantic model registered
            under ``command`` in
            :data:`SCHEMA_REGISTRY`; the CLI
            conformance gate enforces this at test time.
        lines: Iterable of pre-formatted text lines (used unchanged
            for text mode).
        notices: Optional typed :class:`Notice`
            diagnostics surfaced on the envelope's ``notices`` channel.
            The text-mode rendering is unchanged; callers fold the same
            notices into ``lines`` themselves so JSON and text cannot
            drift.
    """
    from ...core.json_contract import emit_json_success

    metadata_invocation = _is_metadata_invocation()
    sandbox_notice = None if metadata_invocation else _active_sandbox_notice()
    resolved_notices: tuple[Notice, ...]
    if sandbox_notice is None:
        resolved_notices = tuple(notices) if notices is not None else ()
    else:
        resolved_notices = (sandbox_notice, *notices) if notices is not None else (sandbox_notice,)

    format_name = _format_of(ctx)
    if format_name == _FORMAT_JSON:
        active_profile = None if metadata_invocation else _active_profile_label()
        emit_json_success(command, result, notices=resolved_notices, active_profile=active_profile)
        return
    # Route non-JSON paths through render_command_output so unsupported
    # ``--format`` values (e.g. ``xml``) raise the shared refusal contract.
    # ``render_command_output``
    # ignores ``payload`` outside JSON mode and emits the line iterator.
    rendered_lines = lines if sandbox_notice is None else (f"SANDBOX\t{sandbox_notice.message}", *lines)
    rendered = render_command_output(format_name=format_name, payload=result, lines=rendered_lines)
    if rendered.text:
        typer.echo(rendered.text)


def _active_sandbox_notice() -> Notice | None:
    """Return the persistent sandbox-active :class:`Notice`, or ``None``.

    Resolves the active bucket id through the same core precedence chain
    every command uses (:func:`~cadrumo.core.resolve_active_bucket_id`), then
    reads its plaintext manifest label directly through the light
    ``adapters.persistence.storage.bucket`` primitives — the same tolerant
    read :func:`~cadrumo.application.workflow.read_profile_bucket_by_id`
    performs, but reached without importing the heavy ``workflow`` /
    ``bucket_maintenance`` facades (which pull the registry) — and checks it
    against the reserved sandbox label prefix
    (:data:`~cadrumo.core.external_constants.SANDBOX_LABEL_PREFIX`). This keeps
    the state-free CLI surface (``cadrumo`` / ``--help`` / ``--version``, which
    reach this helper via :func:`_emit_envelope`) off the registry-loading
    import path, honouring this module's lazy-import contract. Returns
    ``None`` when no profile is active, the active bucket's manifest is
    absent, unreadable, or fails strict validation, or the active profile
    is not a sandbox, so a real profile's output is never annotated and a
    corrupt/torn manifest degrades this purely-advisory indicator rather
    than breaking every command's output. The manifest is deliberately
    re-read on every call (no caching) so a mid-process ``switch`` is
    reflected on the very next command.
    """
    from ...adapters.persistence.storage import StorageValidationError
    from ...adapters.persistence.storage.bucket import bucket_paths, manifest_path, read_manifest
    from ...core import FormerProductStateError, resolve_active_bucket_id
    from ...core.config import load_settings
    from ...core.external_constants import SANDBOX_LABEL_PREFIX
    from ...core.json_contract import Notice, NoticeSeverity

    try:
        bucket_id = resolve_active_bucket_id()
        if bucket_id is None:
            return None
        paths = bucket_paths(load_settings().cadrumo_local_storage_root, bucket_id)
        if not manifest_path(paths).is_file():
            return None
        label = read_manifest(paths).label
    except (FormerProductStateError, StorageValidationError, ValueError):
        return None
    if not label.startswith(SANDBOX_LABEL_PREFIX):
        return None
    return Notice(
        severity=NoticeSeverity.INFO,
        code="config.profile.sandbox.active_indicator",
        message=tr(
            "cli.config.profile.sandbox.active_indicator_info",
            default=(
                "You are operating inside the sandbox %{label}, not a real profile; "
                "every command runs against this isolated, discardable bucket."
            ),
            label=label,
        ),
        suggestion="aeat config profile sandbox discard",
    )


def _active_profile_label() -> str | None:
    """Return the active taxpayer profile's display label, or ``None``.

    Resolves the active bucket id through the same core precedence chain
    every command uses (:func:`~cadrumo.core.resolve_active_bucket_id`), then
    reads its plaintext manifest label
    (:func:`~cadrumo.application.workflow.read_profile_bucket_by_id`) — the
    same non-secret display name :func:`_active_sandbox_notice` reads,
    never opening the encrypted per-bucket database and never touching the
    redacted profile/bucket UUID. Returns ``None`` when no profile is
    active, Cadrumo has rejected a legacy product-state location, or the manifest is
    absent, unreadable, or fails strict validation, so a non-profile-bound
    command and a degraded manifest both leave the envelope spine's
    ``active_profile`` null rather than breaking the emit. This is the identity anchor injected at the CLI
    transport boundary because the ``core`` layer that builds the envelope
    (:func:`~cadrumo.core.json_contract.emit_json_success`) never scans
    profile manifests.
    """
    from ...adapters.persistence.storage import StorageValidationError
    from ...application.workflow import read_profile_bucket_by_id
    from ...core import FormerProductStateError, resolve_active_bucket_id

    try:
        bucket_id = resolve_active_bucket_id()
        if bucket_id is None:
            return None
        pointer = read_profile_bucket_by_id(bucket_id)
    except (FormerProductStateError, StorageValidationError):
        return None
    return pointer.label if pointer is not None else None


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

    The suggested next command distinguishes "no profile registered at
    all" (suggest create) from "at least one profile is registered but
    none is active" (suggest login), so an operator who has already
    created a profile and merely logged out is never told to create a
    second one. ``list_profile_buckets`` reads only manifest files and
    never unlocks a bucket, so this check is cheap.
    """
    from ...application.workflow import list_profile_buckets
    from ._errors import CliRefusedBoundaryError

    # Each branch calls tr() with a literal key so the locale scaffold's
    # static discovery can find both keys; a single tr(variable) call would
    # be invisible to that AST-literal scan and the second key would never
    # get scaffolded across the four catalogues.
    if list_profile_buckets():
        return CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile_registered"))
    return CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))


def _state() -> WorkflowState:
    from ...application.workflow import workflow_state_repository
    from ...core import resolve_active_bucket_id

    # Without an active profile there is no bucket database to open;
    # workflow_state_repository().load() would raise a raw StorageError
    # ("cadrumo_database_url is empty") that leaks internal plumbing to the
    # operator. Refuse early with the operator-facing no-active-profile
    # message instead.
    if resolve_active_bucket_id() is None:
        raise _no_active_profile_refusal()
    return workflow_state_repository().load()


def _label_for(listing: AuthProviderListing) -> str:
    return _translate(listing.label)


def _translate(translatable: str) -> str:
    """Render a str in the operator's preferred locale (Spanish first)."""
    from ...core.i18n import tr

    return tr(translatable)


# ---------------------------------------------------------------------
# Period normaliser
# ---------------------------------------------------------------------
#
# The ledger ``--period`` surface speaks ONE strict operator grammar — the
# canonical AEAT modelo tokens (``0A`` annual, ``1T``-``4T`` quarters,
# ``01``-``12`` months) the modelo surfaces already teach (one strict period
# grammar everywhere, AEAT tokens only). Those tokens carry no year of their
# own, so every ledger ``--period`` command also takes ``--year`` to supply
# the year context — exactly the modelo ``--year``/``--period`` composition,
# so ``--period 1T --year 2024`` reads identically across ledger and modelo.
# A filing period is ALWAYS carried as a ``(year, bare-token)`` pair — never a
# combined calendar string. The internal value the ledger filters by is a
# :class:`Period` date span built directly from that pair; there is no calendar
# shape, no year-qualified hybrid, and no conversion layer. A calendar shape
# (``2024Q1`` / ``2024-03`` / ``2024``) is refused with a message naming the
# AEAT tokens and the ``--year`` argument.


def _ledger_aeat_token(token: str) -> str | None:
    """Return the normalised ledger-meaningful registry token, or ``None``.

    Validates ``token`` against the registry period union and accepts it only
    when it is a span-shaped :class:`StandardPeriodCode` member the
    ledger can filter by (quarters, months, annual). Extended-union members the ledger
    does not filter by (``EXT-*``, ``AD-HOC``, ``EVENT-N``) and instalment
    claves (``1P``-``4P``) return ``None``.
    """
    from ...core import StandardPeriodCode

    try:
        registry_period = StandardPeriodCode(token.strip().upper()).value
    except ValueError:
        return None
    if registry_period not in frozenset(StandardPeriodCode):
        return None
    return registry_period


def _canonical_period(period: str, *, year: int) -> Period:
    """Resolve a strict AEAT ``--period`` token plus ``--year`` to a :class:`Period`.

    The ledger ``--period`` surface accepts only the canonical AEAT modelo
    tokens (``0A`` annual, ``1T``-``4T`` quarters, ``01``-``12`` months),
    validated through the registry period union at :mod:`core`,
    and composes them with ``--year`` exactly as the modelo surface does. A
    calendar shape (``2026Q1`` / ``2026-03`` / ``2026``) or any other notation
    is refused with a message naming the AEAT tokens and the ``--year``
    argument. The ``(year, token)`` pair builds the
    :class:`Period` date span the ledger filters by — there is no
    intermediate calendar string.
    """
    from ...core import Period, PeriodError

    stripped = period.strip()
    if not stripped:
        raise _bad(tr("cli.common.errors.period_empty"))

    registry_period = _ledger_aeat_token(stripped)
    if registry_period is not None:
        try:
            resolved = Period.from_year_and_code(year, registry_period)
        except PeriodError:
            pass
        else:
            if resolved.has_date_span():
                return resolved
            # A registry-valid token the ledger cannot filter by (an instalment
            # clave such as ``1P``): refuse with the AEAT-token guidance below.

    raise _bad(tr("cli.common.errors.period_unrecognised", raw=period))


def _filter_canonical_period(token: str, *, year: int) -> Period:
    """Resolve a ``--filter period=`` bare token plus ``--filter year=`` to :class:`Period`.

    The ledger ``--filter`` grammar carries the filing year as a separate
    ``year=`` clause, so ``period=`` is the same bare AEAT token the
    ``--period`` option accepts (``1T`` / ``0A`` / ``03``). A calendar shape or
    a year-qualified hybrid (``2026Q1`` / ``2026-1T``) is refused with a message
    naming the AEAT tokens. Reuses the same ``(year, token)→Period`` mapping the
    ``--period`` / ``--year`` commands use.
    """
    return _canonical_period(token, year=year)


def _optional_canonical_period(period: str | None, *, year: int | None) -> Period | None:
    """Resolve an optional ``--period`` / ``--year`` pair to :class:`Period` or ``None``.

    Returns ``None`` when no ``--period`` is supplied (the command scopes the
    whole ledger). When ``--period`` is supplied it requires ``--year`` (the
    AEAT token carries no year of its own) and converts the pair through
    :func:`_canonical_period`; a ``--period``
    with no ``--year`` refuses with an instructive message naming the
    ``--year`` argument.
    """
    if period is None:
        return None
    if year is None:
        raise _bad(tr("cli.common.errors.period_missing_year", token=period.strip()))
    return _canonical_period(period, year=year)


def _parse_iso_date(raw: str, *, label: str) -> _date:
    from ...core.parsing import parse_iso8601_date

    try:
        parsed = parse_iso8601_date(raw.strip())
    except ValueError as exc:
        raise _bad(tr("cli.common.errors.invalid_iso_date", label=label, raw=raw)) from exc
    if parsed is None:
        # ``parse_iso8601_date`` treats a blank/empty string as "absent" and
        # returns ``None`` rather than raising; this gate requires a value,
        # so blank input refuses with the same message as a malformed one.
        raise _bad(tr("cli.common.errors.invalid_iso_date", label=label, raw=raw))
    return parsed


def _parse_iso_date_str(raw: str, *, label: str) -> str:
    """Validate ``raw`` as an ISO-8601 date and return its canonical string.

    The shared ISO gate (:func:`_parse_iso_date`)
    refuses every non-ISO ordering by construction (``15/01/2026``,
    ``01-15-2026``, ``2026/01/15``); this wrapper returns the canonical
    ``YYYY-MM-DD`` form for the several service contracts that persist the date
    as a 10-character string rather than a :class:`~datetime.date`. The
    DD/MM-vs-MM/DD ambiguity never arises because only the ISO ordering parses.
    """
    return _parse_iso_date(raw, label=label).isoformat()


def _parse_optional_iso_date_str(raw: str | None, *, label: str) -> str | None:
    """Validate an optional ISO-8601 date, returning its canonical string or ``None``.

    Returns ``None`` when ``raw`` is ``None`` (the date was not supplied);
    otherwise delegates to
    :func:`_parse_iso_date_str`, so a supplied
    non-ISO date refuses at the CLI boundary.
    """
    if raw is None:
        return None
    return _parse_iso_date_str(raw, label=label)


# ---------------------------------------------------------------------
# Canonical decimal-amount validator
# ---------------------------------------------------------------------
#
# One accepted grammar for every manual-entry numeric input: a dot decimal
# separator, an optional one- or two-digit (euro-cent) fractional part, no
# thousands grouping, no scientific notation, no ``NaN``/``Infinity``. The
# two-digit fractional cap is what makes the Spanish thousands-grouping shape
# ``1.000`` (a dot followed by three digits) refuse rather than silently become
# ``1.0``. ``1234.56`` and a bare ``1000`` / ``0`` accept; ``1.000``,
# ``1.234,56``, ``1e3``, ``NaN``, ``Infinity`` all refuse.
#
# The grammar itself lives in
# :func:`~cadrumo.core.decimal.try_parse_canonical_decimal`, in ``core`` rather
# than here, because the application-layer calculate-input boundary needs the
# same shape and cannot import from ``entrypoints``. What stays here is the
# thing that is genuinely CLI-owned: the localised, instructive refusal. One
# grammar, one refusal per boundary.


def parse_decimal_amount(raw: str, *, label: str, signed: bool = True) -> Decimal:
    """Parse a required canonical-grammar decimal at the CLI boundary.

    Validates ``raw`` against the canonical decimal regex (dot separator, no
    thousands grouping, no scientific notation, no ``NaN``/``Infinity``) before
    constructing :class:`~decimal.Decimal`, then asserts :meth:`~decimal.Decimal.is_finite`
    as defence-in-depth. Refuses ``1.000``, ``1.234,56``, ``1e3``, ``NaN``,
    ``Infinity``, and ``-Infinity`` with the localised
    ``cli.ledger.errors.invalid_decimal`` refusal that names the field, echoes
    the raw value, and states the accepted form.

    Args:
        raw: The operator-supplied raw string.
        label: The field label echoed in the refusal message.
        signed: When ``True`` (default) a leading ``-`` is accepted; when
            ``False`` the non-negative variant is used and a negative input
            refuses.
    """
    parsed = try_parse_canonical_decimal(raw, signed=signed, max_fraction_digits=2)
    if parsed is None:
        raise _bad(tr("cli.ledger.errors.invalid_decimal", label=label, raw=raw))
    return parsed


def parse_optional_decimal_amount(raw: str | None, *, label: str, signed: bool = True) -> Decimal | None:
    """Parse an optional canonical-grammar decimal, or ``None`` when unset.

    Returns ``None`` when ``raw`` is ``None`` (the field was not supplied);
    otherwise delegates to
    :func:`parse_decimal_amount`, so the same
    canonical grammar and :meth:`~decimal.Decimal.is_finite` guard apply.
    """
    if raw is None:
        return None
    return parse_decimal_amount(raw, label=label, signed=signed)


def optional_decimal_text(value: Decimal | None) -> str | None:
    """Render an optional decimal without scientific notation."""
    if value is None:
        return None
    return format(value, "f")


def resolve_pull_year_range(
    *,
    year: int | None,
    year_from: int | None,
    year_to: int | None,
) -> tuple[int, int]:
    """Resolve mutually exclusive single-year and inclusive range pull options."""
    if year is not None and (year_from is not None or year_to is not None):
        raise typer.BadParameter("use --year for a single-year pull or --from-year/--to-year for a range, not both")
    if year is not None:
        return year, year
    if year_from is None and year_to is None:
        raise typer.BadParameter("either --year or both --from-year and --to-year are required")
    if year_from is None or year_to is None:
        raise typer.BadParameter("--from-year and --to-year must be supplied together")
    if year_from > year_to:
        raise typer.BadParameter("--from-year must be less than or equal to --to-year")
    return year_from, year_to


def _profile_to_taxpayer(state: WorkflowState) -> TaxpayerProfile:
    from ...application.user_profile import projection_for_taxpayer

    record = state.active_profile_record()
    if record is None:
        return projection_for_taxpayer({}, tax_id_default="00000000T")
    return projection_for_taxpayer(record, tax_id_default="00000000T")


# ---------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------


def active_bucket_id_or_refuse() -> str:
    """Return the active profile bucket id or raise the canonical no-active-profile refusal.

    Stateless single source for the cold-start bucket-id guard shared across
    bucket-bound CLI command families. :func:`_active_bucket_id_or_bad`
    delegates here.
    """
    from ...core import require_active_bucket_id
    from ...core.errors import NoActiveProfileError

    try:
        return require_active_bucket_id()
    except NoActiveProfileError as exc:
        raise _no_active_profile_refusal() from exc


def _active_bucket_id_or_bad(state: WorkflowState) -> str:
    """Return the active profile bucket id or raise the CLI 'bad' error."""
    return active_bucket_id_or_refuse()


def _tx_repo(state: WorkflowState) -> TransactionCatalogueRepository:
    from ...application.workflow import active_transaction_catalogue_repository
    from ...domain.transactions import LedgerNoActiveBucketError

    try:
        return active_transaction_catalogue_repository(state)
    except LedgerNoActiveBucketError as exc:
        raise _no_active_profile_refusal() from exc


def _invoice_repo(*, bucket_id: str | None = None) -> InvoiceCatalogueRepository:
    from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository

    return InvoiceCatalogueRepository(bucket_id=bucket_id)


def _draft_repo(*, bucket_id: str | None = None) -> ModeloDraftRepository:
    from ...adapters.persistence.profile.filing_drafts import ModeloDraftRepository

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
    from ...core.i18n import clear_output_language_cache

    ctx.with_resource(override_settings(cadrumo_output_language=language))
    clear_output_language_cache()
