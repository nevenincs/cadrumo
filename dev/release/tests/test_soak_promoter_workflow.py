"""Structural proof for the workflow that crosses the soak boundary.

The promoter is the one scheduled thing in this pipeline that can publish, so
its shape is a safety property rather than a style preference. Two assertions
here are load-bearing above the rest: that no dispatch input can shorten a
window, and that the workflow itself holds no publication credential.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT: Final[Path] = REPO_ROOT
_WORKFLOW: Final[Path] = _REPO_ROOT / ".github" / "workflows" / "release-soak-promoter.yml"


def _document() -> Any:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _run_surface(document: Any) -> str:
    return "\n".join(
        str(step.get("run", "")) for job in document["jobs"].values() for step in job.get("steps", []) if "run" in step
    )


def test_the_promoter_carries_no_schedule_trigger() -> None:
    """The soak wait is retired.

    The orchestrator dispatches publication immediately
    after sealing a candidate, so a scheduled tick would have nothing to cross and
    would violate this project's standing no-scheduled-CI policy.
    """
    triggers = _document()[True]

    assert "schedule" not in triggers, "the soak wait is retired; no cron trigger should exist"
    assert "workflow_dispatch" in triggers, "the manual escape hatch must survive"


def test_no_input_can_shorten_a_soak_window() -> None:
    """The one axis the soak defends is time, so no form field may move it.

    The hotfix carve-out is authorised ON THE CANDIDATE, where an incident
    reference and a release-owner approval are recorded and refused at
    construction without both. An input here would let the same shortening
    happen untraceably, on the dispatch form, which is precisely the human act
    in the loop this design removes.
    """
    inputs = _document()[True]["workflow_dispatch"]["inputs"] or {}

    forbidden = re.compile(r"hours|deadline|soak|window|force|skip|now|override|expedite", re.IGNORECASE)
    offenders = [name for name in inputs if forbidden.search(name)]
    assert not offenders, f"inputs that could move the soak boundary: {offenders}"


def test_the_scheduled_job_is_short_lived_and_on_the_self_hosted_fleet() -> None:
    """A tick must not hold a shared runner slot.

    The fleet is four self-hosted runners shared across products. The soak is
    measured in days; a job that waited inside the window rather than exiting
    would starve the fleet for days per release.
    """
    job = _document()["jobs"]["promote"]

    assert job["runs-on"][0] == "self-hosted"
    assert job["timeout-minutes"] <= 30, "a promoter tick decides and exits; it never waits out a window"

    surface = _run_surface(_document())
    assert "sleep" not in surface, "a tick must not sleep inside the soak window"


def test_promotion_is_serialised_and_never_cancelled_mid_dispatch() -> None:
    """Cancelling between dispatch and consumption would re-dispatch the cohort.

    The candidate is consumed only after its dispatch returns, so a tick killed
    in that gap leaves a promoted cohort still selectable and the next tick
    dispatches it again.
    """
    concurrency = _document()["concurrency"]

    assert concurrency["cancel-in-progress"] is False
    assert "cadrumo" in concurrency["group"], "the group must be product-scoped on a shared account"


def test_the_promoter_holds_no_publication_credential() -> None:
    """It dispatches the publication authority; it never publishes.

    The OIDC token and every channel credential stay with publish-release.yml
    inside the release environment. A promoter that could upload would be a
    second publication path, bypassing Gate 2 entirely.
    """
    document = _document()
    job = document["jobs"]["promote"]

    assert job["permissions"].get("id-token") != "write"
    assert "environment" not in job, "only the publication authority runs in the release environment"

    surface = _run_surface(document)
    for verb in ("uv publish", "twine upload", "gh release create"):
        assert verb not in surface, f"the promoter must not {verb}"


def test_the_promoter_dispatches_the_single_publication_authority() -> None:
    """The dispatch target is pinned, and the decision logic is not shell arithmetic."""
    surface = _run_surface(_document())

    assert "dev.release.soak_promoter" in surface, "the decision must run in the tested module"
    assert "publish-release.yml" in Path(_WORKFLOW).read_text(encoding="utf-8")


def test_the_dispatch_target_is_the_module_the_unit_tests_cover() -> None:
    """The workflow and the tested code cannot drift apart silently.

    A workflow invoking a module path that does not exist fails only when the
    schedule next fires, which for a promoter could be long after the change
    that broke it.
    """
    invoked = _REPO_ROOT / "dev" / "release" / "soak_promoter.py"

    assert invoked.is_file()
    assert "def main(" in invoked.read_text(encoding="utf-8"), "the workflow invokes this module as a CLI"


def test_the_report_only_guard_tests_truth_not_emptiness() -> None:
    """`${VAR:+flag}` expands for the string "false", which is non-empty.

    A boolean dispatch input renders as the literal `false`, so the
    emptiness-test form passed `--report-only` on EVERY manual dispatch and a
    manual promoter run could therefore never promote anything. A scheduled
    tick leaves the input unset, so the schedule was unaffected - which is
    precisely why the defect was invisible in the path anyone would watch.
    """
    surface = _run_surface(_document())

    assert "${REPORT_ONLY:+" not in surface, "the emptiness-test form treats the string 'false' as true"
    assert '"${REPORT_ONLY}" == "true"' in surface, "the flag must be gated on the value being true"


def test_the_report_only_input_is_a_boolean_defaulting_to_false() -> None:
    """A dispatch that accepts the defaults must be able to promote.

    Pinned together with the guard above: the two only make sense as a pair,
    since a default of true would reproduce the same never-promotes outcome
    through configuration rather than through shell semantics.
    """
    report_only = _document()[True]["workflow_dispatch"]["inputs"]["report_only"]

    assert report_only["type"] == "boolean"
    assert report_only["default"] is False
