"""Static safety tests enforcing the read-only contract.

This module is the belt-and-braces version of the ADR-D1 grep gate.
It walks every ``.py`` file under ``src/aeat/history/`` and asserts:

1. None contain mutating-Playwright patterns (form.submit, page.fill,
   page.click, page.type, page.select_option, page.check,
   page.press, page.set_input_files).
2. No public API name exported via :mod:`aeat.history.__init__`
   matches a write-verb regex (submit, send, ack, acknowledge,
   mark_, confirm, file_, post_).

If AEAT ever needs a write surface, that surface is **not** built in
this subpackage. See the live-AEAT-write safety charter (#116).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from . import __all__ as history_public_api

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


_HISTORY_ROOT = Path(__file__).resolve().parent

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
    return sorted(path for path in _HISTORY_ROOT.rglob("*.py") if "__pycache__" not in path.parts)


def test_no_mutating_playwright_calls() -> None:
    offenders: list[tuple[str, int, str]] = []
    for path in _iter_py_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if path.name == "test_no_write_surface.py":
                # Avoid self-matching on the regex pattern literal above.
                continue
            if _FORBIDDEN_PLAYWRIGHT_RE.search(line):
                offenders.append((str(path), lineno, line))
    assert offenders == [], f"forbidden write-surface patterns found: {offenders!r}"


def test_no_write_verbs_in_public_api() -> None:
    offenders = [name for name in history_public_api if _FORBIDDEN_PUBLIC_API_RE.match(name)]
    assert offenders == [], (
        f"public API exposes write-verb names: {offenders!r}. Filing history is a read-only surface; see ADR D1."
    )
