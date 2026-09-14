"""Public envelopes for migrated exceptions never expose positional diagnostics."""

from __future__ import annotations

import pytest

from ..application.modelo.m036_lifecycle import M036DeclarationNotFoundError
from ..core.errors.error_codes import build_error_envelope
from ..core.errors.hierarchy import InternalInvariantError
from ..domain.calculations.registry.authority_artifact import AuthorityArtifactUnavailableError

pytestmark = [pytest.mark.unit]


@pytest.mark.parametrize(
    ("error", "secret", "expected_code"),
    [
        (
            AuthorityArtifactUnavailableError(r"C:\Users\alice\private-authority.db"),
            "alice",
            "FAIL_AUTHORITY_ARTIFACT_UNAVAILABLE",
        ),
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
