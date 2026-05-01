"""Windows encoding regression tests for stderr error emission."""

from __future__ import annotations

import io
import os
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from ...entrypoints.cli._errors import write_stderr
from . import WorkspaceLockedError, render_error_text

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


@contextmanager
def _output_language(language: str) -> Iterator[None]:
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
        ("es", "operación"),
        ("hu", "művelet"),
    ],
)
def test_cp1252_stderr_path_does_not_raise_on_non_ascii_output(
    language: str,
    expected_fragment: str,
) -> None:
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")

    with _output_language(language):
        write_stderr(render_error_text(WorkspaceLockedError()), stream=stream)

    rendered = buffer.getvalue().decode("utf-8")
    assert expected_fragment in rendered
