"""Unit tests for shared Sede Playwright stage error mapping."""

from __future__ import annotations

import pytest

from ......core.logging import get_logger
from ..._playwright import PlaywrightError, PlaywrightTimeoutError
from .._browser_stage import run_playwright_stage
from ..errors import SedeFailureMode, SedeNavigationError, SedeParseError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


async def _timeout() -> None:
    raise PlaywrightTimeoutError("selector timeout")


async def _playwright_error() -> None:
    raise PlaywrightError("browser failure")


@pytest.mark.asyncio
async def test_shape_timeout_reports_external_shape_change() -> None:
    with pytest.raises(SedeParseError, match=r"page element was not visible") as excinfo:
        await run_playwright_stage(
            _timeout(),
            stage="wait-control",
            description="expected control",
            timeout_ms=250,
            surface_label="Demo Surface",
            log_prefix="demo surface",
            logger=get_logger(__name__),
            timeout_is_shape_change=True,
        )

    assert excinfo.value.failure_mode == SedeFailureMode.EXTERNAL_SHAPE_CHANGED
    assert excinfo.value.context is not None
    assert excinfo.value.context["stage"] == "wait-control"
    assert excinfo.value.context["expected"] == "expected control"


@pytest.mark.asyncio
async def test_navigation_timeout_reports_live_navigation_failure() -> None:
    with pytest.raises(SedeNavigationError, match=r"browser stage") as excinfo:
        await run_playwright_stage(
            _timeout(),
            stage="networkidle",
            description="network idle",
            timeout_ms=250,
            surface_label="Demo Surface",
            log_prefix="demo surface",
            logger=get_logger(__name__),
        )

    assert excinfo.value.failure_mode == SedeFailureMode.LIVE_NAVIGATION_FAILED
    assert excinfo.value.context is not None
    assert excinfo.value.context["stage"] == "networkidle"
    assert excinfo.value.context["timeout_ms"] == 250


@pytest.mark.asyncio
async def test_playwright_error_reports_cause_type() -> None:
    with pytest.raises(SedeNavigationError, match=r"browser stage") as excinfo:
        await run_playwright_stage(
            _playwright_error(),
            stage="click-submit",
            description="submit button",
            timeout_ms=250,
            surface_label="Demo Surface",
            log_prefix="demo surface",
            logger=get_logger(__name__),
        )

    assert excinfo.value.failure_mode == SedeFailureMode.LIVE_NAVIGATION_FAILED
    assert excinfo.value.context is not None
    assert excinfo.value.context["cause_type"] == "Error"
