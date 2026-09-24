"""Who is allowed to publish the documentation site, and from where.

Documentation publication is a release consequence, so an automated publish is a
supported authority. The hazard is specific to a shared self-hosted fleet: a
co-resident automated run must not publish by accident. The delivery
credentials live only in the protected ``docs`` environment, so an automated
run must carry every one of them to proceed; any gap refuses it before a single
network call. A local human session carries no automation marker and is
unaffected, and the zone wiring verb refuses automation outright.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...deploy import docs_static_site
from ..docs_static_site import (
    _CI_MARKERS,
    DELIVERY_CREDENTIAL_ENV,
    _require_authorized_publish_environment,
    language_build_command,
    site_build_environment,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Placeholder values only: the guard reads presence, never the value.
_CREDENTIALS = {name: f"placeholder-{index}" for index, name in enumerate(DELIVERY_CREDENTIAL_ENV)}


def test_an_automated_run_inside_the_delivery_environment_is_authorised() -> None:
    """An automated run carrying every delivery credential proceeds."""
    assert not hasattr(docs_static_site, "_require_human_publish_environment"), (
        "the documentation publisher must not retain a human-only guard"
    )
    for marker in _CI_MARKERS:
        _require_authorized_publish_environment(environment={marker: "true", **_CREDENTIALS})


@pytest.mark.parametrize("absent", DELIVERY_CREDENTIAL_ENV)
def test_an_automated_run_missing_any_credential_is_refused(absent: str) -> None:
    """Each credential is required on its own; the refusal names what is missing."""
    for marker in _CI_MARKERS:
        environment = {marker: "true", **{k: v for k, v in _CREDENTIALS.items() if k != absent}}
        with pytest.raises(SystemExit) as refusal:
            _require_authorized_publish_environment(environment=environment)
        message = str(refusal.value)
        assert absent in message, "the refusal must name the missing credential"
        assert marker in message, "the refusal must name the marker that classified the run"


def test_a_credential_that_is_present_but_blank_is_not_provisioning() -> None:
    """A forge exports a declared-but-unset secret as the empty string."""
    environment = {"CI": "true", **_CREDENTIALS, "CLOUDFLARE_API_TOKEN": "   "}
    with pytest.raises(SystemExit):
        _require_authorized_publish_environment(environment=environment)


def test_a_local_human_session_needs_no_credentials_to_pass_the_guard() -> None:
    """The authority guard classifies automation only; a local session passes it."""
    _require_authorized_publish_environment(environment={})


def test_an_unprovisioned_automated_publish_stops_before_any_cloud_call(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Driven through the real publish entry point: the refusal precedes every command and request."""
    with pytest.raises(SystemExit) as refusal:
        docs_static_site._publish(tmp_path, environment={"GITHUB_ACTIONS": "true"})
    assert "CLOUDFLARE_API_TOKEN" in str(refusal.value)
    assert capsys.readouterr().out == "", "an unprovisioned run must not start a build, upload or deploy"


def test_zone_wiring_refuses_every_automated_run() -> None:
    """Provisioning changes the shared zone and is a local, human decision."""
    for marker in _CI_MARKERS:
        with pytest.raises(SystemExit) as refusal:
            docs_static_site._provision(environment={marker: "true", **_CREDENTIALS})
        assert marker in str(refusal.value)


def test_the_build_path_carries_no_automation_conditional() -> None:
    """The site build behaves identically under automation and locally.

    A build that quietly differed under a marker would ship a different site
    than the one a local session verifies.
    """
    deploy_keys = ("CADRUMO_DOCS_BASE_URL", "CADRUMO_DOCS_JOBS", "CADRUMO_DOCS_PAGEFIND_MODE")

    local_environment = {key: site_build_environment(base_environment={})[key] for key in deploy_keys}
    local_command = language_build_command("es", Path("out"))

    automated_base = {"CI": "true", "GITHUB_ACTIONS": "true", **_CREDENTIALS}
    automated_environment = {key: site_build_environment(base_environment=automated_base)[key] for key in deploy_keys}

    assert automated_environment == local_environment
    assert language_build_command("es", Path("out")) == local_command


def test_a_cutover_publish_refuses_every_automated_run(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """The cutover changes the shared zone; CI publishes without it and is refused with it."""
    for marker in _CI_MARKERS:
        with pytest.raises(SystemExit) as refusal:
            docs_static_site._publish(tmp_path, cutover=True, environment={marker: "true", **_CREDENTIALS})
        assert marker in str(refusal.value)
    assert capsys.readouterr().out == "", "a refused cutover must not start a build, upload or deploy"
