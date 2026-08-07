"""End-to-end CLI tests for the ``aeat config check`` hardware and contention rows.

Verifies that the workstation doctor surfaces the measured hardware profile and
the model-load contention verdict as typed dependency rows, that both render
through the EXISTING ``dependencies`` channel with no payload shape change, and
that neither changes the command's exit contract. Real CLI surface, real
measurement of this machine, isolated storage root, no mocks.

Nothing here loads, pulls, or runs a model. The rows are built from readings --
the hardware profile, the runtime's resident set, the model catalogue -- and a
reading is not an inference.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from .....application.provisioning import ContentionSnapshot
from .....core import AcceleratorKind, ContentionCause
from .....core.config import override_settings
from .....tests.cli_runner import invoke_cached_cli
from .....tests.secure_sql import isolated_profile_storage_root
from .._check_hardware_rows import CONTENTION_ROW_ID, contention_row

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_HARDWARE_ROW_ID = "local-inference-hardware"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        override_settings(cadrumo_local_storage_root=tmp_path / "storage", cadrumo_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
    ):
        yield


def _config_check_payload() -> dict[str, Any]:
    result = invoke_cached_cli(["--format", "json", "config", "check"])
    assert result.exit_code in (0, 2), result.output
    return json.loads(result.output)["result"]


def _snapshot(
    *,
    admitted: bool,
    causes: tuple[ContentionCause, ...],
    detail: str = "detail",
    remediation: str = "remediation",
) -> ContentionSnapshot:
    """Build a verdict the application layer could genuinely have produced.

    Constructed rather than measured because the machine's real state cannot be
    driven to each branch on demand, and the projection under test consumes only
    the verdict -- it re-derives nothing. The measured path is covered by the
    end-to-end cases above it.
    """
    return ContentionSnapshot(
        model="test-model:1b",
        requirement_bytes=1_000_000_000,
        safety_margin_bytes=500_000_000,
        accelerator=AcceleratorKind.UNKNOWN,
        admitted=admitted,
        causes=causes,
        detail=detail,
        remediation=remediation,
    )


def test_the_doctor_reports_the_hardware_profile_and_contention_rows() -> None:
    """Both rows reach the operator through the existing dependency channel."""
    payload = _config_check_payload()
    by_id = {row["service"]: row for row in payload["dependencies"]}

    assert _HARDWARE_ROW_ID in by_id, "the measured hardware profile must be reported"
    assert CONTENTION_ROW_ID in by_id, "the model-load contention verdict must be reported"
    assert by_id[_HARDWARE_ROW_ID]["detail"], "a hardware row with no detail reports nothing"


def test_the_new_rows_change_no_payload_shape() -> None:
    """They are dependency rows, so the envelope gains fields nowhere.

    Asserted because the alternative -- a bespoke ``hardware`` or ``contention``
    block on the result -- is exactly what the envelope contract forbids, and it
    is an easy thing to reach for when adding a differently-shaped row.
    """
    payload = _config_check_payload()

    assert set(payload) == {"profile_id", "ok", "capabilities", "dependencies", "preflight", "issues"}
    for row in payload["dependencies"]:
        assert set(row) == {"service", "available", "detail", "remediation"}


def test_neither_row_flips_the_commands_exit_contract() -> None:
    """The rows are reported for visibility; capability/dependency pairing owns ``ok``.

    A contended machine is not a misconfigured one. If contention could set
    ``ok`` false, running the doctor while another application held the GPU
    would report the profile as broken.
    """
    payload = _config_check_payload()
    by_id = {row["service"]: row for row in payload["dependencies"]}
    contention = by_id[CONTENTION_ROW_ID]

    assert not any(CONTENTION_ROW_ID in issue for issue in payload["issues"])
    if not contention["available"]:
        assert payload["ok"] == (not payload["issues"]), "ok follows issues, never the contention row"


def test_an_unmeasurable_machine_reports_open_rather_than_manufacturing_a_shortfall() -> None:
    """Reporting fails open where acting fails closed.

    An unreadable figure is not evidence of a shortfall. The acting path refuses
    on exactly this state -- that asymmetry is the point -- but a diagnostic
    that marked the row unavailable would tell an operator their machine cannot
    run a model when the truth is only that it could not be measured.
    """
    row = contention_row(_snapshot(admitted=False, causes=(ContentionCause.UNREADABLE,)))

    assert row.available is True
    assert "unverified" in row.detail
    assert row.remediation, "an unmeasurable machine still names how to make it measurable"


def test_a_measured_shortfall_reports_closed_with_the_remediation_that_applies() -> None:
    """A measured shortfall is a real state with a real, and specific, fix.

    The cause travels from the application layer rather than being inferred
    here, because the remediations are not interchangeable: unloading a model
    Cadrumo selected is ours to offer, closing a peer application is not.
    """
    resident = contention_row(
        _snapshot(admitted=False, causes=(ContentionCause.RUNTIME_RESIDENT,), remediation="unload the resident"),
    )
    peer = contention_row(
        _snapshot(admitted=False, causes=(ContentionCause.PEER_PROCESS,), remediation="close the other application"),
    )

    assert resident.available is False
    assert peer.available is False
    assert resident.remediation != peer.remediation, "the two causes must not collapse to one instruction"


def test_an_unmeasurable_machine_that_also_measures_short_reports_the_shortfall() -> None:
    """The more actionable claim wins when both hold.

    Fail-open covers "could not tell" ALONE. A machine that could not read one
    figure and measured a shortfall in another has a real shortfall, and
    reporting it as merely unverified would bury the actionable half.
    """
    row = contention_row(
        _snapshot(admitted=False, causes=(ContentionCause.UNREADABLE, ContentionCause.PEER_PROCESS)),
    )

    assert row.available is False
    assert "unverified" not in row.detail


def test_an_admitted_load_and_an_unselectable_role_both_report_available() -> None:
    """The two clean states, distinguished by what they say rather than by the flag.

    A machine with headroom and a machine with no catalogued model both report
    available -- neither is a fault -- but conflating them would tell an
    operator with no model that their hardware is fine, which is true and
    useless.
    """
    admitted = contention_row(_snapshot(admitted=True, causes=(), detail="headroom is sufficient"))
    unselectable = contention_row(None)

    assert admitted.available is True
    assert unselectable.available is True
    assert unselectable.remediation == "", "there is no action to name when no model is selected"
    assert admitted.detail != unselectable.detail
