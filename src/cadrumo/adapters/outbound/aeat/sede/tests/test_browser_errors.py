"""Real-behavior tests for BrowserAdapterTypeError at the sede page boundary.

Coverage:
- contract-A: BrowserAdapterTypeError is bound in ERROR_REGISTRY.
- contract-B: build_error_envelope produces a valid envelope for BrowserAdapterTypeError.
- contract-C: require_playwright_page rejects a non-Page object with the same
  typed error and diagnostic context consumed by the Renta WEB Open, NIF-IVA,
  and GROI drivers.
"""

from __future__ import annotations

import pytest

from ......core.errors import ERROR_REGISTRY, build_error_envelope
from .._adapter_utils import require_playwright_page
from ..errors import BrowserAdapterTypeError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


# ---------------------------------------------------------------------------
# contract-A: registry binding
# ---------------------------------------------------------------------------


def test_browser_adapter_type_error_is_registered_in_error_registry() -> None:
    assert "ERROR_SEDE_BROWSER_ADAPTER_TYPE" in ERROR_REGISTRY


# ---------------------------------------------------------------------------
# contract-B: envelope round-trip
# ---------------------------------------------------------------------------


def test_browser_adapter_type_error_round_trips_through_build_error_envelope() -> None:
    err = BrowserAdapterTypeError(
        "BrowserContext.new_page() did not return a Playwright Page; got <class 'str'>",
        context={"actual_type": "str"},
    )
    envelope = build_error_envelope(err)
    assert envelope.code == "ERROR_SEDE_BROWSER_ADAPTER_TYPE"
    assert envelope.retryable is False
    assert "actual_type" in (envelope.context or {})


def test_require_playwright_page_rejects_wrong_page_type() -> None:
    with pytest.raises(BrowserAdapterTypeError) as exc_info:
        require_playwright_page(object())

    assert exc_info.value.context is not None
    assert exc_info.value.context["actual_type"] == "object"
