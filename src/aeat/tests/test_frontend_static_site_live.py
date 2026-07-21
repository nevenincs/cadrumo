"""Real AWS and HTTPS delivery-contract test for the Cadrumo landing page."""

from __future__ import annotations

import pytest
from dev.deploy.frontend_static_site import (
    CANONICAL_DOCS_BASE_URL,
    CANONICAL_SITE_URL,
    STACK_REGION,
    _endpoint_response,
    _repo_root,
    _required_executable,
    _stack_target,
    main,
)

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_core]


def test_live_public_delivery_contract() -> None:
    """The production landing, docs, missing, and origin responses hold."""
    repo_root = _repo_root()
    target = _stack_target(_required_executable("aws"), repo_root)

    root_status, _ = _endpoint_response(f"{CANONICAL_SITE_URL}/")
    missing_status, _ = _endpoint_response(f"{CANONICAL_SITE_URL}/__cadrumo-frontend-delivery-missing__.html")
    docs_status, _ = _endpoint_response(f"{CANONICAL_DOCS_BASE_URL}/")
    direct_s3_status, _ = _endpoint_response(
        f"https://{target.bucket}.s3.{STACK_REGION}.amazonaws.com/index.html",
    )

    assert root_status == 200
    assert missing_status == 404
    assert docs_status == 200
    assert direct_s3_status == 403


def test_live_root_sync_dry_run_preserves_documentation() -> None:
    """The production dry run fails closed before a docs mutation can proceed."""
    assert main(["dry-run"]) == 0
