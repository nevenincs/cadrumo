"""Portable canonical collection-path admission without a native GNOME service."""

from __future__ import annotations

import pytest

from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError

from ..gnome_collection_protection import gnome_collection_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.parametrize("spelling, identifier", [("login", b"login"), ("a_2fb", b"a/b"), ("_c3_a9", b"\xc3\xa9")])
def test_exact_canonical_collection_path_preserves_identifier_bytes(spelling: str, identifier: bytes) -> None:
    assert gnome_collection_id("/org/freedesktop/secrets/collection/" + spelling) == identifier


@pytest.mark.parametrize("spelling", ["", "_", "_2", "_GG", "_2F", "_61", "_00", "a/b", "é"])
def test_malformed_or_noncanonical_collection_path_is_refused(spelling: str) -> None:
    with pytest.raises(AutomationCustodyError) as refused:
        gnome_collection_id("/org/freedesktop/secrets/collection/" + spelling)
    assert refused.value.reason is AutomationCustodyCode.INVALID
