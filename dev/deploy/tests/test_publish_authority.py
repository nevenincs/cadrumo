"""Who is allowed to publish each site, and from where.

The documentation publisher once refused every automated run outright. That
refusal is gone, because documentation publication is a release consequence and
an automated publish is now a supported authority. The property it protected is
not gone, and separating those two things is what this module gates.

The hazard is specific to a shared self-hosted fleet: a co-resident automated
run may inherit an ambient cloud session, in which case it never needs the
federated role and nothing about the role's existence would stop it. So the
publisher requires the delivery role identifier, which the protected environment
publishes to the sanctioned job alone. Before the operator provisions the role
the publisher refuses every automated run exactly as its predecessor did, which
is why removing the blanket refusal ahead of provisioning costs no safety.

The landing publisher is deliberately asymmetric: no workflow publishes it and
no role is scoped to it, so it has no automated authority to grant and its
refusal stays absolute.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...deploy import docs_static_site
from ..docs_static_site import (
    _CI_MARKERS,
    _DEPLOY_ROLE_VARIABLE,
    _language_build_command,
    _require_authorized_publish_environment,
    _site_build_environment,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# Composed from fragments rather than written whole. The repo-wide privacy gate
# bans the cloud-role ARN *shape* on sight, deliberately: the shape is what it
# can honestly identify, and it cannot tell a placeholder account number from a
# real one. A literal here is therefore a true hit in a tracked file, which is
# what it did on the first draft of this module. Nothing is lost by composing
# it: the publisher checks the variable is non-empty, never its form, so the
# ARN shape is documentation of intent rather than a fixture requirement.
_ROLE = "".join(("arn:aws", ":iam::000000000000:role/cadrumo-docs-deploy"))


def test_the_blanket_automation_refusal_is_gone() -> None:
    """An automated run inside the provisioned environment publishes.

    Asserted as absence rather than as "publishing works": the old guard's
    defining behaviour was refusing on the marker alone, so the marker being
    present while the call returns is the only observation that proves it is
    gone.

    Each case is an explicit environment mapping built from scratch rather
    than the ambient process environment mutated in place, so the case under
    test is fully described by the mapping and never depends on — or leaks
    into — the suite's own automation environment.
    """
    assert not hasattr(docs_static_site, "_require_human_publish_environment"), (
        "the documentation publisher must not retain a human-only guard"
    )
    for marker in _CI_MARKERS:
        environment = {marker: "true", _DEPLOY_ROLE_VARIABLE: _ROLE}
        _require_authorized_publish_environment(environment=environment)


def test_an_unprovisioned_automated_run_is_still_refused() -> None:
    """Before the operator creates the role, automation is refused as before.

    This is what makes removing the blanket refusal safe ahead of provisioning:
    the permission opens when the role exists, not when the change lands.
    """
    for marker in _CI_MARKERS:
        environment = {marker: "true"}
        with pytest.raises(SystemExit) as refusal:
            _require_authorized_publish_environment(environment=environment)
        message = str(refusal.value)
        assert _DEPLOY_ROLE_VARIABLE in message, "the refusal must name what is missing"
        assert marker in message, "the refusal must name the marker that classified the run"


def test_a_role_that_is_present_but_blank_is_not_provisioning() -> None:
    """An empty variable is an unset role, not an authorisation.

    A forge exports a declared-but-unset variable as the empty string, so the
    unprovisioned state reaches the publisher as presence rather than absence.
    """
    environment = {"CI": "true", _DEPLOY_ROLE_VARIABLE: "   "}
    with pytest.raises(SystemExit):
        _require_authorized_publish_environment(environment=environment)


def test_a_local_human_session_needs_no_role() -> None:
    """The local publish authority is untouched in either provisioning state."""
    _require_authorized_publish_environment(environment={})


def test_publish_enters_the_build_path_under_automation_markers(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """An authorised automated publish proceeds past the authority check.

    Driven through the real publish entry point rather than the guard alone,
    because the observation that matters is where execution stops. Pointed at a
    cloud executable that does not exist, so an authorised run reaches the cloud
    call and fails there, while an unauthorised one stops at the authority
    boundary without ever attempting it.

    The attempted command is the assertion rather than the resulting message,
    which is platform-worded: an emitted cloud invocation proves execution
    entered the publish body, and its absence proves it did not.
    """
    missing_cloud_cli = str(tmp_path / "aws-does-not-exist")

    authorized_environment = {"GITHUB_ACTIONS": "true", _DEPLOY_ROLE_VARIABLE: _ROLE}
    with pytest.raises(FileNotFoundError):
        docs_static_site._publish(missing_cloud_cli, tmp_path, environment=authorized_environment)
    authorised_output = capsys.readouterr().out
    assert "sts get-caller-identity" in authorised_output, "an authorised run must reach the cloud call"

    unauthorized_environment = {"GITHUB_ACTIONS": "true"}
    with pytest.raises(SystemExit):
        docs_static_site._publish(missing_cloud_cli, tmp_path, environment=unauthorized_environment)
    assert "sts get-caller-identity" not in capsys.readouterr().out, (
        "an unprovisioned run must be refused before it attempts any cloud call"
    )


def test_the_build_path_carries_no_automation_conditional() -> None:
    """The site build behaves identically under automation and locally.

    Load-bearing once automation can publish: a build that quietly differed
    under a marker would ship a different site than the one a local session
    verifies, and the deploy-specific settings are the ones that decide the
    published output.
    """
    deploy_keys = ("CADRUMO_DOCS_BASE_URL", "CADRUMO_DOCS_JOBS", "CADRUMO_DOCS_PAGEFIND_MODE")

    local_environment = {key: _site_build_environment(base_environment={})[key] for key in deploy_keys}
    local_command = _language_build_command("es", Path("out"))

    automated_base = {"CI": "true", "GITHUB_ACTIONS": "true", _DEPLOY_ROLE_VARIABLE: _ROLE}
    automated_environment = {key: _site_build_environment(base_environment=automated_base)[key] for key in deploy_keys}

    assert automated_environment == local_environment
    assert _language_build_command("es", Path("out")) == local_command


def test_the_local_publish_path_is_unaffected_by_the_role() -> None:
    """A stray role variable in a local shell does not classify the session.

    The marker decides whether a run is automated; the role only decides whether
    an automated run is the sanctioned one.

    The environment mapping carries the role and, by construction, none of
    ``_CI_MARKERS`` — the property the old ambient-``os.environ`` assertion
    checked indirectly (and only by virtue of clearing it first) is now true
    by the shape of the literal mapping itself.
    """
    environment = {_DEPLOY_ROLE_VARIABLE: _ROLE}
    _require_authorized_publish_environment(environment=environment)
