"""The strict base64 codec refuses every spelling its encoder would not emit."""

from __future__ import annotations

import pytest

from ..base64_codec import b64_decode, b64_decode_canonical, b64_encode

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("payload", (b"", b"A", b"AB", b"ABC", bytes(range(256))))
def test_canonical_decode_round_trips_the_encoder(payload: bytes) -> None:
    assert b64_decode_canonical(b64_encode(payload)) == payload


def test_a_non_zero_padding_bit_spelling_decodes_strictly_but_is_not_canonical() -> None:
    # "QR==" and "QQ==" both decode to b"A"; only the second is what the encoder emits.
    assert b64_decode("QR==") == b"A"
    assert b64_decode_canonical("QQ==") == b"A"
    with pytest.raises(ValueError, match="canonical"):
        b64_decode_canonical("QR==")


@pytest.mark.parametrize(
    "text",
    ("QQ", "QQ=", "Q Q==", "QQ==\n", "QQ==QQ==", "QQ-=", "caf\u00e9"),
    ids=(
        "unpadded",
        "short-padding",
        "inner-space",
        "trailing-newline",
        "padding-then-data",
        "url-alphabet",
        "non-ascii",
    ),
)
def test_canonical_decode_refuses_malformed_text(text: str) -> None:
    with pytest.raises(ValueError):
        b64_decode_canonical(text)
