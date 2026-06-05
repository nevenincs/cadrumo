"""CLI tests for review operator error rendering."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from ....core.i18n import tr
from .._review import app as review_app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_review_queue_unknown_kind_localises_without_raw_selector(cli_runner: CliRunner) -> None:
    sensitive_kind = "client-tax-id-12345678Z-private-note"

    result = cli_runner.invoke(review_app, ["queue", "--kind", sensitive_kind])

    assert result.exit_code != 0
    assert tr("review.operator.errors.unknown_kind") in result.output
    assert sensitive_kind not in result.output
    assert "review.operator.errors.unknown_kind" not in result.output
