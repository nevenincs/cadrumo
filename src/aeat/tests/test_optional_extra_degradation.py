"""Lean-core graceful degradation: the package imports without the optional extras,
and each feature boundary refuses instructively when its extra is absent.

The optional integration stacks (``google`` / ``browser`` / ``anthropic``) live in
``[project.optional-dependencies]``. These tests use a real import blocker — a
``sys.meta_path`` finder that makes the package genuinely unimportable, the same
condition a fresh ``pip install aeat`` (no extras) produces — rather than a mock.
With the extra blocked the core CLI must still build, and reaching the feature
must raise the feature's own typed error naming ``pip install aeat[<extra>]``.
"""

from __future__ import annotations

import importlib
import importlib.abc
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _ImportBlocker(importlib.abc.MetaPathFinder):
    """A meta-path finder that refuses to resolve the named top-level packages."""

    def __init__(self, blocked: frozenset[str]) -> None:
        self._blocked = blocked

    def find_spec(self, fullname: str, path: object = None, target: object = None) -> None:
        top = fullname.split(".", 1)[0]
        if top in self._blocked or fullname.startswith(("google.auth", "google.oauth2")):
            raise ModuleNotFoundError(f"blocked optional import: {fullname}")
        return None


@contextmanager
def _block_imports(*names: str) -> Iterator[None]:
    """Make ``names`` (and their submodules) genuinely unimportable for the block."""
    blocked = frozenset(names)
    saved: dict[str, ModuleType] = {}
    for mod_name in list(sys.modules):
        top = mod_name.split(".", 1)[0]
        if top in blocked or mod_name.startswith(("google.auth", "google.oauth2")):
            saved[mod_name] = sys.modules.pop(mod_name)
    blocker = _ImportBlocker(blocked)
    sys.meta_path.insert(0, blocker)
    try:
        yield
    finally:
        sys.meta_path.remove(blocker)
        sys.modules.update(saved)


def test_blocker_actually_blocks() -> None:
    """Guard the test instrument itself: the blocked package is truly unimportable."""
    with _block_imports("anthropic"), pytest.raises(ModuleNotFoundError):
        importlib.import_module("anthropic")


def test_cli_builds_with_every_optional_extra_blocked() -> None:
    """A fresh-install operator with no extras can still build and run the core CLI."""
    from typer.testing import CliRunner

    with _block_imports("anthropic", "playwright", "playwright_stealth", "googleapiclient", "google_auth_oauthlib"):
        from ..entrypoints.cli import app

        result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0, result.output


def test_anthropic_boundary_refuses_instructively_without_the_extra() -> None:
    """Building the Anthropic adapter without the extra raises LLMConfigError, not ModuleNotFoundError."""
    from ..adapters.outbound.llm._client import LLMClient
    from ..adapters.outbound.llm._errors import LLMConfigError
    from ..adapters.outbound.llm._models import LLMProvider
    from ..core.config import load_settings

    client = LLMClient(settings=load_settings())
    with _block_imports("anthropic"), pytest.raises(LLMConfigError) as raised:
        client._build_adapter(LLMProvider.ANTHROPIC)
    assert raised.value.suggestion == "pip install aeat[anthropic]"


@pytest.mark.asyncio
async def test_browser_boundary_refuses_instructively_without_the_extra() -> None:
    """Starting the Playwright runtime without the extra raises BrowserError with the install hint."""
    from ..adapters.outbound.aeat.browser._errors import BrowserError

    with _block_imports("playwright", "playwright_stealth"):
        from ..adapters.outbound.aeat.browser import _factory

        with pytest.raises(BrowserError) as raised:
            await _factory._start_playwright()
    assert raised.value.suggestion == "pip install aeat[browser]"


def test_google_extra_unavailable_is_observed_by_the_probe_without_the_extra() -> None:
    """With the google stack blocked the doctor probe reports it absent + the install hint."""
    from ..core import GOOGLE_EXTRA, optional_extra_available

    with _block_imports("googleapiclient", "google_auth_oauthlib"):
        assert optional_extra_available(GOOGLE_EXTRA) is False
    # Restored afterwards (the dev environment has the extra installed).
    assert optional_extra_available(GOOGLE_EXTRA) is True
