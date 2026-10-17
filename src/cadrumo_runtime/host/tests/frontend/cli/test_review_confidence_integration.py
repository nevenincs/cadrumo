"""Integration tests for the ``review queue --confidence-below`` CLI gate."""

from __future__ import annotations

import pytest

from cadrumo.core.config import override_settings

from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.usefixtures("open_bucket_cli_backend")
def test_review_queue_out_of_range_confidence_is_instructive() -> None:
    with override_settings(cadrumo_output_language="en"):
        result = invoke_cached_cli(["app", "review", "queue", "--confidence-below", "1.5"])

    assert result.exit_code != 0
    flattened = " ".join(result.output.replace("│", " ").split())
    assert "between 0 and 1" in flattened, result.output
