"""Application-owned operator auth refusal contracts."""

from __future__ import annotations

import pytest

from ....core.errors.error_codes import build_error_envelope
from ..operator_results import AuthOperationScopeConflictError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_auth_scope_conflict_has_explicit_no_recovery() -> None:
    """The shared logout/reset scope error carries no untyped recovery command."""
    error = AuthOperationScopeConflictError(
        translated_message="application.auth.operator.errors.scope_conflict",
    )

    assert build_error_envelope(error).action is None
