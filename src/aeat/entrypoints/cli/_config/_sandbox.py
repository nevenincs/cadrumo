"""Sandboxed experiment workspace commands for ``aeat config profile sandbox``.

An operator (or an LLM agent driving the CLI) needs to run experiments
(imports, classifications, calculations) without polluting the main profile's
records, and discard the experiment cleanly afterwards. A sandbox is an
ordinary profile bucket labelled with the reserved
:data:`~aeat.application.bucket_maintenance.SANDBOX_LABEL_PREFIX`; every verb
here delegates to :mod:`aeat.application.bucket_maintenance`
(``create_sandbox`` / ``discard_sandbox`` / ``BucketMaintenanceService``),
which in turn delegates to the same atomic profile-create span and
destructive-erase primitives ``config profile create`` / ``duplicate`` /
``delete`` already use — this module owns only CLI argument parsing, pointer
resolution, and envelope emission
(``composition-service-no-parallel-write-path``).

Isolation is not a new guarantee this module invents: it is the pre-existing
per-bucket encrypted-storage boundary every profile bucket already has (one
SQLite database + one secure-object namespace root per bucket id). A sandbox
is simply a bucket an operator can create, work in, and discard on a fast,
low-ceremony lifecycle without the "is this a real client?" hesitation a bare
``config profile create`` / ``delete`` pair carries.
"""

from __future__ import annotations

import typer

from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from ....core.json_contract import Notice, NoticeSeverity
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError

sandbox_app = typer.Typer(
    name="sandbox",
    help=tr(
        "cli.config.profile.sandbox.help",
        default=("Run experiments in an isolated, discardable bucket that never touches main profile state."),
    ),
    no_args_is_help=True,
)


def register_sandbox_commands(profile_app: typer.Typer) -> None:
    """Mount the ``sandbox`` sub-app on ``config profile``."""
    _register_sandbox_create_command(sandbox_app)
    _register_sandbox_list_command(sandbox_app)
    _register_sandbox_use_command(sandbox_app)
    _register_sandbox_discard_command(sandbox_app)
    profile_app.add_typer(sandbox_app, name="sandbox")


def _register_sandbox_create_command(app: typer.Typer) -> None:
    @app.command(
        "create",
        help=tr(
            "cli.config.profile.sandbox.create_help",
            default="Fork a new isolated sandbox bucket and activate it.",
        ),
    )
    def config_profile_sandbox_create(
        ctx: typer.Context,
        name: str = typer.Argument(
            ...,
            help=tr("cli.config.profile.sandbox.create_name_help", default="Sandbox name."),
        ),
        from_profile: str | None = typer.Option(
            None,
            "--from-profile",
            help=tr(
                "cli.config.profile.sandbox.create_from_profile_help",
                default="Seed the sandbox with an existing profile's facts (read-only source).",
            ),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Create and activate a sandbox bucket through ``create_sandbox``."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.bucket_maintenance import (
            CreateSandboxCommand,
            SandboxAlreadyExistsError,
            SandboxSourceNotFoundError,
            create_sandbox,
        )
        from .._config_payloads import ConfigProfileSandboxCreateResult

        try:
            outcome = create_sandbox(CreateSandboxCommand(name=name, from_profile=from_profile))
        except SandboxAlreadyExistsError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.already_exists",
                context={"label": exc.label},
            ) from exc
        except SandboxSourceNotFoundError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.source_not_found",
                context={"name": exc.name},
            ) from exc

        result = ConfigProfileSandboxCreateResult(
            bucket_id=outcome.bucket_id,
            label=outcome.label,
            seeded_from=outcome.seeded_from,
        )
        activation_notice = Notice(
            severity=NoticeSeverity.INFO,
            code="config.profile.sandbox.create.active",
            message=tr(
                "cli.config.profile.sandbox.create_active_info",
                default=(
                    "The sandbox is now the ACTIVE profile; every command runs against "
                    "it until you switch away or discard it."
                ),
            ),
            suggestion="aeat config profile sandbox discard",
        )
        _emit_envelope(
            ctx,
            command="config.profile.sandbox.create",
            result=result,
            lines=(
                f"bucket_id\t{outcome.bucket_id}",
                f"label\t{outcome.label}",
                f"seeded_from\t{outcome.seeded_from or '<none>'}",
                f"INFO\t{activation_notice.message}",
            ),
            notices=(activation_notice,),
        )


def _register_sandbox_list_command(app: typer.Typer) -> None:
    @app.command(
        "list",
        help=tr(
            "cli.config.profile.sandbox.list_help",
            default="List every sandbox bucket.",
        ),
    )
    def config_profile_sandbox_list(
        ctx: typer.Context,
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """List every profile bucket whose label carries the sandbox prefix."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.bucket_maintenance import SANDBOX_LABEL_PREFIX
        from ....application.workflow import list_profile_buckets
        from ....core import resolve_active_bucket_id
        from .._config_payloads import ConfigProfileSandboxListResult, ProfilePointerPayload

        active = resolve_active_bucket_id()
        buckets = list_profile_buckets()
        rows = sorted(
            (pointer for pointer in buckets.values() if pointer.label.startswith(SANDBOX_LABEL_PREFIX)),
            key=lambda pointer: pointer.label.casefold(),
        )
        active_label = next((p.label for p in rows if p.bucket_id == active), None)
        result = ConfigProfileSandboxListResult(
            active_profile=active_label,
            sandboxes=[
                ProfilePointerPayload(
                    name=pointer.label,
                    bucket_id=pointer.bucket_id,
                    active=pointer.bucket_id == active,
                )
                for pointer in rows
            ],
        )
        if not rows:
            lines = ["sandboxes\t<none>"]
        else:
            lines = []
            for pointer in rows:
                marker = "*" if pointer.bucket_id == active else " "
                lines.append(f"{marker}\t{pointer.label}")
        _emit_envelope(ctx, command="config.profile.sandbox.list", result=result, lines=lines)


def _register_sandbox_use_command(app: typer.Typer) -> None:
    @app.command(
        "use",
        help=tr(
            "cli.config.profile.sandbox.use_help",
            default="Switch the active profile to an existing sandbox.",
        ),
    )
    def config_profile_sandbox_use(
        ctx: typer.Context,
        name: str = typer.Argument(
            ...,
            help=tr("cli.config.profile.sandbox.use_name_help", default="Sandbox name (without the prefix)."),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Activate an existing sandbox through the canonical select-lifecycle-span primitive."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.bucket_maintenance import sandbox_label
        from ....application.user_profile import select_profile_with_lifecycle_span
        from ....application.workflow import read_profile_bucket
        from ....domain.user_profile import ProfileNotFoundError
        from .._config_payloads import ConfigProfileSandboxUseResult

        label = sandbox_label(name)
        pointer = read_profile_bucket(label)
        if pointer is None:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.unknown_sandbox",
                context={"name": name},
            )
        try:
            select_profile_with_lifecycle_span(pointer.bucket_id)
        except ProfileNotFoundError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.unknown_sandbox",
                context={"name": name},
            ) from exc

        result = ConfigProfileSandboxUseResult(active_profile=pointer.label)
        _emit_envelope(
            ctx,
            command="config.profile.sandbox.use",
            result=result,
            lines=(f"active_profile\t{pointer.label}",),
        )


def _register_sandbox_discard_command(app: typer.Typer) -> None:
    @app.command(
        "discard",
        help=tr(
            "cli.config.profile.sandbox.discard_help",
            default="Permanently erase a sandbox bucket.",
        ),
    )
    def config_profile_sandbox_discard(
        ctx: typer.Context,
        name: str = typer.Argument(
            ...,
            help=tr("cli.config.profile.sandbox.discard_name_help", default="Sandbox name (without the prefix)."),
        ),
        confirmed: bool = typer.Option(
            False,
            "--yes",
            help=tr("cli.config.profile.sandbox.discard_yes_help", default="Confirm the destructive erase."),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Discard a sandbox bucket through ``discard_sandbox``."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.bucket_maintenance import (
            DiscardSandboxCommand,
            SandboxDiscardRefusedError,
            SandboxNotFoundError,
            discard_sandbox,
            sandbox_label,
        )
        from ....application.workflow import read_profile_bucket
        from ....domain.buckets import BucketDeleteRefusedError
        from .._config_payloads import ConfigProfileSandboxDiscardResult

        label = sandbox_label(name)
        pointer = read_profile_bucket(label)
        if pointer is None:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.unknown_sandbox",
                context={"name": name},
            )
        if not confirmed:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.discard_requires_yes",
                context={"name": name},
            )
        try:
            outcome = discard_sandbox(
                DiscardSandboxCommand(bucket_id=pointer.bucket_id, confirmed=confirmed),
            )
        except SandboxNotFoundError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.unknown_sandbox",
                context={"name": name},
            ) from exc
        except SandboxDiscardRefusedError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.discard_not_a_sandbox",
                context={"name": name},
            ) from exc
        except BucketDeleteRefusedError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.sandbox.discard_active_profile",
                context={"name": name},
            ) from exc

        result = ConfigProfileSandboxDiscardResult(
            bucket_id=outcome.bucket_id,
            previous_label=outcome.previous_label,
        )
        _emit_envelope(
            ctx,
            command="config.profile.sandbox.discard",
            result=result,
            lines=(
                f"bucket_id\t{outcome.bucket_id}",
                f"previous_label\t{outcome.previous_label}",
            ),
        )


__all__ = ["register_sandbox_commands", "sandbox_app"]
