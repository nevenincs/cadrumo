"""``aeat security`` sub-app — operator key-management tooling.

Exposes the substrate's master-key rotation helper as a single
operator-facing command:

- ``aeat security rotate-master-key --old-key-file <path> --new-key-file <path>``
  re-encrypts every governance envelope under the new master key.

The command is read-write but does not touch AEAT remote services in
any way — it operates entirely on the operator's local disk under
the configured ``aeat_*_dir`` settings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Operator key-management commands.", no_args_is_help=True)

_console = Console()


def _read_key_file(path: Path) -> bytes:
    """Read a 32-byte raw master key from ``path``.

    The on-disk format is ASCII-hex (64 lowercase hex characters) so
    operators can safely cat / inspect / move the file without binary-
    handling concerns. The trailing newline is tolerated.
    """
    if not path.exists():
        raise typer.BadParameter(f"key file not found: {path}")
    text = path.read_text(encoding="ascii").strip()
    try:
        raw = bytes.fromhex(text)
    except ValueError as exc:
        raise typer.BadParameter(
            f"key file at {path} is not valid hex (expected 64 hex chars)",
        ) from exc
    if len(raw) != 32:
        raise typer.BadParameter(
            f"key file at {path} has {len(raw)} bytes; expected exactly 32",
        )
    return raw


@app.command("rotate-master-key")
def rotate_master_key_cmd(
    old_key_file: Annotated[
        Path,
        typer.Option(
            "--old-key-file",
            help="Path to a 64-hex-char file containing the current master key.",
        ),
    ],
    new_key_file: Annotated[
        Path,
        typer.Option(
            "--new-key-file",
            help="Path to a 64-hex-char file containing the new master key.",
        ),
    ],
) -> None:
    """Re-encrypt every governance envelope under ``--new-key-file``.

    Operator workflow:

    1. Mint a new 32-byte master key (e.g.
       ``python -c "import secrets; print(secrets.token_hex(32))" > new-key.hex``).
    2. Run ``aeat security rotate-master-key --old-key-file old.hex --new-key-file new.hex``.
    3. After the run reports rotated/skipped/errors, decommission the
       old key (move ``old.hex`` to a sealed offline backup, then
       overwrite the operating master-key source — keyring entry or
       file-fallback — with the new key bytes).

    Resume idempotency: re-running the command with the same arguments
    after a partial run is safe. Already-rotated envelopes decrypt
    under ``--new-key-file`` and are skipped.

    The command emits a summary table with per-row counts and exits
    non-zero on the first ``errors > 0`` reading so operator
    automation can gate on the result.
    """
    # Imports are deferred so non-rotate CLI commands don't pay the
    # storage substrate's Alembic plugin-discovery cost.
    from ..config import load_settings
    from ..storage import (
        EphemeralMasterKeyProvider,
        default_rotation_plan,
        rotate_master_key,
    )

    old_key = _read_key_file(old_key_file)
    new_key = _read_key_file(new_key_file)
    if old_key == new_key:
        raise typer.BadParameter(
            "--old-key-file and --new-key-file must contain different keys.",
        )
    settings = load_settings()
    old_provider = EphemeralMasterKeyProvider(key=old_key)
    new_provider = EphemeralMasterKeyProvider(key=new_key)
    summary = rotate_master_key(
        default_rotation_plan(settings),
        old_master_key_provider=old_provider,
        new_master_key_provider=new_provider,
    )

    table = Table(title="Master-key rotation summary")
    table.add_column("metric")
    table.add_column("count", justify="right")
    table.add_row("rotated", str(summary.rotated))
    table.add_row("skipped", str(summary.skipped))
    table.add_row("errors", str(summary.errors))
    _console.print(table)

    if summary.errors > 0:
        _console.print(
            "[red]One or more envelopes failed to rotate. Inspect the log "
            "for the affected paths and re-run after addressing the cause.[/red]"
        )
        raise typer.Exit(code=1)


__all__ = ["app"]
