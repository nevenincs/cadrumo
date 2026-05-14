"""Focused unit tests for application.auth._sessions.storage_state_paths.

`storage_state_paths` composes Settings + AuthProviderKind into the
storage-state JSON path. Three branches:

1. ``kind=AuthProviderKind.CERTIFICATE`` → certificate stem (``storage``).
2. ``kind=AuthProviderKind.CLAVE_MOVIL`` → clave-movil stem
   (``clave-movil-storage``).
3. ``kind=None`` → defaults to AuthProviderKind.CERTIFICATE.

Previously no direct unit-test coverage. The helper is consumed by
``load_persisted_session``, ``delete_persisted_session``, and the
broader auth-session lifecycle. A regression in the stem mapping
(swapping cert ↔ clave-movil) would silently route session reads
and writes to the wrong file.

Tests pin the path composition contract; assertions are
structural / composition-contract assertions, not calculation
tautologies.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...core.config import Settings
from . import AuthProviderKind
from ._sessions import storage_state_paths

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _settings(token_dir: Path, profile_name: str = "operator") -> Settings:
    return Settings(
        aeat_token_dir=token_dir,
        aeat_default_profile_name=profile_name,
    )


def test_storage_state_paths_certificate_uses_storage_stem(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    result = storage_state_paths(settings, AuthProviderKind.CERTIFICATE)

    assert result.storage_state == tmp_path / "operator-storage.json"


def test_storage_state_paths_clave_movil_uses_clave_movil_storage_stem(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    result = storage_state_paths(settings, AuthProviderKind.CLAVE_MOVIL)

    assert result.storage_state == tmp_path / "operator-clave-movil-storage.json"


def test_storage_state_paths_none_defaults_to_certificate(tmp_path: Path) -> None:
    """The default kind is CERTIFICATE; explicit None and unsupplied
    kwarg return the same path as explicit CERTIFICATE."""
    settings = _settings(tmp_path)

    default_result = storage_state_paths(settings)
    explicit_result = storage_state_paths(settings, AuthProviderKind.CERTIFICATE)

    assert default_result.storage_state == explicit_result.storage_state


def test_storage_state_paths_composes_profile_name_into_filename(tmp_path: Path) -> None:
    """The profile name from Settings.aeat_default_profile_name is
    interpolated into the filename — swapping profiles changes the
    target path so two operator profiles do not share session state."""
    settings_a = _settings(tmp_path, profile_name="operator")
    settings_b = _settings(tmp_path, profile_name="other-profile")

    result_a = storage_state_paths(settings_a, AuthProviderKind.CERTIFICATE)
    result_b = storage_state_paths(settings_b, AuthProviderKind.CERTIFICATE)

    assert result_a.storage_state == tmp_path / "operator-storage.json"
    assert result_b.storage_state == tmp_path / "other-profile-storage.json"
    assert result_a.storage_state != result_b.storage_state


def test_storage_state_paths_composes_token_dir_into_full_path(tmp_path: Path) -> None:
    """The token_dir from Settings.aeat_token_dir is the parent of
    the storage_state path."""
    nested_dir = tmp_path / "subdir" / "tokens"
    nested_dir.mkdir(parents=True)
    settings = _settings(nested_dir)

    result = storage_state_paths(settings, AuthProviderKind.CERTIFICATE)

    assert result.storage_state.parent == nested_dir


def test_storage_state_paths_returns_strict_frozen_model(tmp_path: Path) -> None:
    """The returned StorageStatePaths is a strict/frozen pydantic
    model; attempting to mutate the storage_state field raises."""
    settings = _settings(tmp_path)

    result = storage_state_paths(settings, AuthProviderKind.CERTIFICATE)

    with pytest.raises(Exception, match="frozen"):
        result.storage_state = tmp_path / "other.json"
