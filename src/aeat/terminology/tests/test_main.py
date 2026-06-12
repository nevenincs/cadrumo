"""Real entrypoint coverage for ``python -m aeat.terminology``."""

from __future__ import annotations

import pytest

from .. import __main__
from ..cli import app

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_module_entrypoint_uses_terminology_cli_app() -> None:
    assert __main__.app is app
