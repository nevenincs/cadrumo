"""The public pre-secret readiness attestation launches the real supervised KDF child."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ......core.config import Settings
from ..errors import ProfileCustodyRefusal, ProfileCustodyRefusedError
from ..kdf_supervision import attest_profile_kdf_worker_readiness

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

# These cases prove what readiness admits and releases, not start-up speed; a
# loaded parallel run has measured worker start-up past five seconds.
_READY_DEADLINE_SECONDS = 120.0


def _settings(tmp_path: Path) -> Settings:
    # A temporary root of this case's own, so parallel cases cannot share or
    # mask the neutral directories this one must leave behind as none.
    settings = Settings(cadrumo_local_storage_root=tmp_path, cadrumo_temp_dir=Path("kdf-readiness"))
    assert settings.cadrumo_temp_dir.resolve().is_relative_to(tmp_path.resolve())
    return settings


def _neutral_directories(settings: Settings) -> list[Path]:
    return sorted(settings.cadrumo_temp_dir.glob("cadrumo-profile-kdf-*"))


def test_unpackaged_interpreter_attests_the_canonical_worker_and_releases_both_children(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delattr(sys, "cadrumo_build", raising=False)
    settings = _settings(tmp_path)

    readiness = attest_profile_kdf_worker_readiness(settings=settings, timeout_seconds=_READY_DEADLINE_SECONDS)

    assert readiness.ready_environment_keys == readiness.declared_environment_keys
    assert list(readiness.ready_environment_keys) == sorted(set(readiness.ready_environment_keys))
    # The child is given a closed environment, never the parent's search path.
    assert "PATH" not in readiness.ready_environment_keys
    assert "PYTHONHASHSEED" in readiness.ready_environment_keys
    assert readiness.worker_joined
    assert readiness.neutral_directory_removed
    # Only a native host distinguishes the fixed worker invocation; this
    # interpreter gives the near-miss child the same environment, so the
    # unchanged attestation admits it and the result reports that honestly.
    assert not readiness.noncanonical_invocation_refused
    assert readiness.noncanonical_worker_joined
    assert readiness.noncanonical_neutral_directory_removed
    # Both launches created their neutral directories here, and both are gone.
    assert settings.cadrumo_temp_dir.is_dir()
    assert _neutral_directories(settings) == []


def test_a_declared_fixed_name_the_host_does_not_pin_refuses_readiness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A package declaring a fixed name its host never supplies must not be
    # admitted: the ready child reports names it received, and the declared one
    # is missing from them.
    monkeypatch.setattr(sys, "cadrumo_build", {"fixed_environment_names": ("PACKAGE_IDENTITY",)}, raising=False)
    monkeypatch.delenv("PACKAGE_IDENTITY", raising=False)
    settings = _settings(tmp_path)

    with pytest.raises(ValueError, match="environment is not allowlisted"):
        attest_profile_kdf_worker_readiness(settings=settings, timeout_seconds=_READY_DEADLINE_SECONDS)

    assert _neutral_directories(settings) == []


def test_a_child_that_cannot_attest_before_the_deadline_is_a_supervision_refusal(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(ProfileCustodyRefusedError) as refused:
        attest_profile_kdf_worker_readiness(settings=settings, timeout_seconds=1e-6)

    assert refused.value.refusal is ProfileCustodyRefusal.KDF_SUPERVISION_UNAVAILABLE
    assert _neutral_directories(settings) == []


def test_a_non_positive_timeout_is_refused_before_any_launch(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(ValueError, match="timeout must be positive"):
        attest_profile_kdf_worker_readiness(settings=settings, timeout_seconds=0)

    assert _neutral_directories(settings) == []
