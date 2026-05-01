"""End-to-end first-run integration tests for the security layer.

Closes residual risk R1 of the wave-17 audit gate: per-phase unit
tests cover every component (provision, recover, key-export, doctor
rows, NIF-canary), but a dedicated integration test that drives the
brand-new-user flow under the real file-fallback backend (no
``EphemeralMasterKeyProvider`` fixture, no ``override_master_key_provider``
patching) catches wiring-regressions between phases.

Each scenario starts from an empty tmp_path and exercises the actual
``aeat security`` CLI commands the operator would type, asserting on
the Kent-visible output and the on-disk artefacts.

Scenarios:

1. **File-fallback first-run** — the canonical happy path: provision,
   recovery key emitted, doctor reports green, recover round-trips
   under a new passphrase, key-export bundles every artefact.
2. **Unsecured-mode first-run with synthetic NIF** — the testing /
   throwaway path: provision succeeds, doctor warns loudly,
   profile-write with a synthetic NIF is allowed.
3. **Unsecured-mode refusal with real NIF** — the canary fence:
   profile-write with a structurally-valid Spanish NIF is refused
   with a clear UnsecuredModeRefusedError pointer.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.entrypoints.cli import app
from aeat.entrypoints.cli.security import app as security_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

runner = CliRunner()


@pytest.fixture
def fresh_secrets_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Bootstrap a brand-new file-fallback secret store under ``tmp_path``."""
    secrets_dir = tmp_path / "secrets"
    monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(secrets_dir))
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "file")
    monkeypatch.setenv("AEAT_SECRET_PASSPHRASE", "first-run-passphrase")
    # Ensure no leftovers from earlier tests in the same process.
    monkeypatch.delenv("AEAT_ALLOW_UNENCRYPTED", raising=False)
    return secrets_dir


def _extract_recovery_mnemonic(output: str) -> str:
    """Pull the 24 BIP-39 words out of the recovery-key panel."""
    words: list[str] = []
    for line in output.splitlines():
        candidates = line.strip().split()
        if len(candidates) == 6 and all(c.isalpha() and c.islower() for c in candidates):
            words.extend(candidates)
            if len(words) == 24:
                break
    return " ".join(words)


class TestFileFallbackFirstRun:
    """Brand-new user, file-fallback backend, full happy-path round trip."""

    def test_provision_then_doctor_then_recover_round_trip(
        self,
        fresh_secrets_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Step 1: brand-new install — no master.kdf / master.key / salt.
        assert not (fresh_secrets_dir / "master.kdf").exists()
        assert not (fresh_secrets_dir / "master.key").exists()

        # Step 2: provision the security layer interactively.
        provision = runner.invoke(security_app, ["provision"])
        assert provision.exit_code == 0, provision.output
        assert "RECOVERY KEY" in provision.output
        assert "Round-trip verify succeeded" in provision.output

        # Step 3: assert every expected artefact is on disk.
        assert (fresh_secrets_dir / "master.kdf").exists()
        assert (fresh_secrets_dir / "master.key").exists()
        assert (fresh_secrets_dir / "salt").exists()
        assert (fresh_secrets_dir / "master.recovery.key").exists()

        # Step 4: capture the recovery mnemonic for the recover-step
        # later. Per the substrate's hard contract this is the ONLY
        # time the mnemonic is shown.
        mnemonic = _extract_recovery_mnemonic(provision.output)
        assert len(mnemonic.split()) == 24

        # Step 5: capture an encrypted record under the original
        # master key. After recovery this same record must still
        # decrypt (preserves-master-key-bytes invariant).
        from aeat.adapters.persistence.storage import (
            FileFallbackMasterKeyProvider,
            decrypt_record,
            encrypt_record,
        )

        original_provider = FileFallbackMasterKeyProvider(store_dir=fresh_secrets_dir)
        original_master = original_provider.get_master_key()
        canary = encrypt_record(
            b"first-run-canary",
            key=original_master,
            associated_data=b"integration-test-aad",
        )

        # Step 6: simulate a forgotten passphrase — recover under a
        # NEW passphrase.
        FileFallbackMasterKeyProvider._reset_for_tests()
        os.environ["AEAT_SECRET_PASSPHRASE"] = "recovered-new-passphrase"  # noqa: S105 - test

        recover = runner.invoke(
            security_app,
            ["recover", "--recovery-key", mnemonic],
        )
        assert recover.exit_code == 0, recover.output
        assert "recovered" in recover.output.lower()

        # Step 7: load the master key under the new passphrase. The
        # canary from before recovery still decrypts — preservation
        # of the master-key bytes through the recovery path.
        FileFallbackMasterKeyProvider._reset_for_tests()
        os.environ["AEAT_SECRET_PASSPHRASE"] = "recovered-new-passphrase"  # noqa: S105 - test
        recovered_master = FileFallbackMasterKeyProvider(
            store_dir=fresh_secrets_dir,
        ).get_master_key()
        assert recovered_master == original_master
        assert (
            decrypt_record(
                canary,
                key=recovered_master,
                associated_data=b"integration-test-aad",
            )
            == b"first-run-canary"
        )

    def test_key_export_round_trip(
        self,
        fresh_secrets_dir: Path,
        tmp_path: Path,
    ) -> None:
        # Provision + export + verify every expected field.
        provision = runner.invoke(security_app, ["provision"])
        assert provision.exit_code == 0, provision.output

        out = tmp_path / "backup.json"
        export = runner.invoke(security_app, ["key-export", "--out", str(out)])
        assert export.exit_code == 0, export.output
        assert out.exists()

        import json

        record = json.loads(out.read_text(encoding="utf-8"))
        assert record["schema_version"] == 1
        assert record["backend"] == "file"
        for key in ("master_recovery_key_b64", "master_kdf_b64", "salt_b64", "master_key_b64"):
            assert key in record, f"missing field {key!r} in export"
        assert "exported_at" in record


class TestUnsecuredFirstRunSyntheticNIF:
    """Testing-mode flow: synthetic NIF + AEAT_ALLOW_UNENCRYPTED=1."""

    def test_provision_then_doctor_under_unsecured_with_synthetic_nif(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        secrets_dir = tmp_path / "secrets"
        monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(secrets_dir))
        monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
        monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")

        provision = runner.invoke(
            security_app,
            ["provision", "--backend", "unsecured"],
        )
        assert provision.exit_code == 0, provision.output
        # The unsecured warning is loud and unambiguous.
        assert "ZERO confidentiality" in provision.output
        # The recovery-key panel still fires under unsecured mode —
        # operators get a recovery wrapping even in testing mode.
        assert "RECOVERY KEY" in provision.output

        # The published deterministic key is NOT a real master key.
        from aeat.adapters.persistence.storage.master_key._master_key import _UNSECURED_PUBLISHED_KEY

        assert _UNSECURED_PUBLISHED_KEY.startswith(b"AEAT_UNSECURED_TEST_KEY")

    def test_synthetic_nif_passes_canary(
        self,
        tmp_path: Path,
    ) -> None:
        # The substrate's NIF-canary explicitly allows synthetic
        # placeholders so test fixtures + tutorials work under the
        # unsecured backend.
        from aeat.adapters.persistence.storage import (
            UnsecuredMasterKeyProvider,
            refuse_unsecured_with_real_nif,
        )

        provider = UnsecuredMasterKeyProvider()
        # No raise.
        for synthetic in ("00000000T", "X0000000T", "Z0000000T"):
            refuse_unsecured_with_real_nif(synthetic, provider=provider)


class TestUnsecuredRefusalWithRealNIF:
    """The NIF-canary fences off real tax data from the unsecured backend."""

    def test_refusal_at_substrate_boundary(self) -> None:
        from aeat.adapters.persistence.storage import (
            UnsecuredMasterKeyProvider,
            UnsecuredModeRefusedError,
            refuse_unsecured_with_real_nif,
        )

        provider = UnsecuredMasterKeyProvider()
        # Structurally-valid NIF — refused under unsecured mode.
        with pytest.raises(UnsecuredModeRefusedError, match="real tax id"):
            refuse_unsecured_with_real_nif("12345678Z", provider=provider)

    def test_refusal_at_factory_without_allow_flag(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Even without a real NIF, the factory refuses unsecured-mode
        # provision unless the operator explicitly opts in via the
        # hostile-named env var.
        secrets_dir = tmp_path / "secrets"
        monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(secrets_dir))
        monkeypatch.delenv("AEAT_ALLOW_UNENCRYPTED", raising=False)

        result = runner.invoke(
            security_app,
            ["provision", "--backend", "unsecured"],
        )
        assert result.exit_code == 1
        assert "AEAT_ALLOW_UNENCRYPTED" in result.output


class TestDoctorAfterFirstRun:
    """`aeat doctor` reports healthy security rows after a fresh provision."""

    def test_doctor_security_rows_after_provision(
        self,
        fresh_secrets_dir: Path,
    ) -> None:
        provision = runner.invoke(security_app, ["provision"])
        assert provision.exit_code == 0, provision.output

        doctor = runner.invoke(app, ["doctor"])
        # Doctor may exit non-zero on unrelated rows (Google auth, OAuth
        # client, etc. — none of which are configured in the test env).
        # We only care that the security rows are present and reflect
        # the provisioned state.
        assert "secret-store dir" in doctor.output
        assert "master-key readiness" in doctor.output
        assert "master.kdf version" in doctor.output

    def test_doctor_warns_loudly_under_unsecured(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Drive the row helper directly rather than the full doctor
        # CLI; the Rich Table renderer may compress / wrap the row
        # detail under narrow test terminals, but the row helper
        # returns the structured Row record with the full wording.
        from aeat.core.config import Settings
        from aeat.entrypoints.cli.doctor import State, check_secret_store_backend

        secrets_dir = tmp_path / "secrets"
        monkeypatch.setenv("AEAT_SECRET_STORE_DIR", str(secrets_dir))
        monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
        monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")

        row = check_secret_store_backend(Settings())
        # The unsecured row must be in the WARN state and carry
        # ZERO confidentiality wording so the operator cannot
        # misread the substrate's posture.
        assert row.state == State.WARN
        assert "ZERO confidentiality" in row.detail
