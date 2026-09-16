"""The profile readiness surfaces must agree with each other and with the record.

``status``, ``view`` and ``app overview status`` all report on the same record.
Each case below reproduces a defect where one of them failed outright, or told
the operator something the others contradicted.
"""

from __future__ import annotations

import json

import pytest

from ...tests.cli_runner import invoke_cached_cli
from ..profile_command_specs import PROFILE_COMMAND_SPECS
from .isolated_storage_fixture import (
    COMPLETE_NATURAL_PERSON_FLAGS,
    profile_cli,
    profile_view_document,
)
from .isolated_storage_fixture import live_cli_profile as live_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("live_cli_profile")]


def _complete_the_profile() -> None:
    edited = profile_cli("edit", "--quiet", *COMPLETE_NATURAL_PERSON_FLAGS)
    assert edited.exit_code == 0, edited.output
    promoted = profile_cli("complete-setup")
    assert promoted.exit_code == 0, promoted.output


def test_status_and_overview_answer_for_a_completed_profile() -> None:
    """Completing setup must not break the surfaces that report readiness.

    Reproduction: once ``complete-setup`` succeeded, ``config profile status``
    raised an internal error (it projected answers against a process-global
    wizard catalogue nothing registers) and ``app overview status`` refused
    (it projected the taxpayer without the pinned profile schema). Both were
    fine while the profile was incomplete, so completing setup was what broke
    them. ``status`` then failed a third way: its Modelo baseline check
    resolved the IRPF income-category vocabulary with no authority operation
    open, and succeeded only when an earlier call had cached the answer.
    """
    _complete_the_profile()

    status = profile_cli("status")
    assert status.exit_code == 0, status.output
    assert json.loads(status.stdout)["result"]["configured"] is True

    overview = invoke_cached_cli(("--format", "json", "app", "overview", "status"))
    assert overview.exit_code == 0, overview.output


def test_viewing_an_incomplete_profile_succeeds_and_still_lists_what_is_missing() -> None:
    """An unfinished record is a valid record; its gaps are information.

    Reproduction: ``config profile view`` on a freshly created profile exited 2
    while its own envelope said ``warning``, because unset required fields were
    counted as blocking errors. The write door already defers those while the
    record is incomplete, so the viewer must agree -- without hiding them.
    """
    shown = profile_cli("view")

    assert shown.exit_code == 0, shown.output
    result = json.loads(shown.stdout)["result"]
    assert result["setup_state"] == "incomplete"
    assert result["valid"] is True
    assert any(issue["code"] == "required_field_missing" for issue in result["issues"])


def test_status_and_view_count_the_same_missing_required_fields() -> None:
    """One record, one answer to "what is still required".

    Reproduction: on a fresh profile ``view`` listed three missing required
    fields while ``status`` evidence counted two. ``status`` derived the set
    from the wizard's key catalogue, which omits gated questions, instead of
    from the completeness module ``view`` uses.
    """
    view_result = profile_view_document()["result"]
    assert isinstance(view_result, dict)
    missing_in_view = [issue for issue in view_result["issues"] if issue["code"] == "required_field_missing"]

    status = profile_cli("status")
    evidence = json.loads(status.stdout)["result"]["precondition_action"]["evidence"]
    counts = [item["values"]["required_fields_missing_count"] for item in evidence]

    assert missing_in_view
    assert counts == [len(missing_in_view)]


def test_view_publishes_the_identity_its_spec_declares() -> None:
    """The envelope's command field is how automation routes a result.

    Reproduction: ``config profile view`` published ``config.profile.show``,
    the retired name of the verb, so an automation keyed on the declared
    identity never matched the document it received.
    """
    declared = next(spec.result_schema.identity for spec in PROFILE_COMMAND_SPECS if spec.key == "config_profile_view")

    assert profile_view_document()["command"] == declared
