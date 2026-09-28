"""The test keychain backends are loadable by name and never chosen automatically.

keyring offers every imported backend class to its automatic selection. A test
process imports these modules, so a viable one became that process's default
keychain wherever no real backend outranked it, a headless Linux runner among
them: logins there minted receipts into a process-local store that no child
process could read.
"""

from __future__ import annotations

import keyring.core
import pytest
from keyring.backend import KeyringBackend

from .call_time_refusing_keyring import CALL_TIME_REFUSING_KEYRING, CallTimeRefusingKeyring
from .in_memory_keyring import IN_MEMORY_KEYRING, InMemoryKeyring

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_test_backends_are_not_offered_to_automatic_selection() -> None:
    offered = set(KeyringBackend.get_viable_backends())

    assert InMemoryKeyring not in offered
    assert CallTimeRefusingKeyring not in offered


def test_the_test_backends_still_load_by_name_and_pass_the_usability_probe() -> None:
    working = keyring.core.load_keyring(IN_MEMORY_KEYRING)
    refusing = keyring.core.load_keyring(CALL_TIME_REFUSING_KEYRING)

    assert isinstance(working, InMemoryKeyring)
    assert isinstance(refusing, CallTimeRefusingKeyring)
    assert working.priority > 0
    assert refusing.priority > 0
    working.set_password("service", "account", "value")
    assert working.get_password("service", "account") == "value"
