"""CLI presentation for the registered review-package recipient operations."""

from __future__ import annotations

import typer

from ..common import emit_envelope
from ..runtime_collab_recipient import (
    submit_collab_recipient_add,
    submit_collab_recipient_list,
    submit_collab_recipient_remove,
)
from .collab_payloads import (
    ConfigCollabRecipientAddResult,
    ConfigCollabRecipientListResult,
    ConfigCollabRecipientRemoveResult,
    RecipientFingerprintRowPayload,
)


def collab_recipient_add(
    ctx: typer.Context,
    recipient_id: str,
    public_key: str,
    label: str = "",
) -> None:
    """Register one trusted recipient through its profile worker operation."""
    projection = submit_collab_recipient_add(
        ctx,
        recipient_id=recipient_id,
        public_key=public_key,
        label=label,
    ).projection
    row = projection.recipient
    result = ConfigCollabRecipientAddResult(
        recipient_id=row.recipient_id,
        label=row.label,
        public_key_hex=row.public_key_hex,
        fingerprint_sha256=row.fingerprint_sha256,
        added_at=row.added_at,
    )
    emit_envelope(
        ctx,
        command="config.collab.recipient.add",
        result=result,
        lines=(
            f"recipient_id\t{row.recipient_id}",
            f"label\t{row.label}",
            f"fingerprint_sha256\t{row.fingerprint_sha256}",
        ),
    )


def collab_recipient_list(ctx: typer.Context) -> None:
    """List the complete registered recipient set in canonical order."""
    projection = submit_collab_recipient_list(ctx).projection
    rows = [
        RecipientFingerprintRowPayload(
            recipient_id=row.recipient_id,
            label=row.label,
            public_key_hex=row.public_key_hex,
            fingerprint_sha256=row.fingerprint_sha256,
            added_at=row.added_at,
        )
        for row in projection.recipients
    ]
    result = ConfigCollabRecipientListResult(recipients=rows, count=projection.count)
    lines = [f"count\t{projection.count}"]
    lines.extend(f"{row.recipient_id}\t{row.label}\t{row.fingerprint_sha256}" for row in rows)
    emit_envelope(ctx, command="config.collab.recipient.list", result=result, lines=lines)


def collab_recipient_remove(ctx: typer.Context, recipient_id: str) -> None:
    """Remove one trusted recipient through its profile worker operation."""
    projection = submit_collab_recipient_remove(ctx, recipient_id=recipient_id).projection
    result = ConfigCollabRecipientRemoveResult(
        recipient_id=projection.recipient_id,
        remaining=projection.remaining,
    )
    emit_envelope(
        ctx,
        command="config.collab.recipient.remove",
        result=result,
        lines=(
            f"recipient_id\t{projection.recipient_id}",
            f"remaining\t{projection.remaining}",
        ),
    )


__all__ = ["collab_recipient_add", "collab_recipient_list", "collab_recipient_remove"]
