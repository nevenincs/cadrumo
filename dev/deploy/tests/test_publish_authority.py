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

import os
from pathlib import Path

import pytest
from dev.deploy import docs_static_site, frontend_static_site
from dev.deploy.docs_static_site import (
    _CI_MARKERS,
    _DEPLOY_ROLE_VARIABLE,
    _language_build_command,
    _require_authorized_publish_environment,
    _site_build_environment,
)
from dev.deploy.frontend_static_site import _require_human_publish_environment

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROLE = "arn:aws:iam::000000000000:role/cadrumo-docs-deploy"


def _clear_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start from a known-empty authority environment.

    These tests run under automation themselves, so every marker and the role
    variable are cleared first; otherwise the suite's own environment would
    decide the outcome instead of the case under test.
    """
    for marker in _CI_MARKERS:
        monkeypatch.delenv(marker, raising=False)
    monkeypatch.delenv(_DEPLOY_ROLE_VARIABLE, raising=False)


def test_the_blanket_automation_refusal_is_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    """An automated run inside the provisioned environment publishes.

    Asserted as absence rather than as "publishing works": the old guard's
    defining behaviour was refusing on the marker alone, so the marker being
    present while the call returns is the only observation that proves it is
    gone.
    """
    assert not hasattr(docs_static_site, "_require_human_publish_environment"), (
        "the documentation publisher must not retain a human-only guard"
    )
    for marker in _CI_MARKERS:
        _clear_authority(monkeypatch)
        monkeypatch.setenv(marker, "true")
        monkeypatch.setenv(_DEPLOY_ROLE_VARIABLE, _ROLE)
        _require_authorized_publish_environment()


def test_an_unprovisioned_automated_run_is_still_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Before the operator creates the role, automation is refused as before.

    This is what makes removing the blanket refusal safe ahead of provisioning:
    the permission opens when the role exists, not when the change lands.
    """
    for marker in _CI_MARKERS:
        _clear_authority(monkeypatch)
        monkeypatch.setenv(marker, "true")
        with pytest.raises(SystemExit) as refusal:
            _require_authorized_publish_environment()
        message = str(refusal.value)
        assert _DEPLOY_ROLE_VARIABLE in message, "the refusal must name what is missing"
        assert marker in message, "the refusal must name the marker that classified the run"


def test_a_role_that_is_present_but_blank_is_not_provisioning(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty variable is an unset role, not an authorisation.

    A forge exports a declared-but-unset variable as the empty string, so the
    unprovisioned state reaches the publisher as presence rather than absence.
    """
    _clear_authority(monkeypatch)
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv(_DEPLOY_ROLE_VARIABLE, "   ")
    with pytest.raises(SystemExit):
        _require_authorized_publish_environment()


def test_a_local_human_session_needs_no_role(monkeypatch: pytest.MonkeyPatch) -> None:
    """The local publish authority is untouched in either provisioning state."""
    _clear_authority(monkeypatch)
    _require_authorized_publish_environment()


def test_publish_enters_the_build_path_under_automation_markers(
    monkeypatch: pytest.MonkeyPatch,
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

    _clear_authority(monkeypatch)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv(_DEPLOY_ROLE_VARIABLE, _ROLE)
    with pytest.raises(FileNotFoundError):
        docs_static_site._publish(missing_cloud_cli, tmp_path)
    authorised_output = capsys.readouterr().out
    assert "sts get-caller-identity" in authorised_output, "an authorised run must reach the cloud call"

    _clear_authority(monkeypatch)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(SystemExit):
        docs_static_site._publish(missing_cloud_cli, tmp_path)
    assert "sts get-caller-identity" not in capsys.readouterr().out, (
        "an unprovisioned run must be refused before it attempts any cloud call"
    )


def test_the_build_path_carries_no_automation_conditional(monkeypatch: pytest.MonkeyPatch) -> None:
    """The site build behaves identically under automation and locally.

    Load-bearing once automation can publish: a build that quietly differed
    under a marker would ship a different site than the one a local session
    verifies, and the deploy-specific settings are the ones that decide the
    published output.
    """
    deploy_keys = ("CADRUMO_DOCS_BASE_URL", "CADRUMO_DOCS_JOBS", "CADRUMO_DOCS_PAGEFIND_MODE")

    _clear_authority(monkeypatch)
    local_environment = {key: _site_build_environment()[key] for key in deploy_keys}
    local_command = _language_build_command("es", Path("out"))

    _clear_authority(monkeypatch)
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv(_DEPLOY_ROLE_VARIABLE, _ROLE)
    automated_environment = {key: _site_build_environment()[key] for key in deploy_keys}

    assert automated_environment == local_environment
    assert _language_build_command("es", Path("out")) == local_command


def test_the_landing_publisher_refuses_every_automated_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """The landing page has no automated authority, so the role buys nothing.

    Refused even holding the documentation role, because that role is scoped to
    the documentation bucket prefix and no workflow publishes this site at all.
    """
    for marker in _CI_MARKERS:
        _clear_authority(monkeypatch)
        monkeypatch.setenv(marker, "true")
        monkeypatch.setenv(_DEPLOY_ROLE_VARIABLE, _ROLE)
        with pytest.raises(SystemExit) as refusal:
            _require_human_publish_environment()
        assert marker in str(refusal.value)


def test_the_landing_guard_is_its_own_and_not_the_documentation_one() -> None:
    """Two authorities, two guards.

    Sharing one function is how the documentation site's new automated
    authority would silently extend to a surface that was never granted any.
    """
    assert frontend_static_site._require_human_publish_environment.__module__ == frontend_static_site.__name__
    assert not hasattr(docs_static_site, "_require_human_publish_environment")


def test_the_local_publish_path_is_unaffected_by_the_role(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stray role variable in a local shell does not classify the session.

    The marker decides whether a run is automated; the role only decides whether
    an automated run is the sanctioned one. Both publishers agree.
    """
    _clear_authority(monkeypatch)
    monkeypatch.setenv(_DEPLOY_ROLE_VARIABLE, _ROLE)
    assert not any(marker in os.environ for marker in _CI_MARKERS)
    _require_authorized_publish_environment()
    _require_human_publish_environment()
