"""Pin the fail-closed contract on the master-key passphrase resolver.

The passphrase resolver is part of the live-write security perimeter.
The Settings DI migration MUST preserve the existing failure modes:

- ``aeat_secret_passphrase=None`` refuses in non-interactive sessions
  instead of hanging on the interactive prompt.
- A SecretStr containing only trailing CRLF strips to empty and
  raises ``SecretStoreError``, matching the historic "env-var set to
  raw newline" failure mode.
- A non-empty SecretStr is returned with trailing CRLF stripped.

Tests exercise the real Settings override path; no env-var
manipulation, no patching of the resolver itself.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from ......core.config import override_settings
from ...errors import SecretStoreError
from .._master_key import _default_passphrase_callback

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_passphrase_present_in_settings_is_returned_with_crlf_stripped() -> None:
    with override_settings(aeat_secret_passphrase=SecretStr("super-secret\r\n")):
        assert _default_passphrase_callback() == "super-secret"


def test_crlf_only_passphrase_raises_secret_store_error() -> None:
    with (
        override_settings(aeat_secret_passphrase=SecretStr("\r\n")),
        pytest.raises(SecretStoreError, match="whitespace-only"),
    ):
        _default_passphrase_callback()


def test_unset_passphrase_refuses_noninteractive_prompt() -> None:
    """Unset settings fail closed under pytest's non-interactive stdin capture."""
    with (
        override_settings(aeat_secret_passphrase=None),
        pytest.raises(SecretStoreError, match="AEAT_SECRET_PASSPHRASE"),
    ):
        _default_passphrase_callback()
