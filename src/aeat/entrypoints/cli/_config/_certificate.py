"""Certificate-source registry CLI command surface.

Mounted on ``config auth`` as ``aeat config auth certificate ...``.
Register, enumerate, select, and remove named PKCS#12 certificate
sources — the multi-cert slice of GitHub issue #591 (a gestor managing
several taxpayers registers one certificate per entity and selects the
active one, rather than re-running ``auth configure --file`` on every
switch).
"""

from __future__ import annotations

from pathlib import Path

import typer

from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError

certificate_app = typer.Typer(
    name="certificate",
    help=tr(
        "cli.config.auth.certificate.help",
        default="Manage named certificate sources for the certificate auth provider",
    ),
    no_args_is_help=True,
)


@certificate_app.command(
    "register",
    help=tr(
        "cli.config.auth.certificate.register_help",
        default="Register (or re-point) a named certificate source",
    ),
)
def certificate_register(
    ctx: typer.Context,
    name: str = typer.Option(
        ...,
        "--name",
        help=tr(
            "cli.config.auth.certificate.register.name_help",
            default="Identifier for this certificate source (e.g. 'personal', 'apoderado-acme')",
        ),
    ),
    file: Path = typer.Option(
        ...,
        "--file",
        help=tr(
            "cli.config.auth.certificate.register.file_help",
            default="Path to the PKCS#12 (.p12/.pfx) bundle",
        ),
    ),
    friendly_name: str | None = typer.Option(
        None,
        "--friendly-name",
        help=tr(
            "cli.config.auth.certificate.register.friendly_name_help",
            default="Optional human-readable label distinct from --name",
        ),
    ),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Register (or re-point) a named certificate source for the active profile."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import (
        AuthConfigureDanglingActiveProfileError,
        AuthConfigureNoActiveBucketError,
        register_operator_certificate_source,
    )

    try:
        result = register_operator_certificate_source(
            name=name,
            certificate_path=file,
            friendly_name=friendly_name,
        )
    except AuthConfigureNoActiveBucketError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.no_active_bucket",
        ) from exc
    except AuthConfigureDanglingActiveProfileError as exc:
        raise _CliRefusedBoundaryError(str(exc)) from exc

    from .._config_payloads import CertificateSourceMutationPayload

    payload = CertificateSourceMutationPayload(name=result.name, certificate_path=result.certificate_path)
    _emit_envelope(
        ctx,
        command="config.auth.certificate.register",
        result=payload,
        lines=(
            f"name\t{result.name}",
            f"certificate_path\t{result.certificate_path}",
            f"next_action\taeat config auth certificate select --name {result.name}",
        ),
    )


@certificate_app.command(
    "list",
    help=tr("cli.config.auth.certificate.list_help", default="List every registered certificate source"),
)
def certificate_list(
    ctx: typer.Context,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Enumerate every registered certificate source for the active profile."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import list_operator_certificate_sources
    from .._config_payloads import CertificateSourceListPayload, CertificateSourcePayloadEntry

    report = list_operator_certificate_sources()
    payload = CertificateSourceListPayload(
        sources=[
            CertificateSourcePayloadEntry(
                name=source.name,
                certificate_path=source.certificate_path,
                friendly_name=source.friendly_name,
                active=source.active,
                registered_at=source.registered_at,
            )
            for source in report.sources
        ],
        active_source=report.active_source,
    )
    if not report.sources:
        lines = ["sources\t<none>", "next_action\taeat config auth certificate register --name NAME --file PATH"]
    else:
        lines = [f"active_source\t{report.active_source or '<none>'}"]
        for source in report.sources:
            marker = "*" if source.active else " "
            label = f" ({source.friendly_name})" if source.friendly_name else ""
            lines.append(f"{marker}\t{source.name}{label}\t{source.certificate_path}")
    _emit_envelope(ctx, command="config.auth.certificate.list", result=payload, lines=lines)


@certificate_app.command(
    "select",
    help=tr("cli.config.auth.certificate.select_help", default="Select the active certificate source"),
)
def certificate_select(
    ctx: typer.Context,
    name: str = typer.Option(
        ...,
        "--name",
        help=tr(
            "cli.config.auth.certificate.select.name_help",
            default="Registered certificate source to activate",
        ),
    ),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Mark ``name`` the active certificate source; its path becomes the certificate-provider path."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import (
        AuthConfigureDanglingActiveProfileError,
        AuthConfigureNoActiveBucketError,
        CertificateSourceNotFoundError,
        select_operator_certificate_source,
    )
    from ....core.errors import resolve_error_message

    try:
        result = select_operator_certificate_source(name=name)
    except AuthConfigureNoActiveBucketError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.no_active_bucket",
        ) from exc
    except AuthConfigureDanglingActiveProfileError as exc:
        raise _CliRefusedBoundaryError(str(exc)) from exc
    except CertificateSourceNotFoundError as exc:
        raise _CliRefusedBoundaryError(resolve_error_message(exc)) from exc

    from .._config_payloads import CertificateSourceMutationPayload

    payload = CertificateSourceMutationPayload(
        name=result.name,
        certificate_path=result.certificate_path,
        active=result.active,
    )
    _emit_envelope(
        ctx,
        command="config.auth.certificate.select",
        result=payload,
        lines=(
            f"name\t{result.name}",
            f"certificate_path\t{result.certificate_path}",
            f"active\t{result.active}",
        ),
    )


@certificate_app.command(
    "remove",
    help=tr("cli.config.auth.certificate.remove_help", default="Remove a registered certificate source"),
)
def certificate_remove(
    ctx: typer.Context,
    name: str = typer.Option(
        ...,
        "--name",
        help=tr(
            "cli.config.auth.certificate.remove.name_help",
            default="Registered certificate source to remove",
        ),
    ),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Remove ``name`` from the certificate-source registry. A no-op when ``name`` is not registered."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import (
        AuthConfigureDanglingActiveProfileError,
        AuthConfigureNoActiveBucketError,
        remove_operator_certificate_source,
    )

    try:
        result = remove_operator_certificate_source(name=name)
    except AuthConfigureNoActiveBucketError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.no_active_bucket",
        ) from exc
    except AuthConfigureDanglingActiveProfileError as exc:
        raise _CliRefusedBoundaryError(str(exc)) from exc

    from .._config_payloads import CertificateSourceMutationPayload

    payload = CertificateSourceMutationPayload(name=result.name, removed=result.removed)
    _emit_envelope(
        ctx,
        command="config.auth.certificate.remove",
        result=payload,
        lines=(
            f"name\t{result.name}",
            f"removed\t{result.removed}",
        ),
    )


__all__ = ["certificate_app"]
