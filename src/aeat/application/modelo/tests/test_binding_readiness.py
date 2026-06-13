"""Real-behaviour coverage for binding-readiness fallbacks."""

from __future__ import annotations

import logging

import pytest

from ....core import Period
from ....domain.calculations.registry import RegistryValidationError
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


def test_unresolvable_typed_period_scope_is_logged_as_conservative_unresolved(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit Period scopes use the typed registry token at the snapshot boundary."""
    caplog.set_level(logging.DEBUG, logger="aeat.application.modelo._binding_readiness")

    resolved = profile_resolvable_binding_ids(
        modelo="not-a-modelo",
        bucket_id="operator",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
    )

    assert resolved == frozenset()
    assert any(
        "binding-readiness: registry snapshot unavailable" in record.message and "period=1T" in record.message
        for record in caplog.records
    )


def test_typed_period_scope_must_match_filing_year() -> None:
    """The helper refuses contradictory typed coordinates before querying the registry."""

    with pytest.raises(RegistryValidationError, match="does not match filing year"):
        profile_resolvable_binding_ids(
            modelo="303",
            bucket_id="operator",
            filing_year=2025,
            period=Period.from_year_and_code(2026, "1T"),
        )
