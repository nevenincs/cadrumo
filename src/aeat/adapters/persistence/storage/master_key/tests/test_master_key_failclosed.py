"""Focused fail-closed coverage for the settings-DI passphrase override.

Proves the settings dependency-injection contract:
``override_settings(aeat_secret_passphrase=None)`` raises the same
error as the unset-env path (the original native-env contract that
the ContextVar override seam replaced). The regression refers to
the field by its prior name ``aeat_master_key_passphrase``; the
field landed at ``aeat_secret_passphrase`` in ``aeat.core.config``
(no behaviour difference; same single-source-of-truth surface).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ......core.config import override_settings
from ...errors import SecretStoreError
from .._master_key import (
    PASSPHRASE_ENV_VAR,
    _default_passphrase_callback,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@pytest.fixture
def _no_env_passphrase(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Strip any inherited ``AEAT_SECRET_PASSPHRASE`` env value.

    The fail-closed semantics under test require the resolver to
    fall through to ``getpass.getpass`` (which raises in non-TTY)
    when no override and no env value are set. The autouse fixtures
    in this test module reuse ``monkeypatch`` to ensure no parent-
    process env leaks change the test outcome.
    """
    monkeypatch.delenv(PASSPHRASE_ENV_VAR, raising=False)
    yield


def test_override_passphrase_none_falls_through_to_getpass(
    _no_env_passphrase: None,
) -> None:
    """``override_settings(aeat_secret_passphrase=None)`` triggers the prompt path.

    Pydantic-settings' ``override_settings(field=None)`` re-runs the
    settings resolver with the field cleared. The master-key
    ``_default_passphrase_callback`` then sees ``configured is None``
    and falls through to ``getpass.getpass`` — which in a non-TTY
    test context raises a ``getpass.GetPassWarning``/``EOFError``
    or returns "". The contract: the override path matches the
    unset-env path so test-side settings overrides cannot smuggle a
    silent default.
    """

    def _fake_getpass(prompt: str) -> str:
        raise EOFError("no terminal available for passphrase prompt")

    with override_settings(aeat_secret_passphrase=None), pytest.raises(EOFError):
        _default_passphrase_callback(getpass_fn=_fake_getpass)


def test_override_passphrase_only_crlf_raises_secret_store_error(
    _no_env_passphrase: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An override consisting only of CRLF raises ``SecretStoreError``.

    The resolver strips trailing CRLF (some shells append it via
    ``$(cat .secret)``) then refuses an empty result. The contract
    is shared between the env-var path and the override path so the
    test-side seam cannot smuggle an empty passphrase through the
    secret store either. Interior whitespace is preserved by
    design (some passphrase policies require it).
    """
    with override_settings(aeat_secret_passphrase="\r\n"), pytest.raises(SecretStoreError):
        _default_passphrase_callback()


def test_override_passphrase_valid_value_resolves(
    _no_env_passphrase: None,
) -> None:
    """A non-empty override value resolves cleanly via the override seam."""
    with override_settings(aeat_secret_passphrase="real-passphrase-value-123"):
        assert _default_passphrase_callback() == "real-passphrase-value-123"
