"""User-facing configuration facade.

The ``config history`` sub-command browses the append-only event log
through :class:`BucketEventHistoryRepository`.
"""

from __future__ import annotations

import typing
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

import click
import typer

from ....application.config_reset import CONFIG_RESET_SCOPE_CLI_VALUES as _CONFIG_RESET_SCOPE_CLI_VALUES
from ....application.config_reset import parse_config_reset_scope as _parse_config_reset_scope
from ....application.operator_surface import build_help_document as _build_help_document
from ....application.operator_surface import render_help_text as _render_help_text
from ....application.wizard import build_wizard_command as _build_wizard_command
from ....application.workflow import read_profile_bucket as _read_profile_bucket
from ....core import resolve_active_bucket_id as _resolve_active_bucket_id
from ....core.errors import AeatError as _AeatError
from ....core.external_constants import OutputLanguage
from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES as _SUPPORTED_OUTPUT_LANGUAGES
from ....core.i18n import tr
from ....core.logging import get_logger as _get_logger
from ....core.redaction import (
    CLI_BUCKET_ID_PLACEHOLDER,
    CLI_PROFILE_ID_PLACEHOLDER,
    redact_for_cli_output,
    redact_structured_for_cli_output,
)
from ....core.time import now as _now
from ....core.wizard_catalogue import get_setup_flow as _get_setup_flow
from .._command_suggestions import AeatTyperGroup as _AeatTyperGroup
from .._common import _emit, _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ._apoderado import apoderado_app, register_apoderado_commands
from ._auth import auth_app
from ._auth_diagnostics import auth_diagnostics_app
from ._errors import ConfigBoundaryError as _ConfigBoundaryError
from ._repair_cli import register_repair_maintenance_commands

if typing.TYPE_CHECKING:
    from ....domain.buckets import BucketEvent, BucketEventType

_log = _get_logger(__name__)

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
bucket_app = typer.Typer(
    name="bucket",
    help=tr("cli.config.bucket.help"),
    no_args_is_help=True,
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


@repair_app.command(
    "profile",
    help=tr("cli.config.repair.profile_help"),
)
def repair_profile(
    ctx: typer.Context,
    profile: str | None = typer.Option(
        None,
        "--profile",
        help=tr("cli.config.repair.profile_name_help"),
    ),
    clear_active: bool = typer.Option(
        False,
        "--clear-active",
        help=tr("cli.config.repair.profile_clear_active_help"),
    ),
    repair_manifest_status: bool = typer.Option(
        False,
        "--repair-manifest-status",
        help=tr(
            "cli.config.repair.profile_repair_manifest_status_help",
            default="Backfill a legacy active bucket manifest status from the encrypted profile record.",
        ),
    ),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.config.repair.yes_help")),
) -> None:
    """Inspect profile health or safely repair a degraded active-profile pointer/manifest."""
    from ....application.workflow import (
        repair_active_profile_manifest_status,
        repair_active_profile_pointer,
    )
    from ....core import resolve_active_bucket_id as _resolve_active_bucket_id

    if clear_active and repair_manifest_status:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.repair.profile_one_action",
        )
    if profile is not None and not clear_active and not repair_manifest_status:
        _emit_profile_record_status(ctx, profile)
        return
    if profile is not None:
        resolved = _resolve_profile_by_label(profile)
        if resolved.bucket_id != _resolve_active_bucket_id():
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.repair.profile_clear_active_mismatch",
                context={"profile": profile},
            )
    if (clear_active or repair_manifest_status) and not yes:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.repair.profile_requires_yes",
        )
    from .._config_payloads import RepairProfileResult

    if repair_manifest_status:
        result = repair_active_profile_manifest_status(confirmed=yes)
        health = result.after or result.before
        lines = [
            f"dry_run\t{result.dry_run}",
            f"repaired\t{result.repaired}",
            f"active_profile\t{CLI_PROFILE_ID_PLACEHOLDER if health.active_profile else ''}",
            f"status\t{health.status}",
            f"manifest_status\t{result.status or ''}",
            f"reason\t{result.reason}",
        ]
        if health.profile_record_error:
            lines.append(f"profile_record_error\t{health.profile_record_error}")
        if health.next_action:
            lines.append(f"next_action\t{health.next_action}")
        repair_payload = RepairProfileResult.model_validate(
            _redact_profile_repair_payload(result.model_dump(mode="json"))
        )
        _emit_envelope(ctx, command="config.repair.profile", result=repair_payload, lines=lines)
        return
    result = repair_active_profile_pointer(clear_active=clear_active, confirmed=yes)
    health = result.after or result.before
    payload = _redact_profile_repair_payload(result.model_dump(mode="json"))
    lines = [
        f"dry_run\t{result.dry_run}",
        f"cleared_pointer\t{result.cleared_pointer}",
        f"active_profile\t{CLI_PROFILE_ID_PLACEHOLDER if health.active_profile else ''}",
        f"source\t{health.source}",
        f"status\t{health.status}",
        f"registered_bucket\t{health.registered_bucket}",
        f"profile_record_present\t{health.profile_record_present}",
        f"repairable_by_clearing_pointer\t{health.repairable_by_clearing_pointer}",
    ]
    if health.profile_record_error:
        lines.append(f"profile_record_error\t{health.profile_record_error}")
    if health.next_action:
        lines.append(f"next_action\t{health.next_action}")
    repair_payload = RepairProfileResult.model_validate(payload)
    _emit_envelope(ctx, command="config.repair.profile", result=repair_payload, lines=lines)


def _redact_profile_repair_payload(payload: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """Return a paste-safe repair payload with internal profile ids removed."""
    redacted = redact_structured_for_cli_output(payload)
    if not isinstance(redacted, dict):
        return {}
    return redacted


def _profile_record_missing_next_action(profile_id: str, *, label: str) -> str:
    if profile_id == _resolve_active_bucket_id():
        return "aeat config repair profile --clear-active --yes"
    return f"aeat config repair profile --profile {label}"


def _emit_profile_record_status(ctx: typer.Context, label: str) -> None:
    """Emit a non-secret status report for one registered profile bucket.

    ``label`` is the operator-facing profile name; it resolves to the
    immutable bucket UUID via the manifest scan.
    """
    from ....domain.user_profile import ProfileNotFoundError
    from .._config_payloads import RepairProfileResult

    pointer = _resolve_profile_by_label(label)
    profile_id = pointer.bucket_id
    try:
        record = _read_profile_record(profile_id=profile_id, bucket_id=profile_id)
    except ProfileNotFoundError:
        payload = {
            "profile_id": profile_id,
            "bucket_id": profile_id,
            "display_name": pointer.label,
            "registered_bucket": True,
            "profile_record_present": False,
            "status": "missing_profile_record",
            "next_action": _profile_record_missing_next_action(profile_id, label=pointer.label),
        }
        repair_payload = RepairProfileResult.model_validate(redact_structured_for_cli_output(payload))
        _emit_envelope(
            ctx,
            command="config.repair.profile",
            result=repair_payload,
            lines=(
                "readiness\tmissing_profile_record",
                f"profile_id\t{CLI_PROFILE_ID_PLACEHOLDER}",
                f"bucket_id\t{CLI_BUCKET_ID_PLACEHOLDER}",
                f"display_name\t{pointer.label}",
                "registered_bucket\tpresent",
                "profile_record\tmissing",
                f"next_action\t{payload['next_action']}",
            ),
        )
        raise typer.Exit(code=2) from None
    except _AeatError as exc:
        payload = {
            "profile_id": profile_id,
            "bucket_id": profile_id,
            "display_name": pointer.label,
            "registered_bucket": True,
            "profile_record_present": False,
            "status": "profile_record_unreadable",
            "error": f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else type(exc).__name__}",
            "next_action": _profile_record_unreadable_next_action(profile_id, label=pointer.label),
        }
        repair_payload = RepairProfileResult.model_validate(redact_structured_for_cli_output(payload))
        _emit_envelope(
            ctx,
            command="config.repair.profile",
            result=repair_payload,
            lines=(
                "readiness\tprofile_record_unreadable",
                f"profile_id\t{CLI_PROFILE_ID_PLACEHOLDER}",
                f"bucket_id\t{CLI_BUCKET_ID_PLACEHOLDER}",
                f"display_name\t{pointer.label}",
                "registered_bucket\tpresent",
                "profile_record\tunreadable",
                f"next_action\t{payload['next_action']}",
            ),
        )
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        _log.debug("config repair profile wrapped unexpected profile-record exception", exc_info=True)
        boundary = _ConfigBoundaryError(exc)
        payload = {
            "profile_id": profile_id,
            "bucket_id": profile_id,
            "display_name": pointer.label,
            "registered_bucket": True,
            "profile_record_present": False,
            "status": "profile_record_unreadable",
            "error": f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else type(exc).__name__}",
            "next_action": _profile_record_unreadable_next_action(profile_id, label=pointer.label),
        }
        repair_payload = RepairProfileResult.model_validate(redact_structured_for_cli_output(payload))
        _emit_envelope(
            ctx,
            command="config.repair.profile",
            result=repair_payload,
            lines=(
                "readiness\tprofile_record_unreadable",
                f"profile_id\t{CLI_PROFILE_ID_PLACEHOLDER}",
                f"bucket_id\t{CLI_BUCKET_ID_PLACEHOLDER}",
                f"display_name\t{pointer.label}",
                "registered_bucket\tpresent",
                "profile_record\tunreadable",
                f"next_action\t{payload['next_action']}",
            ),
        )
        raise typer.Exit(code=2) from boundary
    payload = {
        "profile_id": profile_id,
        "bucket_id": profile_id,
        "display_name": record.display_name,
        "registered_bucket": True,
        "profile_record_present": True,
        "status": record.status.value,
        "next_action": f"aeat config profile switch {pointer.label}",
    }
    repair_payload = RepairProfileResult.model_validate(redact_structured_for_cli_output(payload))
    _emit_envelope(
        ctx,
        command="config.repair.profile",
        result=repair_payload,
        lines=(
            "readiness\tready",
            f"display_name\t{record.display_name}",
            f"profile_id\t{CLI_PROFILE_ID_PLACEHOLDER}",
            f"bucket_id\t{CLI_BUCKET_ID_PLACEHOLDER}",
            "registered_bucket\tpresent",
            "profile_record\tpresent",
            f"status\t{record.status.value}",
            f"next_action\t{payload['next_action']}",
        ),
    )




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


def _validate_bundle_schema_version(bundle: object) -> None:
    """Raise UnsupportedBundleSchemaVersionError if bundle version is not supported."""
    from ....application.user_profile import (
        SUPPORTED_BUNDLE_SCHEMA_VERSIONS,
        UnsupportedBundleSchemaVersionError,
    )

    version = getattr(bundle, "bundle_schema_version", None)
    if version not in SUPPORTED_BUNDLE_SCHEMA_VERSIONS:
        raise UnsupportedBundleSchemaVersionError(
            f"bundle_schema_version {version!r} is not supported; "
            f"supported versions: {sorted(SUPPORTED_BUNDLE_SCHEMA_VERSIONS)}",
            translated_message="application.user_profile.errors.unsupported_bundle_schema_version",
        )


def _emit_profile_lifecycle_event(
    *,
    event_type: BucketEventType,
    bucket_id: str,
    object_id: str,
    payload: dict[str, str],
) -> None:
    """Append a profile-lifecycle event to the bucket-event-history catalogue.

    Closes W74.P357.S2067 for the export + import verbs: the symmetric
    PROFILE_EXPORTED / PROFILE_IMPORTED events join the existing
    PROFILE_BUCKET_CREATED / PROFILE_VALUES_UPDATED / PROFILE_TOMBSTONED /
    PROFILE_DUPLICATED / PROFILE_ACTIVATED emissions already wired in the
    application-layer ProfileLifecycleService / orchestration. Records the
    event through the canonical derive_bucket_event_id + repository pair so
    downstream auditors can reconstruct the sequence from the on-disk
    catalogue.
    """
    from ....domain.buckets import (
        BucketEvent,
        BucketEventHistoryCatalogue,
        BucketEventHistoryRepository,
        BucketEventObjectType,
        derive_bucket_event_id,
    )

    occurred_at = _now().replace(microsecond=0)
    actor = "operator"
    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.PROFILE,
        object_id=object_id,
        payload=payload,
    )
    event = BucketEvent(
        event_id=event_id,
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.PROFILE,
        object_id=object_id,
        payload_version=1,
        payload=payload,
    )
    repo = BucketEventHistoryRepository()
    catalogue = repo.load()
    repo.save(BucketEventHistoryCatalogue(events={**catalogue.events, event_id: event}))


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


@profile_app.command("switch", help=tr("cli.config.profile.switch_help"))
def config_profile_switch(
    ctx: typer.Context,
    name: str = typer.Argument(..., help=tr("cli.config.profile.switch_name_help")),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Select an existing profile as the active profile."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile import select_profile_with_lifecycle_span
    from ....domain.user_profile import ProfileNotFoundError

    pointer = _read_profile_bucket(name)
    if pointer is None:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": name},
        )
    _assert_profile_record_present(ctx, profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id, label=pointer.label)
    from .._config_payloads import ConfigProfileSwitchResult

    try:
        select_profile_with_lifecycle_span(pointer.bucket_id)
    except ProfileNotFoundError as exc:
        _emit_profile_record_missing(
            ctx, profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id, label=pointer.label
        )
        raise typer.Exit(code=2) from exc
    result = ConfigProfileSwitchResult(active_profile=pointer.label)
    _emit_envelope(
        ctx,
        command="config.profile.switch",
        result=result,
        lines=(f"active_profile\t{pointer.label}",),
    )


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


def _profile_record_unreadable_next_action(profile_id: str, *, label: str) -> str:
    if profile_id == _resolve_active_bucket_id():
        return "aeat config repair profile --clear-active --yes"
    return f"aeat config repair profile --profile {label}"


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


@profile_app.command("preflight", help=tr("cli.config.profile.preflight_help"))
def config_profile_preflight(
    ctx: typer.Context,
    modelo: str = typer.Option(..., "--modelo", help=tr("cli.config.profile.preflight_modelo_help")),
    revision_id: str = typer.Option(
        ..., "--revision-id", help=tr("cli.config.profile.preflight_revision_id_help")
    ),
    filing_year: int = typer.Option(
        ..., "--filing-year", help=tr("cli.config.profile.preflight_filing_year_help")
    ),
    period: str = typer.Option(..., "--period", help=tr("cli.config.profile.preflight_period_help")),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Report which profile fields a given filing context requires that are missing.

    Operates on the active profile. Exits with code ``2`` when any required
    field is missing so operators discover the gap via the shell exit status.
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
    from .._config_payloads import ConfigProfilePreflightResult, ProfilePreflightMissingPayload

    report = ProfilePreflightService(schema=load_user_profile_schema()).report(
        record=record,
        modelo=modelo,
        revision_id=revision_id,
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
        default="Initialize a new active profile and config bucket.",
    ),
    epilog=tr(
        "cli.config.profile.create_epilog",
        default=(
            "Minimal freelancer profile: --entity-type natural_person"
            " --tax-id <NIF> --irpf-income-categories actividad_economica"
            " --quiet --accept-defaults"
        ),
    ),
)(_wizard_create_command)


_config_profile_edit_callback = profile_app.command(
    "edit",
    help=tr(
        "cli.config.profile.edit_help",
        default="Re-run the wizard against an existing profile; updates values in place.",
    ),
)(_wizard_edit_command)


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
    "export",
    help=tr(
        "cli.config.profile.export_help",
        default="Write a portable profile bundle to PATH.",
    ),
)
def config_profile_export(
    ctx: typer.Context,
    name: str | None = typer.Argument(
        None,
        help=tr("cli.config.profile.export_name_help", default="Profile to export; defaults to active."),
    ),
    out: Path = typer.Option(
        ...,
        "--to",
        help=tr("cli.config.profile.export_out_help", default="Destination path for the JSON bundle."),
    ),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Serialize a profile bundle to a JSON file.

    The bundle wraps the live :class:`UserProfileRecord` read through
    the canonical lifecycle service. ``config profile import`` is the
    symmetric reader and re-provisions the record into a fresh bucket
    via the atomic-create provisioner.
    """
    from ....application.user_profile import serialize_profile_bundle
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile import profile_storage_session
    from ....domain.user_profile import ProfileNotFoundError
    from ....domain.user_profile._portable_export import UserProfilePortableExport

    _profile_state().load()
    if name is not None:
        pointer = _resolve_profile_by_label(name)
    else:
        pointer = _resolve_active_profile_pointer()
        if pointer is None:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.errors.no_active_profile",
            )
    from ....domain.buckets import BucketEventType

    # Serialize the bundle and record the PROFILE_EXPORTED lifecycle event in
    # one bucket session: the bucket-event-history repository is profile-bound
    # storage and routes to the active bucket session, so the emit must run
    # inside an open session — not after the span closes.
    def _serialize_and_record() -> UserProfilePortableExport:
        serialized = serialize_profile_bundle(bucket_id=pointer.bucket_id)
        _emit_profile_lifecycle_event(
            event_type=BucketEventType.PROFILE_EXPORTED,
            bucket_id=pointer.bucket_id,
            object_id=pointer.bucket_id,
            payload={
                "display_name": pointer.label or "",
                "out": str(out),
                "schema_version": str(serialized.bundle_schema_version),
            },
        )
        return serialized

    try:
        from ....adapters.persistence.storage import has_active_bucket_session
        from ....core import resolve_active_bucket_id as _resolve_active_bucket_id

        if pointer.bucket_id == _resolve_active_bucket_id() and has_active_bucket_session():
            bundle = _serialize_and_record()
        else:
            with profile_storage_session(pointer.bucket_id):
                bundle = _serialize_and_record()
    except ProfileNotFoundError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": pointer.label},
        ) from exc
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    from .._config_payloads import ConfigProfileExportResult

    export_result = ConfigProfileExportResult(
        profile_id=pointer.bucket_id,
        display_name=pointer.label,
        out=str(out),
        schema_version=bundle.bundle_schema_version,
    )
    _emit_envelope(
        ctx,
        command="config.profile.export",
        result=export_result,
        lines=(
            f"profile_id\t{pointer.bucket_id}",
            f"display_name\t{pointer.label}",
            f"out\t{out}",
            f"schema_version\t{bundle.bundle_schema_version}",
        ),
    )


@profile_app.command(
    "import",
    help=tr(
        "cli.config.profile.import_help",
        default="Register a portable profile bundle from PATH into the active bucket.",
    ),
)
def config_profile_import(
    ctx: typer.Context,
    path: Path = typer.Argument(
        ..., help=tr("cli.config.profile.import_path_help", default="Path to the JSON bundle.")
    ),
    label: str | None = typer.Option(
        None,
        "--label",
        help=tr("cli.config.profile.import_label_help"),
    ),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Read a portable profile bundle from a JSON file and register it.

    The imported profile lands in its **own** bucket through the
    canonical atomic-create provisioner (``register_active_profile``):
    bucket directory + manifest + encrypted record + active pointer
    in one all-or-nothing sequence. The imported bundle is recovery
    from a backup archive, so it becomes the new active profile. A
    crash mid-import rolls every write back, leaving no phantom bucket.

    ``--label`` overrides the operator-facing display name. Re-importing
    an exported profile into a storage root that already carries it
    would otherwise dead-end on a duplicate-label refusal; ``--label``
    lands the second copy under a fresh, non-colliding label while
    still minting its own immutable UUID identity.
    """
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile import (
        ProfileAlreadyRegisteredError,
        UnsupportedBundleSchemaVersionError,
        deserialize_profile_bundle,
        profile_storage_session,
    )
    from ....application.workflow import (
        read_profile_bucket as _read_profile_bucket,
    )
    from ....application.workflow import read_profile_bucket_by_id
    from ....domain.user_profile._portable_export import UserProfilePortableExport

    if not path.is_file():
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.import_missing_bundle",
            context={"path": str(path)},
        )
    try:
        bundle = UserProfilePortableExport.model_validate_json(path.read_text(encoding="utf-8"))
    except _AeatError:
        raise
    except Exception as exc:
        _log.debug("config profile import rejected invalid portable bundle", exc_info=True)
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.import_invalid_bundle",
            context={"error": str(exc)},
        ) from exc
    try:
        _validate_bundle_schema_version(bundle)
    except UnsupportedBundleSchemaVersionError as exc:
        raise _CliRefusedBoundaryError(str(exc)) from exc
    record = bundle.profile
    bundle_profile_id = record.profile_id

    # D5 two-tier collision guard. When --label is absent the operator intends
    # identity-preserving recovery: keep the bundle UUID (D5). When --label is
    # supplied the operator wants a fresh independent copy under a new name; in
    # that case mint a new UUID so the two profiles coexist without collision.
    explicit_label = label.strip() if label is not None and label.strip() else None
    fresh_uuid_mode = explicit_label is not None

    # Tier 1 (identity-preserving path): refuse if the bundle UUID already exists.
    if not fresh_uuid_mode and read_profile_bucket_by_id(bundle_profile_id) is not None:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.import_uuid_collision",
            context={"profile_id": bundle_profile_id},
        )

    target_label = explicit_label if explicit_label is not None else record.display_name
    # Tier 2: refuse if the target label is taken by any existing profile.
    existing = _read_profile_bucket(target_label)
    if existing is not None:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.import_label_taken_different_id",
            context={"name": target_label},
        )
    try:
        # Preserve the bundle's profile_id only on the identity-preserving path
        # (no --label). When --label is supplied, _atomic_create_profile mints a
        # fresh UUID so the new copy is a distinct identity.
        target_id = _atomic_create_profile(
            display_name=target_label,
            facts=record.facts,
            profile_id=None if fresh_uuid_mode else bundle_profile_id,
        )
    except ProfileAlreadyRegisteredError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.already_exists",
            context={"name": target_label},
        ) from exc
    from ....domain.buckets import BucketEventType
    from .._config_payloads import ConfigProfileImportResult

    # Import v2 financial-history objects into the newly-provisioned bucket
    # and record the PROFILE_IMPORTED lifecycle event in the same span: the
    # bucket-event-history repository is profile-bound storage and routes to
    # the active bucket session, so it must run inside the open session.
    with profile_storage_session(target_id):
        deserialize_profile_bundle(bundle, target_bucket_id=target_id)
        _emit_profile_lifecycle_event(
            event_type=BucketEventType.PROFILE_IMPORTED,
            bucket_id=target_id,
            object_id=target_id,
            payload={
                "display_name": target_label,
                "source_path": str(path),
                "schema_version": str(bundle.bundle_schema_version),
                "fresh_uuid_mode": str(fresh_uuid_mode).lower(),
            },
        )

    import_result = ConfigProfileImportResult(
        profile_id=target_id,
        display_name=target_label,
        schema_version=bundle.bundle_schema_version,
    )
    _emit_envelope(
        ctx,
        command="config.profile.import",
        result=import_result,
        lines=(
            f"profile_id\t{target_id}",
            f"display_name\t{target_label}",
            f"schema_version\t{bundle.bundle_schema_version}",
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
    """Clear the active-profile pointer so subsequent verbs refuse without an explicit switch."""
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
        click_type=click.Choice(_CONFIG_RESET_SCOPE_CLI_VALUES),
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


@bucket_app.command("history", help=tr("cli.config.bucket.history_help"))
def bucket_history(
    ctx: typer.Context,
    bucket_id: typing.Annotated[
        str,
        typer.Argument(help=tr("cli.config.bucket.bucket_id_help")),
    ],
    event_type: typing.Annotated[
        list[str] | None,
        typer.Option(
            "--event-type",
            help=tr("cli.config.bucket.event_type_help"),
        ),
    ] = None,
    since: typing.Annotated[
        str | None,
        typer.Option(
            "--since",
            help=tr("cli.config.bucket.since_help"),
        ),
    ] = None,
    until: typing.Annotated[
        str | None,
        typer.Option(
            "--until",
            help=tr("cli.config.bucket.until_help"),
        ),
    ] = None,
    object_id: typing.Annotated[
        str | None,
        typer.Option(
            "--object-id",
            help=tr("cli.config.bucket.object_id_help"),
        ),
    ] = None,
    actor: typing.Annotated[
        str | None,
        typer.Option(
            "--actor",
            help=tr("cli.config.bucket.actor_help"),
        ),
    ] = None,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Browse the append-only bucket-event history."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....domain.buckets import BucketEventHistoryRepository

    selected = _parse_bucket_event_types(event_type)
    since_dt = _parse_bucket_history_instant(since, flag="--since")
    until_dt = _parse_bucket_history_instant(until, flag="--until")
    if since_dt is not None and until_dt is not None and since_dt > until_dt:
        raise typer.BadParameter(tr("cli.config.bucket.history.since_after_until"))
    object_id_token = object_id.strip() if object_id else None
    actor_token = actor.strip() if actor else None

    catalogue = BucketEventHistoryRepository().load()
    events = tuple(
        event
        for event in catalogue.for_bucket(bucket_id, event_types=selected)
        if _bucket_history_event_matches(
            event,
            since_dt=since_dt,
            until_dt=until_dt,
            object_id_token=object_id_token,
            actor_token=actor_token,
        )
    )
    from .._config_payloads import BucketHistoryResult

    bucket_result = BucketHistoryResult(
        operation="config.bucket.history",
        bucket_id=bucket_id,
        event_types=[t.value for t in selected] if selected else None,
        since=since_dt.isoformat() if since_dt else None,
        until=until_dt.isoformat() if until_dt else None,
        object_id=object_id_token,
        actor=actor_token,
        events=[dict(_bucket_history_event_payload(event)) for event in events],
    )
    lines = ["operation\tconfig.bucket.history", f"bucket_id\t{bucket_id}", f"event_count\t{len(events)}"] + [
        f"{e.occurred_at.isoformat()}\t{e.event_type.value}\t{e.object_type.value}\t{e.object_id}\t{e.actor}"
        for e in events
    ]
    _emit_envelope(ctx, command="config.bucket.history", result=bucket_result, lines=lines)


def _parse_bucket_event_types(event_type: list[str] | None) -> tuple[BucketEventType, ...] | None:
    """Parse the ``--event-type`` flag tuple, raising :class:`typer.BadParameter` on unknown values.

    Returns ``None`` when no filter was supplied so the catalogue
    walker reads the full event stream; otherwise returns a typed
    tuple of :class:`BucketEventType`.
    """
    if not event_type:
        return None
    from ....domain.buckets import BucketEventType

    parsed: list[BucketEventType] = []
    for value in event_type:
        token = value.strip()
        try:
            parsed.append(BucketEventType(token))
        except ValueError as exc:
            # str(exc) here is Python's raw "'x' is not a valid
            # BucketEventType" — untranslated and dev-flavoured. Surface a
            # localized refusal naming the bad token and the valid set.
            raise typer.BadParameter(
                tr(
                    "cli.config.bucket.history.invalid_event_type",
                    value=token,
                    valid=", ".join(member.value for member in BucketEventType),
                ),
            ) from exc
    return tuple(parsed)


def _parse_bucket_history_instant(raw: str | None, *, flag: str) -> datetime | None:
    """Parse one ``--since`` / ``--until`` value into a :class:`datetime`, or ``None`` when absent."""
    if not raw:
        return None

    try:
        return datetime.fromisoformat(raw.strip())
    except ValueError as exc:
        raise typer.BadParameter(
            tr("cli.config.bucket.history.invalid_timestamp", flag=flag, raw=raw),
        ) from exc


def _bucket_history_event_matches(
    event: BucketEvent,
    *,
    since_dt: datetime | None,
    until_dt: datetime | None,
    object_id_token: str | None,
    actor_token: str | None,
) -> bool:
    """Return True when ``event`` passes every active history filter.

    Filters checked, in order: --since (lower bound), --until
    (upper bound), --object-id (exact match), --actor (exact match).
    ``None`` for any filter means the gate is open.
    """
    if since_dt is not None and event.occurred_at < since_dt:
        return False
    if until_dt is not None and event.occurred_at > until_dt:
        return False
    if object_id_token is not None and event.object_id != object_id_token:
        return False
    return not (actor_token is not None and event.actor != actor_token)


def _bucket_history_event_payload(event: BucketEvent) -> Mapping[str, object]:
    """Project one bucket event onto its JSON payload row."""
    return {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "occurred_at": event.occurred_at.isoformat(),
        "actor": event.actor,
        "object_type": event.object_type.value,
        "object_id": event.object_id,
        "payload": dict(event.payload),
    }


from ._profile_censo import register as _register_profile_censo

_register_profile_censo(profile_app)

app.add_typer(profile_app, name="profile")
register_apoderado_commands(auth_app, resolve_active_profile_pointer=_resolve_active_profile_pointer)
auth_app.add_typer(auth_diagnostics_app, name="diagnostics")
app.add_typer(auth_app, name="auth")
app.add_typer(bucket_app, name="bucket")

from ._google import google_app as _google_app

app.add_typer(_google_app, name="google")

__all__ = ["apoderado_app", "app", "auth_app", "tr"]

