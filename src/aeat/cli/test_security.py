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
