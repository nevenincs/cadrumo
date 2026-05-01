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

    The on-disk format is ASCII-hex (64 hex characters; ``bytes.fromhex``
    accepts both upper- and lower-case) so operators can safely cat /
    inspect / move the file without binary-handling concerns. The
    trailing newline is tolerated.
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
    recovery_key: Annotated[
        str | None,
        typer.Option(
            "--recovery-key",
            help=(
                "Existing 24-word recovery mnemonic. The substrate re-wraps "
                "``master.recovery.key`` under the new master key while "
                "preserving the operator's printed mnemonic. Mutually "
                "exclusive with ``--regenerate-recovery-key``."
            ),
        ),
    ] = None,
    regenerate_recovery_key: Annotated[
        bool,
        typer.Option(
            "--regenerate-recovery-key",
            help=(
                "Mint a fresh recovery key + 24-word mnemonic and re-wrap "
                "``master.recovery.key`` under it. The substrate displays "
                "the new mnemonic ONCE; the previously-printed mnemonic is "
                "permanently invalidated. Mutually exclusive with "
                "``--recovery-key``."
            ),
        ),
    ] = False,
) -> None:
    """Re-encrypt every governance envelope under ``--new-key-file``.

    Operator workflow:

    1. Mint a new 32-byte master key (e.g.
       ``python -c "import secrets; print(secrets.token_hex(32))" > new-key.hex``).
    2. Run ``aeat security rotate-master-key --old-key-file old.hex --new-key-file new.hex``,
       supplying EITHER ``--recovery-key "<24 words>"`` (to preserve the
       operator's existing mnemonic) OR ``--regenerate-recovery-key``
       (to mint a fresh one and display it). The substrate refuses to
       run if ``master.recovery.key`` exists and neither flag is set —
       a silent no-op on the recovery wrapping would leave it carrying
       the OLD master-key bytes, and a later
       ``aeat security recover`` would silently restore the substrate
       to the old key while the data is at the new one (total
       data loss on the canonical recovery path).
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
    from ...adapters.persistence.storage import (
        DecryptionError,
        EphemeralMasterKeyProvider,
        decode_mnemonic,
        default_blob_store_roots,
        default_rotation_plan,
        generate_recovery_key,
        load_wrapped_master_key,
        rotate_blob_stores,
        rotate_master_key,
        save_wrapped_master_key,
        unwrap_master_key,
        wrap_master_key,
    )
    from ...adapters.persistence.storage import RecoveryKey
    from ...core.config import load_settings

    if recovery_key is not None and regenerate_recovery_key:
        raise typer.BadParameter(
            "--recovery-key and --regenerate-recovery-key are mutually exclusive.",
        )

    old_key = _read_key_file(old_key_file)
    new_key = _read_key_file(new_key_file)
    if old_key == new_key:
        raise typer.BadParameter(
            "--old-key-file and --new-key-file must contain different keys.",
        )
    settings = load_settings()
    secret_dir = Path(settings.aeat_secret_store_dir)
    recovery_path = secret_dir / "master.recovery.key"
    recovery_wrapping_existed = recovery_path.exists()

    # Pre-flight on the recovery wrapping. Refuse if it exists and the
    # operator hasn't told us how to update it. This is the H-1 fence
    # — without it, rotation silently leaves master.recovery.key
    # holding the OLD master-key bytes, and a later `aeat security
    # recover` re-mints the substrate to the OLD key while the data
    # is at the NEW key. Total data loss on the documented recovery
    # path.
    if recovery_wrapping_existed and recovery_key is None and not regenerate_recovery_key:
        _console.print(
            f"[red]master.recovery.key exists at {recovery_path}.[/red]\n"
            "Master-key rotation must also update the recovery wrapping, otherwise "
            "the wrapping keeps holding the OLD master-key bytes and a later "
            "`aeat security recover` would restore the substrate to the old key.\n\n"
            "Pass either:\n"
            '  --recovery-key "<24 words>"         (preserve the operator\'s '
            "printed mnemonic; the substrate re-wraps the new master key under "
            "the same KEK)\n"
            "  --regenerate-recovery-key           (mint a fresh recovery key "
            "and 24-word mnemonic; the previously-printed mnemonic is "
            "permanently invalidated)\n",
        )
        raise typer.Exit(code=1)
    if recovery_key is not None and not recovery_wrapping_existed:
        raise typer.BadParameter(
            f"--recovery-key was given but no master.recovery.key exists at {recovery_path}; "
            "run `aeat security provision` to create one first.",
        )

    # Validate the supplied mnemonic up-front so we surface bad input
    # before doing the heavy rotation work.
    supplied_recovery_bytes: bytes | None = None
    if recovery_key is not None:
        try:
            supplied_recovery_bytes = decode_mnemonic(recovery_key)
        except ValueError as exc:
            raise typer.BadParameter(f"invalid --recovery-key: {exc}") from exc
        # Verify the mnemonic matches the on-disk wrapping by
        # unwrapping with the OLD master key. If the unwrap fails or
        # the unwrapped bytes don't match `old_key`, refuse — running
        # the rotation would re-wrap garbage.
        existing_wrapped = load_wrapped_master_key(recovery_path)
        try:
            recovered_old_master = unwrap_master_key(
                wrapped=existing_wrapped,
                recovery_key_bytes=supplied_recovery_bytes,
            )
        except DecryptionError as exc:
            _console.print(
                "[red]--recovery-key did not unwrap master.recovery.key.[/red] "
                "Verify every word matches what was printed at provision time.",
            )
            raise typer.Exit(code=1) from exc
        if recovered_old_master != old_key:
            _console.print(
                "[red]--recovery-key unwrapped master.recovery.key but the bytes "
                "do NOT match --old-key-file.[/red] Either the recovery key is "
                "from a different installation, or --old-key-file is wrong.",
            )
            raise typer.Exit(code=1)

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

    # Update the recovery wrapping last (after envelopes + blobs are
    # safely re-encrypted). On crash between blob rotation and
    # recovery re-wrap, the operator's existing mnemonic still
    # unwraps the old master-key bytes — and the substrate's data is
    # already at the new key — so a `recover` would surface a
    # mismatch instead of silently restoring stale state. The H-1
    # fence above plus the explicit pre-flight ensures we only land
    # here when the operator has authorised the recovery-wrapping
    # update.
    if supplied_recovery_bytes is not None:
        # Preserve the existing mnemonic. The recovery KEK is derived
        # purely from the recovery-key bytes; re-wrap the new master
        # key under the same KEK and persist.
        rewrapped = wrap_master_key(
            master_key=new_key,
            recovery_key=RecoveryKey(
                raw=supplied_recovery_bytes,
                mnemonic=recovery_key.strip() if recovery_key else "",
            ),
        )
        save_wrapped_master_key(rewrapped, recovery_path)
        _console.print(
            "[green]✓ master.recovery.key re-wrapped under the existing 24-word "
            "mnemonic. The operator's printed mnemonic remains valid.[/green]",
        )
    elif regenerate_recovery_key:
        fresh = generate_recovery_key()
        rewrapped = wrap_master_key(master_key=new_key, recovery_key=fresh)
        save_wrapped_master_key(rewrapped, recovery_path)
        # Display the new mnemonic ONCE — same panel format as
        # provision_cmd. The substrate never persists the mnemonic.
        _console.print(
            "\n[bold yellow]══════════════════════════════════════════════[/]\n"
            "[bold yellow]NEW RECOVERY KEY — STORE THIS NOW[/]\n"
            "[bold yellow]══════════════════════════════════════════════[/]\n",
        )
        words = fresh.mnemonic.split()
        for row_start in range(0, len(words), 6):
            row = "  ".join(f"[cyan]{w:>10s}[/]" for w in words[row_start : row_start + 6])
            _console.print(f"  {row}")
        _console.print(
            "\n[bold yellow]══════════════════════════════════════════════[/]\n"
            "[yellow]Print these words and store them somewhere safe. The "
            "substrate will never display this mnemonic again. The "
            "PREVIOUSLY-printed mnemonic is now permanently invalidated "
            "and will fail to unwrap master.recovery.key.[/yellow]",
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
    from ...adapters.persistence.storage import (
        assert_corpus_clean,
        build_corpus_manifest,
        manifest_path_for,
        save_corpus_manifest,
    )
    from ...adapters.persistence.storage.errors import CorpusManifestDriftError, CorpusManifestError
    from ...core.config import load_settings

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
    from ...adapters.persistence.storage import migrate_master_key_kdf
    from ...adapters.persistence.storage.master_key._master_key import _default_passphrase_callback
    from ...adapters.persistence.storage.errors import MasterKeyUnavailableError
    from ...core.config import load_settings

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


@app.command("provision")
def provision_cmd(
    backend: Annotated[
        str | None,
        typer.Option(
            "--backend",
            help=(
                "Master-key backend to provision: 'keyring' (OS keychain), "
                "'file' (passphrase-derived Argon2id KEK), or 'unsecured' "
                "(testing only; requires AEAT_ALLOW_UNENCRYPTED=1 and "
                "refuses real NIFs). Defaults to the configured backend."
            ),
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Overwrite an existing master key. Default refuses if any artefact already exists.",
        ),
    ] = False,
) -> None:
    """Provision the security layer for a brand-new installation.

    Operator workflow:

    1. Choose a backend (keyring is recommended; file-fallback is the
       resilient backup; unsecured is testing-only).
    2. For file-fallback: enter a passphrase. The substrate uses
       Argon2id (OWASP-current top tier) to derive a KEK that wraps a
       random 32-byte master key.
    3. The substrate displays a 24-word recovery key ONCE. Print it,
       store it somewhere safe. Without it, a forgotten passphrase or a
       lost keychain means losing every persisted record.
    4. The substrate round-trips a canary record under the new master
       key to confirm provisioning succeeded.

    Re-running ``aeat security provision`` on a provisioned store
    refuses unless ``--force`` is passed; the recovery-key flow is the
    intended remediation path for forgotten passphrases.
    """
    from ...adapters.persistence.storage import (
        FileFallbackMasterKeyProvider,
        KeyringMasterKeyProvider,
        UnsecuredMasterKeyProvider,
        decrypt_record,
        encrypt_record,
        generate_recovery_key,
        save_wrapped_master_key,
        wrap_master_key,
    )
    from ...core.config import SecretStoreBackend, load_settings

    settings = load_settings()
    secret_dir = Path(settings.aeat_secret_store_dir)
    secret_dir.mkdir(parents=True, exist_ok=True)
    chosen_backend = backend or settings.aeat_secret_store_backend.value
    try:
        resolved = SecretStoreBackend(chosen_backend)
    except ValueError as exc:
        raise typer.BadParameter(f"unknown backend: {chosen_backend!r}") from exc

    # Refuse to clobber an existing master.key / master.kdf / salt
    # triplet without --force. Operators with a provisioned store who
    # forgot their passphrase should use `aeat security recover`.
    existing = [p for p in (secret_dir / "master.key", secret_dir / "master.kdf", secret_dir / "salt") if p.exists()]
    if existing and not force:
        _console.print(
            "[red]a master key is already provisioned in[/red] "
            f"{secret_dir}.\n"
            '  - Use `aeat security recover --recovery-key "<24 words>"` '
            "to restore from a recovery key.\n"
            "  - Use `aeat security provision --force` to overwrite "
            "(only when you have lost the existing master key).",
        )
        raise typer.Exit(code=1)

    # Detect a pre-existing keyring entry up-front. The file-fallback
    # existence check above is blind to keyring entries. Without this
    # check, ``provision`` against a default-AUTO install with a
    # populated keychain would silently FETCH the existing keychain-
    # backed master key K1 (when backend resolves to KEYRING) or mint
    # a divergent K2 in the file backend (when ``provision`` falls
    # through to FILE for a never-keyring-aware path). The recovery
    # wrapping would be bound to whichever K the provision-time
    # provider returned, while the runtime ``get_master_key_provider``
    # may resolve to the OTHER K — net result: any record encrypted
    # post-provision under the runtime-resolved K is permanently
    # unreadable after a recover. The probe here applies to KEYRING
    # AND AUTO backends; FILE explicitly opts out of keyring lookup.
    _keyring_module: object = None
    if resolved in (SecretStoreBackend.KEYRING, SecretStoreBackend.AUTO):
        from ...adapters.persistence.storage.master_key._master_key import KEYRING_SERVICE, KEYRING_USERNAME

        try:
            import keyring as _imported_keyring
        except ImportError as exc:
            if resolved is SecretStoreBackend.KEYRING:
                _console.print(f"[red]keyring package not importable: {exc}[/red]")
                raise typer.Exit(code=1) from exc
            # AUTO without an importable keyring package falls
            # through to file-fallback below.
            _existing_keyring_entry = None
        else:
            _keyring_module = _imported_keyring
            try:
                _existing_keyring_entry = _imported_keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
            except Exception as exc:
                # Catch ``Exception`` rather than just ``KeyringError``
                # so platform-specific exceptions (libsecret's
                # ``secretstorage.exceptions.LockedException``,
                # ``dbus.exceptions.DBusException``, Windows
                # Credential Manager COM errors, etc.) surface a clean
                # operator-facing message instead of a Python
                # traceback. The substrate's
                # ``KeyringMasterKeyProvider.get_master_key`` already
                # wraps every non-KeyringError as
                # ``KeyringUnavailableError`` defensively; mirror that
                # discipline at the CLI probe.
                if resolved is SecretStoreBackend.KEYRING:
                    _console.print(
                        f"[red]OS keychain refused get_password: {exc}[/red]\n"
                        "Unlock the OS keychain (Touch ID / Hello / libsecret) and retry, "
                        "or set `--backend file` to use the passphrase backend.",
                    )
                    raise typer.Exit(code=1) from exc
                # AUTO with a locked keychain falls through to file
                # without --force only when no file-fallback exists
                # AND no keychain entry exists. Without the probe
                # result we conservatively pretend "no entry" so the
                # AUTO mint happens in file. The runtime AUTO factory
                # will surface the locked-keychain error on the next
                # use; that's the right operator signal.
                _existing_keyring_entry = None
        if _existing_keyring_entry is not None:
            if not force:
                _console.print(
                    "[red]a master key is already stored in the OS keychain[/red] "
                    f"(service={KEYRING_SERVICE!r}, account={KEYRING_USERNAME!r}).\n"
                    '  - Use `aeat security recover --recovery-key "<24 words>"` '
                    "to restore the file-fallback artefacts from a recovery key.\n"
                    "  - Use `aeat security provision --force` to delete the "
                    "keyring entry and mint a fresh master key (this invalidates "
                    "every existing on-disk record encrypted under the old key).",
                )
                raise typer.Exit(code=1)
            # --force on an existing keyring entry: delete-then-mint
            # so we get a genuinely fresh master key (and a recovery
            # wrapping that actually corresponds to it). Without this
            # the recovery wrapping would be regenerated around the
            # PRE-EXISTING master key, and the previously-printed
            # mnemonic would be silently invalidated.
            assert _keyring_module is not None
            try:
                _keyring_module.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)  # type: ignore[attr-defined]
            except Exception as exc:
                # Same Exception-catching discipline as the
                # get_password probe above — platform-specific
                # exceptions (libsecret, dbus, Windows COM) must
                # surface a clean operator message rather than a
                # raw traceback.
                _console.print(
                    f"[red]failed to delete the existing keyring entry: {exc}[/red]\n"
                    "Clear the entry manually (Keychain Access / Credential Manager / libsecret-tool) "
                    "and re-run.",
                )
                raise typer.Exit(code=1) from exc
            # Drop any in-process cache so the subsequent
            # get_master_key call observes the cleared keyring.
            KeyringMasterKeyProvider._reset_for_tests()
            _console.print(
                "[yellow]existing keyring entry deleted; minting a fresh master key.[/yellow]",
            )

    # Provision the master-key provider per the chosen backend. This
    # mints (or fetches) the master key as a side effect.
    if resolved is SecretStoreBackend.UNSECURED:
        if not settings.aeat_allow_unencrypted:
            _console.print(
                "[red]unsecured mode requires AEAT_ALLOW_UNENCRYPTED=1.[/red]\n"
                "Unsecured mode uses a published deterministic master key — "
                "intended for testing / throwaway data only. Set the env var "
                "and retry, or pick `--backend keyring|file` for real data.",
            )
            raise typer.Exit(code=1)
        provider = UnsecuredMasterKeyProvider()
        _console.print(
            "[yellow]provisioning unsecured backend: "
            "ZERO confidentiality, real NIFs will be refused at profile-write.[/yellow]",
        )
    elif resolved is SecretStoreBackend.KEYRING:
        provider = KeyringMasterKeyProvider()
        # Probe early so failures surface here instead of in a later
        # downstream consumer.
        provider.get_master_key()
        _console.print(
            f"[green]keychain backend probed; master key minted under service '{provider._service}'.[/green]",
        )
    else:  # FILE or AUTO with file-fallback path.
        # When --force is set, wipe any pre-existing file-fallback
        # artefacts BEFORE the mint. The torn-state gate in
        # ``FileFallbackMasterKeyProvider.get_master_key`` refuses to
        # mint over partial on-disk state (data-loss safeguard); the
        # operator's explicit --force is the override that says "I
        # know this destroys any prior key — proceed". Wipe the salt
        # and kdf as well so the subsequent get_master_key sees a
        # clean cold-start state.
        if force:
            for stale in (
                secret_dir / "master.key",
                secret_dir / "master.kdf",
                secret_dir / "salt",
            ):
                stale.unlink(missing_ok=True)
            FileFallbackMasterKeyProvider._reset_for_tests()
        # Resolve the passphrase via the same callback the substrate
        # uses; AEAT_SECRET_PASSPHRASE env var is preferred for non-
        # interactive runs, interactive prompt otherwise.
        provider = FileFallbackMasterKeyProvider(store_dir=secret_dir)
        provider.get_master_key()
        _console.print(
            f"[green]file-fallback backend provisioned at {secret_dir}; "
            "master key wrapped under your passphrase via Argon2id.[/green]",
        )

    master_key = provider.get_master_key()

    # Generate the recovery key + display the 24-word mnemonic ONCE.
    # The substrate never persists the mnemonic; the operator MUST
    # copy it now.
    recovery = generate_recovery_key()
    wrapped = wrap_master_key(master_key=master_key, recovery_key=recovery)
    save_wrapped_master_key(wrapped, secret_dir / "master.recovery.key")
    _console.print(
        "\n[bold yellow]══════════════════════════════════════════════[/]\n"
        "[bold yellow]RECOVERY KEY — STORE THIS NOW[/]\n"
        "[bold yellow]══════════════════════════════════════════════[/]\n",
    )
    _console.print(
        "Write down (or print) the following 24 words and store them somewhere safe.\n"
        "WE WILL NEVER SHOW THIS KEY AGAIN. Without it, a forgotten passphrase\n"
        "or a lost keychain means losing every persisted record.\n",
    )
    # Render the words in 4 rows of 6 for legibility.
    words = recovery.mnemonic.split()
    for row_index in range(0, len(words), 6):
        chunk = words[row_index : row_index + 6]
        _console.print("    " + "  ".join(f"[cyan]{w:>8s}[/]" for w in chunk))
    _console.print(
        "\n[bold yellow]══════════════════════════════════════════════[/]\n",
    )

    # Round-trip verify: encrypt then decrypt a canary plaintext under
    # the new master key. If this fails, the provisioning is broken
    # and the operator should retry rather than trusting the store.
    canary = b"aeat.security.provision.canary.v1"
    canary_aad = b"aeat.security.provision.canary.aad.v1"
    try:
        blob = encrypt_record(canary, key=master_key, associated_data=canary_aad)
        recovered = decrypt_record(blob, key=master_key, associated_data=canary_aad)
    except Exception as exc:  # pragma: no cover - defensive
        _console.print(f"[red]round-trip verify failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    # Use a raise rather than an `assert` so the verification still
    # gates correctness under `python -O`, which strips assert statements.
    if recovered != canary:
        _console.print("[red]round-trip verify failed: canary plaintext mismatch[/red]")
        raise typer.Exit(code=1)

    _console.print(
        "[green]✓ Round-trip verify succeeded.[/green]\n"
        f"[green]✓ Security layer provisioned at {secret_dir}.[/green]\n"
        f"[green]✓ Recovery key wrapped at {secret_dir / 'master.recovery.key'}.[/green]\n",
    )
    _console.print(
        "Next steps: run `aeat doctor` to confirm the substrate is healthy, "
        "then proceed with `aeat setup` (if not already run) or any "
        "persisting CLI command.",
    )


@app.command("recover")
def recover_cmd(
    recovery_key: Annotated[
        str,
        typer.Option(
            "--recovery-key",
            help="The 24-word recovery mnemonic shown at provision time, space-separated and quoted.",
        ),
    ],
) -> None:
    """Recover the master key from a 24-word recovery mnemonic.

    Operator workflow when the active provider becomes unavailable
    (forgotten passphrase, corrupted file-fallback, lost OS keychain):

    1. Locate the 24-word recovery key shown at the original
       ``aeat security provision`` time.
    2. Run this command, supplying the words via ``--recovery-key``.
    3. The substrate unwraps the master key from
       ``master.recovery.key`` using the recovery key, then re-mints
       a fresh ``master.key`` + ``master.kdf`` + ``salt`` triplet
       under a file-fallback backend with the operator's new
       passphrase. The recovery wrapping itself is preserved so
       future recoveries remain possible.

    The previous master.key contents are overwritten — operators who
    are unsure whether their original passphrase still works should
    use ``aeat security provision --force`` instead (which generates
    a brand-new master key and recovery key).
    """
    from ...adapters.persistence.storage import (
        FileFallbackMasterKeyProvider,
        decode_mnemonic,
        decrypt_record,
        encrypt_record,
        load_wrapped_master_key,
        unwrap_master_key,
    )
    from ...adapters.persistence.storage.errors import DecryptionError
    from ...core.config import load_settings

    settings = load_settings()
    secret_dir = Path(settings.aeat_secret_store_dir)
    wrapped_path = secret_dir / "master.recovery.key"
    if not wrapped_path.exists():
        _console.print(
            f"[red]no recovery wrapping at {wrapped_path}.[/red] "
            "If you provisioned the substrate before the recovery feature "
            "shipped, you must use the original passphrase / keychain entry.",
        )
        raise typer.Exit(code=1)

    try:
        recovery_bytes = decode_mnemonic(recovery_key)
    except ValueError as exc:
        _console.print(f"[red]invalid recovery key:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    wrapped = load_wrapped_master_key(wrapped_path)
    try:
        master_key = unwrap_master_key(
            wrapped=wrapped,
            recovery_key_bytes=recovery_bytes,
        )
    except DecryptionError as exc:
        _console.print(
            "[red]recovery key did not unwrap the master.recovery.key file.[/red] "
            "Verify every word matches what you wrote down at provision time.",
        )
        raise typer.Exit(code=1) from exc

    _console.print("[green]✓ Master key recovered from the 24-word mnemonic.[/green]")

    # Re-mint the file-fallback artefacts under the operator's new
    # passphrase, preserving the recovered master-key bytes so every
    # existing on-disk record continues to decrypt cleanly. The
    # provider's complete_recovery() method writes master.kdf /
    # master.key / salt via the atomic tempfile-and-replace pattern;
    # a crash between writes leaves the existing on-disk state
    # untouched (no broken-installation window).
    provider = FileFallbackMasterKeyProvider(store_dir=secret_dir)
    provider.complete_recovery(master_key)

    # Round-trip canary verify under the restored key. Use a raise
    # rather than an `assert` so the verification still gates
    # correctness under `python -O`, which strips assert statements.
    canary_aad = b"aeat.security.recover.canary.aad.v1"
    canary = b"recover-canary"
    blob = encrypt_record(canary, key=master_key, associated_data=canary_aad)
    if decrypt_record(blob, key=master_key, associated_data=canary_aad) != canary:
        _console.print("[red]round-trip verify failed: recovered canary mismatch[/red]")
        raise typer.Exit(code=1)
    _console.print(
        f"[green]✓ Master key restored to file-fallback at {secret_dir} "
        "(under your new passphrase).[/green]\n"
        "[green]✓ Round-trip verify under the restored master key succeeded.[/green]",
    )


@app.command("key-export")
def key_export_cmd(
    output_path: Annotated[
        Path,
        typer.Option(
            "--out",
            help="Destination path for the exported portable JSON file.",
        ),
    ],
) -> None:
    """Export the active master-key state as a portable backup file.

    The export bundles the recovery-key wrapping
    (``master.recovery.key``) plus, for file-fallback installations,
    the ``master.kdf`` parameters and the per-store ``salt``. The
    operator stores this file off-site (cloud backup, USB drive,
    paper printout). To restore on a new machine: copy the file back
    into ``aeat_secret_store_dir`` then run
    ``aeat security recover --recovery-key`` to re-mint the active
    backend state.

    The export is itself ciphertext at rest — the
    ``master.recovery.key`` is wrapped under the recovery KEK; the
    file-fallback artefacts wrap the master key under the operator's
    Argon2id-derived KEK. No new cryptography is introduced; the
    export is a portable repackaging of the existing wrapped state.
    """
    import base64
    import json
    from datetime import UTC, datetime

    from ...adapters.persistence.storage import atomic_write_secure_bytes
    from ...core.config import load_settings

    settings = load_settings()
    secret_dir = Path(settings.aeat_secret_store_dir)
    recovery_path = secret_dir / "master.recovery.key"
    if not recovery_path.exists():
        _console.print(
            f"[red]no master.recovery.key at {recovery_path}.[/red] "
            "Run `aeat security provision` first to generate the recovery wrapping.",
        )
        raise typer.Exit(code=1)

    record: dict[str, object] = {
        "schema_version": 1,
        "exported_at": datetime.now(UTC).isoformat(),
        "backend": settings.aeat_secret_store_backend.value,
        "master_recovery_key_b64": base64.b64encode(
            recovery_path.read_bytes(),
        ).decode("ascii"),
    }
    kdf_path = secret_dir / "master.kdf"
    salt_path = secret_dir / "salt"
    master_key_path = secret_dir / "master.key"
    if kdf_path.exists():
        record["master_kdf_b64"] = base64.b64encode(kdf_path.read_bytes()).decode("ascii")
    if salt_path.exists():
        record["salt_b64"] = base64.b64encode(salt_path.read_bytes()).decode("ascii")
    if master_key_path.exists():
        record["master_key_b64"] = base64.b64encode(master_key_path.read_bytes()).decode("ascii")

    resolved_output = output_path.expanduser().resolve()
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record, indent=2, sort_keys=True).encode("utf-8")
    # Atomic write via the provider's tempfile-and-replace helper so a
    # mid-write crash leaves any pre-existing export untouched. The
    # tempfile is created with O_CREAT|O_EXCL + mode=0o600 on POSIX;
    # the sensitive payload is never world-readable, even briefly
    # (no chmod-after-close TOCTOU). Windows inherits the parent
    # directory's ACL; the export's confidentiality posture there
    # depends on per-user profile permissions.
    atomic_write_secure_bytes(resolved_output, payload)
    _console.print(
        f"[green]✓ Master-key state exported to {resolved_output}.[/green]\n"
        "Store this file off-site. To restore on a new machine: copy it back "
        "into the configured secret-store directory, then run "
        '`aeat security recover --recovery-key "<24 words>"`.',
    )


__all__ = ["app"]
