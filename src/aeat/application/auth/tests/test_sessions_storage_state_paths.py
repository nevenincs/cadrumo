"""Focused unit tests for application.auth._sessions.storage_state_paths.

`storage_state_paths` composes the active profile + AuthProviderKind into the
encrypted storage-state logical key. Three branches:

1. ``kind=AuthProviderKind.CERTIFICATE`` → certificate stem (``storage``).
2. ``kind=AuthProviderKind.CLAVE_MOVIL`` → clave-movil stem
   (``clave-movil-storage``).
3. ``kind=None`` → defaults to AuthProviderKind.CERTIFICATE.

Previously no direct unit-test coverage. The helper is consumed by
``load_persisted_session``, ``delete_persisted_session``, and the
broader auth-session lifecycle. The returned path is not a plaintext
filesystem destination. A regression in the stem mapping (swapping cert
<-> clave-movil) would silently route session reads and writes to the
wrong encrypted object.

Tests pin the path composition contract; assertions are
structural / composition-contract assertions, not calculation
tautologies.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core.config import Settings
from .. import AuthProviderKind
from .._sessions import storage_state_paths

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True, name="_active_profile")
def active_profile(tmp_path: Path) -> Iterator[None]:
    """Set the active-profile setting so the precedence chain resolves.

    Routes through :func:`aeat.core.config.override_settings`, the
    canonical Settings injection mechanism. Tests that exercise a
    different profile name nest a further `override_settings` block
    in their body.

    The package-level `_isolated_aeat_root` conftest fixture handles
    `aeat_local_storage_root` redirection separately.
    """

    from ....core.config import override_settings

    with override_settings(aeat_active_profile="operator"):
        yield


def _settings(token_dir: Path) -> Settings:
    return Settings(aeat_token_dir=token_dir)


def test_storage_state_paths_certificate_uses_storage_stem(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    result = storage_state_paths(settings, AuthProviderKind.CERTIFICATE)

    assert result.storage_state == Path(".aeat/auth/sessions/operator-storage.json")


def test_storage_state_paths_clave_movil_uses_clave_movil_storage_stem(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    result = storage_state_paths(settings, AuthProviderKind.CLAVE_MOVIL)

    assert result.storage_state == Path(".aeat/auth/sessions/operator-clave-movil-storage.json")


def test_storage_state_paths_none_defaults_to_certificate(tmp_path: Path) -> None:
    """The default kind is CERTIFICATE; explicit None and unsupplied
    kwarg return the same path as explicit CERTIFICATE."""
    settings = _settings(tmp_path)

    default_result = storage_state_paths(settings)
    explicit_result = storage_state_paths(settings, AuthProviderKind.CERTIFICATE)

    assert default_result.storage_state == explicit_result.storage_state


def test_storage_state_paths_composes_profile_name_into_filename(tmp_path: Path) -> None:
    """The active profile name is interpolated into the filename so
    two operator profiles do not share session state. The active
    profile resolves through the operator-facing precedence chain
    (env var > pointer file); switching it between calls changes the
    target path."""

    from ....core.config import override_settings

    settings = _settings(tmp_path)

    with override_settings(aeat_active_profile="operator"):
        result_a = storage_state_paths(settings, AuthProviderKind.CERTIFICATE)

    with override_settings(aeat_active_profile="other-profile"):
        result_b = storage_state_paths(settings, AuthProviderKind.CERTIFICATE)

    assert result_a.storage_state == Path(".aeat/auth/sessions/operator-storage.json")
    assert result_b.storage_state == Path(".aeat/auth/sessions/other-profile-storage.json")
    assert result_a.storage_state != result_b.storage_state


def test_storage_state_paths_is_independent_of_plaintext_token_dir(tmp_path: Path) -> None:
    """Encrypted session object keys must not drift with the legacy token dir."""
    settings_a = _settings(tmp_path / "tokens-a")
    settings_b = _settings(tmp_path / "tokens-b")

    result_a = storage_state_paths(settings_a, AuthProviderKind.CERTIFICATE)
    result_b = storage_state_paths(settings_b, AuthProviderKind.CERTIFICATE)

    assert result_a.storage_state == result_b.storage_state
    assert result_a.storage_state == Path(".aeat/auth/sessions/operator-storage.json")


def test_storage_state_paths_returns_strict_frozen_model(tmp_path: Path) -> None:
    """The returned StorageStatePaths is a strict/frozen pydantic
    model; attempting to mutate the storage_state field raises."""
    settings = _settings(tmp_path)

    result = storage_state_paths(settings, AuthProviderKind.CERTIFICATE)

    attr = "storage_state"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(result, attr, tmp_path / "other.json")
