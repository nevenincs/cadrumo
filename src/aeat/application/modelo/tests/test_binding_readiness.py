"""Real-behaviour coverage for binding-readiness fallbacks."""

from __future__ import annotations

import logging

import pytest

from .._binding_readiness import profile_resolvable_binding_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_unresolvable_registry_scope_is_logged_as_conservative_unresolved(caplog: pytest.LogCaptureFixture) -> None:
    """Invalid registry scopes return no resolved bindings and emit debug diagnostics."""
    caplog.set_level(logging.DEBUG, logger="aeat.application.modelo._binding_readiness")

    resolved = profile_resolvable_binding_ids(
        modelo="not-a-modelo",
        bucket_id="operator",
        filing_year=2026,
        period=None,
    )

    assert resolved == frozenset()
    assert any(
        "binding-readiness: annual period unavailable" in record.message
        and "treating profile bindings as unresolved" in record.message
        for record in caplog.records
    )
