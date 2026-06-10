"""User-facing configuration facade.

The ``config history`` sub-command browses the append-only event log
through :class:`BucketEventHistoryRepository`.
"""

from __future__ import annotations

from typing import cast

import click
import typer
import typer._click.types as typer_click_types

from ....application.config_reset import CONFIG_RESET_SCOPE_CLI_VALUES as _CONFIG_RESET_SCOPE_CLI_VALUES
from ....application.config_reset import parse_config_reset_scope as _parse_config_reset_scope
from ....application.modelo import ModeloWorkRegistryYearMismatchError as _ModeloWorkRegistryYearMismatchError
from ....application.operator_surface import build_help_document as _build_help_document
from ....application.operator_surface import render_help_text as _render_help_text
from ....application.wizard import build_wizard_command as _build_wizard_command
from ....application.workflow import ProfileLabelAmbiguousError as _ProfileLabelAmbiguousError
from ....application.workflow import read_profile_bucket as _read_profile_bucket
from ....core import resolve_active_bucket_id as _resolve_active_bucket_id
from ....core.errors import AeatError as _AeatError
from ....core.external_constants import OutputLanguage
from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES as _SUPPORTED_OUTPUT_LANGUAGES
from ....core.i18n import tr
from ....core.logging import get_logger as _get_logger
from ....core.wizard_catalogue import get_setup_flow as _get_setup_flow
from .._command_suggestions import AeatTyperGroup as _AeatTyperGroup
from .._common import _emit, _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from .._errors import command_error_boundary as _command_error_boundary
from ._apoderado import apoderado_app, register_apoderado_commands
from ._auth import auth_app
from ._auth_diagnostics import auth_diagnostics_app
from ._bucket_history import _parse_bucket_event_types, register_bucket_history_commands
from ._custody import register_custody_commands
from ._errors import ConfigBoundaryError as _ConfigBoundaryError
from ._profile_bundle import register_profile_bundle_commands
from ._repair_cli import register_repair_maintenance_commands
from ._repair_profile import (
    profile_record_missing_next_action as _profile_record_missing_next_action,
)
from ._repair_profile import (
    profile_record_unreadable_next_action as _profile_record_unreadable_next_action,
)
from ._repair_profile import register_repair_profile_command

_log = _get_logger(__name__)

# CAST-RATIONALE-CONFIG-RESET-SCOPE-CHOICE: typer vendors its own copy of click, so
# click.Choice is a click.types.ParamType while typer.Option's click_type expects
# typer._click.types.ParamType. They are the same object at runtime (the vendored
# click), so the cast only bridges the static type duality — no Any escape.
_CONFIG_RESET_SCOPE_CHOICE: typer_click_types.ParamType = cast(
    typer_click_types.ParamType, click.Choice(_CONFIG_RESET_SCOPE_CLI_VALUES)
)

_wizard_create_command = _build_wizard_command(_get_setup_flow(), mode="create")
_wizard_edit_command = _build_wizard_command(_get_setup_flow(), mode="edit")

app = typer.Typer(
    name="config",
    help=tr("cli.config.app_help"),
    no_args_is_help=False,
    invoke_without_command=True,
    add_help_option=False,
)
profile_app = typer.Typer(
    name="profile",
    help=tr("cli.config.profile.help"),
    no_args_is_help=True,
    cls=_AeatTyperGroup,
)
repair_app = typer.Typer(
    name="repair",
    help=tr("cli.config.repair.help"),
    no_args_is_help=False,
    invoke_without_command=True,
)

_OUTPUT_LANGUAGE_CLI = click.Choice(_SUPPORTED_OUTPUT_LANGUAGES)


@app.callback()
def config_root(
    ctx: typer.Context,
    help_: bool = typer.Option(False, "--help", "-h", help=tr("cli.config.workflow_help"), is_eager=True),
) -> None:
    """Render config-level workflow help when requested."""
    if help_ or ctx.invoked_subcommand is None:
        document = _build_help_document("config")
        _emit(ctx, document, _render_help_text(document).splitlines())
        raise typer.Exit()


def _profile_state():
    from ....application.workflow import workflow_state_repository

    return workflow_state_repository()


def _resolve_profile_by_label(name: str):
    """Resolve an operator-supplied profile label to its bucket pointer.

    Raises :class:`_CliRefusedBoundaryError` when no live profile carries
    ``name`` or when the label is ambiguous. Returns a
    :class:`ProfileBucketPointer` carrying the immutable UUID
    ``bucket_id`` and the ``label``.
    """
    try:
        pointer = _read_profile_bucket(name)
    except _ProfileLabelAmbiguousError as exc:
        # ``ProfileLabelAmbiguousError`` is a ``WorkflowError``, NOT a
        # ``ValueError``; refuse clearly with the dedicated ambiguity message
        # rather than letting it escape to an unhandled traceback or picking
        # an arbitrary bucket.
        raise _CliRefusedBoundaryError(
            translated_message="errors.refused.refused_profile_label_ambiguous",
        ) from exc
    except ValueError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": name},
        ) from exc
    if pointer is None:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": name},
        )
    return pointer


def _resolve_active_profile_pointer():
    """Resolve the active profile (by UUID) to its bucket pointer or ``None``."""
    from ....application.workflow import read_profile_bucket_by_id

    active = _resolve_active_bucket_id()
    if active is None:
        return None
    return read_profile_bucket_by_id(active)


def _atomic_create_profile(*, display_name, facts, profile_id: str | None = None) -> str:
    """Provision a new profile bucket through the canonical atomic-create.

    Both ``config profile import`` (recovery from a backup) and
    ``config profile duplicate`` route here so every create path lands
    on the single atomic provisioner ``register_active_profile``:
    bucket directory + manifest + encrypted record + active-profile
    pointer in one all-or-nothing unit of work owned by
    ``ProfileRepository.create``, with rollback on any failure.

    When ``profile_id`` is supplied (bundle import with D5 identity
    preservation), it is used as-is; otherwise a fresh UUID is minted.
    The resolved UUID is returned so the caller can report it.

    Cold-start: the active-profile pointer must aim at the new UUID
    before ``workflow_state_repository().update`` opens its per-bucket
    engine, and a master-key session must be active before the
    encrypted record is written. The genuine prior pointer is captured
    and restored if the surrounding span fails, closing the window the
    repository's own rollback cannot see.
    """
    from ....application.user_profile import (
        profile_create_storage_span,
        register_active_profile,
    )
    from ....domain.user_profile import new_profile_id

    profile_id = profile_id or new_profile_id()
    with profile_create_storage_span(profile_id) as routing_profile_id:
        repository = _profile_state()
        repository.update(
            lambda current: register_active_profile(
                current,
                profile_id=profile_id,
                display_name=display_name,
                facts=facts,
                # `duplicate` and `import` legitimately reproduce an
                # existing profile's tax id; the duplicate-tax-id
                # refusal applies to a fresh `profile create` only.
                enforce_unique_tax_id=False,
                routing_profile_id=routing_profile_id,
            )
        )
    return profile_id


@profile_app.command("list", help=tr("cli.config.list.help"))
def config_list(
    ctx: typer.Context,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """List every registered profile via the manifest-scan helper.

    Replaces the prior behaviour that enumerated only the active
    profile's key values (Axis B / Axis D / dual-persona pain). The
    canonical source of profile-existence truth is the per-bucket
    ``manifest.toml`` file written by every profile-creation path;
    :func:`list_profile_buckets` reads them and returns the full
    set without unlocking any bucket.
    """
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.workflow import list_profile_buckets
    from .._config_payloads import ConfigListResult, ProfilePointerPayload

    active = _resolve_active_bucket_id()
    buckets = list_profile_buckets()
    rows = sorted(buckets.values(), key=lambda pointer: pointer.label.casefold())
    active_label = next((p.label for p in rows if p.bucket_id == active), None)
    result = ConfigListResult(
        active_profile=active_label,
        profiles=[
            ProfilePointerPayload(
                name=pointer.label,
                bucket_id=pointer.bucket_id,
                active=pointer.bucket_id == active,
            )
            for pointer in rows
        ],
    )
    if not rows:
        lines = [f"active_profile\t{active_label or '<none>'}", "profiles\t<none>"]
    else:
        lines = [f"active_profile\t{active_label or '<none>'}"]
        for pointer in rows:
            marker = "*" if pointer.bucket_id == active else " "
            lines.append(f"{marker}\t{pointer.label}")
    _emit_envelope(ctx, command="config.profile.list", result=result, lines=lines)


def _assert_profile_record_present(ctx: typer.Context, *, profile_id: str, bucket_id: str, label: str) -> None:
    from ....domain.user_profile import ProfileNotFoundError

    try:
        _read_profile_record(profile_id=profile_id, bucket_id=bucket_id)
    except ProfileNotFoundError:
        _emit_profile_record_missing(ctx, profile_id=profile_id, bucket_id=bucket_id, label=label)
        raise typer.Exit(code=2) from None
    except _AeatError as exc:
        _emit_profile_record_unreadable(ctx, profile_id=profile_id, bucket_id=bucket_id, label=label, error=exc)
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        _log.debug("config profile readiness wrapped unexpected profile-record exception", exc_info=True)
        boundary = _ConfigBoundaryError(exc)
        _emit_profile_record_unreadable(ctx, profile_id=profile_id, bucket_id=bucket_id, label=label, error=boundary)
        raise typer.Exit(code=2) from boundary


def _emit_profile_record_missing(ctx: typer.Context, *, profile_id: str, bucket_id: str, label: str) -> None:
    payload = {
        "profile_id": profile_id,
        "bucket_id": bucket_id,
        "display_name": label,
        "registered_bucket": True,
        "profile_record_present": False,
        "configured": False,
        "next_action": _profile_record_missing_next_action(profile_id, label=label),
    }
    _emit(
        ctx,
        payload,
        (
            "readiness\tmissing_profile_record",
            f"profile_id\t{profile_id}",
            f"bucket_id\t{bucket_id}",
            f"display_name\t{label}",
            "registered_bucket\tpresent",
            "profile_record\tmissing",
            f"next_action\t{payload['next_action']}",
        ),
    )


def _emit_profile_record_unreadable(
    ctx: typer.Context,
    *,
    profile_id: str,
    bucket_id: str,
    label: str,
    error: Exception,
) -> None:
    message = str(error).splitlines()[0] if str(error) else type(error).__name__
    payload = {
        "profile_id": profile_id,
        "bucket_id": bucket_id,
        "display_name": label,
        "registered_bucket": True,
        "profile_record_present": False,
        "status": "profile_record_unreadable",
        "error": f"{type(error).__name__}: {message}",
        "next_action": _profile_record_unreadable_next_action(profile_id, label=label),
    }
    _emit(
        ctx,
        payload,
        (
            "readiness\tprofile_record_unreadable",
            f"profile_id\t{profile_id}",
            f"bucket_id\t{bucket_id}",
            f"display_name\t{label}",
            "registered_bucket\tpresent",
            "profile_record\tunreadable",
            f"next_action\t{payload['next_action']}",
        ),
    )


def _read_profile_record(*, profile_id: str, bucket_id: str):
    """Read a profile record under a bucket session scoped to that profile."""
    from ....adapters.persistence.storage import has_active_bucket_session
    from ....application.user_profile import build_lifecycle_service, profile_storage_session
    from ....core import resolve_active_bucket_id as _resolve_active_bucket_id

    if bucket_id == _resolve_active_bucket_id() and has_active_bucket_session():
        return build_lifecycle_service(bucket_id=bucket_id).read(profile_id)
    with profile_storage_session(bucket_id):
        service = build_lifecycle_service(bucket_id=bucket_id)
        return service.read(profile_id)


@profile_app.command("show", help=tr("cli.config.profile.show_help"))
def config_profile_show(
    ctx: typer.Context,
    name: str | None = typer.Argument(None, help=tr("cli.config.profile.show_name_help")),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """View one profile's facts (defaults to the active profile).

    Emits a ``record_validity`` header line carrying the validation
    outcome of the canonical ProfileValidationService — the persisted
    record's schema validity, a distinct notion from the *filing
    readiness* gate reported by ``config profile status``. When blocking
    issues exist, the command exits with code 2 after rendering the report
    so operators discover the failure on stdout and via the shell exit
    status.
    """
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile import ProfileValidationService, record_to_path_values
    from ....domain.user_profile import ProfileNotFoundError, load_user_profile_schema

    if name is not None:
        # ``show`` is the inspect surface: a tombstoned profile is still
        # resolvable by name so the operator can confirm a delete and
        # read the retained record. The verb renders the tombstoned
        # status; it never reports the profile as a live ``ready`` one.
        try:
            pointer = _read_profile_bucket(name, include_tombstoned=True)
        except _ProfileLabelAmbiguousError as exc:
            # ``ProfileLabelAmbiguousError`` is a ``WorkflowError``, NOT a
            # ``ValueError``; refuse clearly with the dedicated ambiguity
            # message rather than escaping to an unhandled traceback.
            raise _CliRefusedBoundaryError(
                translated_message="errors.refused.refused_profile_label_ambiguous",
            ) from exc
        except ValueError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.unknown_profile",
                context={"name": name},
            ) from exc
        if pointer is None:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.unknown_profile",
                context={"name": name},
            )
    else:
        pointer = _resolve_active_profile_pointer()
        if pointer is None:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.errors.no_active_profile",
            )
    try:
        record = _read_profile_record(profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id)
    except ProfileNotFoundError as exc:
        _emit_profile_record_missing(
            ctx, profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id, label=pointer.label
        )
        raise typer.Exit(code=2) from exc
    except _AeatError as exc:
        _emit_profile_record_unreadable(
            ctx, profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id, label=pointer.label, error=exc
        )
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        _log.debug("config profile show wrapped unexpected profile-record exception", exc_info=True)
        boundary = _ConfigBoundaryError(exc)
        _emit_profile_record_unreadable(
            ctx, profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id, label=pointer.label, error=boundary
        )
        raise typer.Exit(code=2) from boundary
    from ....domain.user_profile import UserProfileStatus
    from .._config_payloads import ConfigProfileShowResult, ProfileFactPayload, ProfileIssuePayload

    report = ProfileValidationService(schema=load_user_profile_schema()).validate_record(record)
    blocking = [issue for issue in report.issues if issue.severity.value == "error"]
    is_tombstoned = record.status is UserProfileStatus.TOMBSTONED
    values = record_to_path_values(record)
    result = ConfigProfileShowResult(
        profile_id=record.profile_id,
        display_name=record.display_name,
        status=record.status.value,
        valid=not blocking and not is_tombstoned,
        schema_version=report.schema_version,
        issues=[
            ProfileIssuePayload(
                severity=issue.severity.value,
                code=issue.code,
                path=issue.path,
                message=issue.message,
            )
            for issue in report.issues
        ],
        facts=[ProfileFactPayload(path=path, value=str(value)) for path, value in sorted(values.items())],
    )
    lines: list[str] = []
    # ``show`` reports *record validity* (does the persisted profile record
    # satisfy its schema?), a distinct notion from the *filing readiness*
    # gate that ``config profile status`` reports (does the profile carry
    # the facts needed to start filing — tax_id and an activity?). The two
    # surfaces previously both printed the bare token ``readiness`` with the
    # words ``ready``/``blocked``, so a schema-valid but onboarding-incomplete
    # profile read as a self-contradiction (``show: ready`` vs
    # ``status: blocked``). ``show`` now emits the ``record_validity`` token
    # with ``valid``/``invalid`` so the two measures no longer collide.
    if is_tombstoned:
        lines.append("record_validity\ttombstoned")
    elif blocking:
        lines.append(f"record_validity\tinvalid\tissues={len(blocking)}")
    else:
        lines.append(f"record_validity\tvalid\tissues={len(report.issues)}")
    lines.append(f"profile_id\t{record.profile_id}")
    lines.append(f"display_name\t{record.display_name}")
    lines.append(f"status\t{record.status.value}")
    for issue in report.issues:
        lines.append(f"{issue.severity.value}\t{issue.code}\t{issue.path or '-'}\t{issue.message}")
    lines.extend(f"{path}\t{value}" for path, value in sorted(values.items()))
    _emit_envelope(ctx, command="config.profile.show", result=result, lines=lines)
    if blocking:
        raise typer.Exit(code=2)


def _resolve_preflight_revision_id(*, modelo: str, filing_year: int, period: str, revision_id: str | None) -> str:
    """Resolve the registry revision a preflight check is assessed against.

    When ``revision_id`` is supplied it is an explicit override and is
    validated against the registry for the modelo and filing year. When it
    is omitted the active revision for the natural key (modelo, filing
    year, period) is resolved through the modelo-addressing resolver, which
    consumes the :class:`ValidatedRegistryAuthority` and never a raw loader.

    Refuses instructively when the natural key resolves no revision or is
    ambiguous: the refusal names the candidate revisions or points at
    ``aeat app modelo describe <modelo>`` rather than emitting a bare error.
    """
    from ....application.modelo import resolve_registry_revision_for_work_target
    from ....domain.calculations.registry import (
        AmbiguousRevisionSelectionError,
        NoRevisionForPeriodError,
        RegistrySnapshotError,
    )

    try:
        return resolve_registry_revision_for_work_target(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            registry_revision_id=revision_id,
        )
    except AmbiguousRevisionSelectionError as exc:
        # ``select_revision`` selected more than one revision. The candidate
        # revision ids ride on the typed ``candidate_ids`` field, so the
        # refusal lists them without parsing the human-readable message.
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.preflight_revision_ambiguous",
            context={"modelo": modelo, "period": period, "candidates": ", ".join(exc.candidate_ids)},
        ) from exc
    except NoRevisionForPeriodError as exc:
        # The natural key resolved no revision. Point the operator at the
        # discovery command rather than emitting a bare unresolved error.
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.preflight_revision_unresolved",
            context={"modelo": modelo, "filing_year": filing_year, "period": period},
        ) from exc
    except RegistrySnapshotError as exc:
        # Any residual snapshot failure not modelled by the two typed
        # subclasses above still refuses instructively via the discovery
        # pointer rather than surfacing a bare error to the operator.
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.preflight_revision_unresolved",
            context={"modelo": modelo, "filing_year": filing_year, "period": period},
        ) from exc
    except _ModeloWorkRegistryYearMismatchError as exc:
        # An explicit ``--revision-id`` override that is unknown to the
        # modelo or does not cover the filing year. List the registered
        # revisions so the operator can correct the override.
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.preflight_revision_override_invalid",
            context={"modelo": modelo, "filing_year": filing_year, "detail": str(exc)},
        ) from exc


@profile_app.command("preflight", help=tr("cli.config.profile.preflight_help"))
def config_profile_preflight(
    ctx: typer.Context,
    modelo: str = typer.Option(..., "--modelo", help=tr("cli.config.profile.preflight_modelo_help")),
    filing_year: int = typer.Option(..., "--filing-year", help=tr("cli.config.profile.preflight_filing_year_help")),
    period: str = typer.Option(..., "--period", help=tr("cli.config.profile.preflight_period_help")),
    revision_id: str | None = typer.Option(
        None, "--revision-id", help=tr("cli.config.profile.preflight_revision_id_help")
    ),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Report which profile fields a given filing context requires that are missing.

    Operates on the active profile. ``--revision-id`` is an explicit override
    for exact replay; when omitted the active revision for the natural key
    (modelo, filing year, period) is resolved through the modelo-addressing
    resolver. Exits with code ``2`` when any required field is missing so
    operators discover the gap via the shell exit status.
    """
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile import ProfilePreflightService
    from ....domain.user_profile import ProfileNotFoundError, load_user_profile_schema

    pointer = _resolve_active_profile_pointer()
    if pointer is None:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.errors.no_active_profile",
        )
    try:
        record = _read_profile_record(profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id)
    except ProfileNotFoundError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": pointer.label or pointer.bucket_id},
        ) from exc
    resolved_revision_id = _resolve_preflight_revision_id(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
    )
    from .._config_payloads import ConfigProfilePreflightResult, ProfilePreflightMissingPayload

    report = ProfilePreflightService(schema=load_user_profile_schema()).report(
        record=record,
        modelo=modelo,
        revision_id=resolved_revision_id,
        filing_year=filing_year,
        period=period,
    )
    result = ConfigProfilePreflightResult(
        profile_id=report.profile_id,
        modelo=report.modelo,
        revision_id=report.revision_id,
        filing_year=report.filing_year,
        period=report.period,
        ready=report.ready,
        missing=[
            ProfilePreflightMissingPayload(
                selector=requirement.selector,
                section_key=requirement.section_key,
                field_key=requirement.field_key,
            )
            for requirement in report.missing
        ],
    )
    lines = [
        f"readiness\t{'ready' if report.ready else 'missing'}\tmissing={len(report.missing)}",
        f"profile_id\t{report.profile_id}",
        f"modelo\t{report.modelo}",
        f"revision_id\t{report.revision_id}",
        f"filing_year\t{report.filing_year}",
        f"period\t{report.period}",
    ]
    for requirement in report.missing:
        lines.append(f"missing\t{requirement.section_key}\t{requirement.field_key}\t{requirement.selector}")
    _emit_envelope(ctx, command="config.profile.preflight", result=result, lines=lines)
    if not report.ready:
        raise typer.Exit(code=2)


@profile_app.command("validate", help=tr("cli.config.profile.validate_help"))
def config_profile_validate(
    ctx: typer.Context,
    name: str | None = typer.Argument(None, help=tr("cli.config.profile.validate_name_help")),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Validate a profile against the loaded schema (defaults to the active profile).

    Exits with code ``2`` when blocking issues surface so operators discover
    schema-conformance failures via the shell exit status. Report-only
    companion to :func:`config_profile_show` — same validator, narrower
    payload (no fact dump).
    """
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile import ProfileValidationService
    from ....domain.user_profile import ProfileNotFoundError, load_user_profile_schema

    if name is not None:
        try:
            pointer = _read_profile_bucket(name, include_tombstoned=True)
        except _ProfileLabelAmbiguousError as exc:
            # ``ProfileLabelAmbiguousError`` is a ``WorkflowError``, NOT a
            # ``ValueError``; refuse clearly with the dedicated ambiguity
            # message rather than escaping to an unhandled traceback.
            raise _CliRefusedBoundaryError(
                translated_message="errors.refused.refused_profile_label_ambiguous",
            ) from exc
        except ValueError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.unknown_profile",
                context={"name": name},
            ) from exc
        if pointer is None:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.unknown_profile",
                context={"name": name},
            )
    else:
        pointer = _resolve_active_profile_pointer()
        if pointer is None:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.errors.no_active_profile",
            )
    try:
        record = _read_profile_record(profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id)
    except ProfileNotFoundError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": name or pointer.label or pointer.bucket_id},
        ) from exc
    from .._config_payloads import ConfigProfileValidateResult, ProfileIssuePayload

    report = ProfileValidationService(schema=load_user_profile_schema()).validate_record(record)
    blocking = [issue for issue in report.issues if issue.severity.value == "error"]
    result = ConfigProfileValidateResult(
        profile_id=record.profile_id,
        display_name=record.display_name,
        status=record.status.value,
        valid=not blocking,
        schema_version=report.schema_version,
        issues=[
            ProfileIssuePayload(
                severity=issue.severity.value,
                code=issue.code,
                path=issue.path,
                message=issue.message,
            )
            for issue in report.issues
        ],
    )
    lines = [
        f"readiness\t{'blocked' if blocking else 'ready'}\tissues={len(report.issues)}",
        f"profile_id\t{record.profile_id}",
        f"display_name\t{record.display_name}",
        f"status\t{record.status.value}",
        f"schema_version\t{report.schema_version}",
        f"valid\t{not blocking}",
    ]
    for issue in report.issues:
        lines.append(f"{issue.severity.value}\t{issue.code}\t{issue.path or '-'}\t{issue.message}")
    _emit_envelope(ctx, command="config.profile.validate", result=result, lines=lines)
    if blocking:
        raise typer.Exit(code=2)


@profile_app.command("delete", help=tr("cli.config.profile.delete_help"))
def config_profile_delete(
    ctx: typer.Context,
    name: str = typer.Argument(..., help=tr("cli.config.profile.delete_name_help")),
    confirmed: bool = typer.Option(False, "--yes", help=tr("cli.config.profile.delete_yes_help")),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Tombstone a profile. Immutable filing snapshots are retained."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile import delete_profile_with_lifecycle_span
    from ....domain.user_profile import ProfileNotFoundError

    if not confirmed:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.delete_requires_yes",
            context={"name": name},
        )
    # Resolve the operator-supplied label to a bucket pointer FIRST. This
    # is a plaintext manifest scan that needs no bucket session, so an
    # unknown name surfaces a clear "unknown profile" refusal distinct
    # from any session-state diagnostic — the operator can always tell
    # whether the name exists. ``delete`` does not require a pre-existing
    # session: like ``switch``, it opens its own scoped to the target.
    pointer = _resolve_profile_by_label(name)
    deleting_active_profile = pointer.bucket_id == _resolve_active_bucket_id()
    try:
        record = delete_profile_with_lifecycle_span(pointer.bucket_id)
    except ProfileNotFoundError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": name},
        ) from exc
    from .._config_payloads import ConfigProfileDeleteResult

    result = ConfigProfileDeleteResult(
        profile_id=record.profile_id,
        display_name=record.display_name,
        status=record.status.value,
        active_profile_cleared=deleting_active_profile,
    )
    lines = [
        f"profile_id\t{record.profile_id}",
        f"display_name\t{record.display_name}",
        f"status\t{record.status.value}",
    ]
    if deleting_active_profile:
        # The deleted profile was the active one; ProfileRepository.delete
        # cleared the active-profile pointer as part of the tombstone.
        # Make that consequence explicit so the operator is not left in a
        # silent no-active-profile state.
        lines.append("active_profile\t<none>")
        lines.append(f"notice\t{tr('cli.config.profile.delete_active_cleared')}")
    _emit_envelope(ctx, command="config.profile.delete", result=result, lines=lines)


@profile_app.command("duplicate", help=tr("cli.config.profile.duplicate_help"))
def config_profile_duplicate(
    ctx: typer.Context,
    source: str = typer.Argument(..., help=tr("cli.config.profile.duplicate_source_help")),
    target: str = typer.Argument(..., help=tr("cli.config.profile.duplicate_target_help")),
    display_name: str | None = typer.Option(
        None, "--display-name", help=tr("cli.config.profile.duplicate_display_name_help")
    ),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Copy SOURCE into TARGET as a new active profile.

    The TARGET profile lands through the canonical atomic-create
    provisioner (``register_active_profile``): the source record's
    facts are read, then a fresh bucket directory + manifest +
    encrypted record + active pointer are written in one
    all-or-nothing sequence. The prior copytree-then-rewrite path
    bypassed the provisioner and could leave a half-copied bucket on
    a crash; the atomic provisioner rolls every write back instead.
    """
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile import ProfileAlreadyRegisteredError
    from ....application.workflow import read_profile_bucket as _read_profile_bucket
    from ....domain.user_profile import ProfileNotFoundError

    source_pointer = _resolve_profile_by_label(source)
    if _read_profile_bucket(target) is not None:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.already_exists",
            context={"name": target},
        )

    try:
        source_record = _read_profile_record(
            profile_id=source_pointer.bucket_id,
            bucket_id=source_pointer.bucket_id,
        )
    except ProfileNotFoundError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": source},
        ) from exc

    try:
        target_id = _atomic_create_profile(
            display_name=display_name or target,
            facts=source_record.facts,
        )
    except ProfileAlreadyRegisteredError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.already_exists",
            context={"name": target},
        ) from exc

    from .._config_payloads import ConfigProfileDuplicateResult

    result = ConfigProfileDuplicateResult(
        source_profile_id=source_pointer.bucket_id,
        target_profile_id=target_id,
        display_name=display_name or target,
    )
    _emit_envelope(
        ctx,
        command="config.profile.duplicate",
        result=result,
        lines=(
            f"source_profile_id\t{source_pointer.bucket_id}",
            f"target_profile_id\t{target_id}",
            f"display_name\t{display_name or target}",
        ),
    )


# `create` and `edit` are two closures off the same wizard flow,
# each bound to its verb. The `create` closure refuses a name that
# already has a manifest; the `edit` closure refuses a name that has
# none. The verb — not a runtime-detected pointer — is the authority
# for the create-vs-edit branch.
_config_profile_create_callback = profile_app.command(
    "create",
    help=tr(
        "cli.config.profile.create_help",
        default="Initialize a new active profile.",
    ),
    epilog=tr(
        "cli.config.profile.create_epilog",
        default=(
            "Minimal freelancer profile: --entity-type natural_person"
            " --tax-id <NIF> --irpf-income-categories actividad_economica"
            " --quiet --accept-defaults"
        ),
    ),
)(_command_error_boundary(_wizard_create_command))


_config_profile_edit_callback = profile_app.command(
    "edit",
    help=tr(
        "cli.config.profile.edit_help",
        default="Re-run the wizard against an existing profile; updates values in place.",
    ),
)(_command_error_boundary(_wizard_edit_command))


@profile_app.command(
    "rename",
    help=tr(
        "cli.config.profile.rename_help",
        default="Rename a profile by updating its display label.",
    ),
)
def config_profile_rename(
    ctx: typer.Context,
    source: str = typer.Argument(
        ..., help=tr("cli.config.profile.rename_source_help", default="Existing profile name.")
    ),
    target: str = typer.Argument(..., help=tr("cli.config.profile.rename_target_help", default="New profile name.")),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Rename a profile by changing its operator-visible label.

    Profile identity is an immutable UUID, so a rename is a pure label
    edit: the encrypted record display name and the plaintext bucket
    manifest label are updated, and nothing else moves. The bucket
    directory, keystore directory, secure-object key, and active-profile
    pointer are untouched.
    """
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile import (
        ProfileAlreadyRegisteredError,
        rename_profile,
    )
    from ....domain.user_profile import ProfileNotFoundError

    pointer = _resolve_profile_by_label(source)
    try:
        record = rename_profile(profile_id=pointer.bucket_id, new_label=target)
    except ProfileAlreadyRegisteredError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.already_exists",
            context={"name": target},
        ) from exc
    except ProfileNotFoundError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": source},
        ) from exc

    from .._config_payloads import ConfigProfileRenameResult

    rename_result = ConfigProfileRenameResult(
        profile_id=record.profile_id,
        previous_display_name=source,
        display_name=record.display_name,
    )
    _emit_envelope(
        ctx,
        command="config.profile.rename",
        result=rename_result,
        lines=(
            f"profile_id\t{record.profile_id}",
            f"previous_display_name\t{source}",
            f"display_name\t{record.display_name}",
        ),
    )


@profile_app.command(
    "logout",
    help=tr(
        "cli.config.profile.logout_help",
        default="Sign out of the active profile by clearing the pointer file.",
    ),
)
def config_profile_logout(
    ctx: typer.Context,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Clear the active-profile pointer so subsequent verbs refuse without an explicit unlock."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile import logout_active_profile

    before = logout_active_profile()
    from .._config_payloads import ConfigProfileLogoutResult

    logout_result = ConfigProfileLogoutResult(
        logged_out_profile=before or "",
        active_profile=None,
        session_warning=tr("cli.config.profile.logout_session_warning"),
    )
    _emit_envelope(
        ctx,
        command="config.profile.logout",
        result=logout_result,
        lines=(
            f"logged_out_profile\t{before or '<none>'}",
            tr("cli.config.profile.logout_session_warning"),
        ),
    )


@profile_app.command("status", help=tr("cli.config.status.help"))
def config_status(
    ctx: typer.Context,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Show the readiness of the current configuration profile."""
    _activate_subcommand_output_language(ctx, output_language)
    from pydantic import ValidationError

    from ....application.user_profile import record_to_path_values
    from ....application.wizard import project_answers
    from ....application.workflow import (
        assess_active_profile_health,
        read_profile_bucket_by_id,
        workflow_state_repository,
    )
    from .._config_payloads import ConfigStatusResult

    profile_health = assess_active_profile_health()
    # The health snapshot carries the profile UUID; operators address
    # profiles by their label, so resolve it for every display line.
    active_uuid = profile_health.active_profile
    _active_pointer = read_profile_bucket_by_id(active_uuid) if active_uuid else None
    active_profile = _active_pointer.label if _active_pointer is not None else active_uuid
    if profile_health.status == "none":
        result = ConfigStatusResult(active_profile=None, registered_profile=False, configured=False)
        _emit_envelope(
            ctx,
            command="config.profile.status",
            result=result,
            lines=(
                tr("cli.config.status.empty_profile"),
                f"next_action\t{profile_health.next_action}",
            ),
        )
        return
    if profile_health.status == "dangling_pointer":
        result = ConfigStatusResult(active_profile=active_profile, registered_profile=False, configured=False)
        _emit_envelope(
            ctx,
            command="config.profile.status",
            result=result,
            lines=(
                f"profile\t{active_profile}",
                "readiness\tdangling_pointer",
                "registered_profile\tmissing",
                f"next_action\t{profile_health.next_action}",
            ),
        )
        raise typer.Exit(code=2)
    if profile_health.status in {"missing_profile_record", "profile_record_unreadable"}:
        result = ConfigStatusResult(
            active_profile=active_profile,
            registered_profile=True,
            profile_record_present=False,
            configured=False,
            profile_record_error=profile_health.profile_record_error,
        )
        lines = [
            f"profile\t{active_profile}",
            f"readiness\t{profile_health.status}",
            "registered_profile\tpresent",
            (
                "profile_record\tunreadable"
                if profile_health.status == "profile_record_unreadable"
                else "profile_record\tmissing"
            ),
        ]
        if profile_health.profile_record_error:
            lines.append(f"profile_record_error\t{profile_health.profile_record_error}")
        lines.append(f"next_action\t{profile_health.next_action}")
        _emit_envelope(ctx, command="config.profile.status", result=result, lines=lines)
        raise typer.Exit(code=2)
    state = workflow_state_repository().load()
    record = state.active_profile_record()
    values = record_to_path_values(record)
    # ``status`` reports *filing readiness*: a profile is only ``ready`` here
    # once it carries the facts needed to start filing work (a tax id and an
    # activity description). This is a stricter, forward-looking gate than the
    # *record validity* that ``config profile show`` reports — a freshly
    # created record can be schema-``valid`` (show) while still ``blocked``
    # for filing (status) because no activity has been declared yet. The two
    # surfaces use distinct header tokens (``readiness`` vs ``record_validity``)
    # so this legitimate difference no longer reads as a contradiction.
    if not values.get("identity.tax_id") or not values.get("activities.description"):
        result = ConfigStatusResult(
            active_profile=active_profile,
            tax_id_present=bool(values.get("identity.tax_id")),
            activity_present=bool(values.get("activities.description")),
            configured=False,
        )
        if active_profile is None:
            lines = (tr("cli.config.status.empty_profile"),)
        else:
            lines = (
                f"profile\t{active_profile}",
                "readiness\tblocked",
                f"identity.tax_id\t{'present' if values.get('identity.tax_id') else 'missing'}",
                f"activities.description\t{'present' if values.get('activities.description') else 'missing'}",
                f"next_action\taeat config profile edit {active_profile}",
            )
        _emit_envelope(ctx, command="config.profile.status", result=result, lines=lines)
        return
    try:
        projection = project_answers(_get_setup_flow(), values)
    except ValidationError:
        _log.debug("config profile status projection validation failed; reporting profile incomplete")
        result = ConfigStatusResult(
            active_profile=active_profile,
            profile_id=active_uuid,
            tax_id_present=bool(values.get("identity.tax_id")),
            activity_present=bool(values.get("activities.description")),
            configured=False,
        )
        _emit_envelope(
            ctx,
            command="config.profile.status",
            result=result,
            lines=(tr("cli.config.status.empty_profile"),),
        )
        return
    # Operators address a profile by its display name; the immutable
    # bucket UUID is carried as a secondary `profile_id` field so the
    # report stays unambiguous after the UUID-identity cutover.
    result = ConfigStatusResult(
        active_profile=active_profile,
        profile_id=active_uuid,
        tax_id_present=bool(values.get("identity.tax_id")),
        activity_present=bool(values.get("activities.description")),
        iva_regime=values.get("iva.regime", ""),
        tax_residence_ccaa=values.get("tax_residence.ccaa", ""),
        next_action="aeat app overview status",
    )
    _emit_envelope(
        ctx,
        command="config.profile.status",
        result=result,
        lines=(
            f"profile\t{active_profile or ''}",
            f"profile_id\t{active_uuid or ''}",
            f"identity.tax_id\t{values.get('identity.tax_id', '<unset>')}",
            f"activities.description\t{values.get('activities.description', '<unset>')}",
            f"iva.regime\t{values.get('iva.regime', '<unset>')}",
            f"tax_residence.ccaa\t{values.get('tax_residence.ccaa', '<unset>')}",
            tr("cli.config.status.next_step"),
        ),
    )
    del projection


@app.command("reset", help=tr("cli.config.reset.help"))
def config_reset(
    ctx: typer.Context,
    scope: str = typer.Option(
        "all",
        "--scope",
        click_type=_CONFIG_RESET_SCOPE_CHOICE,
        help=tr("cli.config.reset.scope_help"),
    ),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.config.reset.yes_help")),
) -> None:
    """Reset operator-entered configuration scopes."""
    from ....application.config_reset import reset_config

    if not yes:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.reset.requires_yes",
        )
    from .._config_payloads import ConfigResetResult

    scope_enum = _parse_config_reset_scope(scope)
    report = reset_config(scope_enum, confirmed=True)
    result = ConfigResetResult(
        scope=report.scope.value,
        removed_profile_ids=list(report.removed_profile_ids),
        removed_auth_session=report.removed_auth_session,
    )
    _emit_envelope(
        ctx,
        command="config.reset",
        result=result,
        lines=(
            f"scope\t{report.scope.value}",
            f"removed_profiles\t{len(report.removed_profile_ids)}",
            f"removed_auth\t{report.removed_auth_session}",
        ),
    )


from ._profile_censo import register as _register_profile_censo

_register_profile_censo(profile_app)
register_profile_bundle_commands(
    profile_app,
    profile_state=_profile_state,
    resolve_profile_by_label=_resolve_profile_by_label,
    resolve_active_profile_pointer=_resolve_active_profile_pointer,
    atomic_create_profile=_atomic_create_profile,
)

register_repair_profile_command(
    repair_app,
    resolve_profile_by_label=_resolve_profile_by_label,
    read_profile_record=_read_profile_record,
)
register_repair_maintenance_commands(repair_app)
register_bucket_history_commands(profile_app)
register_custody_commands(
    app,
    resolve_active_profile_pointer=_resolve_active_profile_pointer,
    resolve_profile_by_label=_resolve_profile_by_label,
    assert_profile_record_present=_assert_profile_record_present,
)
app.add_typer(repair_app, name="repair")
app.add_typer(profile_app, name="profile")
register_apoderado_commands(auth_app, resolve_active_profile_pointer=_resolve_active_profile_pointer)
auth_app.add_typer(auth_diagnostics_app, name="diagnostics")
app.add_typer(auth_app, name="auth")

from ._google import google_app as _google_app

app.add_typer(_google_app, name="google")

__all__ = [
    "OutputLanguage",
    "_parse_bucket_event_types",
    "apoderado_app",
    "app",
    "auth_app",
    "auth_diagnostics_app",
    "profile_app",
    "register_apoderado_commands",
    "register_bucket_history_commands",
    "register_custody_commands",
    "register_profile_bundle_commands",
    "register_repair_maintenance_commands",
    "register_repair_profile_command",
    "repair_app",
    "tr",
]
