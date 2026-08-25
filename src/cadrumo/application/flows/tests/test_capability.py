"""Frontend-capability classification over the real host — no mocks.

``detect_frontend_capability`` inspects the real process stdio and the
real ``TERM`` environment; the tests assert its classification
structurally (enum members) rather than stubbing the host. An explicit
override is honoured verbatim, and the capture-stdio pytest process — a
genuinely non-interactive host — is detected as such.
"""

from __future__ import annotations

import sys

import pytest

from ....core.flows import FrontendCapability
from ..capability import detect_frontend_capability

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_override_is_returned_verbatim() -> None:
    for member in FrontendCapability:
        assert detect_frontend_capability(override=member) is member


def test_non_tty_pytest_process_detects_non_interactive() -> None:
    # pytest captures stdio, so neither stream is a real TTY: the honest
    # classification is non-interactive.
    assert not sys.stdin.isatty()
    assert detect_frontend_capability() is FrontendCapability.NON_INTERACTIVE
