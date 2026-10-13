"""CLI presentation for model-provider settings: masked status and the person's guarded changes.

Mounted as ``aeat config provider``. A key is read once from the protected
machine-secret channel (or a no-echo prompt) and is never an argument, an
output field or a log value; every result is the masked status contract.
"""

from __future__ import annotations

import typer
from pydantic import SecretStr

from ....application.provider_settings.contracts import ProviderSettingsRefusalCode, ProviderStatusEntry
from ....core.i18n.render import tr
from ..common import emit_envelope
from .secure_input import MachineSecretPayload


class ProviderSecretSetSecrets(MachineSecretPayload):
    """Strict machine-channel payload for ``config provider set``: the provider key only."""

    secret: SecretStr


def _entry_line(entry: ProviderStatusEntry) -> str:
    return "\t".join(
        (
            entry.id,
            entry.mode.value,
            entry.readiness.value,
            entry.source.value,
            entry.reason.value if entry.reason is not None else "-",
            entry.revision,
        )
    )


def provider_status(ctx: typer.Context) -> None:
    """List every provider's masked status and the revision each change sends back."""
    from .runtime_provider_settings import read_status

    status = read_status(ctx)
    emit_envelope(
        ctx,
        command="config.provider.status",
        result=status,
        lines=(f"development\t{status.development}", *(_entry_line(entry) for entry in status.providers)),
    )


def _emit_entry(ctx: typer.Context, command: str, entry: ProviderStatusEntry) -> None:
    emit_envelope(ctx, command=command, result=entry, lines=(_entry_line(entry),))


def provider_set(
    ctx: typer.Context,
    provider_id: str,
    expected_revision: str,
    base_url: str | None = None,
    clear_base_url: bool = False,
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
) -> None:
    """Store or replace one provider's key; it is checked for form only and reads ``not_verified``."""
    from .runtime_provider_settings import refuse, set_credential
    from .secure_input import prompt_secret_no_echo, read_machine_secret_payload, select_machine_secret_channel

    if base_url is not None and clear_base_url:
        refuse(ProviderSettingsRefusalCode.BASE_URL_REJECTED)
    selection = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    if selection is not None:
        value = read_machine_secret_payload(ProviderSecretSetSecrets, selection=selection).secret.get_secret_value()
    else:
        value = prompt_secret_no_echo(tr("cli.config.provider.secret_prompt"))
    try:
        entry = set_credential(
            ctx,
            provider_id=provider_id,
            expected_revision=expected_revision,
            base_url=base_url,
            clear_base_url=clear_base_url,
            secret=bytearray(value.encode("utf-8")),
        )
    finally:
        value = ""
    _emit_entry(ctx, "config.provider.set", entry)


def provider_remove(ctx: typer.Context, provider_id: str, expected_revision: str) -> None:
    """Turn one provider off; its key is dropped and no development fallback applies."""
    from .runtime_provider_settings import remove_credential

    _emit_entry(
        ctx,
        "config.provider.remove",
        remove_credential(ctx, provider_id=provider_id, expected_revision=expected_revision),
    )


def provider_reset(ctx: typer.Context, provider_id: str, expected_revision: str) -> None:
    """Return one provider to unset."""
    from .runtime_provider_settings import reset_provider

    _emit_entry(
        ctx,
        "config.provider.reset",
        reset_provider(ctx, provider_id=provider_id, expected_revision=expected_revision),
    )


__all__ = [
    "ProviderSecretSetSecrets",
    "provider_remove",
    "provider_reset",
    "provider_set",
    "provider_status",
]
