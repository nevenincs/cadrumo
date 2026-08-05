"""Source-only Python consumer for the shared JCS vector corpus.

This module is deliberately callable by a later verification gate; importing it
does not execute the corpus. The JavaScript consumer in ``verify.mjs`` reads the
same JSON file independently.
"""

from __future__ import annotations

from hashlib import sha256

from dev.docs.terminology._jcs import CanonicalJsonError, canonical_json_bytes

from . import load_vectors


def verify_python_vectors() -> None:
    """Verify every vector against the production Python canonicalizer."""

    for vector in load_vectors():
        value = vector.get("value")
        try:
            actual = canonical_json_bytes(value)
        except CanonicalJsonError:
            if vector.get("error") != "rejected":
                raise
            continue
        if vector.get("error") == "rejected":
            raise AssertionError(f"JCS vector {vector['id']!r} was accepted")
        expected_hex = vector["expected_utf8_hex"]
        if actual.hex() != expected_hex:
            raise AssertionError(f"JCS vector {vector['id']!r} bytes differ")
        expected_sha256 = vector.get("expected_sha256")
        if expected_sha256 is not None and sha256(actual).hexdigest() != expected_sha256:
            raise AssertionError(f"JCS vector {vector['id']!r} digest differs")


__all__ = ["verify_python_vectors"]
