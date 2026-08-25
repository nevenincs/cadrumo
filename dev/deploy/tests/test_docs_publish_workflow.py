"""Conformance gate for the documentation delivery workflow.

Documentation publication is a release CONSEQUENCE, never a release GATE, and
most of these assertions exist to keep it that way. A strict multi-root site
build placed inside the publication path would let a documentation defect strand
a half-published release: the index upload is irreversible, so a failure after it
cannot be unwound, and blocking on a rebuildable artifact would trade a
recoverable problem for an unrecoverable one.

The workflow is inert until the operator provisions the deploy role, so the
tests that matter now are structural: what it is triggered by, what identity it
runs under, that it stores no credential, and that a failure cannot reach back
into the release.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from ..._paths import REPO_ROOT
from ...deploy import docs_static_site

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "docs-publish.yml"
_PUBLICATION = REPO_ROOT / ".github" / "workflows" / "publish-release.yml"


def _document() -> dict[str, Any]:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _job() -> dict[str, Any]:
    return _document()["jobs"]["publish-docs"]


def _run_surface() -> str:
    return "\n".join(str(step.get("run", "")) for step in _job()["steps"] if "run" in step)


def test_it_runs_after_a_release_rather_than_during_one() -> None:
    """Downstream of publication, and dispatchable for a manual retry."""
    triggers = _document()[True]
    assert set(triggers) == {"release", "workflow_dispatch"}
    assert triggers["release"]["types"] == ["published"]


def test_publication_never_waits_on_documentation() -> None:
    """The load-bearing separation: a docs defect cannot strand a release.

    Asserted against the publication authority itself rather than only this
    workflow, because the failure mode is publication acquiring a dependency on
    documentation, not documentation acquiring one on publication.
    """
    publication = yaml.safe_load(_PUBLICATION.read_text(encoding="utf-8"))
    for name, job in publication["jobs"].items():
        surface = "\n".join(str(step.get("run", "")) for step in job["steps"] if "run" in step)
        assert "docs_static_site" not in surface, f"publication job {name!r} must not build or publish the docs site"
        assert "docs-publish" not in str(job.get("needs", "")), f"publication job {name!r} must not wait on docs"


def test_it_builds_the_released_commit_not_the_current_head() -> None:
    """Documentation must describe the release that triggered it."""
    checkout = next(step for step in _job()["steps"] if str(step.get("uses", "")).startswith("actions/checkout@"))
    ref = str(checkout["with"]["ref"])
    assert "release.target_commitish" in ref
    assert checkout["with"]["persist-credentials"] is False


def test_it_federates_an_identity_and_stores_no_credential() -> None:
    """No secret at rest, which is what makes a shared runner host tolerable."""
    job = _job()
    assert job["permissions"]["id-token"] == "write"
    assert job["environment"] == "docs", "the protected environment is the product boundary on a shared fleet"
    surface = _run_surface()
    for forbidden in ("AWS_SECRET_ACCESS_KEY", "AWS_ACCESS_KEY_ID", "aws_secret", "secrets."):
        assert forbidden not in surface, f"the docs workflow must not reference {forbidden!r}"


def test_it_refuses_instructively_before_it_is_provisioned() -> None:
    """Inert until the role exists, and it says so rather than failing obscurely.

    The refusal is the first step, so an unprovisioned run stops before checking
    anything out rather than partway through a build.
    """
    steps = _job()["steps"]
    first = steps[0]
    assert "role" in str(first["name"]).lower()
    body = str(first["run"])
    assert "REFUSED" in body
    assert "OP-3" in body, "the refusal must name the operator decision that unblocks it"
    assert "least-privilege" in body


def test_the_publish_step_exports_the_role_under_the_publisher_own_name() -> None:
    """The workflow half of the authority transfer, pinned to the code half.

    The publisher no longer refuses automation outright; it requires this
    identifier instead. Exported under any other name the publisher would refuse
    a fully provisioned run, and the failure would look like missing
    provisioning rather than a naming drift, so the two halves are pinned
    together here.
    """
    variable = docs_static_site._DEPLOY_ROLE_VARIABLE
    publish = next(step for step in _job()["steps"] if "docs_static_site" in str(step.get("run", "")))
    assert variable in publish.get("env", {}), f"the publish step must export {variable!r}"
    assert publish["env"][variable] == f"${{{{ vars.{variable} }}}}"


def test_a_documentation_failure_cannot_unwind_the_release() -> None:
    """It alerts and stops. Anything more would be the coupling this avoids."""
    steps = _job()["steps"]
    # Matched by containment rather than exact equality: the guard now also
    # admits a cancelled run, because a cancellation (runner eviction, a
    # concurrency interaction) leaves the same silence a failure would and
    # `failure()` alone does not fire for it. An exact-equality match pinned the
    # guard's spelling rather than its meaning.
    alert = next(step for step in steps if "failure()" in str(step.get("if", "")))
    body = str(alert["run"])
    assert "::error::" in body
    assert "remains published" in body
    surface = _run_surface()
    for forbidden in ("gh release delete", "git push", "uv publish", "--delete"):
        assert forbidden not in surface, f"the docs workflow must never run {forbidden!r}"


def test_it_runs_on_the_self_hosted_fleet() -> None:
    """Operator ruling: no hosted runners, in any lane."""
    assert _job()["runs-on"] == ["self-hosted", "Linux", "X64"]
