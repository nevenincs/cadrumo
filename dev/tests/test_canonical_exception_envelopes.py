"""Public envelopes for migrated exceptions never expose positional diagnostics."""

from __future__ import annotations

import pytest

from cadrumo.application.modelo.m036_lifecycle import M036DeclarationNotFoundError
from cadrumo.core.errors.error_codes import build_error_envelope
from cadrumo.core.errors.hierarchy import InternalInvariantError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("error", "secret", "expected_code"),
    [
        (
            M036DeclarationNotFoundError("private-declaration-123"),
            "private-declaration-123",
            "REFUSED_M036_DECLARATION_NOT_FOUND",
        ),
        (
            InternalInvariantError("private-runtime-state-456"),
            "private-runtime-state-456",
            "INTERNAL_INVARIANT",
        ),
    ],
)
def test_migrated_exception_envelope_uses_registered_public_message(
    error: BaseException,
    secret: str,
    expected_code: str,
) -> None:
    envelope = build_error_envelope(error)

    assert envelope.code == expected_code
    assert envelope.message
    assert secret not in envelope.message
    assert ".canonical_" not in envelope.message
