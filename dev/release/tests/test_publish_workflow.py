"""Proof that the publication path asks the identity authority before uploading.

The authority documented itself as running at two places while running at one:
the cohort seal asked it, and the workflow that performs the irreversible index
upload did not ask it at all. Nothing failed, because a guard that is never
invoked cannot fail - which is exactly why it needs a gate of its own rather
than the module's own prose.

The assertions are about placement, not vocabulary. The upload cannot be undone,
so the question has to be asked in the same job, before that step, with the
arguments that let it answer. Each of those is a way the guard could be present
and still useless, so each has a case, and the last case removes the guard from
a copy of the document to prove the gate would notice.
"""

from __future__ import annotations

from typing import Any, Final

import pytest
import yaml

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WORKFLOW: Final = REPO_ROOT / ".github" / "workflows" / "publish.yml"
_AUTHORITY: Final = "dev.release.version_identity"
_UPLOAD: Final = "uv publish"


def _document() -> dict[str, Any]:
    """Return the parsed publication workflow."""
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _upload_job(document: dict[str, Any]) -> dict[str, Any]:
    """Return the one job whose run surface performs the index upload."""
    jobs = document["jobs"]
    uploading = [job for job in jobs.values() if _UPLOAD in _run_surface(job)]
    assert len(uploading) == 1, f"expected exactly one uploading job, found {len(uploading)}"
    return uploading[0]


def _run_surface(job: dict[str, Any]) -> str:
    """Return every run script in the job, joined."""
    return "\n".join(str(step.get("run", "")) for step in job["steps"] if "run" in step)


def _executed(job: dict[str, Any]) -> str:
    """Return the job's run scripts with comment lines removed.

    A gate that matches the whole run surface is satisfied by the explanatory
    comment above the invocation, so a workflow with the guard commented out
    would still pass. Only executed lines count.
    """
    return "\n".join(
        line
        for step in job["steps"]
        if "run" in step
        for line in str(step["run"]).splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def _step_index(job: dict[str, Any], needle: str) -> int:
    """Return the index of the first step whose run script contains ``needle``."""
    for index, step in enumerate(job["steps"]):
        if needle in str(step.get("run", "")):
            return index
    raise AssertionError(f"no step in the uploading job runs {needle!r}")


def test_the_identity_authority_runs_in_the_uploading_job() -> None:
    """The guard has to share a job with the upload it guards.

    An earlier job can be skipped, re-run, or satisfied by a stale artifact
    while the upload proceeds. Sharing the job is what makes the guard's answer
    describe the bytes actually about to be sent.
    """
    job = _upload_job(_document())
    assert _AUTHORITY in _executed(job), "the upload runs unguarded by the identity authority"


def test_the_identity_authority_runs_before_the_upload() -> None:
    """Ordering is the whole guarantee: after the upload there is nothing to refuse."""
    job = _upload_job(_document())
    assert _step_index(job, _AUTHORITY) < _step_index(job, _UPLOAD)


def test_the_upload_asks_the_publication_scope() -> None:
    """The seal scope refuses only a burned version, which is not enough here.

    Publication is the act every collision rule names as its reason, so it is
    the one place those rules are asked.
    """
    executed = _executed(_upload_job(_document()))
    assert "--scope publish" in executed
    assert "--scope seal" not in executed, "the seal scope asks no destination anything"


def test_the_upload_supplies_what_the_forge_check_needs() -> None:
    """Without both, the gate refuses this release for colliding with itself.

    The tag and the release for this version already exist by the time the
    upload runs - the release cut them and dispatched this run - so the guard is
    told which commit they sit on and exempts them by identity. It refuses
    without that argument rather than guessing, so a workflow that omits it
    blocks every release.
    """
    executed = _executed(_upload_job(_document()))
    assert "--repository" in executed
    assert "--own-source-commit" in executed
    assert "git rev-parse HEAD" in executed, "the exempted commit must be the one this job checked out"


def test_the_guard_reaches_the_forge_with_a_credential() -> None:
    """A forge check without a token refuses, which would block every release."""
    job = _upload_job(_document())
    guard = next(step for step in job["steps"] if _AUTHORITY in str(step.get("run", "")))
    assert "GH_TOKEN" in guard.get("env", {})


def test_the_job_checks_out_the_tag_it_publishes() -> None:
    """`git rev-parse HEAD` only names the release's commit if the tag is checked out."""
    job = _upload_job(_document())
    checkout = next(step for step in job["steps"] if str(step.get("uses", "")).startswith("actions/checkout@"))
    assert checkout["with"]["ref"] == "${{ inputs.tag }}"


def test_the_gate_notices_a_publication_path_that_lost_its_guard() -> None:
    """Detector teeth: this exact regression is what the gate exists to catch.

    The guard was lost once already, when the workflow that carried it was
    consolidated into this one, and nothing went red because a guard that is
    never invoked never fails.
    """
    document = _document()
    job = _upload_job(document)
    job["steps"] = [step for step in job["steps"] if _AUTHORITY not in str(step.get("run", ""))]
    assert _AUTHORITY not in _executed(job)
    with pytest.raises(AssertionError, match="no step in the uploading job runs"):
        _step_index(job, _AUTHORITY)
