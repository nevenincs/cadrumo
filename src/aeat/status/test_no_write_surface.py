"""Static safety tests enforcing the read-only contract (#227).

Mirrors :mod:`aeat.history.test_no_write_surface`, adapted for the
status subpackage. Walks every ``.py`` file under
``src/aeat/status/`` and asserts:

1. None contain mutating-Playwright patterns (form.submit, page.fill,
   page.click, page.type, page.select_option, page.check,
   page.press, page.set_input_files).
2. No public API name exported via :mod:`aeat.status.__init__`
   matches a write-verb regex (submit, send, ack, acknowledge,
   mark_, confirm, file_, post_).

See the live-AEAT-write safety charter (#116) and ADR D1 of
[[2026-04-18-aeat-filing-detail-fetch-adr]].
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from . import __all__ as status_public_api

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


_STATUS_ROOT = Path(__file__).resolve().parent

_FORBIDDEN_PLAYWRIGHT_RE = re.compile(
    r"page\.(fill|click|type|select_option|check|press|set_input_files)"
    r"|form\.submit"
    r"|\.click\(\)",
)
_FORBIDDEN_PUBLIC_API_RE = re.compile(
    r"^(submit|send|ack|acknowledge|mark_|confirm|file_|post_)",
    re.IGNORECASE,
)


def _iter_py_files() -> list[Path]:
    return sorted(path for path in _STATUS_ROOT.rglob("*.py") if "__pycache__" not in path.parts)


def test_no_mutating_playwright_calls() -> None:
    offenders: list[tuple[str, int, str]] = []
    for path in _iter_py_files():
        # The regex literal above appears verbatim in this file — avoid
        # self-matching.
        if path.name == "test_no_write_surface.py":
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _FORBIDDEN_PLAYWRIGHT_RE.search(line):
                offenders.append((str(path), lineno, line))
    assert offenders == [], f"forbidden write-surface patterns found: {offenders!r}"


def test_no_write_verbs_in_public_api() -> None:
    offenders = [name for name in status_public_api if _FORBIDDEN_PUBLIC_API_RE.match(name)]
    assert offenders == [], (
        f"public API exposes write-verb names: {offenders!r}. Status reader is a read-only surface; see ADR D1."
    )
