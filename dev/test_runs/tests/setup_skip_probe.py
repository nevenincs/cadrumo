"""Child-pytest probe whose only test is skipped before its body starts."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

SKIP_REASON = "setup skip persistence probe"


@pytest.mark.skipif(True, reason=SKIP_REASON)
def test_skipped_before_its_body() -> None:
    """Never runs: the verdict is decided at setup, where no call report follows."""
    raise AssertionError("a setup-phase skip ran the test body")
