"""Real AWS and HTTPS delivery-contract test for Cadrumo documentation."""

from __future__ import annotations

import pytest
from dev.deploy.docs_static_site import (
    _LEGACY_DOCS_URL,
    _MISSING_DOCS_PATH,
    CANONICAL_DOCS_BASE_URL,
    STACK_REGION,
    _endpoint_response,
    _repo_root,
    _required_executable,
    _stack_target,
)

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_core]


def test_live_public_delivery_contract() -> None:
    """The production canonical, legacy, missing, and origin responses hold."""
    repo_root = _repo_root()
    target = _stack_target(_required_executable("aws"), repo_root)

    canonical_status, _ = _endpoint_response(f"{CANONICAL_DOCS_BASE_URL}/")
    legacy_status, legacy_headers = _endpoint_response(_LEGACY_DOCS_URL)
    missing_status, _ = _endpoint_response(f"{CANONICAL_DOCS_BASE_URL}/{_MISSING_DOCS_PATH}")
    direct_s3_status, _ = _endpoint_response(
        f"https://{target.bucket}.s3.{STACK_REGION}.amazonaws.com/docs/index.html",
    )

    assert canonical_status == 200
    assert legacy_status == 308
    assert legacy_headers.get("location") == f"{CANONICAL_DOCS_BASE_URL}/"
    assert missing_status == 404
    assert direct_s3_status == 403
