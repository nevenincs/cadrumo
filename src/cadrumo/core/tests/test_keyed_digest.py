"""Known-answer coverage for the caller-owned HMAC-SHA256 primitive."""

from __future__ import annotations

import pytest

from ..keyed_digest import keyed_digest_bytes, keyed_digest_hex

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_hmac_sha256_matches_rfc_4231_case_1() -> None:
    key = b"\x0b" * 20
    message = b"Hi There"
    expected = bytes.fromhex("b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7")

    assert keyed_digest_bytes(key=key, message=message) == expected
    assert keyed_digest_hex(key=key, message=message) == (
        "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7"
    )
