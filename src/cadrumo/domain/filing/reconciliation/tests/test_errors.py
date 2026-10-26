"""Tests for the reconciliation error hierarchy.

`ReconciliationError` and its children are surfaced to operators via the
typed-error registry (`core/errors/registry/_domain.py`) which references
them by string-literal dotted name. The string reference is invisible to
static AST import-graph analysis, so the module needs an explicit test
file to keep it inside the coverage gate.
"""

from __future__ import annotations

import pytest

from .....core.errors.hierarchy import CadrumoError
from ..errors import (
    ReconciliationDeclaracionParseError,
    ReconciliationDriftError,
    ReconciliationError,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_reconciliation_error_is_an_cadrumo_error() -> None:
    """The base reconciliation error inherits from CadrumoError so the
    error-registry boundary can resolve it through the typed-error path."""

    assert issubclass(ReconciliationError, CadrumoError)


def test_reconciliation_declaracion_parse_error_is_a_reconciliation_error() -> None:
    """Parse failures during reconciliation flow up through the
    reconciliation error hierarchy."""

    assert issubclass(ReconciliationDeclaracionParseError, ReconciliationError)
    assert issubclass(ReconciliationDeclaracionParseError, CadrumoError)


def test_reconciliation_drift_error_is_a_reconciliation_error() -> None:
    """Arithmetic/identity drift detected during reconciliation flows
    up through the reconciliation error hierarchy."""

    assert issubclass(ReconciliationDriftError, ReconciliationError)
    assert issubclass(ReconciliationDriftError, CadrumoError)


def test_reconciliation_error_carries_translated_message() -> None:
    """Reconciliation errors round-trip the translated_message key
    through CadrumoError so the rendering boundary sees a tr() key, not
    a hardcoded English string."""

    exc = ReconciliationDriftError(
        translated_message="errors.reconciliation.drift_detected",
        context={"modelo": "303", "diff": "EUR 12.34"},
    )

    assert exc.translated_message == "errors.reconciliation.drift_detected"
    assert exc.context == {"modelo": "303", "diff": "EUR 12.34"}


def test_reconciliation_hierarchy_catch_order_matches_specificity() -> None:
    """Catching the base ReconciliationError catches every subclass —
    the standard hierarchy guarantee, locked here so subclass additions
    don't accidentally bypass it."""

    for subclass in (ReconciliationDeclaracionParseError, ReconciliationDriftError):
        instance = subclass()
        with pytest.raises(ReconciliationError):
            raise instance
