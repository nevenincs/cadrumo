"""``aeat secrets`` CLI — operator-facing secret-store management.

Four subcommands:

- ``aeat secrets list`` — dump every persisted lookup digest (the
  plaintext keys are intentionally unrecoverable; the digest is the
  only stable handle).
- ``aeat secrets put <key>`` — persist a new secret. Reads the value
  from a file (``--from-file PATH``) or from stdin
  (``--from-stdin``). Optional flags pin classification and expiry.
- ``aeat secrets rm <key>`` — delete the record.
- ``aeat secrets rotate <key>`` — replace the value while preserving
  the existing classification + metadata.

The CLI consumes the post-#398 error decorator and the post-#399
``--json`` schema-registry contract.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import typer
from rich.console import Console

from ..storage import (
    SecretRecord,
    SensitivityClass,
    get_secret_store,
)
from ..storage.errors import (
    SecretAlreadyExistsError,
    SecretNotFoundError,
)

app = typer.Typer(help="Secret-store management.")
_console = Console()


def _parse_expires_in(value: str) -> datetime:
    """Parse a ``--expires-in`` shorthand into an absolute UTC datetime.

    Accepts the suffix shorthand ``Nd`` / ``Nh`` / ``Nm`` (days /
    hours / minutes); any other shape raises ``typer.BadParameter``.
    """
    if not value:
        raise typer.BadParameter("--expires-in must be non-empty (e.g. 90d / 24h / 30m).")
    suffix = value[-1].lower()
    quantity_str = value[:-1]
    if suffix not in {"d", "h", "m"} or not quantity_str.isdigit():
        raise typer.BadParameter("--expires-in must be Nd / Nh / Nm where N is a positive integer.")
    quantity = int(quantity_str)
    if quantity <= 0:
        raise typer.BadParameter("--expires-in must be positive.")
    delta = {
        "d": timedelta(days=quantity),
        "h": timedelta(hours=quantity),
        "m": timedelta(minutes=quantity),
    }[suffix]
    return datetime.now(UTC) + delta


def _read_value(from_file: Path | None, from_stdin: bool) -> bytes:
    if from_file is not None and from_stdin:
        raise typer.BadParameter("--from-file and --from-stdin are mutually exclusive.")
    if from_file is not None:
        return from_file.read_bytes()
    if from_stdin:
        # Read raw bytes from stdin so binary secrets (certificates,
        # PKCS#12 archives) round-trip cleanly.
        return sys.stdin.buffer.read()
    raise typer.BadParameter("supply --from-file PATH or --from-stdin.")


@app.command("list")
def list_command() -> None:
    """List the digests of every persisted secret.

    Plaintext keys are intentionally unrecoverable from the store; the
    digest is the only stable handle for inventory / auditing.
    """
    store = get_secret_store()
    digests = list(store.list_digests())
    if not digests:
        _console.print("[dim]no secrets persisted[/dim]")
        return
    for digest in digests:
        _console.print(digest)


@app.command("put")
def put_command(
    key: str = typer.Argument(..., help="Natural key under which to store the secret."),
    from_file: Path | None = typer.Option(
        None,
        "--from-file",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Read the secret value from this file.",
    ),
    from_stdin: bool = typer.Option(
        False,
        "--from-stdin",
        help="Read the secret value from stdin (raw bytes).",
    ),
    classification: SensitivityClass = typer.Option(
        SensitivityClass.SECRET,
        "--classification",
        case_sensitive=False,
        help="Sensitivity class. Must be SECRET or SESSION.",
    ),
    expires_in: str = typer.Option(
        "90d",
        "--expires-in",
        help="Expiry shorthand (e.g. 90d / 24h / 30m).",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Replace an existing record at the same key.",
    ),
) -> None:
    """Persist a new secret under ``key``."""
    if classification not in {SensitivityClass.SECRET, SensitivityClass.SESSION}:
        raise typer.BadParameter("--classification must be SECRET or SESSION.")
    value = _read_value(from_file, from_stdin)
    expires_at = _parse_expires_in(expires_in)
    record = SecretRecord(
        key=key,
        value=value,
        classification=classification,
        created_at=datetime.now(UTC),
        expires_at=expires_at,
    )
    store = get_secret_store()
    try:
        store.put(record, overwrite=overwrite)
    except SecretAlreadyExistsError as exc:
        raise typer.Exit(code=2) from exc
    _console.print(f"[green]stored[/green] under key {key!r} (expires_at={expires_at.isoformat()})")


@app.command("rm")
def rm_command(
    key: str = typer.Argument(..., help="Natural key of the record to delete."),
) -> None:
    """Delete the record persisted under ``key``."""
    store = get_secret_store()
    try:
        store.delete(key)
    except SecretNotFoundError as exc:
        raise typer.Exit(code=1) from exc
    _console.print(f"[green]deleted[/green] {key!r}")


@app.command("rotate")
def rotate_command(
    key: str = typer.Argument(..., help="Natural key of the record to rotate."),
    from_file: Path | None = typer.Option(
        None,
        "--from-file",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Read the new secret value from this file.",
    ),
    from_stdin: bool = typer.Option(
        False,
        "--from-stdin",
        help="Read the new secret value from stdin.",
    ),
    expires_in: str = typer.Option(
        "90d",
        "--expires-in",
        help="New expiry shorthand (e.g. 90d / 24h / 30m).",
    ),
) -> None:
    """Rotate the value of an existing secret."""
    value = _read_value(from_file, from_stdin)
    expires_at = _parse_expires_in(expires_in)
    store = get_secret_store()
    try:
        store.rotate(key, value, expires_at=expires_at)
    except SecretNotFoundError as exc:
        raise typer.Exit(code=1) from exc
    _console.print(f"[green]rotated[/green] {key!r} (expires_at={expires_at.isoformat()})")


__all__ = ["app"]
