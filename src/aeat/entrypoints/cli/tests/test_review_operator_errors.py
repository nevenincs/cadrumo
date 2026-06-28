"""CLI tests for review operator error rendering."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from .._review import app as review_app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_review_queue_unknown_kind_localises_without_raw_selector(cli_runner: CliRunner) -> None:
    sensitive_kind = "client-tax-id-12345678Z-private-note"

    result = cli_runner.invoke(review_app, ["queue", "--kind", sensitive_kind])

    assert result.exit_code != 0
    assert sensitive_kind not in result.output
    assert "review.operator.errors.unknown_kind" not in result.output


def test_review_queue_unknown_kind_lists_accepted_set(cli_runner: CliRunner) -> None:
    """An unknown ``--kind`` refusal names the accepted set (CLI-instructive gate).

    The architecture-boundaries mandate requires a closed-set CLI argument's
    refusal to enumerate the accepted values rather than emit a bare
    ``value invalid``. The accepted set is the documented, emitted source-kind
    vocabulary; the parseable-but-empty ``live_notification`` /
    ``sync_divergence`` tokens are intentionally not advertised.
    """
    from ....application.review import ACCEPTED_KINDS

    result = cli_runner.invoke(review_app, ["queue", "--kind", "bogus"])

    assert result.exit_code != 0
    # The Rich error box wraps and pads the message across lines, so assert
    # each accepted token appears rather than one contiguous run. Stripping
    # the box-drawing glyphs and collapsing whitespace removes the padding the
    # renderer inserts mid-token at the right margin.
    flattened = " ".join(result.output.replace("│", " ").replace("│", " ").split())
    for accepted in ACCEPTED_KINDS:
        assert accepted in flattened
    # The parseable-but-empty kinds are intentionally not advertised.
    assert "live_notification" not in flattened
    assert "sync_divergence" not in flattened
