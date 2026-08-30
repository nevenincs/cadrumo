"""CLI surface tests for `aeat app live justificante {list, view}`.

The ``capture`` verb is a live read (covered by the application-layer
orchestrator and the opt-in live test); these tests exercise the local
read verbs and the registration wiring without contacting AEAT.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from click.testing import Result

from ....application.live.justificante import JustificanteCaptureSnapshotService
from ....core.period import Period
from ....tests.cli_runner import invoke_cached_cli
from ._live_read_profile_fixture import _ACTIVE_TEST_BUCKET_ID, _isolated_backend

__all__ = ["_isolated_backend"]

# INTENTIONAL: integration because it exercises the local justificante read verbs and
# registration wiring without contacting AEAT.
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke_justificante(args: Sequence[str]) -> Result:
    return invoke_cached_cli(["app", "live", "justificante", *args])


def test_justificante_list_is_empty_on_fresh_bucket() -> None:
    result = _invoke_justificante(["list"])
    assert result.exit_code == 0, result.output
    assert "count\t0" in result.output


def test_justificante_capture_command_is_not_registered() -> None:
    result = _invoke_justificante(["capture", "--help"])

    assert result.exit_code != 0
    assert "No such command" in result.output


def test_justificante_view_refuses_unknown_snapshot() -> None:
    result = _invoke_justificante(["view", "no-such-snapshot"])
    assert result.exit_code != 0


def test_justificante_list_and_view_emit_registry_period_tokens() -> None:
    pdf_bytes = b"%PDF-1.4\njustificante period cli smoke\n%%EOF"
    snapshot = JustificanteCaptureSnapshotService(bucket_id=_ACTIVE_TEST_BUCKET_ID).capture(
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        expediente_id="202613000010001A",
        csv="ABCD1234EFGH5678",
        pdf_bytes=pdf_bytes,
        pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        captured_at=datetime(2026, 4, 20, 10, 30, tzinfo=UTC),
    )

    listed = _invoke_justificante(["list"])
    assert listed.exit_code == 0, listed.output
    assert f"{snapshot.snapshot_id}\t130\t2026\t1T\t" in listed.output
    assert "2026 1T" not in listed.output

    viewed = _invoke_justificante(["view", snapshot.snapshot_id[:12]])
    assert viewed.exit_code == 0, viewed.output
    assert "period\t1T" in viewed.output
    assert "period\t2026 1T" not in viewed.output
