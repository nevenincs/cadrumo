"""Architecture contract for the application-owned profile-custody port."""

from __future__ import annotations

import pytest

from cadrumo.adapters.persistence.storage.errors import PersistenceError
from cadrumo.adapters.persistence.storage.profile_custody import build_profile_custody_port
from cadrumo.application.user_profile.custody_ports import (
    bind_profile_custody_port,
    profile_custody_port,
    profile_is_persistence_failure,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_nested_composition_restores_the_exact_outer_port() -> None:
    outer = build_profile_custody_port()
    inner = build_profile_custody_port()

    with bind_profile_custody_port(outer):
        assert profile_custody_port() is outer
        with bind_profile_custody_port(inner):
            assert profile_custody_port() is inner
        assert profile_custody_port() is outer


def test_persistence_failure_classification_preserves_the_exact_storage_family() -> None:
    port = build_profile_custody_port()

    with bind_profile_custody_port(port):
        assert profile_is_persistence_failure(PersistenceError())
        assert not profile_is_persistence_failure(RuntimeError("not a storage failure"))
