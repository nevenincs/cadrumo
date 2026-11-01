"""A measured progress count groups its thousands the way the language writes them."""

from __future__ import annotations

import pytest

from .....core.config import override_settings
from ..modal_wording import progress_text

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("language", "expected"),
    (
        ("en", "1,234 / 5,678 (21%)"),
        ("es", "1.234 / 5.678 (21%)"),
        ("ca", "1.234 / 5.678 (21%)"),
        ("hu", "1 234 / 5 678 (21%)"),
    ),
)
def test_progress_counts_read_in_the_output_language(language: str, expected: str) -> None:
    with override_settings(cadrumo_output_language=language):
        assert progress_text(1234, 5678, None, None) == expected
