"""Public operation failures retain the canonical error envelope taxonomy."""

import json

import pytest

from ..error_codes import build_error_envelope, get_registered_error_code_by_code, render_error_json
from ..hierarchy import InternalInvariantError, PublicErrorProjectionError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    "code",
    (
        "REFUSED_AUTH_CONFIGURE_NO_ACTIVE_BUCKET",
        "LOCKED_STORAGE_LOCK_ACQUISITION",
        "INTERNAL_INVARIANT",
    ),
)
def test_projected_failure_keeps_code_category_retryability_and_runbook(code) -> None:
    reference = "sha256:0123456789ab"
    projected = PublicErrorProjectionError(code, diagnostic_ref=reference)
    canonical = get_registered_error_code_by_code(code)
    envelope = build_error_envelope(projected)
    assert envelope.code == canonical.code
    assert envelope.category == canonical.category.value
    assert envelope.retryable == canonical.retryable
    assert envelope.runbook_id == canonical.runbook_id
    document = json.loads(render_error_json(projected, command="config.auth.configure"))
    assert document["error"]["context"] == {"diagnostic_ref": reference, "error_code": code}
    assert document["command"] == "config.auth.configure"


def test_projected_failure_refuses_a_private_path_as_diagnostic_reference() -> None:
    with pytest.raises(InternalInvariantError) as rejected:
        PublicErrorProjectionError("INTERNAL_INVARIANT", diagnostic_ref="private-secret-directory/profile.log")
    assert "private-secret-directory" not in str(rejected.value)
