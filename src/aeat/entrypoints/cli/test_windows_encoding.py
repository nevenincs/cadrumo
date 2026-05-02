"""Windows encoding regression tests for CLI stderr emission.

Pins the contract that
:func:`aeat.entrypoints.cli._errors.write_stderr` never raises when
the underlying stream uses the Windows default ``cp1252`` codec, even
when :func:`aeat.core.errors.render_error_text` produces non-ASCII
characters under the operator's configured language.
"""

from __future__ import annotations

import io
import os
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from ...core.access_gate import LiveSubmitForbiddenError
from ...core.errors import render_error_text
from ._errors import write_stderr

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@contextmanager
def _output_language(language: str) -> Iterator[None]:
    """Temporarily override ``AEAT_OUTPUT_LANGUAGE`` for the duration of a test."""
    previous = os.environ.get("AEAT_OUTPUT_LANGUAGE")
    os.environ["AEAT_OUTPUT_LANGUAGE"] = language
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("AEAT_OUTPUT_LANGUAGE", None)
        else:
            os.environ["AEAT_OUTPUT_LANGUAGE"] = previous


@pytest.mark.parametrize(
    ("language", "expected_fragment"),
    [
        ("es", "envío"),
        ("hu", "élő"),
    ],
)
def test_cp1252_stderr_path_does_not_raise_on_non_ascii_output(
    language: str,
    expected_fragment: str,
) -> None:
    """``write_stderr`` survives a ``cp1252`` stream when emitting non-ASCII glyphs."""
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")

    with _output_language(language):
        write_stderr(render_error_text(LiveSubmitForbiddenError()), stream=stream)

    rendered = buffer.getvalue().decode("utf-8")
    assert expected_fragment in rendered
