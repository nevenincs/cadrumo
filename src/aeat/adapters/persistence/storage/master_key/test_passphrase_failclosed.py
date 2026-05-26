"""Pin the fail-closed contract on the master-key passphrase resolver.

The passphrase resolver is part of the live-write security perimeter.
The Settings DI migration MUST preserve the existing failure modes:

- ``aeat_secret_passphrase=None`` falls through to the interactive
  prompt (the historic "env var unset" path).
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

from .....core.config import DEV_TEST_DATABASE_PASSWORD, override_settings
from ..errors import SecretStoreError
from ._master_key import _default_passphrase_callback

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_passphrase_present_in_settings_is_returned_with_crlf_stripped() -> None:
    with override_settings(aeat_secret_passphrase=SecretStr(f"{DEV_TEST_DATABASE_PASSWORD}\r\n")):
        assert _default_passphrase_callback() == DEV_TEST_DATABASE_PASSWORD


def test_crlf_only_passphrase_raises_secret_store_error() -> None:
    with (
        override_settings(aeat_secret_passphrase=SecretStr("\r\n")),
        pytest.raises(SecretStoreError, match="whitespace-only"),
    ):
        _default_passphrase_callback()
