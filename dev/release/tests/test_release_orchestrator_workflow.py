"""Structural proof for the single operator-facing surface of a release.

This workflow is the one place a human still makes a release decision, so its
SHAPE carries the safety properties the removed approval click used to imply.
Two absences are asserted as hard as any presence: no input may re-add human
ceremony, and no job may reach the publication authority directly.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_WORKFLOW: Final[Path] = _REPO_ROOT / ".github" / "workflows" / "release-orchestrator.yml"


def _document() -> Any:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _run_surface(document: Any, *job_names: str) -> str:
    jobs = document["jobs"]
    selected = [jobs[name] for name in job_names] if job_names else list(jobs.values())
    return "\n".join(str(step.get("run", "")) for job in selected for step in job.get("steps", []) if "run" in step)


def test_the_dispatch_takes_exactly_two_inputs() -> None:
    """One rehearsal flag and one resume handle. Nothing else.

    The input set is pinned as an exact equality rather than a subset, because
    every additional input is a decision moved out of the code and onto a form
    where it is neither validated nor recorded.
    """
    triggers = _document()[True]

    assert set(triggers) == {"workflow_dispatch"}, "the orchestrator is dispatched, never triggered by a push"
    assert set(triggers["workflow_dispatch"]["inputs"]) == {"dry_run", "resume_packaging_run_id"}


def test_no_input_reintroduces_a_human_confirmation() -> None:
    """The dispatch IS the intent act; a phrase to type would be ceremony.

    Matched by pattern over input names rather than an allowlist, so a future
    `confirm_publish` or `type_yes_to_continue` reds without anyone remembering
    to extend a list.
    """
    inputs = _document()[True]["workflow_dispatch"]["inputs"]

    ceremony = re.compile(r"confirm|acknowledg|i_understand|type_|yes|approve|proceed", re.IGNORECASE)
    offenders = [name for name in inputs if ceremony.search(name)]
    assert not offenders, f"inputs re-adding the removed human ceremony: {offenders}"


def test_dry_run_defaults_to_the_safe_value() -> None:
    """A dispatch that accepts every default must rehearse, never release.

    The costly direction is asymmetric: defaulting to a real release makes an
    accidental Run-button press irreversible, while defaulting to a rehearsal
    costs one extra dispatch.
    """
    dry_run = _document()[True]["workflow_dispatch"]["inputs"]["dry_run"]

    assert dry_run["type"] == "boolean"
    assert dry_run["default"] is True


def test_two_dispatches_cannot_interleave_two_versions() -> None:
    """Serialised and never cancelled.

    Interleaving races two versions through one manifest: the second bump
    would compute its version from a tree the first had already advanced.
    """
    concurrency = _document()["concurrency"]

    assert concurrency["cancel-in-progress"] is False
    assert "cadrumo" in concurrency["group"], "the group must be product-scoped on a shared account"


def test_every_job_runs_on_the_self_hosted_fleet() -> None:
    """No hosted runner, ever - the standing operator mandate on cost."""
    for name, job in _document()["jobs"].items():
        runner = job["runs-on"]
        assert isinstance(runner, list) and runner[0] == "self-hosted", f"{name} escapes the self-hosted fleet"


def test_the_orchestrator_never_publishes_and_never_dispatches_the_publication() -> None:
    """It ends at the sealed candidate. The promoter alone crosses the soak.

    Dispatching publish-release.yml from here would bypass the soak entirely -
    the whole point of sealing a candidate is that no run can span the window,
    so a run that publishes has not waited.
    """
    document = _document()
    surface = _run_surface(document)

    assert "publish-release.yml" not in surface, "the orchestrator must not reach the publication authority"
    for verb in ("uv publish", "twine upload", "gh release create"):
        assert verb not in surface, f"the orchestrator must not {verb}"
    for name, job in document["jobs"].items():
        assert job.get("permissions", {}).get("id-token") != "write", f"{name} must not mint an OIDC token"
        assert "environment" not in job, f"{name} must not enter a deployment environment"


def test_the_bump_stage_runs_the_tested_bump_executor() -> None:
    """The bump is a module invocation, never shell re-implementing seven surfaces.

    Seven declaration surfaces, a lock, and a changelog block were previously
    transcribed by hand from a printed checklist. Re-expressing that in YAML
    would recreate the same error class one layer down, untested.
    """
    surface = _run_surface(_document(), "bump")

    assert "dev.release.version_bump" in surface
    # The version must never be supplied by hand: it is computed from
    # conventional-commit history inside the module.
    assert "--version" not in surface, "a hand-supplied version is the error class this stage removes"


def test_the_bump_publishes_the_version_and_commit_the_chain_keys_on() -> None:
    """Downstream stages READ the bump's outputs rather than re-deriving them.

    Re-deriving is how a campaign ends up building a different commit than the
    one the bump landed - the two would differ only when something else raced,
    which is exactly when it matters.
    """
    bump = _document()["jobs"]["bump"]

    assert set(bump["outputs"]) == {"version", "commit"}
    assert "steps.bump.outputs.version" in str(bump["outputs"]["version"])


def test_only_the_bump_job_may_write_repository_contents() -> None:
    """Ref-writing authority is confined to the one stage that lands a commit."""
    for name, job in _document()["jobs"].items():
        if name == "bump":
            assert job["permissions"]["contents"] == "write"
            continue
        assert job.get("permissions", {}).get("contents") != "write", f"{name} must not write refs"


def test_the_campaign_resolves_its_own_run_rather_than_the_newest() -> None:
    """Identity, not recency - the hazard the whole resolver exists for.

    packaging-smoke QUEUES rather than cancels on a newer dispatch, so the
    newest run of that workflow can belong to a neighbouring campaign.
    Promoting it would seal a cohort this release never built, and every
    downstream hash check would still pass because the cohort is internally
    consistent - just not ours.
    """
    surface = _run_surface(_document(), "campaign")

    assert "dev.release.run_resolution" in surface
    assert ".github/workflows/packaging-smoke.yml" in surface
    # The stage must key on a head commit, which is what makes the resolution
    # an identity question rather than an ordering one.
    assert "--head-sha" in surface

    # A bare newest-run query is exactly the shortcut this must never take.
    for shortcut in ("--limit 1", "runs?per_page=1", "| head -1", "[0].id", "--jq '.workflow_runs[0]"):
        assert shortcut not in surface, f"campaign stage takes the recency shortcut: {shortcut}"


def test_the_campaign_builds_the_commit_the_bump_landed() -> None:
    """The campaign keys on the bump's output commit, never a re-derived one.

    A re-derived commit differs from the bump's only when something else raced
    - which is precisely the moment the difference matters.
    """
    campaign = _document()["jobs"]["campaign"]

    assert "bump" in campaign["needs"]
    assert "needs.bump.outputs.commit" in str(campaign)
