"""``aeat config check`` reports the off-host eligibility bar to the operator.

The bar is a standing per-profile permission for a taxpayer's document to leave
the machine, so its state has to be legible without reading the profile store.
Two claims, over the real CLI surface with real persistence:

* the capability APPEARS as a check row, with a posture and a source, on an
  untouched deployment where it is off;
* an operator who turned the bar on while the deployment has not opted in is
  TOLD which of the two switches is still closed, rather than meeting a
  per-invocation refusal with no explanation. That branch's firing path needs a
  registered, unlocked profile this lane has no fixture for, so it is pinned
  structurally and the gap is named in the test itself.

The rows are rendered by iterating :class:`~core.ServiceCapability`, so the
first claim would hold for any member; it is asserted anyway, because the point
is that THIS member reaches the operator and a future narrowing of that loop
would be invisible otherwise.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from .....core.capabilities import ServiceCapability
from .....core.config import override_settings
from .....tests.cli_runner import invoke_cached_cli
from .isolated_storage_fixture import config_check_backend, config_check_isolated_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["config_check_backend", "config_check_isolated_backend"]


def _payload() -> dict[str, Any]:
    result = invoke_cached_cli(["--format", "json", "config", "check"])
    assert result.exit_code in (0, 2), result.output
    return json.loads(result.output)["result"]


def _row(payload: dict[str, Any], capability: ServiceCapability) -> dict[str, Any]:
    rows = {row["capability"]: row for row in payload["capabilities"]}
    assert capability.value in rows, f"{capability.value} is absent from the config check capability rows: {rows}"
    return rows[capability.value]


def test_the_eligibility_bar_is_reported_and_is_off_on_an_untouched_deployment() -> None:
    row = _row(_payload(), ServiceCapability.CLOUD_EVIDENCE_UPLOAD)

    assert row["enabled"] is False
    assert row["source"], "a reported posture with no source cannot be acted on"


def test_the_bar_being_off_raises_no_issue() -> None:
    """The negative half, and the reason the structural check below is not redundant."""
    payload = _payload()

    assert [issue for issue in payload["issues"] if "cloud_evidence_upload" in issue] == []


def test_the_issue_branch_reads_both_the_capability_and_the_deployment_flag() -> None:
    """Structural, and the limitation is stated rather than papered over.

    NOT COVERED END TO END: making the issue fire needs a registered, unlocked
    profile carrying an explicit opt-in fact, which this CLI test lane has no
    fixture for; the surrounding tests all run with no active profile. Rather
    than assert a condition that cannot arise here and read as coverage, this
    pins the branch's INPUTS -- an issue keyed on the capability alone would
    fire on a deployment that already refuses, and one keyed on the flag alone
    would fire for a profile that never asked. Both readings must be present.

    The behaviour those inputs feed is proved where it can be: the resolver's
    own gate tests under ``application/user_profile/tests``.
    """
    source = (Path(__file__).resolve().parents[1] / "_check_cli.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    branches = [
        node for node in ast.walk(tree) if isinstance(node, ast.If) and "CLOUD_EVIDENCE_UPLOAD" in ast.dump(node.test)
    ]
    assert branches, "no config-check branch reads the cloud-evidence eligibility bar at all"
    assert any("cadrumo_evidence_cloud_upload_permitted" in ast.dump(node.test) for node in branches), (
        "the eligibility-bar issue is keyed on the capability alone; it must also read the deployment "
        "opt-in, or it fires for a deployment that already refuses the read"
    )


def test_the_gestor_bar_is_visible_as_the_reason_the_capability_is_off() -> None:
    """A gestor deployment must be able to SEE that the bar is categorical."""
    with override_settings(cadrumo_evidence_gestor_mode=True):
        row = _row(_payload(), ServiceCapability.CLOUD_EVIDENCE_UPLOAD)

    assert row["enabled"] is False
    assert row["source"] == "safety_floor", (
        "under gestor mode the reported source must be the safety floor, not the ordinary default -- "
        "an operator cannot tell a categorical bar from an unanswered question otherwise"
    )
