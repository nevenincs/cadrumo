"""Smoke tests for the ``aeat security`` Typer sub-app."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, Field
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]

_NIF_CANARY = "12345678Z"
_HKDF_CONTEXT_TX = b"aeat.financial.transactions.catalogue.v1"


class _Sample(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    taxpayer_nif: str
    amount: str = Field(default="0.00")


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _patch_master_key(tmp_path: Path) -> Iterator[None]:
    """Bootstrap a SecretStore + master-key override for the test."""
    from ..storage import (
        EncryptedBlobStore,
        EphemeralMasterKeyProvider,
        SecretStore,
        override_master_key_provider,
        override_secret_store,
    )

    provider = EphemeralMasterKeyProvider()
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs",
        master_key_provider=provider,
    )
    secret_store = SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )
    override_master_key_provider(provider)
    override_secret_store(secret_store)
    try:
        yield
    finally:
        override_master_key_provider(None)
        override_secret_store(None)


def _seed_envelope(target: Path, *, key: bytes, hkdf_context: bytes) -> None:
    from ..storage import (
        Envelope,
        EphemeralMasterKeyProvider,
        SensitivityClass,
        save_encrypted_envelope,
    )

    envelope = Envelope[_Sample](
        schema_version=1,
        written_at=datetime(2026, 4, 30, 12, 0, tzinfo=UTC),
        classification=SensitivityClass.FINANCIAL,
        payload=_Sample(taxpayer_nif=_NIF_CANARY, amount="987.65"),
    )
    save_encrypted_envelope(
        envelope,
        target,
        master_key_provider=EphemeralMasterKeyProvider(key=key),
        hkdf_context=hkdf_context,
    )


def _write_key(path: Path, *, key: bytes) -> None:
    path.write_text(key.hex(), encoding="ascii")


def test_rotate_master_key_round_trip(
    tmp_path: Path,
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Operator runs the CLI and every governance envelope rotates."""
    import secrets

    old_key = secrets.token_bytes(32)
    new_key = secrets.token_bytes(32)
    while new_key == old_key:
        new_key = secrets.token_bytes(32)
    old_path = tmp_path / "old.hex"
    new_path = tmp_path / "new.hex"
    _write_key(old_path, key=old_key)
    _write_key(new_path, key=new_key)

    txs_dir = tmp_path / "transactions"
    txs_dir.mkdir()
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(txs_dir))
    drafts_dir = tmp_path / "drafts"
    drafts_dir.mkdir()
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(drafts_dir))
    submissions_dir = tmp_path / "submissions"
    submissions_dir.mkdir()
    monkeypatch.setenv("AEAT_SUBMISSIONS_DIR", str(submissions_dir))
    monkeypatch.setenv("AEAT_SUBMISSION_BROWSER_TRACE_DIR", str(tmp_path / "traces"))

    # Seed a financial-transactions envelope under the old key.
    target = txs_dir / "rec-001.envelope.json"
    _seed_envelope(target, key=old_key, hkdf_context=_HKDF_CONTEXT_TX)

    # Capture original ciphertext bytes so we can assert rotation
    # actually replaced them.
    before = target.read_text(encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "security",
            "rotate-master-key",
            "--old-key-file",
            str(old_path),
            "--new-key-file",
            str(new_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "rotated" in result.output

    after = target.read_text(encoding="utf-8")
    assert before != after, "rotate-master-key did not rewrite the on-disk envelope"
    assert _NIF_CANARY not in after


def test_rotate_refuses_when_recovery_wrapping_exists_without_flag(
    tmp_path: Path,
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Wave-24 H-1 regression: rotate-master-key MUST NOT silently
    # proceed when ``master.recovery.key`` exists and the operator
    # hasn't told us how to update it. Without the fence, the
    # wrapping would keep holding the OLD master-key bytes and a
    # later ``aeat security recover`` would restore the substrate
    # to the old key while data is at the new one.
    import secrets

    from ..storage import RecoveryKey, save_wrapped_master_key, wrap_master_key

    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(secrets_dir))
    old_key = secrets.token_bytes(32)
    new_key = secrets.token_bytes(32)
    old_path = tmp_path / "old.hex"
    new_path = tmp_path / "new.hex"
    _write_key(old_path, key=old_key)
    _write_key(new_path, key=new_key)
    # Provision an existing recovery wrapping under a fresh mnemonic.
    rk = RecoveryKey(raw=secrets.token_bytes(32), mnemonic="abandon " * 24)
    save_wrapped_master_key(
        wrap_master_key(master_key=old_key, recovery_key=rk),
        secrets_dir / "master.recovery.key",
    )

    result = runner.invoke(
        app,
        [
            "security",
            "rotate-master-key",
            "--old-key-file",
            str(old_path),
            "--new-key-file",
            str(new_path),
        ],
    )
    assert result.exit_code == 1
    assert "master.recovery.key exists" in result.output
    assert "--recovery-key" in result.output
    assert "--regenerate-recovery-key" in result.output


def test_rotate_with_regenerate_recovery_produces_recoverable_new_key(
    tmp_path: Path,
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Wave-24 H-1 regression: --regenerate-recovery-key mints a
    # fresh mnemonic + re-wraps the NEW master key. Decoding the new
    # mnemonic and unwrapping master.recovery.key must yield the
    # NEW master-key bytes (not the old).
    import secrets

    from ..storage import (
        RecoveryKey,
        decode_mnemonic,
        load_wrapped_master_key,
        save_wrapped_master_key,
        unwrap_master_key,
        wrap_master_key,
    )

    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(secrets_dir))
    txs_dir = tmp_path / "transactions"
    txs_dir.mkdir()
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(txs_dir))
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(tmp_path / "drafts"))
    monkeypatch.setenv("AEAT_SUBMISSIONS_DIR", str(tmp_path / "submissions"))

    old_key = secrets.token_bytes(32)
    new_key = secrets.token_bytes(32)
    _write_key(tmp_path / "old.hex", key=old_key)
    _write_key(tmp_path / "new.hex", key=new_key)
    rk = RecoveryKey(raw=secrets.token_bytes(32), mnemonic="abandon " * 24)
    save_wrapped_master_key(
        wrap_master_key(master_key=old_key, recovery_key=rk),
        secrets_dir / "master.recovery.key",
    )

    result = runner.invoke(
        app,
        [
            "security",
            "rotate-master-key",
            "--old-key-file",
            str(tmp_path / "old.hex"),
            "--new-key-file",
            str(tmp_path / "new.hex"),
            "--regenerate-recovery-key",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "NEW RECOVERY KEY" in result.output

    fresh_mnemonic = _extract_recovery_mnemonic(result.output)
    assert len(fresh_mnemonic.split()) == 24
    fresh_bytes = decode_mnemonic(fresh_mnemonic)

    # Unwrap with the fresh mnemonic; must yield the NEW master-key
    # bytes — proving the substrate's recovery flow now lands on the
    # active master key after rotation.
    wrapped = load_wrapped_master_key(secrets_dir / "master.recovery.key")
    recovered = unwrap_master_key(wrapped=wrapped, recovery_key_bytes=fresh_bytes)
    assert recovered == new_key
    assert recovered != old_key


def test_rotate_with_recovery_key_preserves_existing_mnemonic(
    tmp_path: Path,
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Wave-24 H-1 regression: --recovery-key "<existing mnemonic>"
    # re-wraps the NEW master key under the SAME KEK so the
    # operator's previously-printed mnemonic remains valid.
    import secrets

    from ..storage import (
        encode_mnemonic,
        load_wrapped_master_key,
        save_wrapped_master_key,
        unwrap_master_key,
        wrap_master_key,
    )
    from ..storage._recovery import RecoveryKey

    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(secrets_dir))
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(tmp_path / "transactions"))
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(tmp_path / "drafts"))
    monkeypatch.setenv("AEAT_SUBMISSIONS_DIR", str(tmp_path / "submissions"))

    old_key = secrets.token_bytes(32)
    new_key = secrets.token_bytes(32)
    _write_key(tmp_path / "old.hex", key=old_key)
    _write_key(tmp_path / "new.hex", key=new_key)
    rk_bytes = secrets.token_bytes(32)
    rk_mnemonic = encode_mnemonic(rk_bytes)
    save_wrapped_master_key(
        wrap_master_key(
            master_key=old_key,
            recovery_key=RecoveryKey(raw=rk_bytes, mnemonic=rk_mnemonic),
        ),
        secrets_dir / "master.recovery.key",
    )

    result = runner.invoke(
        app,
        [
            "security",
            "rotate-master-key",
            "--old-key-file",
            str(tmp_path / "old.hex"),
            "--new-key-file",
            str(tmp_path / "new.hex"),
            "--recovery-key",
            rk_mnemonic,
        ],
    )
    assert result.exit_code == 0, result.output
    assert "remains valid" in result.output

    # The same mnemonic must now unwrap to the NEW master key.
    wrapped = load_wrapped_master_key(secrets_dir / "master.recovery.key")
    recovered = unwrap_master_key(wrapped=wrapped, recovery_key_bytes=rk_bytes)
    assert recovered == new_key


def test_rotate_recovery_key_must_match_old_key_file(
    tmp_path: Path,
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Wave-24 H-1 defensive: --recovery-key + --old-key-file must
    # agree. If the supplied mnemonic decrypts master.recovery.key
    # to bytes that don't match --old-key-file, the operator has
    # provided inconsistent inputs and the rotation must refuse
    # rather than re-wrap garbage.
    import secrets

    from ..storage import (
        encode_mnemonic,
        save_wrapped_master_key,
        wrap_master_key,
    )
    from ..storage._recovery import RecoveryKey

    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(secrets_dir))

    old_key_in_wrapping = secrets.token_bytes(32)
    different_old_key = secrets.token_bytes(32)
    new_key = secrets.token_bytes(32)
    _write_key(tmp_path / "old.hex", key=different_old_key)
    _write_key(tmp_path / "new.hex", key=new_key)
    rk_bytes = secrets.token_bytes(32)
    rk_mnemonic = encode_mnemonic(rk_bytes)
    save_wrapped_master_key(
        wrap_master_key(
            master_key=old_key_in_wrapping,
            recovery_key=RecoveryKey(raw=rk_bytes, mnemonic=rk_mnemonic),
        ),
        secrets_dir / "master.recovery.key",
    )

    result = runner.invoke(
        app,
        [
            "security",
            "rotate-master-key",
            "--old-key-file",
            str(tmp_path / "old.hex"),
            "--new-key-file",
            str(tmp_path / "new.hex"),
            "--recovery-key",
            rk_mnemonic,
        ],
    )
    assert result.exit_code == 1
    assert "do NOT match" in result.output


def test_same_key_rejected(
    tmp_path: Path,
    runner: CliRunner,
) -> None:
    import secrets

    key_file = tmp_path / "k.hex"
    key_file.write_text(secrets.token_bytes(32).hex(), encoding="ascii")

    result = runner.invoke(
        app,
        [
            "security",
            "rotate-master-key",
            "--old-key-file",
            str(key_file),
            "--new-key-file",
            str(key_file),
        ],
    )
    assert result.exit_code != 0
    assert "different" in result.output


class TestVerifyCorpus:
    """Wave-11 corpus integrity manifest CLI."""

    def _seed_casillas(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "130").mkdir()
        (root / "130" / "2026Q1.json").write_text(
            '{"records": [{"casilla_id": "01"}]}',
            encoding="utf-8",
        )

    def test_regenerate_then_verify_clean(
        self,
        tmp_path: Path,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        casillas_root = tmp_path / "casillas"
        self._seed_casillas(casillas_root)
        monkeypatch.setenv("AEAT_CASILLAS_ROOT", str(casillas_root))

        regen = runner.invoke(app, ["security", "verify-corpus", "--corpus", "casillas", "--regenerate"])
        assert regen.exit_code == 0, regen.output
        assert "regenerated" in regen.output

        verify = runner.invoke(app, ["security", "verify-corpus", "--corpus", "casillas"])
        assert verify.exit_code == 0, verify.output
        assert "clean" in verify.output

    def test_drift_exits_nonzero(
        self,
        tmp_path: Path,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        casillas_root = tmp_path / "casillas"
        self._seed_casillas(casillas_root)
        monkeypatch.setenv("AEAT_CASILLAS_ROOT", str(casillas_root))
        runner.invoke(app, ["security", "verify-corpus", "--corpus", "casillas", "--regenerate"])

        # Mutate one file; drift should flag.
        (casillas_root / "130" / "2026Q1.json").write_text(
            '{"records": [{"casilla_id": "99"}]}',
            encoding="utf-8",
        )
        result = runner.invoke(app, ["security", "verify-corpus", "--corpus", "casillas"])
        assert result.exit_code == 1
        assert "drift detected" in result.output

    def test_missing_sidecar_exits_nonzero(
        self,
        tmp_path: Path,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        casillas_root = tmp_path / "casillas"
        self._seed_casillas(casillas_root)
        monkeypatch.setenv("AEAT_CASILLAS_ROOT", str(casillas_root))
        result = runner.invoke(app, ["security", "verify-corpus", "--corpus", "casillas"])
        assert result.exit_code == 1
        assert "no manifest sidecar" in result.output


def test_malformed_key_file_rejected(
    tmp_path: Path,
    runner: CliRunner,
) -> None:
    bad = tmp_path / "bad.hex"
    bad.write_text("not hex", encoding="ascii")
    good = tmp_path / "good.hex"
    import secrets

    good.write_text(secrets.token_bytes(32).hex(), encoding="ascii")

    result = runner.invoke(
        app,
        [
            "security",
            "rotate-master-key",
            "--old-key-file",
            str(bad),
            "--new-key-file",
            str(good),
        ],
    )
    assert result.exit_code != 0
    assert "hex" in result.output


class TestMigrateMasterKeyKdf:
    """Wave-12 scrypt -> Argon2id master.kdf migration CLI."""

    @staticmethod
    def _seed_v1_store(tmp_path: Path, *, passphrase: str) -> tuple[Path, bytes]:
        """Lay down a v1 store at ``tmp_path / "secrets"`` and return (store, master-key)."""
        import base64
        import secrets as _secrets

        from ..storage import encrypt_record
        from ..storage._master_key import (
            _b64encode,
            _derive_legacy_scrypt_kek,
            _LegacyKdfParameters,
        )

        store = tmp_path / "secrets"
        store.mkdir(parents=True, exist_ok=True)
        salt = _secrets.token_bytes(16)
        legacy_params = _LegacyKdfParameters(
            version=1,
            algorithm="scrypt",
            n=2**14,
            r=8,
            p=1,
            salt_b64=_b64encode(salt),
        )
        passphrase_bytes = passphrase.encode("utf-8")
        legacy_kek = _derive_legacy_scrypt_kek(passphrase_bytes, salt, legacy_params)
        master_key = _secrets.token_bytes(32)
        blob = encrypt_record(master_key, key=legacy_kek, associated_data=b"aeat.master-key.v1")
        (store / "salt").write_bytes(salt)
        (store / "master.kdf").write_text(legacy_params.model_dump_json(), encoding="utf-8")
        (store / "master.key").write_bytes(base64.b64encode(blob.to_wire()))
        return store, master_key

    def test_migrate_then_load(
        self,
        tmp_path: Path,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """End-to-end: seed v1, run migrate via CLI, load works under v2."""
        store, plaintext_key = self._seed_v1_store(tmp_path, passphrase="hunter2")  # noqa: S106 - test passphrase
        monkeypatch.setenv("AEAT_SECRET_PASSPHRASE", "hunter2")

        result = runner.invoke(
            app,
            [
                "security",
                "migrate-master-key-kdf",
                "--store-dir",
                str(store),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "v2 (Argon2id)" in result.output

        # File backend now loads v2 cleanly with the same passphrase.
        from ..storage import FileFallbackMasterKeyProvider

        FileFallbackMasterKeyProvider._reset_for_tests()
        loaded = FileFallbackMasterKeyProvider(
            store_dir=store,
            passphrase_callback=lambda: "hunter2",
        ).get_master_key()
        assert loaded == plaintext_key

    def test_migrate_idempotent_on_v2_store(
        self,
        tmp_path: Path,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Running the CLI on an already-v2 store reports skipped and exits 0."""
        from ..storage import FileFallbackMasterKeyProvider

        store = tmp_path / "secrets"
        FileFallbackMasterKeyProvider(
            store_dir=store,
            passphrase_callback=lambda: "hunter2",
        ).get_master_key()
        FileFallbackMasterKeyProvider._reset_for_tests()
        monkeypatch.setenv("AEAT_SECRET_PASSPHRASE", "hunter2")

        result = runner.invoke(
            app,
            [
                "security",
                "migrate-master-key-kdf",
                "--store-dir",
                str(store),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "already v2" in result.output

    def test_migrate_wrong_passphrase_exits_nonzero(
        self,
        tmp_path: Path,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A wrong passphrase exits 1 and does not modify the v1 store."""
        store, _ = self._seed_v1_store(tmp_path, passphrase="correct")  # noqa: S106 - test passphrase
        before_kdf = (store / "master.kdf").read_bytes()
        before_key = (store / "master.key").read_bytes()
        monkeypatch.setenv("AEAT_SECRET_PASSPHRASE", "wrong")

        result = runner.invoke(
            app,
            [
                "security",
                "migrate-master-key-kdf",
                "--store-dir",
                str(store),
            ],
        )
        assert result.exit_code == 1
        assert "migration failed" in result.output
        assert (store / "master.kdf").read_bytes() == before_kdf
        assert (store / "master.key").read_bytes() == before_key

    def test_missing_store_dir_rejected(
        self,
        tmp_path: Path,
        runner: CliRunner,
    ) -> None:
        """Pointing at a non-existent store dir is rejected with a usage error."""
        result = runner.invoke(
            app,
            [
                "security",
                "migrate-master-key-kdf",
                "--store-dir",
                str(tmp_path / "does-not-exist"),
            ],
        )
        assert result.exit_code != 0
        assert "does not exist" in result.output


class TestProvisionCommand:
    """Interactive `aeat security provision` flow."""

    def test_file_backend_round_trip(
        self,
        tmp_path: Path,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        secrets_dir = tmp_path / "secrets"
        monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(secrets_dir))
        monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "file")
        monkeypatch.setenv("AEAT_SECRET_PASSPHRASE", "test-pp-1234")

        result = runner.invoke(app, ["security", "provision"])
        assert result.exit_code == 0, result.output
        # The CLI prints the recovery-key block exactly once + the
        # round-trip verify ack.
        assert "RECOVERY KEY" in result.output
        assert "Round-trip verify succeeded" in result.output
        # The recovery-key wrapping landed at master.recovery.key.
        assert (secrets_dir / "master.recovery.key").exists()
        # File-fallback artefacts persisted.
        assert (secrets_dir / "master.key").exists()
        assert (secrets_dir / "master.kdf").exists()
        assert (secrets_dir / "salt").exists()

    def test_refuses_to_overwrite_existing_store_without_force(
        self,
        tmp_path: Path,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir(parents=True)
        # Pre-existing artefacts.
        (secrets_dir / "master.key").write_bytes(b"placeholder")
        (secrets_dir / "master.kdf").write_text(
            '{"version": 2, "algorithm": "argon2id"}',
            encoding="utf-8",
        )
        (secrets_dir / "salt").write_bytes(b"\x00" * 16)
        monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(secrets_dir))
        monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "file")
        monkeypatch.setenv("AEAT_SECRET_PASSPHRASE", "test-pp-1234")

        result = runner.invoke(app, ["security", "provision"])
        assert result.exit_code == 1
        assert "already provisioned" in result.output
        assert "aeat security recover" in result.output

    def test_force_overwrites_existing_store(
        self,
        tmp_path: Path,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir(parents=True)
        (secrets_dir / "master.key").write_bytes(b"placeholder")
        monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(secrets_dir))
        monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "file")
        monkeypatch.setenv("AEAT_SECRET_PASSPHRASE", "test-pp-1234")

        result = runner.invoke(app, ["security", "provision", "--force"])
        assert result.exit_code == 0, result.output
        assert "RECOVERY KEY" in result.output

    def test_unsecured_backend_requires_allow_unencrypted(
        self,
        tmp_path: Path,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(tmp_path / "secrets"))
        monkeypatch.delenv("AEAT_ALLOW_UNENCRYPTED", raising=False)
        result = runner.invoke(app, ["security", "provision", "--backend", "unsecured"])
        assert result.exit_code == 1
        assert "AEAT_ALLOW_UNENCRYPTED" in result.output

    def test_unsecured_backend_succeeds_with_allow_flag(
        self,
        tmp_path: Path,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(tmp_path / "secrets"))
        monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
        result = runner.invoke(app, ["security", "provision", "--backend", "unsecured"])
        assert result.exit_code == 0, result.output
        assert "ZERO confidentiality" in result.output
        assert "RECOVERY KEY" in result.output

    def test_keyring_backend_refuses_when_entry_exists_without_force(
        self,
        tmp_path: Path,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Wave-22 M-3 regression: provisioning the keyring backend
        # over an existing keychain entry without --force used to
        # silently FETCH the old key and regenerate the recovery
        # wrapping, invalidating the operator's previously-printed
        # mnemonic. Now refuses with a clear pointer at recover or
        # --force.
        keyring = pytest.importorskip("keyring")

        store: dict[tuple[str, str], str] = {("aeat:secure-persistence", "master"): "preexisting-b64"}

        def _get(service: str, username: str) -> str | None:
            return store.get((service, username))

        def _refuse(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("provision must NOT mint when an entry already exists")

        monkeypatch.setattr(keyring, "get_password", _get)
        monkeypatch.setattr(keyring, "set_password", _refuse)
        monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(tmp_path / "secrets"))
        result = runner.invoke(app, ["security", "provision", "--backend", "keyring"])
        assert result.exit_code == 1
        assert "already stored in the OS keychain" in result.output
        assert "aeat security recover" in result.output
        assert "--force" in result.output

    def test_keyring_backend_force_deletes_then_mints(
        self,
        tmp_path: Path,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # With --force, the existing keyring entry must be DELETED
        # and a fresh master key minted — otherwise the freshly-
        # generated recovery wrapping wraps the OLD master key,
        # invalidating any pre-existing printed mnemonic against the
        # on-disk file.
        from ..storage._master_key import KeyringMasterKeyProvider

        keyring = pytest.importorskip("keyring")

        store: dict[tuple[str, str], str] = {("aeat:secure-persistence", "master"): "old-b64"}
        delete_calls: list[tuple[str, str]] = []
        set_calls: list[tuple[str, str, str]] = []

        def _get(service: str, username: str) -> str | None:
            return store.get((service, username))

        def _delete(service: str, username: str) -> None:
            delete_calls.append((service, username))
            store.pop((service, username), None)

        def _set(service: str, username: str, value: str) -> None:
            set_calls.append((service, username, value))
            store[(service, username)] = value

        monkeypatch.setattr(keyring, "get_password", _get)
        monkeypatch.setattr(keyring, "delete_password", _delete)
        monkeypatch.setattr(keyring, "set_password", _set)
        # Match the substrate's keyring backend probe — the no-op
        # backend predicate runs before any get_password call.
        monkeypatch.setattr(KeyringMasterKeyProvider, "_probe_backend", staticmethod(lambda: None))
        monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(tmp_path / "secrets"))
        # Reset any cache from a previous test in the same process.
        KeyringMasterKeyProvider._reset_for_tests()

        result = runner.invoke(app, ["security", "provision", "--backend", "keyring", "--force"])
        assert result.exit_code == 0, result.output
        # Old entry deleted exactly once.
        assert delete_calls == [("aeat:secure-persistence", "master")]
        # New key set after delete (should NOT equal the old value).
        assert len(set_calls) == 1
        assert set_calls[0][2] != "old-b64"
        # Recovery wrapping landed.
        assert (tmp_path / "secrets" / "master.recovery.key").exists()


def _extract_recovery_mnemonic(output: str) -> str:
    """Pull the 24 words out of the recovery-key panel in CLI output."""
    # The provision command prints the words in 4 rows of 6, each
    # word inside a `[cyan]...[/]` rich tag. The CliRunner output
    # has the rich markup stripped, so we just walk the lines and
    # collect the rows that look like a 6-word block.
    words: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        # The recovery-key panel rows are indented and have all-lowercase
        # words. They appear AFTER the "RECOVERY KEY" header and
        # BEFORE the closing separator. The terminal width may wrap
        # rich content; collect everything between markers.
        candidates = stripped.split()
        if len(candidates) == 6 and all(c.isalpha() and c.islower() for c in candidates):
            words.extend(candidates)
            if len(words) == 24:
                break
    return " ".join(words)


class TestRecoverCommand:
    """Recover via 24-word mnemonic + re-mint the file-fallback state."""

    def test_recovery_round_trip_under_new_passphrase(
        self,
        tmp_path: Path,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        secrets_dir = tmp_path / "secrets"
        monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(secrets_dir))
        monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "file")
        monkeypatch.setenv("AEAT_SECRET_PASSPHRASE", "original-pp-1234")

        # Step 1: provision the substrate to mint the recovery key.
        provision = runner.invoke(app, ["security", "provision"])
        assert provision.exit_code == 0, provision.output
        mnemonic = _extract_recovery_mnemonic(provision.output)
        assert len(mnemonic.split()) == 24

        # Step 2: capture the original master-key bytes (via a known
        # encrypted-record round-trip) so we can verify recovery
        # preserves them.
        from ..storage import (
            FileFallbackMasterKeyProvider,
            decrypt_record,
            encrypt_record,
        )

        original_provider = FileFallbackMasterKeyProvider(store_dir=secrets_dir)
        original_master = original_provider.get_master_key()
        canary = encrypt_record(
            b"original-canary",
            key=original_master,
            associated_data=b"canary-aad",
        )

        # Step 3: simulate a forgotten passphrase by changing the
        # operator's passphrase. The new file-fallback state should
        # be re-minted under the NEW passphrase but keep the original
        # master-key bytes (so the canary still decrypts).
        # The substrate's env-var-driven _default_passphrase_callback
        # pops the env var after reading; restore it explicitly with
        # the new value so the recover command resolves the new
        # passphrase without prompting stdin.
        FileFallbackMasterKeyProvider._reset_for_tests()
        import os as _os

        _os.environ["AEAT_SECRET_PASSPHRASE"] = "new-pp-5678"  # noqa: S105

        recover = runner.invoke(
            app,
            ["security", "recover", "--recovery-key", mnemonic],
        )
        assert recover.exit_code == 0, recover.output
        assert "recovered" in recover.output.lower()

        # Step 4: load the master key under the new passphrase; the
        # canary from before recovery still decrypts.
        FileFallbackMasterKeyProvider._reset_for_tests()
        _os.environ["AEAT_SECRET_PASSPHRASE"] = "new-pp-5678"  # noqa: S105
        new_provider = FileFallbackMasterKeyProvider(store_dir=secrets_dir)
        new_master = new_provider.get_master_key()
        assert new_master == original_master
        assert decrypt_record(canary, key=new_master, associated_data=b"canary-aad") == b"original-canary"

    def test_recovery_with_wrong_mnemonic_exits_nonzero(
        self,
        tmp_path: Path,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        secrets_dir = tmp_path / "secrets"
        monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(secrets_dir))
        monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "file")
        monkeypatch.setenv("AEAT_SECRET_PASSPHRASE", "pp")

        runner.invoke(app, ["security", "provision"])
        # All-zero mnemonic: valid checksum, but it's not the
        # provisioned recovery key.
        zero_mnemonic = ("abandon " * 23 + "art").strip()

        result = runner.invoke(
            app,
            ["security", "recover", "--recovery-key", zero_mnemonic],
        )
        assert result.exit_code == 1
        assert "did not unwrap" in result.output

    def test_recovery_without_wrapping_file_exits_nonzero(
        self,
        tmp_path: Path,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir(parents=True)
        monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(secrets_dir))
        # Don't provision — no master.recovery.key exists.
        zero_mnemonic = ("abandon " * 23 + "art").strip()
        result = runner.invoke(
            app,
            ["security", "recover", "--recovery-key", zero_mnemonic],
        )
        assert result.exit_code == 1
        assert "no recovery wrapping" in result.output


class TestKeyExportCommand:
    """`aeat security key-export --out <path>` portable backup."""

    def test_export_after_provision(
        self,
        tmp_path: Path,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        secrets_dir = tmp_path / "secrets"
        monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(secrets_dir))
        monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "file")
        monkeypatch.setenv("AEAT_SECRET_PASSPHRASE", "pp")

        runner.invoke(app, ["security", "provision"])
        out = tmp_path / "backup.json"
        result = runner.invoke(app, ["security", "key-export", "--out", str(out)])
        assert result.exit_code == 0, result.output
        assert out.exists()
        # The export is a JSON object with the expected portable fields.
        import json

        record = json.loads(out.read_text(encoding="utf-8"))
        assert record["schema_version"] == 1
        assert record["backend"] == "file"
        assert "master_recovery_key_b64" in record
        assert "master_kdf_b64" in record
        assert "salt_b64" in record
        assert "master_key_b64" in record
        assert "exported_at" in record

    def test_export_without_provision_exits_nonzero(
        self,
        tmp_path: Path,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir(parents=True)
        monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(secrets_dir))
        out = tmp_path / "backup.json"
        result = runner.invoke(app, ["security", "key-export", "--out", str(out)])
        assert result.exit_code == 1
        assert "no master.recovery.key" in result.output
