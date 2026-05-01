"""Unit tests for the env-file writer (#61).

The writer must satisfy three load-bearing invariants:

* **never-write-secrets**: the PKCS#12 passphrase value never reaches
  the filesystem.
* **idempotent-rerun**: running the writer twice with the same
  answers on the same target file produces a byte-equal result.
* **unrelated-keys-preserved**: keys the wizard does not own are
  round-tripped verbatim.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from ...adapters.outbound.aeat.auth import CertificateBackend
from ...adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from ...core.env_io import read_env_file
from ...core.i18n import Language
from ...domain.deadlines import IVARegime
from ...domain.profile import CCAA
from . import (
    SetupAnswers,
    owned_env_keys,
    write_env_file,
    write_profile_file,
)
from ._env_writer import load_profile_envelope

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


@pytest.fixture(autouse=True)
def _patch_master_key(tmp_path: Path) -> Iterator[None]:
    """Provide a deterministic master key so the profile envelope writer
    does not consult the OS keychain or a passphrase prompt during tests."""
    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs-secret",
        master_key_provider=provider,
    )
    secret_store = SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )
    override_secret_store(secret_store)
    try:
        yield
    finally:
        override_master_key_provider(None)
        override_secret_store(None)


def _answers(tmp_path: Path) -> SetupAnswers:
    cert = tmp_path / "cert.p12"
    cert.write_bytes(b"x")
    return SetupAnswers(
        tax_id="87654321X",
        iva_regime=IVARegime.SIMPLIFICADO,
        has_employees=True,
        pays_professionals_with_retencion=True,
        professional_income_withholding_ge_70pct=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=True,
        third_party_transactions_above_347_threshold=True,
        bienes_extranjero_above_threshold=False,
        tax_residence_ccaa=CCAA.MADRID,
        certificate_path=cert,
        certificate_password_secret_var_name="AEAT_TEST_PW",
        certificate_friendly_name="primary",
        certificate_backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
        default_language=Language.EN,
        output_language=Language.HU,
        aeat_drafts_dir=tmp_path / "drafts",
        aeat_submissions_dir=tmp_path / "subs",
        aeat_manuals_root=tmp_path / "manuals",
        default_profile_path=tmp_path / "profile.json",
        aeat_live_tests_enabled=True,
        aeat_live_tests_google=False,
    )


def test_write_env_file_persists_every_owned_key(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    answers = _answers(tmp_path)
    write_env_file(answers, env_file)
    parsed = read_env_file(env_file)
    for key in owned_env_keys():
        assert key in parsed, f"wizard-owned key {key!r} missing from env file"


def test_write_env_file_never_writes_password_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even if the passphrase is present in os.environ, it never hits disk.

    We deliberately use a distinctive sentinel so a byte-wise search
    against the written file would catch any accidental persistence.
    """
    sentinel = "DO-NOT-LEAK-THIS-PASSPHRASE-9f13b8a2"
    monkeypatch.setenv("AEAT_TEST_PW", sentinel)
    env_file = tmp_path / ".env"
    answers = _answers(tmp_path)

    write_env_file(answers, env_file)

    written = env_file.read_text(encoding="utf-8")
    assert sentinel not in written
    # We *do* persist the env var NAME as an informational comment.
    assert "AEAT_TEST_PW" in written
    # And the env var name must never appear as a KEY=VALUE assignment
    # (it would look like AEAT_TEST_PW=<something>).
    for line in written.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, _value = stripped.partition("=")
        assert key.strip() != "AEAT_TEST_PW"


def test_write_env_file_is_byte_equal_idempotent(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    answers = _answers(tmp_path)

    write_env_file(answers, env_file)
    first = env_file.read_bytes()
    write_env_file(answers, env_file)
    second = env_file.read_bytes()

    assert first == second


def test_write_env_file_preserves_unrelated_keys(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# preface comment\nUNRELATED_KEY=keep-me\nGOOGLE_OAUTH_CLIENT_ID=abc123\n\n# trailing comment\n",
        encoding="utf-8",
    )
    answers = _answers(tmp_path)

    write_env_file(answers, env_file)

    parsed = read_env_file(env_file)
    assert parsed["UNRELATED_KEY"] == "keep-me"
    assert parsed["GOOGLE_OAUTH_CLIENT_ID"] == "abc123"

    text = env_file.read_text(encoding="utf-8")
    assert "# preface comment" in text
    assert "# trailing comment" in text


def test_write_env_file_rewrites_in_place_on_rerun(tmp_path: Path) -> None:
    """Re-running with updated answers overwrites the owned keys in place."""
    env_file = tmp_path / ".env"
    answers = _answers(tmp_path)
    write_env_file(answers, env_file)

    updated = answers.model_copy(update={"aeat_live_tests_enabled": False})
    write_env_file(updated, env_file)

    parsed = read_env_file(env_file)
    assert parsed["AEAT_LIVE_TESTS_ENABLED"] == "false"


def test_write_profile_file_emits_valid_autonomo_profile(tmp_path: Path) -> None:
    old_tax_path = os.environ.get("AEAT_TAX_RESIDENCE_PROFILE_PATH")
    os.environ["AEAT_TAX_RESIDENCE_PROFILE_PATH"] = str(tmp_path / "tax-residence.json")
    answers = _answers(tmp_path)
    target = tmp_path / "profile.json"
    try:
        write_profile_file(answers, target)
    finally:
        if old_tax_path is None:
            os.environ.pop("AEAT_TAX_RESIDENCE_PROFILE_PATH", None)
        else:
            os.environ["AEAT_TAX_RESIDENCE_PROFILE_PATH"] = old_tax_path

    profile = load_profile_envelope(target)
    assert profile.tax_id == "87654321X"
    assert profile.iva_regime is IVARegime.SIMPLIFICADO
    assert profile.pays_professionals_with_retencion is True
    assert profile.third_party_transactions_above_347_threshold is True
    assert (tmp_path / "tax-residence.json").exists()


def test_write_profile_file_writes_ciphertext_envelope(tmp_path: Path) -> None:
    """The on-disk profile must be a CipherEnvelope; the NIF must not survive in plaintext."""
    answers = _answers(tmp_path)
    target = tmp_path / "profile.json"
    write_profile_file(answers, target)

    written = target.read_text(encoding="utf-8")
    # CipherEnvelope wire form — classification at the cipher layer.
    assert '"classification":"identity"' in written
    assert '"encryption":' in written
    # The NIF canary must not appear in plaintext.
    assert "87654321X" not in written


def test_write_profile_file_lock_target_aligns_with_rotation(
    tmp_path: Path,
) -> None:
    # Wave-25 H-2 regression: the setup-profile writer must acquire
    # the writer-canonical sidecar lock (target.with_suffix('.lock'))
    # so concurrent rotate-master-key contends on the same OS-level
    # lock-byte target. With ``aeat_default_profile_path`` set, the
    # rotation plan emits a single-file entry with
    # ``target_filename`` set, and ``RotationPlanEntry.lock_path_for``
    # returns ``envelope_path.with_suffix('.lock')`` for that branch.
    from ...adapters.persistence.storage import LockAcquisitionError, RotationPlanEntry, exclusive_file_lock

    answers = _answers(tmp_path)
    target = tmp_path / "profile.json"
    # Mint the file once so the lock target's directory exists.
    write_profile_file(answers, target)

    rotation_entry = RotationPlanEntry(
        store_dir=target.parent,
        hkdf_context=b"aeat.application.setup.profile.v1",
        target_filename=target.name,
    )
    rotation_lock_target = rotation_entry.lock_path_for(target)
    expected_writer_lock_target = target.with_suffix(".lock")
    assert rotation_lock_target == expected_writer_lock_target

    # End-to-end contention: hold the writer-canonical sidecar; the
    # rotation acquire-with-timeout=0 must fail. Proves both paths
    # land on the same lock-byte target.
    with (
        exclusive_file_lock(expected_writer_lock_target),
        pytest.raises(LockAcquisitionError),
        exclusive_file_lock(rotation_lock_target, timeout=0.0),
    ):
        pass


def test_owned_env_keys_are_stable_and_unique() -> None:
    keys = owned_env_keys()
    assert len(keys) == len(set(keys))
    assert all(key == key.upper() for key in keys)
    assert "AEAT_CERTIFICATE_PATH" in keys


def test_write_env_file_survives_clean_environment(tmp_path: Path) -> None:
    """Even with the password env var unset entirely, the write succeeds.

    This guards against a failure mode where the writer accidentally
    tries to read the passphrase value from ``os.environ``.
    """
    os.environ.pop("AEAT_TEST_PW", None)
    env_file = tmp_path / ".env"
    write_env_file(_answers(tmp_path), env_file)
    parsed = read_env_file(env_file)
    assert parsed["AEAT_CERTIFICATE_PATH"]  # non-empty
