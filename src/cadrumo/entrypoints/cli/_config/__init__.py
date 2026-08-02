"""User-facing configuration facade.

The ``config profile history`` sub-command browses the append-only event
log through :class:`BucketEventHistoryRepository`. The ``config profile
show`` sub-command reads and renders the active profile's persisted
:class:`UserProfileRecord`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import click
import typer

from ....application.operator_surface import build_help_document as _build_help_document
from ....application.operator_surface import render_help_text as _render_help_text
from ....core import resolve_active_bucket_id as _resolve_active_bucket_id
from ....core.external_constants import OutputLanguage as _OutputLanguage
from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES as _SUPPORTED_OUTPUT_LANGUAGES
from ....core.i18n import tr
from ....core.json_contract import Notice as _Notice
from ....core.json_contract import NoticeSeverity as _NoticeSeverity
from ....core.logging import get_logger as _get_logger
from ....core.wizard_catalogue import get_setup_flow as _get_setup_flow
from .._command_suggestions import CadrumoTyperGroup as _CadrumoTyperGroup
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ._apoderado import apoderado_app, register_apoderado_commands
from ._auth import auth_app
from ._auth_diagnostics import auth_diagnostics_app
from ._bucket_archive import register_bucket_archive_commands
from ._bucket_history import register_bucket_history_commands
from ._censo_file import register_censo_commands as _register_censo_commands
from ._certificate import certificate_app
from ._collab import register_collab_commands
from ._custody import register_custody_commands
from ._descendiente import register_descendiente_commands
from ._manager_dispatch import register_lazy_wizard_leaf as _register_lazy_wizard_leaf
from ._profile_bundle import register_profile_bundle_commands

# `_resolve_preflight_revision_id` moved to `_profile_inspect` alongside the
# preflight verb, but this package remains its import site: a consumer already
# reaches it through here, and the extraction was meant to be facade-preserving.
# Keeping the re-export is what makes that true rather than merely claimed.
from ._profile_inspect import _resolve_preflight_revision_id as _resolve_preflight_revision_id
from ._profile_inspect import register_profile_inspect_commands as _register_profile_inspect_commands
from ._profile_readiness import _read_profile_record
from ._repair_cli import register_repair_maintenance_commands
from ._repair_profile import register_repair_profile_command
from ._reset_cli import register_reset_commands
from ._sandbox import register_sandbox_commands
from ._status_rendering import blocked_readiness_status as _blocked_readiness_status
from ._status_rendering import unavailable_profile_record_status as _unavailable_profile_record_status

if TYPE_CHECKING:
    from ....application.workflow import ProfileBucketPointer as _ProfileBucketPointer


_log = _get_logger(__name__)

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
    cls=_CadrumoTyperGroup,
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
        from .._config_payloads import ConfigRootResult

        document = _build_help_document("config")
        result = ConfigRootResult.model_validate(document.model_dump(mode="json"))
        _emit_envelope(
            ctx,
            command="root.config",
            result=result,
            lines=_render_help_text(document).splitlines(),
        )
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
    from ....application.workflow import ProfileLabelAmbiguousError as _ProfileLabelAmbiguousError
    from ....application.workflow import read_profile_bucket as _read_profile_bucket

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
            ),
        )
    return profile_id


def _profile_list_lines(
    rows: Sequence[_ProfileBucketPointer],
    *,
    active: str | None,
    active_label: str | None,
) -> list[str]:
    """Render the profile listing rows, marking the active profile.

    The trailing status token keys on the stable machine value so a
    ``setup_incomplete`` profile — listed and resumable, but not yet
    workable — is never rendered indistinguishably from a workable
    ``active`` one.
    """
    lines = [f"active_profile\t{active_label or '<none>'}"]
    if not rows:
        lines.append("profiles\t<none>")
        return lines
    lines.extend(
        f"{'*' if pointer.bucket_id == active else ' '}\t{pointer.label}\t{pointer.status.value}" for pointer in rows
    )
    return lines


def _profile_setup_incomplete_notices(pointers: Sequence[_ProfileBucketPointer]) -> list[_Notice]:
    """Build the non-blocking advisory for profiles still completing setup.

    A ``SETUP_INCOMPLETE`` profile is live and resumable but not workable,
    so the listing surfaces it through the typed Notice channel — never a
    bespoke advisory payload field. Returns an empty list when no profile
    is mid-setup, so a fully-onboarded listing carries no notice.
    """
    if not pointers:
        return []
    labels = ", ".join(sorted(pointer.label for pointer in pointers))
    return [
        _Notice(
            severity=_NoticeSeverity.INFO,
            code="config.profile.setup_incomplete",
            message=tr(
                "cli.config.list.setup_incomplete_notice",
                count=len(pointers),
                labels=labels,
            ),
            suggestion="aeat config profile status",
            context={"count": str(len(pointers)), "labels": labels},
        ),
    ]


@profile_app.command("list", help=tr("cli.config.list.help"))
def config_list(
    ctx: typer.Context,
    output_language: _OutputLanguage | None = typer.Option(
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
    from ....domain.user_profile import UserProfileStatus
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
                status=pointer.status,
            )
            for pointer in rows
        ],
    )
    lines = _profile_list_lines(rows, active=active, active_label=active_label)
    # An incomplete profile is visible but not workable; surface that as a
    # non-blocking advisory on the typed Notice channel rather than a silent
    # active-looking row (per the CLI-notice diagnostic contract).
    incomplete = [pointer for pointer in rows if pointer.status is UserProfileStatus.SETUP_INCOMPLETE]
    notices = _profile_setup_incomplete_notices(incomplete)
    _emit_envelope(ctx, command="config.profile.list", result=result, lines=lines, notices=notices)


@profile_app.command("delete", help=tr("cli.config.profile.delete_help"))
def config_profile_delete(
    ctx: typer.Context,
    name: str = typer.Argument(..., help=tr("cli.config.profile.delete_name_help")),
    confirmed: bool = typer.Option(False, "--yes", help=tr("cli.config.profile.delete_yes_help")),
    output_language: _OutputLanguage | None = typer.Option(
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
    # session: like ``config login``, it opens its own scoped to the target.
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
        None,
        "--display-name",
        help=tr("cli.config.profile.duplicate_display_name_help"),
    ),
    output_language: _OutputLanguage | None = typer.Option(
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


_register_lazy_wizard_leaf(
    "create",
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
)


_register_lazy_wizard_leaf(
    "edit",
    "edit",
    help=tr(
        "cli.config.profile.edit_help",
        default="Re-run the wizard against an existing profile; updates values in place.",
    ),
)


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
        ...,
        help=tr("cli.config.profile.rename_source_help", default="Existing profile name."),
    ),
    target: str = typer.Argument(..., help=tr("cli.config.profile.rename_target_help", default="New profile name.")),
    output_language: _OutputLanguage | None = typer.Option(
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

    The verb routes through :class:`BucketMaintenanceService` so the
    operator invocation co-emits ``BUCKET_RENAMED`` (maintenance verb)
    alongside the ``PROFILE_RENAMED`` lifecycle event the inner
    single-writer primitive emits, giving the audit trail both events.
    """
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.bucket_maintenance import (
        BucketMaintenanceService,
        RenameBucketCommand,
    )
    from ....application.user_profile import ProfileAlreadyRegisteredError
    from ....domain.user_profile import ProfileNotFoundError

    if not target.strip():
        # The typed RenameBucketCommand refuses a blank label at model
        # validation; surface the same localised refusal the inner
        # primitive raises so the operator never sees a raw schema error.
        raise _CliRefusedBoundaryError(
            translated_message="application.user_profile.errors.profile_label_blank",
            context={"name": source},
        )
    pointer = _resolve_profile_by_label(source)
    try:
        outcome = BucketMaintenanceService().rename(
            RenameBucketCommand(bucket_id=pointer.bucket_id, new_label=target),
        )
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
        profile_id=outcome.bucket_id,
        previous_display_name=source,
        display_name=outcome.new_label,
    )
    _emit_envelope(
        ctx,
        command="config.profile.rename",
        result=rename_result,
        lines=(
            f"profile_id\t{outcome.bucket_id}",
            f"previous_display_name\t{source}",
            f"display_name\t{outcome.new_label}",
        ),
    )


@profile_app.command("status", help=tr("cli.config.status.help"))
def config_status(
    ctx: typer.Context,
    output_language: _OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Show the readiness of the current configuration profile."""
    _activate_subcommand_output_language(ctx, output_language)
    from ._status_frontend import present_status_tui

    # A capable interactive console presents the read-only full-screen status
    # page; a ``--format json`` request and any non-interactive host fall
    # through to the unchanged envelope path below, so the machine contract is
    # reached identically for every non-interactive and JSON caller.
    if present_status_tui(ctx):
        return
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
        result, lines = _unavailable_profile_record_status(
            active_profile=active_profile,
            status=profile_health.status,
            profile_record_error=profile_health.profile_record_error,
            next_action=profile_health.next_action,
        )
        _emit_envelope(ctx, command="config.profile.status", result=result, lines=lines)
        raise typer.Exit(code=2)
    state = workflow_state_repository().load()
    record = state.active_profile_record()
    if record is None:
        result, lines = _unavailable_profile_record_status(
            active_profile=active_profile,
            status="missing_profile_record",
            profile_record_error=None,
            next_action=profile_health.next_action,
        )
        _emit_envelope(ctx, command="config.profile.status", result=result, lines=lines)
        raise typer.Exit(code=2)
    values = record_to_path_values(record)
    if profile_health.status == "incomplete":
        result, lines = _blocked_readiness_status(
            active_profile=active_profile,
            profile_id=active_uuid,
            values=values,
            line_next_action=profile_health.next_action,
            result_next_action=profile_health.next_action,
            missing_required=profile_health.missing_required,
        )
        _emit_envelope(ctx, command="config.profile.status", result=result, lines=lines)
        return
    # ``status`` reports the same profile-wide filing baseline as the modelo
    # readiness gate. An activity description is required when the profile
    # declares economic activity (or is a legal entity), not for a lawful
    # no-business natural person whose only return can be Modelo 100.
    from ....application.modelo import modelo_work_profile_baseline_missing_paths

    baseline_missing = modelo_work_profile_baseline_missing_paths(record)
    if baseline_missing:
        result, blocked_lines = _blocked_readiness_status(
            active_profile=active_profile,
            profile_id=None,
            values=values,
            line_next_action=f"aeat config profile edit {active_profile}",
            result_next_action=None,
        )
        lines = (tr("cli.config.status.empty_profile"),) if active_profile is None else blocked_lines
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
        configured=True,
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


from ._capabilities_cli import register as _register_profile_capabilities
from ._check_cli import register as _register_config_check

_register_profile_capabilities(profile_app)
_register_config_check(app)
register_profile_bundle_commands(
    profile_app,
    atomic_create_profile=_atomic_create_profile,
)
_register_profile_inspect_commands(
    profile_app,
    resolve_active_profile_pointer=_resolve_active_profile_pointer,
)

register_repair_profile_command(
    repair_app,
    resolve_profile_by_label=_resolve_profile_by_label,
    read_profile_record=_read_profile_record,
)
register_repair_maintenance_commands(repair_app)
register_bucket_history_commands(profile_app)
register_bucket_archive_commands(
    profile_app,
    resolve_profile_by_label=_resolve_profile_by_label,
    resolve_active_profile_pointer=_resolve_active_profile_pointer,
)
register_custody_commands(app)
register_descendiente_commands(
    profile_app,
    resolve_active_profile_pointer=_resolve_active_profile_pointer,
)
register_sandbox_commands(profile_app)
register_reset_commands(app)
app.add_typer(repair_app, name="repair")
app.add_typer(profile_app, name="profile")
register_apoderado_commands(auth_app, resolve_active_profile_pointer=_resolve_active_profile_pointer)
_register_censo_commands(profile_app)
auth_app.add_typer(auth_diagnostics_app, name="diagnostics")
auth_app.add_typer(certificate_app, name="certificate")
app.add_typer(auth_app, name="auth")
register_collab_commands(app)

from ._google import google_app as _google_app

app.add_typer(_google_app, name="google")

__all__ = [
    "apoderado_app",
    "app",
    "auth_app",
    "auth_diagnostics_app",
    "certificate_app",
    "profile_app",
    "register_apoderado_commands",
    "register_bucket_archive_commands",
    "register_bucket_history_commands",
    "register_collab_commands",
    "register_custody_commands",
    "register_descendiente_commands",
    "register_profile_bundle_commands",
    "register_repair_maintenance_commands",
    "register_repair_profile_command",
    "register_reset_commands",
    "register_sandbox_commands",
    "repair_app",
    "tr",
]
