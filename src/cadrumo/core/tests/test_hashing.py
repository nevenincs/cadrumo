"""Behavioral contracts for the canonical record encoding and content hashing."""

from __future__ import annotations

import json
import math

import pytest

from ..hashing import (
    CONTENT_DIGEST_PREFIX,
    bounded_canonical_json_bytes,
    canonical_json_bytes,
    canonical_json_digest,
    content_hash_hex,
    prefixed_digest,
    reject_duplicate_json_members,
    reject_json_constant,
    validate_prefixed_digest,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The ruled byte spelling of one accented record, written from the encoding
#: contract rather than read back out of the encoder: sorted keys, no
#: whitespace, and the eñe as its two UTF-8 bytes rather than an escape.
_ACCENTED_CANONICAL_BYTES = b'{"accent":"ni\xc3\xb1o","answer":42}'

#: SHA-256 of the byte string above, computed outside this package.
_ACCENTED_CONTENT_HASH = "5da3482994623aba30c812e0f6de9db77de54bdfa3d88d06a941d60157f7c283"


def test_canonical_json_bytes_emits_utf8_rather_than_ascii_escapes() -> None:
    """Accented text travels as UTF-8, which is what the byte ceilings measure."""
    payload = {"answer": 42, "accent": "niño"}

    encoded = canonical_json_bytes(payload)

    assert encoded == _ACCENTED_CANONICAL_BYTES
    assert content_hash_hex(payload) == _ACCENTED_CONTENT_HASH
    # The escaped spelling of the same record is materially longer, which is
    # precisely why two encoders cannot share one declared byte budget.
    assert len(encoded) < len(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii"))


def test_canonical_json_bytes_survives_a_decode_and_re_encode_unchanged() -> None:
    """A non-ASCII record read back and re-encoded reproduces its own bytes."""
    payload = {
        "actividad": "Instalación de fontanería y climatización",
        "domicilio": "Calle Bailén 17, 3º B, A Coruña",
        "nombre": "Muñoz Peñaranda, José Ángel",
    }

    encoded = canonical_json_bytes(payload)
    reloaded = json.loads(encoded.decode("utf-8"))

    assert canonical_json_bytes(reloaded) == encoded
    assert content_hash_hex(reloaded) == content_hash_hex(payload)


def test_canonical_json_bytes_refuses_non_finite_numbers() -> None:
    """``NaN`` is not JSON, so it never reaches a persisted record."""
    for value in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="not JSON compliant"):
            canonical_json_bytes({"amount": value})


def test_bounded_canonical_json_bytes_measures_encoded_bytes_not_characters() -> None:
    """An accented record is refused on its UTF-8 length, naming its subject."""
    payload = {"nombre": "ñ" * 40}
    scalar_count = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True))

    encoded = canonical_json_bytes(payload)
    assert len(encoded) > scalar_count

    assert bounded_canonical_json_bytes(payload, maximum_bytes=len(encoded), subject="perfil") == encoded
    with pytest.raises(ValueError, match=r"perfil exceeds its .*-byte canonical limit"):
        bounded_canonical_json_bytes(payload, maximum_bytes=len(encoded) - 1, subject="perfil")


def test_prefixed_digest_round_trips_through_its_own_validator() -> None:
    """The writer's spelling is exactly what the reader accepts."""
    digest = prefixed_digest(_ACCENTED_CANONICAL_BYTES)

    assert digest == f"{CONTENT_DIGEST_PREFIX}{_ACCENTED_CONTENT_HASH}"
    assert validate_prefixed_digest(digest, field_name="self_digest") == digest
    assert canonical_json_digest({"answer": 42, "accent": "niño"}, maximum_bytes=64, subject="record") == digest


@pytest.mark.parametrize(
    "value",
    [
        "",
        _ACCENTED_CONTENT_HASH,
        f"sha512:{_ACCENTED_CONTENT_HASH}",
        f"{CONTENT_DIGEST_PREFIX}{_ACCENTED_CONTENT_HASH.upper()}",
        f"{CONTENT_DIGEST_PREFIX}{_ACCENTED_CONTENT_HASH[:-1]}",
        f"{CONTENT_DIGEST_PREFIX}{_ACCENTED_CONTENT_HASH}0",
    ],
)
def test_validate_prefixed_digest_refuses_every_other_spelling(value: str) -> None:
    """Uppercase, unprefixed, wrong-algorithm and wrong-length all refuse."""
    with pytest.raises(ValueError, match="self_digest must be a lowercase sha256 digest"):
        validate_prefixed_digest(value, field_name="self_digest")


def test_strict_decode_hooks_refuse_what_the_encoder_would_never_write() -> None:
    """A duplicate member and a non-finite token both fail on the way in."""
    with pytest.raises(ValueError, match="duplicate JSON member 'answer'"):
        json.loads('{"answer":1,"answer":2}', object_pairs_hook=reject_duplicate_json_members)

    with pytest.raises(ValueError, match="non-finite JSON constant 'NaN'"):
        json.loads('{"amount":NaN}', parse_constant=reject_json_constant)

    assert json.loads('{"b":2,"a":1}', object_pairs_hook=reject_duplicate_json_members) == {"a": 1, "b": 2}


def test_content_hash_hex_changes_for_content_but_not_mapping_order() -> None:
    """Equivalent mappings share an id while a changed value receives a new one."""
    first = {"axis_label": "renta-2025", "captured_at": "2026-04-03T10:00:00+00:00", "payload_text": "alpha"}
    reordered = {"payload_text": "alpha", "captured_at": "2026-04-03T10:00:00+00:00", "axis_label": "renta-2025"}

    assert content_hash_hex(first) == content_hash_hex(reordered)
    assert content_hash_hex(first) != content_hash_hex({**first, "payload_text": "alpha "})
