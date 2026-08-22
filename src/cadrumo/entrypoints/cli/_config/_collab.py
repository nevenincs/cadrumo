"""Recipient-fingerprint registry CLI for review-package collaboration.

Mounts ``aeat config collab recipient add|list|remove`` on the ``config`` root.
A taxpayer records a trusted recipient (an accountant/gestor) by the SHA-256
fingerprint of that recipient's X25519 public key, verified out-of-band (read
aloud, compared over a separate channel) before it is trusted -- exactly the
:class:`~application.modelo.RecipientFingerprintRegistryRepository`
contract this module wires, never re-implements
(``aeat-architecture-boundaries``). The registered public key is
what ``aeat app modelo review-package encrypt-for-recipient`` seals a package
against; see :mod:`~entrypoints.cli._modelo_review_package_cli`.

``add`` is idempotent-guarded to the extent the underlying repository already
is: a duplicate ``recipient_id`` refuses instructively (``RecipientAlreadyRegisteredError``
propagates verbatim through :func:`~entrypoints.cli._errors.command_error_boundary`,
which renders every registered :class:`~core.errors.CadrumoError` at the CLI
boundary) rather than silently overwriting the prior fingerprint -- a
fingerprint swap must be an explicit ``remove`` followed by ``add``, never an
implicit clobber, since the whole point of the out-of-band verification is
that the operator confirms the exact key on file.

See Also:
    :class:`~application.modelo.RecipientFingerprintRegistryRepository`
        Active-bucket persistence boundary this CLI surface delegates to.
    :class:`~application.modelo.RecipientFingerprintRecord`
        Public-key and fingerprint record projected into command results.
    :func:`~application.modelo.public_key_hex_from_raw_bytes`
        Public-key validator used before a recipient is registered.
    :mod:`~entrypoints.cli._config._collab_payloads`
        Typed JSON payload schemas emitted by these commands.
    :mod:`~entrypoints.cli._modelo_review_package_cli`
        Review-package command group that consumes registered recipients for
        ``encrypt-for-recipient``.
"""

from __future__ import annotations

import typer

from ....application.modelo import RecipientFingerprintRegistryRepository, public_key_hex_from_raw_bytes
from ....core.i18n import tr
from .._command_policy import command_execution_policy
from .._common import _emit_envelope
from .._common import active_bucket_id_or_refuse as _active_bucket_id_or_refuse
from ._collab_payloads import (
    ConfigCollabRecipientAddResult,
    ConfigCollabRecipientListResult,
    ConfigCollabRecipientRemoveResult,
    RecipientFingerprintRowPayload,
)
from ._execution_policies import ENCRYPTED_DESTRUCTIVE, ENCRYPTED_READ, ENCRYPTED_WRITE, declare_metadata_group

collab_app = typer.Typer(
    name="collab",
    help=tr(
        "cli.config.collab.help",
    ),
    no_args_is_help=True,
)
recipient_app = typer.Typer(
    name="recipient",
    help=tr(
        "cli.config.collab.recipient.help",
    ),
    no_args_is_help=True,
)


def register_collab_commands(app: typer.Typer) -> None:
    """Mount the ``collab`` sub-app on the ``config`` root."""
    collab_app.add_typer(recipient_app, name="recipient")
    app.add_typer(collab_app, name="collab")


def _registry() -> RecipientFingerprintRegistryRepository:
    bucket_id = _active_bucket_id_or_refuse()
    return RecipientFingerprintRegistryRepository(bucket_id=bucket_id)


def _validated_public_key_hex(public_key: str) -> str:
    """Normalise and validate a CLI-supplied X25519 public key.

    A malformed hex string is a CLI input-format error (``typer.BadParameter``),
    distinct from the registry's own domain refusals (duplicate/missing id),
    which propagate as registered :class:`~core.errors.CadrumoError`
    subclasses and render automatically at the command boundary.
    """
    normalized = public_key.strip().lower()
    try:
        raw = bytes.fromhex(normalized)
    except ValueError as exc:
        raise typer.BadParameter(
            tr(
                "cli.config.collab.recipient.errors.invalid_public_key",
            ),
        ) from exc
    return public_key_hex_from_raw_bytes(raw)


@recipient_app.command(
    "add",
    help=tr(
        "cli.config.collab.recipient.add_help",
    ),
)
@command_execution_policy(ENCRYPTED_WRITE)
def collab_recipient_add(
    ctx: typer.Context,
    recipient_id: str = typer.Argument(
        ...,
        help=tr(
            "cli.config.collab.recipient.recipient_id_help",
        ),
    ),
    public_key: str = typer.Option(
        ...,
        "--public-key",
        help=tr(
            "cli.config.collab.recipient.public_key_help",
        ),
    ),
    label: str = typer.Option(
        "",
        "--label",
        help=tr(
            "cli.config.collab.recipient.label_help",
        ),
    ),
) -> None:
    """Register one trusted recipient's public key, refusing a duplicate id."""
    validated_key_hex = _validated_public_key_hex(public_key)

    registry = _registry()
    registry.add(recipient_id=recipient_id, public_key_hex=validated_key_hex, label=label)
    record = registry.get(recipient_id)

    result = ConfigCollabRecipientAddResult(
        recipient_id=record.recipient_id,
        label=record.label,
        public_key_hex=record.public_key_hex,
        fingerprint_sha256=record.fingerprint_sha256,
        added_at=record.added_at,
    )
    _emit_envelope(
        ctx,
        command="config.collab.recipient.add",
        result=result,
        lines=(
            f"recipient_id\t{record.recipient_id}",
            f"label\t{record.label}",
            f"fingerprint_sha256\t{record.fingerprint_sha256}",
        ),
    )


@recipient_app.command(
    "list",
    help=tr(
        "cli.config.collab.recipient.list_help",
    ),
)
@command_execution_policy(ENCRYPTED_READ)
def collab_recipient_list(ctx: typer.Context) -> None:
    """List every registered recipient's fingerprint."""
    registry = _registry()
    records = registry.list()

    rows = [
        RecipientFingerprintRowPayload(
            recipient_id=record.recipient_id,
            label=record.label,
            public_key_hex=record.public_key_hex,
            fingerprint_sha256=record.fingerprint_sha256,
            added_at=record.added_at,
        )
        for record in records
    ]
    result = ConfigCollabRecipientListResult(recipients=rows, count=len(rows))
    lines = [f"count\t{len(rows)}"]
    lines.extend(f"{row.recipient_id}\t{row.label}\t{row.fingerprint_sha256}" for row in rows)
    _emit_envelope(ctx, command="config.collab.recipient.list", result=result, lines=lines)


@recipient_app.command(
    "remove",
    help=tr(
        "cli.config.collab.recipient.remove_help",
    ),
)
@command_execution_policy(ENCRYPTED_DESTRUCTIVE)
def collab_recipient_remove(
    ctx: typer.Context,
    recipient_id: str = typer.Argument(
        ...,
        help=tr(
            "cli.config.collab.recipient.recipient_id_help",
        ),
    ),
) -> None:
    """Remove the recipient registered under ``recipient_id``."""
    registry = _registry()
    updated = registry.remove(recipient_id)

    result = ConfigCollabRecipientRemoveResult(recipient_id=recipient_id, remaining=len(updated.records))
    _emit_envelope(
        ctx,
        command="config.collab.recipient.remove",
        result=result,
        lines=(
            f"recipient_id\t{recipient_id}",
            f"remaining\t{len(updated.records)}",
        ),
    )


declare_metadata_group(collab_app)
declare_metadata_group(recipient_app)

__all__ = ["collab_app", "recipient_app", "register_collab_commands"]
