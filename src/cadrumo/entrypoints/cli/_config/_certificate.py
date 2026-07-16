"""Certificate-source registry CLI command surface.

Mounted on ``config auth`` as ``aeat config auth certificate ...``.
Register, enumerate, select, remove, and check the expiry/rotation
health of named PKCS#12 certificate sources — multi-cert support lets
a gestor managing several taxpayers register one certificate per
entity and select the active one, rather than re-running
``auth configure --file`` on every switch. ``secret`` is the
per-source passphrase slice: instead of one global, env-only
``CADRUMO_CERTIFICATE_PASSWORD_SECRET`` shared by whichever source happens
to be active, ``certificate secret set`` binds a passphrase to one
named source through a typed
:class:`~application.auth.CertificateSecretBackend` backed solely by
encrypted secure storage.

See Also:
    :func:`~application.auth.register_operator_certificate_source`
        Application service behind ``certificate register``.
    :func:`~application.auth.list_operator_certificate_sources`
        Application service behind ``certificate list``.
    :func:`~application.auth.select_operator_certificate_source`
        Application service behind ``certificate select``.
    :class:`~application.auth.CertificateSecretBackend`
        Per-source passphrase boundary used by ``certificate secret`` verbs.
    :mod:`~entrypoints.cli._config_payloads`
        Typed JSON payload schemas shared by config auth command results.
"""

from __future__ import annotations

from pathlib import Path

import typer

from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from ....core.json_contract import Notice, NoticeSeverity
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


@certificate_app.command(
    "check",
    help=tr(
        "cli.config.auth.certificate.check_help",
        default="Check expiry/rotation health for every registered certificate source",
    ),
)
def certificate_check(
    ctx: typer.Context,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Report expiry/rotation status for every registered certificate source.

    Reuses the same local PKCS#12 expiry probe ``auth test`` runs for the
    active certificate provider, applied per named source rather than
    only the currently selected one. A source within the warning or
    critical renewal window surfaces a non-blocking warning
    :class:`~core.json_contract.Notice` naming it, so a gestor
    managing several apoderado certificates gets a reminder for each one
    individually rather than only the active certificate.
    """
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import ProviderProbeResult, check_operator_certificate_sources
    from .._config_payloads import CertificateSourceCheckEntryPayload, CertificateSourceCheckPayload

    report = check_operator_certificate_sources()
    payload = CertificateSourceCheckPayload(
        entries=[
            CertificateSourceCheckEntryPayload(
                name=entry.name,
                certificate_path=entry.certificate_path,
                friendly_name=entry.friendly_name,
                active=entry.active,
                result=entry.result,
                summary=entry.summary,
                days_until_expiry=entry.days_until_expiry,
            )
            for entry in report.entries
        ],
        has_warnings=report.has_warnings,
    )

    notices = [
        Notice(
            severity=NoticeSeverity.WARNING,
            code=f"config.auth.certificate.check.{entry.result}",
            message=f"{entry.name}: {entry.summary}",
            suggestion=f"aeat config auth certificate select --name {entry.name}",
            context={"name": entry.name, "result": entry.result},
        )
        for entry in report.entries
        if entry.result in (ProviderProbeResult.EXPIRING, ProviderProbeResult.EXPIRED)
    ]

    if not report.entries:
        lines = ["sources\t<none>", "next_action\taeat config auth certificate register --name NAME --file PATH"]
    else:
        lines = []
        for entry in report.entries:
            marker = "*" if entry.active else " "
            label = f" ({entry.friendly_name})" if entry.friendly_name else ""
            lines.append(f"{marker}\t{entry.name}{label}\t{entry.result}\t{entry.summary}")
        for notice in notices:
            lines.append(f"WARNING\t{notice.message}")

    _emit_envelope(
        ctx,
        command="config.auth.certificate.check",
        result=payload,
        lines=lines,
        notices=notices,
    )


secret_app = typer.Typer(
    name="secret",
    help=tr(
        "cli.config.auth.certificate.secret.help",
        default="Manage the passphrase bound to a named certificate source",
    ),
    no_args_is_help=True,
)
certificate_app.add_typer(secret_app)


@secret_app.command(
    "set",
    help=tr(
        "cli.config.auth.certificate.secret.set_help",
        default="Set (or rotate) the passphrase for a registered certificate source",
    ),
)
def certificate_secret_set(
    ctx: typer.Context,
    name: str = typer.Option(
        ...,
        "--name",
        help=tr(
            "cli.config.auth.certificate.secret.set.name_help",
            default="Registered certificate source the passphrase is bound to",
        ),
    ),
    secret: str = typer.Option(
        ...,
        "--secret",
        prompt=True,
        hide_input=True,
        confirmation_prompt=False,
        help=tr(
            "cli.config.auth.certificate.secret.set.secret_help",
            default="The PKCS#12 passphrase (prompted, hidden, never echoed)",
        ),
    ),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Bind (or rotate) the passphrase for the named certificate source."""
    _activate_subcommand_output_language(ctx, output_language)
    from pydantic import SecretStr

    from ....application.auth import (
        AuthConfigureDanglingActiveProfileError,
        AuthConfigureNoActiveBucketError,
        CertificateSourceNotFoundError,
        set_operator_certificate_source_secret,
    )
    from ....core.errors import resolve_error_message

    try:
        result = set_operator_certificate_source_secret(
            name=name,
            secret=SecretStr(secret),
        )
    except AuthConfigureNoActiveBucketError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.no_active_bucket",
        ) from exc
    except AuthConfigureDanglingActiveProfileError as exc:
        raise _CliRefusedBoundaryError(str(exc)) from exc
    except CertificateSourceNotFoundError as exc:
        raise _CliRefusedBoundaryError(resolve_error_message(exc)) from exc

    from .._config_payloads import CertificateSourceSecretMutationPayload

    payload = CertificateSourceSecretMutationPayload(
        name=result.name,
        backend=result.backend,
        has_secret=result.has_secret,
        rotated=result.rotated,
    )
    _emit_envelope(
        ctx,
        command="config.auth.certificate.secret.set",
        result=payload,
        lines=(
            f"name\t{result.name}",
            f"backend\t{result.backend}",
            f"rotated\t{result.rotated}",
        ),
    )


@secret_app.command(
    "remove",
    help=tr(
        "cli.config.auth.certificate.secret.remove_help",
        default="Remove the passphrase bound to a registered certificate source",
    ),
)
def certificate_secret_remove(
    ctx: typer.Context,
    name: str = typer.Option(
        ...,
        "--name",
        help=tr(
            "cli.config.auth.certificate.secret.remove.name_help",
            default="Registered certificate source whose passphrase should be removed",
        ),
    ),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Remove the passphrase bound to the named certificate source. A no-op when unset."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import (
        AuthConfigureDanglingActiveProfileError,
        AuthConfigureNoActiveBucketError,
        remove_operator_certificate_source_secret,
    )

    try:
        result = remove_operator_certificate_source_secret(name=name)
    except AuthConfigureNoActiveBucketError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.no_active_bucket",
        ) from exc
    except AuthConfigureDanglingActiveProfileError as exc:
        raise _CliRefusedBoundaryError(str(exc)) from exc

    from .._config_payloads import CertificateSourceSecretMutationPayload

    payload = CertificateSourceSecretMutationPayload(
        name=result.name,
        backend=result.backend,
        has_secret=result.has_secret,
        removed=result.removed,
    )
    _emit_envelope(
        ctx,
        command="config.auth.certificate.secret.remove",
        result=payload,
        lines=(
            f"name\t{result.name}",
            f"backend\t{result.backend}",
            f"removed\t{result.removed}",
        ),
    )


__all__ = ["certificate_app"]
