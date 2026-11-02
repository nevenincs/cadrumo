"""A reader that forgets its own guard still cannot send a refused API request.

Playwright API requests pass through no route, so every case runs on the real
browser boundary whose proxy stands in for AEAT, and each opens by proving that
proxy carries this context's API traffic. Nothing here contacts AEAT.
"""

from __future__ import annotations

import ast
import logging
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ......core.async_cleanup import close_async_resources
from ......core.config import Settings
from ......domain.calculations.registry.errors import RegistryValidationError
from ......domain.calculations.registry.remote_state_guard import RemoteStateGuardPolicy
from ......domain.calculations.registry.schema_base import EvidenceTier
from ..._playwright import PlaywrightError
from ..api_request_guard import GuardedApiRequests
from .real_http_boundary import EXTERNAL, LocalHttpBoundary, open_real_browser_session, opened_http_boundary

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]

_AEAT_ROOT = Path(__file__).resolve().parents[2]
_GUARD_MODULE = _AEAT_ROOT / "browser" / "api_request_guard.py"
_HOST = EXTERNAL.aeat.domains.www12
_READ_URL = f"{_HOST}/wlpl/SYNT-TEST/ConsultaDocumento"
_WRITE_URL = f"{_HOST}/wlpl/SYNT-TEST/PresentarDeclaracion"
_QUERY_VALUE = "synthetic-query-value"
_POLICY = RemoteStateGuardPolicy(
    id="synthetic-read",
    evidence_tier=EvidenceTier.OFFICIAL_SOURCE_GUIDANCE,
    classification="authenticated_read_surface",
    allowed_hosts=(_HOST.removeprefix("https://"),),
    synthetic_data_allowed=False,
    requires_authentication=True,
    requires_aeat_authorization=True,
)
_NARROW_POLICY = _POLICY.model_copy(update={"id": "synthetic-narrow", "allowed_read_paths": ("/wlpl/SYNT-TEST/Otro",)})
_STATIC_POLICY = _POLICY.model_copy(update={"id": "synthetic-static", "classification": "static_official_only"})


async def _require_traffic_stays_on_the_boundary(context: BrowserContext) -> None:
    """Fail before any AEAT URL is used unless the stand-in proxy itself answers for a foreign host."""
    # The proxy's refusal surfaces either as a response or, when the tunnel closes first, in the abort's call log.
    try:
        response = await context.request.get("https://www.example.com/", max_retries=0)
    except PlaywrightError as exc:
        answered = re.search(r"403 Forbidden\s+- server: BaseHTTP", exc.message) is not None
    else:
        answered = response.status == 403 and response.headers.get("server", "").startswith("BaseHTTP")
    assert answered


@asynccontextmanager
async def _context_on_the_boundary(profile_name: str) -> AsyncGenerator[tuple[BrowserContext, LocalHttpBoundary]]:
    """Yield a production context once its API traffic is proven to stay on the stand-in."""
    async with opened_http_boundary() as boundary:
        playwright, session = await open_real_browser_session(
            boundary=boundary, settings=Settings(), profile_name=profile_name
        )
        context = None
        try:
            context = await session.create_context()
            await _require_traffic_stays_on_the_boundary(context)
            yield context, boundary
        finally:
            await close_async_resources(context, session, task_name="api-guard-test-close")
            await playwright.stop()


async def _forgetful_reader(requests: GuardedApiRequests, url: str) -> None:
    """A planted reader that fetches without calling its own read assertion."""
    await requests.get(url)


@pytest.mark.asyncio
async def test_guard_refuses_what_the_bare_context_would_have_sent(caplog: pytest.LogCaptureFixture) -> None:
    """DETECTOR TEETH: the same write route reaches the stand-in unguarded and nothing reaches it guarded."""
    async with _context_on_the_boundary("api-guard-write") as (context, boundary):
        url = f"{_WRITE_URL}?nif={_QUERY_VALUE}"
        requests = GuardedApiRequests(context, (_POLICY,))

        with caplog.at_level(logging.WARNING), pytest.raises(RegistryValidationError) as refused:
            await _forgetful_reader(requests, url)
        with pytest.raises(RegistryValidationError):
            await requests.post(_WRITE_URL, form={"modelo": "000"})
        assert boundary.requested_urls == []

        await context.request.get(url)
        assert boundary.requested_urls == [url]

    assert _QUERY_VALUE not in str(refused.value)
    refusals = [record.getMessage() for record in caplog.records if "api request refused" in record.getMessage()]
    assert [refusal.split("method=")[1].split()[0] for refusal in refusals] == ["GET", "POST"]
    for refusal in refusals:
        assert "/wlpl/SYNT-TEST/PresentarDeclaracion" in refusal
        assert "synthetic-read" in refusal
        assert _QUERY_VALUE not in refusal


@pytest.mark.asyncio
async def test_a_read_any_member_allows_is_sent_and_every_other_policy_set_refuses() -> None:
    async with _context_on_the_boundary("api-guard-union") as (context, boundary):
        for refused_set in ((), (_NARROW_POLICY,), (_STATIC_POLICY,)):
            with pytest.raises(RegistryValidationError):
                await GuardedApiRequests(context, refused_set).get(_READ_URL)
        assert boundary.requested_urls == []

        response = await GuardedApiRequests(context, (_NARROW_POLICY, _POLICY)).get(_READ_URL)
        assert response.status == 200
        assert boundary.requested_urls == [_READ_URL]


@pytest.mark.asyncio
async def test_an_unreadable_or_off_host_url_is_refused_unsent() -> None:
    async with _context_on_the_boundary("api-guard-malformed") as (context, boundary):
        requests = GuardedApiRequests(context, (_POLICY,))
        for url in ("not a url", "https://[broken/", "https://www.example.com/", f"http{_HOST[5:]}/x"):
            with pytest.raises(RegistryValidationError):
                await requests.get(url)
        assert boundary.requested_urls == []


def _direct_api_request_uses(source: str) -> list[int]:
    """Lines reaching a Playwright ``.request`` other than an intercepted ``route.request``."""
    lines: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute) and node.attr == "request":
            if not (isinstance(node.value, ast.Name) and node.value.id == "route"):
                lines.append(node.lineno)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and any(isinstance(arg, ast.Constant) and arg.value == "request" for arg in node.args)
        ):
            lines.append(node.lineno)
    return lines


@pytest.mark.parametrize(
    "planted",
    [
        "await context.request.get(url)",
        "await page.context.request.post(url)",
        "await page.request.post(url)",
        "api = self._context.request",
        "api = getattr(context, 'request')",
    ],
)
def test_the_static_gate_catches_a_planted_direct_use(planted: str) -> None:
    source = f"async def reader():\n    {planted}\n"
    assert _direct_api_request_uses(source) == [2]


def test_the_static_gate_admits_an_intercepted_route_request() -> None:
    assert _direct_api_request_uses("request = route.request\n") == []


def test_no_aeat_adapter_reaches_a_direct_api_request() -> None:
    sources = [path for path in _AEAT_ROOT.rglob("*.py") if "tests" not in path.parts and path != _GUARD_MODULE]
    assert any(path.name == "notifications.py" for path in sources)
    offenders = {
        path.relative_to(_AEAT_ROOT).as_posix(): lines
        for path in sources
        if (lines := _direct_api_request_uses(path.read_text(encoding="utf-8")))
    }
    assert offenders == {}
