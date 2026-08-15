"""User-facing configuration facade.

The ``config profile history`` sub-command browses the append-only event
log through :class:`BucketEventHistoryRepository`. The ``config profile
show`` sub-command reads and renders the active profile's persisted
:class:`UserProfileRecord`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import typer

from ....application.operator_surface import build_help_document as _build_help_document
from ....application.operator_surface import render_help_text as _render_help_text
from ....core import resolve_active_bucket_id as _resolve_active_bucket_id
from ....core.external_constants import OutputLanguage as _OutputLanguage
from ....core.i18n import tr
from ....core.logging import get_logger as _get_logger
from ....core.wizard_catalogue import get_setup_flow as _get_setup_flow
from .._command_suggestions import CadrumoTyperGroup as _CadrumoTyperGroup
from .._common import _emit_envelope, resolve_cli_precondition_action
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ._apoderado import apoderado_app, register_apoderado_commands
from ._auth import auth_app
from ._auth_diagnostics import auth_diagnostics_app
from ._bucket_history import register_bucket_history_commands
from ._censo_file import register_censo_commands as _register_censo_commands
from ._certificate import certificate_app
from ._collab import register_collab_commands
from ._custody import register_custody_commands
from ._descendiente import register_descendiente_commands
from ._login_frontend import offer_login_to_a_gated_verb
from ._manager_dispatch import register_lazy_wizard_leaf as _register_lazy_wizard_leaf

# `_resolve_preflight_revision_id` moved to `_profile_inspect` alongside the
# preflight verb, but this package remains its import site: a consumer already
# reaches it through here, and the extraction was meant to be facade-preserving.
# Keeping the re-export is what makes that true rather than merely claimed.
from ._profile_delete import register_profile_delete_command as _register_profile_delete_command
from ._profile_inspect import _resolve_preflight_revision_id as _resolve_preflight_revision_id
from ._profile_inspect import register_profile_inspect_commands as _register_profile_inspect_commands
from ._profile_readiness import _read_profile_record
from ._repair_cli import register_repair_maintenance_commands
from ._repair_profile import register_repair_profile_command
from ._reset_cli import register_reset_commands
from ._status_rendering import blocked_readiness_status as _blocked_readiness_status
from ._status_rendering import precondition_action_lines as _precondition_action_lines
from ._status_rendering import unavailable_profile_record_status as _unavailable_profile_record_status
from ._storage_cli import register_storage_commands as _register_storage_commands
from ._storage_cli import storage_app as storage_app

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


@app.callback()
def config_root(
    ctx: typer.Context,
    help_: bool = typer.Option(False, "--help", "-h", help=tr("cli.config.workflow_help"), is_eager=True),
) -> None:
    """Render config-level workflow help when requested."""
    if help_ or ctx.invoked_subcommand is None:
        from .._config_payloads import ConfigHelpEntryPayload, ConfigHelpSectionPayload, ConfigRootResult

        document = _build_help_document("config")
        result = ConfigRootResult(
            surface=document.surface,
            heading=document.heading,
            paragraphs=list(document.paragraphs),
            sections=[
                ConfigHelpSectionPayload(
                    title=section.title,
                    entries=[
                        ConfigHelpEntryPayload(command=entry.command, description=entry.description)
                        for entry in section.entries
                    ],
                )
                for section in document.sections
            ],
            footer=document.footer,
        )
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


def _profile_list_lines(
    rows: Sequence[_ProfileBucketPointer],
    *,
    active: str | None,
    active_label: str | None,
) -> list[str]:
    """Render the profile listing rows, marking the active profile.

    The committed-capsule pointer is an identity-and-label projection. Record
    setup state is intentionally absent until an authenticated record read.
    """
    lines = [f"active_profile\t{active_label or '<none>'}"]
    if not rows:
        lines.append("profiles\t<none>")
        return lines
    lines.extend(f"{'*' if pointer.bucket_id == active else ' '}\t{pointer.label}" for pointer in rows)
    return lines


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
    """List every registered profile via the committed-capsule projection.

    Replaces the prior behaviour that enumerated only the active
    profile's key values (Axis B / Axis D / dual-persona pain). The
    canonical source of profile-existence truth is the committed
    custody capsule set: :func:`list_profile_buckets` projects
    :class:`CommittedProfileRepository` (itself backed by the custody
    adapter's current-capsule discovery) and returns the full set
    without unlocking any bucket. The per-bucket ``manifest.toml``
    file is retired: nothing in this application writes one, and no
    listing or resolution path reads it -- check
    ``PROFILE_CUSTODY_RETIRED_BUCKET_MEMBER_PATHS`` in
    ``adapters.persistence.storage.custody`` if that ever needs
    reconfirming.
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
    lines = _profile_list_lines(rows, active=active, active_label=active_label)
    _emit_envelope(ctx, command="config.profile.list", result=result, lines=lines)


_register_lazy_wizard_leaf(
    "create",
    "create",
    help=tr(
        "cli.config.profile.create_help",
    ),
    epilog=tr(
        "cli.config.profile.create_epilog",
    ),
)


_register_lazy_wizard_leaf(
    "edit",
    "edit",
    help=tr(
        "cli.config.profile.edit_help",
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
    active_profile = _active_pointer.label if _active_pointer is not None else None
    health_action = (
        resolve_cli_precondition_action(profile_health.precondition_verdict)
        if profile_health.precondition_verdict is not None
        else None
    )
    if profile_health.status == "none":
        result = ConfigStatusResult(
            active_profile=None,
            registered_profile=False,
            configured=False,
            precondition_action=health_action,
        )
        _emit_envelope(
            ctx,
            command="config.profile.status",
            result=result,
            lines=(
                tr("cli.config.status.empty_profile"),
                *_precondition_action_lines(health_action),
            ),
        )
        return
    if profile_health.status == "dangling_pointer":
        result = ConfigStatusResult(
            active_profile=active_profile,
            registered_profile=False,
            configured=False,
            precondition_action=health_action,
        )
        _emit_envelope(
            ctx,
            command="config.profile.status",
            result=result,
            lines=(
                f"profile\t{active_profile}",
                "readiness\tdangling_pointer",
                "registered_profile\tmissing",
                *_precondition_action_lines(health_action),
            ),
        )
        raise typer.Exit(code=2)
    if profile_health.status in {"missing_profile_record", "profile_record_unreadable"}:
        result, lines = _unavailable_profile_record_status(
            active_profile=active_profile,
            status=profile_health.status,
            profile_record_error=profile_health.profile_record_error,
            precondition_action=health_action,
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
            precondition_action=health_action,
        )
        _emit_envelope(ctx, command="config.profile.status", result=result, lines=lines)
        raise typer.Exit(code=2)
    values = record_to_path_values(record)
    if profile_health.status == "incomplete":
        result, lines = _blocked_readiness_status(
            active_profile=active_profile,
            profile_id=active_uuid,
            values=values,
            precondition_action=health_action,
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
            precondition_action=None,
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
from ._provision_cli import register_provision_commands as _register_provision_commands

_register_profile_capabilities(profile_app)
_register_config_check(app)
_register_provision_commands(app)
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
_register_profile_delete_command(profile_app, resolve_profile_by_label=_resolve_profile_by_label)
register_custody_commands(app)
register_descendiente_commands(
    profile_app,
    resolve_active_profile_pointer=_resolve_active_profile_pointer,
)
register_reset_commands(app)
app.add_typer(repair_app, name="repair")
app.add_typer(profile_app, name="profile")
_register_storage_commands(app)
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
    "offer_login_to_a_gated_verb",
    "profile_app",
    "register_apoderado_commands",
    "register_bucket_history_commands",
    "register_collab_commands",
    "register_custody_commands",
    "register_descendiente_commands",
    "register_repair_maintenance_commands",
    "register_repair_profile_command",
    "register_reset_commands",
    "repair_app",
    "storage_app",
    "tr",
]
