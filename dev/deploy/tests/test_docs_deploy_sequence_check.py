"""The deploy's cli-sequence check refuses to publish on a real failing sequence.

A separate module because it runs the real check in child interpreters, which
makes it an integration test beside the unit tests of the deploy composition.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..docs_static_site import _check_cli_sequences

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def test_a_failing_sequence_check_refuses_the_publish(tmp_path: Path) -> None:
    """A real check over a page whose sequence has no committed golden stops the deploy."""
    docs = tmp_path / "docs"
    page = docs / "how-to" / "deploy-refusal.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        "# Deploy refusal\n\nCreate a profile with `aeat config profile create`.\n\n"
        "```{cli-sequence} deploy-refusal-case\n:verify: Verify the listing succeeds.\n```\n",
        encoding="utf-8",
    )
    contract = docs / "_sequences" / "contracts" / "how-to" / "deploy-refusal" / "deploy-refusal-case.seq"
    contract.parent.mkdir(parents=True)
    contract.write_text(
        '@result aeat --format json config profile list\n@expect status == "success"\n',
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as refusal:
        _check_cli_sequences(tmp_path, records_root=tmp_path / "records")

    message = str(refusal.value)
    assert "refusing to publish" in message
    assert "deploy-refusal-case" in message and "no committed golden" in message
