"""``aeat security`` sub-app — operator key-management + integrity tooling.

Exposes the substrate's three operator-facing security tools:

- ``aeat security rotate-master-key --old-key-file <path> --new-key-file <path>``
  re-encrypts every governance envelope under the new master key.
- ``aeat security verify-corpus --corpus <name> [--regenerate]``
  builds or verifies the SHA-256 manifest covering every file under
  a CORPUS-class root (casillas, manuals, normatives, vat).
- ``aeat security migrate-master-key-kdf [--store-dir <path>]``
  re-wraps the file-fallback master key from scrypt (v1) to Argon2id
  (v2). Must be run once on every installation that has a v1
  ``master.kdf`` on disk.

Every command is read-write on local disk only — no AEAT remote
service is touched. The configured ``aeat_*_dir`` settings drive
where the on-disk operations land.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Operator key-management + integrity commands.", no_args_is_help=True)

_console = Console()


class _CorpusName(StrEnum):
    """Operator-selectable corpus roots for ``verify-corpus``."""

    CASILLAS = "casillas"
    MANUALS = "manuals"
    NORMATIVES = "normatives"
    VAT = "vat"


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
        default_blob_store_roots,
        default_rotation_plan,
        rotate_blob_stores,
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
    envelope_summary = rotate_master_key(
        default_rotation_plan(settings),
        old_master_key_provider=old_provider,
        new_master_key_provider=new_provider,
    )
    # The blob stores wrap per-record DEKs DIRECTLY under the master
    # key (no HKDF derivation — see _blob_store._DEK_AAD); a rotation
    # that visits only CipherEnvelope files would leave every wrapped
    # DEK encrypted under the old key, rendering the blobs unreadable.
    blob_summary = rotate_blob_stores(
        default_blob_store_roots(settings),
        old_master_key_provider=old_provider,
        new_master_key_provider=new_provider,
    )

    table = Table(title="Master-key rotation summary")
    table.add_column("scope")
    table.add_column("metric")
    table.add_column("count", justify="right")
    table.add_row("envelopes", "rotated", str(envelope_summary.rotated))
    table.add_row("envelopes", "skipped", str(envelope_summary.skipped))
    table.add_row("envelopes", "errors", str(envelope_summary.errors))
    table.add_row("blob_stores", "rotated", str(blob_summary.rotated))
    table.add_row("blob_stores", "skipped", str(blob_summary.skipped))
    table.add_row("blob_stores", "errors", str(blob_summary.errors))
    _console.print(table)

    total_errors = envelope_summary.errors + blob_summary.errors
    if total_errors > 0:
        _console.print(
            "[red]One or more envelopes / wrapped DEKs failed to rotate. "
            "Inspect the log for the affected paths and re-run after addressing the cause.[/red]"
        )
        raise typer.Exit(code=1)


def _corpus_root_for(corpus: _CorpusName, settings) -> Path:  # type: ignore[no-untyped-def]
    """Resolve the on-disk root for ``corpus`` from ``settings``."""
    if corpus is _CorpusName.CASILLAS:
        return Path(settings.aeat_casillas_root)
    if corpus is _CorpusName.MANUALS:
        return Path(settings.aeat_manuals_root)
    if corpus is _CorpusName.NORMATIVES:
        return Path(settings.aeat_normatives_root)
    if corpus is _CorpusName.VAT:
        return Path(settings.aeat_vat_catalogue_root)
    raise typer.BadParameter(f"unknown corpus: {corpus!r}")


@app.command("verify-corpus")
def verify_corpus_cmd(
    corpus: Annotated[
        _CorpusName,
        typer.Option(
            "--corpus",
            case_sensitive=False,
            help="Which corpus to verify: casillas, manuals, normatives, vat.",
        ),
    ],
    regenerate: Annotated[
        bool,
        typer.Option(
            "--regenerate",
            help=(
                "Recompute the manifest after walking the corpus, replacing "
                "any existing sidecar. Use after intentional corpus updates."
            ),
        ),
    ] = False,
) -> None:
    """Verify the integrity manifest for a CORPUS-class root.

    Default: walk the corpus, compare every file's SHA-256 + size
    against the recorded manifest, and exit non-zero with a per-file
    diff on drift.

    With ``--regenerate``: skip the verify step, rebuild the manifest
    from the live corpus contents, and overwrite the sidecar in place.
    Use after intentional corpus updates (e.g. a manual re-fetch).

    Operator runbook:

    1. Run ``aeat security verify-corpus --corpus casillas`` before
       tagging a release. CI gates on a clean exit (drift = exit 1).
    2. After an intentional corpus update (e.g. updating the casilla
       table for a new fiscal year), re-run with ``--regenerate`` to
       rewrite the manifest, then commit the new sidecar.
    """
    from ..config import load_settings
    from ..storage import (
        assert_corpus_clean,
        build_corpus_manifest,
        manifest_path_for,
        save_corpus_manifest,
    )
    from ..storage.errors import CorpusManifestDriftError, CorpusManifestError

    settings = load_settings()
    corpus_root = _corpus_root_for(corpus, settings)
    if not corpus_root.exists():
        raise typer.BadParameter(f"corpus root does not exist: {corpus_root}")
    sidecar = manifest_path_for(corpus_root)

    if regenerate:
        manifest = build_corpus_manifest(corpus_root, corpus_root_name=corpus.value)
        save_corpus_manifest(manifest, sidecar)
        _console.print(
            f"[green]regenerated[/green] manifest for [bold]{corpus.value}[/bold] "
            f"with {len(manifest.entries)} entries -> {sidecar}",
        )
        return

    if not sidecar.exists():
        _console.print(
            f"[red]no manifest sidecar at {sidecar}.[/red] Run with --regenerate to create one.",
        )
        raise typer.Exit(code=1)

    try:
        assert_corpus_clean(corpus_root)
    except CorpusManifestDriftError as exc:
        _console.print(f"[red]drift detected in {corpus.value}:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except CorpusManifestError as exc:
        _console.print(f"[red]manifest invalid for {corpus.value}:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    _console.print(f"[green]clean[/green] {corpus.value} -> {sidecar}")


@app.command("migrate-master-key-kdf")
def migrate_master_key_kdf_cmd(
    store_dir: Annotated[
        Path | None,
        typer.Option(
            "--store-dir",
            help=(
                "Directory containing master.kdf + master.key + salt. Defaults to the configured aeat_secret_store_dir."
            ),
        ),
    ] = None,
) -> None:
    """Migrate the file-fallback ``master.kdf`` from scrypt (v1) to Argon2id (v2).

    Operator workflow:

    1. Ensure the existing master-key passphrase is reachable —
       either set ``AEAT_SECRET_PASSPHRASE`` in the environment, or
       be ready to type it at the interactive prompt.
    2. Run ``aeat security migrate-master-key-kdf``.
    3. Verify the substrate now loads cleanly: e.g.
       ``aeat secrets list`` should return without prompting for the
       passphrase a second time.

    The migration is resume-idempotent: re-running on an already-v2
    store reports ``skipped`` and exits 0. A wrong passphrase aborts
    cleanly without modifying the v1 store on disk.
    """
    from ..config import load_settings
    from ..storage import migrate_master_key_kdf
    from ..storage._master_key import _default_passphrase_callback
    from ..storage.errors import MasterKeyUnavailableError

    settings = load_settings()
    target_store = Path(store_dir) if store_dir is not None else Path(settings.aeat_secret_store_dir)
    if not target_store.exists():
        raise typer.BadParameter(f"secret-store directory does not exist: {target_store}")

    passphrase_text = _default_passphrase_callback()
    passphrase_bytes = passphrase_text.encode("utf-8")

    try:
        result = migrate_master_key_kdf(
            store_dir=target_store,
            passphrase=passphrase_bytes,
        )
    except MasterKeyUnavailableError as exc:
        _console.print(f"[red]migration failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    table = Table(title="master.kdf migration summary")
    table.add_column("metric")
    table.add_column("count", justify="right")
    table.add_row("migrated", str(result.migrated))
    table.add_row("skipped", str(result.skipped))
    _console.print(table)
    _console.print(f"store_dir -> {result.store_dir}")
    if result.migrated:
        _console.print("[green]master.kdf is now v2 (Argon2id).[/green]")
    else:
        _console.print("[green]master.kdf was already v2; no action required.[/green]")


__all__ = ["app"]
