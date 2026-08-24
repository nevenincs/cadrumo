"""End-to-end CLI verification for the modelo-work UX cluster.

Drives the real ``cadrumo`` CLI against an isolated encrypted backend to
pin the modelo-work findings reported by the persona fleet:

* ``work history`` records the work-unit creation event, so the audit
  trail is complete from the moment the unit is provisioned.
* the first ``work calculate`` binding failure guides the operator
  toward ``--binding KEY=VALUE`` and ``bindings list --missing``
  instead of leaving them with a bare refusal.
* ``overview status`` next-step guidance reflects real workspace
  state: once ledger transactions exist it no longer tells the
  operator to import a bank statement.
* ``work revisions`` accepts the work-unit id positionally, matching
  its sibling ``work status``.
* ``work calculate`` confirms the draft was persisted.
* ``work revision`` shows a stored revision's persisted casilla values
  without recomputing.
* an idempotent ``work create`` reports the reuse plainly and applies
  a supplied ``--name`` as a rename rather than silently dropping it.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.calculations.registry import select_revision
from ....tests.cli_envelope import unwrap_envelope_notices as _notices
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.registry_tree import bundled_registry_tree
from ....tests.user_profile import register_cli_profile
from ._modelo_work_ux_support import (
    _create_calculable_work_unit,
    _create_gb_non_resident_profile,
    _create_m130_work_unit,
    _create_profile,
    _invoke,
)
from ._modelo_work_ux_support import _isolated_cli_backend as _isolated_cli_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_work_history_records_creation_event(_isolated_cli_backend: Path) -> None:
    """M17: a freshly-created work unit's history starts with a
    ``modelo.work_unit.created`` event - not an empty stream."""

    _create_profile()
    work_unit_id = _create_m130_work_unit()

    history = _invoke(["--format", "json", "app", "modelo", "work", "history", work_unit_id])
    assert history.exit_code == 0, history.output
    payload = _payload(history.output)

    assert payload["event_count"] == 1
    event = payload["events"][0]
    assert event["event_type"] == "modelo.work_unit.created"
    assert event["object_type"] == "work_unit"
    assert event["object_id"] == work_unit_id
    # The creation event names who provisioned the unit.
    assert event["actor"]
    assert event["payload"]["modelo"] == "130"
    assert event["payload"]["revision_id"] == "2019-y-siguientes"
    notice = next(item for item in _notices(history.output) if item["code"] == "modelo.work.history.next_action")
    assert "aeat " not in notice["message"].lower()
    assert notice["action"]["action"]["action_id"] == "operator.modelo.work.status"


def test_first_work_calculate_binding_error_guides_the_operator(_isolated_cli_backend: Path) -> None:
    """M18: the first ``work calculate`` that hits an unsatisfied binding
    fails with guidance toward ``--binding KEY=VALUE`` and the
    bindings-list discovery command - not a bare refusal."""

    _create_profile()
    work_unit_id = _create_m130_work_unit()

    result = _invoke(["app", "modelo", "work", "calculate", work_unit_id])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    # A missing binding id is named in the error. The exact identifier
    # depends on which bound casilla the formula evaluator hits first;
    # modelo-130 surfaces either the previous-year-negative-results
    # casilla binding or the upstream profile-fact binding it depends on.
    assert (
        "modelo-130-resultados-negativos-anteriores" in result.output
        or "previous_year_economic_activity_net_income" in result.output
    )
    # The bare missing-binding line is followed by actionable guidance.
    assert "--binding" in result.output
    assert "bindings list" in result.output and "--missing" in result.output


def test_work_revisions_accepts_a_positional_work_unit_id(_isolated_cli_backend: Path) -> None:
    """`work revisions <id>` must accept the work-unit id positionally,
    matching its sibling `work status <id>` - the inconsistency where
    `revisions` demanded `--work-unit-id` is gone."""

    _create_profile()
    work_unit_id = _create_m130_work_unit()

    result = _invoke(["--format", "json", "app", "modelo", "work", "revisions", work_unit_id])
    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert payload["work_unit_id_filter"] == work_unit_id


def test_work_status_resolves_a_visible_filing_target(_isolated_cli_backend: Path) -> None:
    """`work status` accepts the operator-facing modelo/year/period target."""

    _create_profile()
    work_unit_id = _create_m130_work_unit()

    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "status",
            "--modelo", "130", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert payload["work_unit_id"] == work_unit_id
    assert payload["short_work_unit_id"] == work_unit_id[-12:]
    assert "current_calculation_revision_id" in payload
    assert "filed_calculation_revision_id" in payload
    notice = next(item for item in _notices(result.output) if item["code"] == "modelo.work.status.next_action")
    assert "aeat " not in notice["message"].lower()
    assert notice["action"]["action"]["action_id"] == "operator.modelo.work.calculate"


def test_displayed_short_work_unit_id_drives_status_and_calculate(_isolated_cli_backend: Path) -> None:
    """The short id surfaced by `work list` is a usable operator handle."""
    _create_profile()
    work_unit_id = _create_calculable_work_unit()
    short_work_unit_id = work_unit_id[-12:]

    status = _invoke(["--format", "json", "app", "modelo", "work", "status", short_work_unit_id])
    assert status.exit_code == 0, status.output
    assert _payload(status.output)["work_unit_id"] == work_unit_id

    calculated = _invoke(["--format", "json", "app", "modelo", "work", "calculate", short_work_unit_id])
    assert calculated.exit_code == 0, calculated.output
    assert _payload(calculated.output)["work_unit_id"] == work_unit_id


def test_work_list_surfaces_revision_pointer_fields(_isolated_cli_backend: Path) -> None:
    """`work list` exposes current/filed calculation pointers for discovery."""

    _create_profile()
    work_unit_id = _create_calculable_work_unit()
    calculated = _invoke(
        ["--format", "json", "app", "modelo", "work", "calculate", work_unit_id],
    )
    assert calculated.exit_code == 0, calculated.output
    revision_id = _payload(calculated.output)["calculation_revision_id"]

    result = _invoke(["--format", "json", "app", "modelo", "work", "list"])
    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    matching = [unit for unit in payload["work_units"] if unit["work_unit_id"] == work_unit_id]
    assert len(matching) == 1
    unit = matching[0]
    assert unit["current_calculation_revision_id"] == revision_id
    assert unit["short_current_calculation_revision_id"] == revision_id[-12:]
    assert unit["filed_calculation_revision_id"] is None


def test_work_list_without_a_selected_unit_does_not_claim_an_executable_action(
    _isolated_cli_backend: Path,
) -> None:
    """The list cannot bind one target until the operator selects a work unit."""
    _create_profile()

    result = _invoke(["--format", "json", "app", "modelo", "work", "list"])

    assert result.exit_code == 0, result.output
    notice = next(item for item in _notices(result.output) if item["code"] == "modelo.work.list.selection_required")
    assert "aeat " not in notice["message"].lower()
    assert notice["action"] is None
    assert notice["context"] == {
        "continuation_outcome": "operator_decision",
        "work_unit_count": "0",
    }


def test_work_list_and_status_text_name_profile_once_without_bucket_placeholders(
    _isolated_cli_backend: Path,
) -> None:
    """Profile-scoped text uses the operator label, never a storage identity."""
    _create_profile()
    work_unit_id = _create_m130_work_unit()

    listed = _invoke(["app", "modelo", "work", "list"])
    assert listed.exit_code == 0, listed.output
    status = _invoke(["app", "modelo", "work", "status", work_unit_id[-12:]])
    assert status.exit_code == 0, status.output

    for result in (listed, status):
        assert result.output.count("active_profile\toperator") == 1
        assert "bucket_id" not in result.output
        assert "<profile-id>" not in result.output
        assert "<bucket-id>" not in result.output
    short_work_unit_id = work_unit_id[-12:]
    assert f"next_action\taeat app modelo work status {work_unit_id}" in listed.output
    assert f"next_action\taeat app modelo work calculate {work_unit_id}" in status.output

    list_json = _invoke(["--format", "json", "app", "modelo", "work", "list"])
    assert list_json.exit_code == 0, list_json.output
    list_action = next(
        item["action"] for item in _notices(list_json.output) if item["code"] == "modelo.work.list.next_action"
    )
    assert list_action == {
        "action": {
            "action_id": "operator.modelo.work.status",
            "target_command_key": "modelo.work.status",
            "cli_path": ["app", "modelo", "work", "status"],
        },
        "argument_bindings": [
            {
                "argument_name": "work_unit_id",
                "status": "resolved",
                "value": work_unit_id,
                "source": "operator_action.verdict_context",
                "source_key": "work_unit_id",
                "source_evidence_id": None,
            },
        ],
    }

    status_json = _invoke(["--format", "json", "app", "modelo", "work", "status", short_work_unit_id])
    assert status_json.exit_code == 0, status_json.output
    action = next(
        item["action"] for item in _notices(status_json.output) if item["code"] == "modelo.work.status.next_action"
    )
    assert action == {
        "action": {
            "action_id": "operator.modelo.work.calculate",
            "target_command_key": "modelo.work.calculate",
            "cli_path": ["app", "modelo", "work", "calculate"],
        },
        "argument_bindings": [
            {
                "argument_name": "work_unit_id",
                "status": "resolved",
                "value": work_unit_id,
                "source": "operator_action.verdict_context",
                "source_key": "work_unit_id",
                "source_evidence_id": None,
            },
        ],
    }


def test_work_list_with_multiple_units_requires_an_explicit_selection(
    _isolated_cli_backend: Path,
) -> None:
    """A multi-row list never projects an action with an invented target."""
    _create_profile()
    _create_m130_work_unit()
    second = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "130",
            "--year",
            "2025",
            "--period",
            "2T",
            "--revision",
            "2019-y-siguientes",
        ],
    )
    assert second.exit_code == 0, second.output

    listed = _invoke(["app", "modelo", "work", "list"])
    assert listed.exit_code == 0, listed.output
    assert "work_unit_count\t2" in listed.output
    assert "next_action\t" not in listed.output

    listed_json = _invoke(["--format", "json", "app", "modelo", "work", "list"])
    assert listed_json.exit_code == 0, listed_json.output
    notice = next(
        item for item in _notices(listed_json.output) if item["code"] == "modelo.work.list.selection_required"
    )
    assert notice["action"] is None
    assert notice["context"] == {
        "continuation_outcome": "operator_decision",
        "work_unit_count": "2",
    }


def test_work_status_and_list_show_presentado_after_file(_isolated_cli_backend: Path) -> None:
    _create_profile(activity_start_date="2025-10-01")
    created = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "4T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    work_unit_id = _payload(created.output)["work_unit_id"]

    calculated = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "05=0.00",
            "--casilla", "06=0.00",
            "--binding", "irpf.previous_year_economic_activity_net_income=13000",
            "--binding", "modelo-130-resultados-negativos-anteriores=0",
        ],
    )  # fmt: skip
    assert calculated.exit_code == 0, calculated.output

    verified = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "verify",
            "--modelo", "130", "--year", "2025", "--period", "4T",
        ],
    )  # fmt: skip
    assert verified.exit_code == 0, verified.output
    assert _payload(verified.output)["granted_verificado_completo"] is True

    filed = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "file",
            "--modelo", "130", "--year", "2025", "--period", "4T",
        ],
    )  # fmt: skip
    assert filed.exit_code == 0, filed.output
    filed_revision_id = _payload(filed.output)["calculation_revision_id"]

    status = _invoke(["--format", "json", "app", "modelo", "work", "status", work_unit_id])
    assert status.exit_code == 0, status.output
    status_payload = _payload(status.output)
    assert status_payload["state"] == "presentado"
    assert status_payload["filed_calculation_revision_id"] == filed_revision_id

    listed = _invoke(["--format", "json", "app", "modelo", "work", "list"])
    assert listed.exit_code == 0, listed.output
    list_payload = _payload(listed.output)
    matching = [unit for unit in list_payload["work_units"] if unit["work_unit_id"] == work_unit_id]
    assert len(matching) == 1
    assert matching[0]["state"] == "presentado"
    assert matching[0]["filed_calculation_revision_id"] == filed_revision_id


def test_work_revisions_resolves_a_visible_filing_target(_isolated_cli_backend: Path) -> None:
    """`work revisions` can filter by modelo/year/period instead of raw id."""

    _create_profile()
    work_unit_id = _create_calculable_work_unit()
    calculated = _invoke(
        ["--format", "json", "app", "modelo", "work", "calculate", work_unit_id],
    )
    assert calculated.exit_code == 0, calculated.output
    revision_id = _payload(calculated.output)["calculation_revision_id"]

    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "revisions",
            "--modelo", "111", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert payload["work_unit_id_filter"] == work_unit_id
    assert [revision["calculation_revision_id"] for revision in payload["revisions"]] == [revision_id]


def test_work_calculate_resolves_a_visible_filing_target(_isolated_cli_backend: Path) -> None:
    """`work calculate` can use modelo/year/period instead of a work-unit id."""

    _create_profile()
    work_unit_id = _create_calculable_work_unit()

    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate",
            "--modelo", "111", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert payload["work_unit_id"] == work_unit_id
    assert payload["saved"] is True


def test_work_verify_defaults_to_current_draft_for_visible_target(_isolated_cli_backend: Path) -> None:
    """`work verify` defaults to the current draft under a natural target."""

    _create_profile()
    work_unit_id = _create_calculable_work_unit()
    calculated = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate",
            "--modelo", "111", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert calculated.exit_code == 0, calculated.output
    revision_id = _payload(calculated.output)["calculation_revision_id"]

    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "verify",
            "--modelo", "111", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert payload["calculation_revision_id"] == revision_id
    assert payload["granted_verificado_completo"] is True

    status = _invoke(["--format", "json", "app", "modelo", "work", "status", work_unit_id])
    assert status.exit_code == 0, status.output
    assert _payload(status.output)["current_calculation_revision_id"] == revision_id


def test_work_file_defaults_to_current_verified_for_visible_target(_isolated_cli_backend: Path) -> None:
    """`work file` selects the current verified revision before workflow gating."""

    _create_profile()
    _create_calculable_work_unit()
    calculated = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate",
            "--modelo", "111", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert calculated.exit_code == 0, calculated.output

    verified = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "verify",
            "--modelo", "111", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert verified.exit_code == 0, verified.output
    revision_id = _payload(verified.output)["calculation_revision_id"]
    status = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "status",
            "--modelo", "111", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert status.exit_code == 0, status.output
    assert _payload(status.output)["current_calculation_revision_id"] == revision_id

    result = _invoke(
        [
            "app", "modelo", "work", "file",
            "--modelo", "111", "--year", "2025", "--period", "1T",
            "--output-language", "ca",
        ],
    )  # fmt: skip
    assert result.exit_code != 0
    assert "file requires a verified-complete revision" not in result.output
    assert "No pending filing obligation" not in result.output
    assert "No hi ha cap obligació de presentació pendent" in result.output
    assert "NO_PENDING_OBLIGATION" in result.output


def test_work_file_help_exposes_explicit_result_elections(_isolated_cli_backend: Path) -> None:
    result = _invoke(["app", "modelo", "work", "file", "--help"])
    assert result.exit_code == 0, result.output
    assert "--refund-election" in result.output
    assert "--payment-election" in result.output
    assert "--disposition" not in result.output


def test_work_dependencies_lists_cross_period_inventory(_isolated_cli_backend: Path) -> None:
    """`work dependencies` exposes the registry-derived filing-history inventory."""

    _create_profile()

    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "dependencies",
            "--year", "2025", "--modelo", "390",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = _payload(result.output)

    assert payload["operation"] == "modelo.work.dependencies"
    assert payload["filing_year"] == 2025
    assert payload["modelo_filter"] == "390"
    assert payload["target_modelos"] == ["390"]
    assert "303" in payload["source_modelos"]
    assert payload["target_count"] >= 1
    annual = next(item for item in payload["items"] if item["target_period"] == {"filing_year": 2025, "code": "0A"})
    assert annual["target_modelo"] == "390"
    assert annual["dependency_count"] >= 4
    assert {dependency["source_modelo"] for dependency in annual["dependencies"]} == {"303"}


def test_work_dependencies_surfaces_current_clean_state_blockers(_isolated_cli_backend: Path) -> None:
    """A target read includes concrete blocker codes for missing upstream filings."""

    _create_profile()

    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "dependencies",
            "--year", "2025", "--modelo", "390", "--period", "0A",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    clean_state = payload["clean_state"]

    assert clean_state["target_modelo"] == "390"
    assert clean_state["target_filing_year"] == 2025
    assert clean_state["target_period"] == {"filing_year": 2025, "code": "0A"}
    assert clean_state["requires_clean_state"] is True
    assert clean_state["clean"] is False
    assert "missing_current_filing_record" in clean_state["blockers"]
    assert "missing_observation" in clean_state["blockers"]
    assert any(
        dependency["source_modelo"] == "303"
        and dependency["period"] == {"filing_year": 2025, "code": "1T"}
        and "missing_current_filing_record" in dependency["blockers"]
        for dependency in clean_state["dependencies"]
    )


def test_work_dependencies_honours_activity_start_date_pre_activity_scoping(
    _isolated_cli_backend: Path,
) -> None:
    """`work dependencies` threads the profile's activity-start-date into the
    clean-state evaluation, so a prior-period dependency that falls strictly
    before the declared activity start is scoped out (clean) - matching the
    verify path. Regression for the handler omitting ``activity_start_date``
    from ``evaluate_cross_period_clean_state``, which made the diagnostic
    report a blocker that verify itself suppresses."""

    register_cli_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.tax_id": "12345678Z",
            "identity.name": "Operator",
            "identity.surnames": "Readiness",
            "activities.description": "design",
            "censo.activity_start_date": "2025-01-01",
        },
    )

    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "dependencies",
            "--year", "2025", "--modelo", "303", "--period", "1T",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    clean_state = _payload(result.output)["clean_state"]

    # The 303/2025/1T target depends on the prior-year 303/2024/4T filing,
    # whose span ends 2024-12-31 - strictly before the 2025-01-01 activity
    # start - so it is suppressed as no-prior-obligation rather than blocking.
    assert clean_state["requires_clean_state"] is True
    assert clean_state["clean"] is True
    assert clean_state["blockers"] == []
    assert any(
        dependency["source_modelo"] == "303"
        and dependency["period"] == {"filing_year": 2024, "code": "4T"}
        and dependency["clean"] is True
        and dependency["blockers"] == []
        for dependency in clean_state["dependencies"]
    )


def test_work_calculate_confirms_the_draft_was_saved(_isolated_cli_backend: Path) -> None:
    """After `work calculate` the operator is told the result was
    persisted as a draft revision and how to resume / re-inspect it -
    the bare casilla table left no save signal."""

    _create_profile()
    work_unit_id = _create_calculable_work_unit()

    result = _invoke(
        ["--format", "json", "app", "modelo", "work", "calculate", work_unit_id],
    )
    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert payload["saved"] is True
    confirmation = payload["saved_confirmation"]
    assert payload["calculation_revision_id"] in confirmation
    assert "--modelo 111" in confirmation
    assert "--year 2025" in confirmation
    assert "--period 1T" in confirmation
    assert f"work revisions {work_unit_id}" not in confirmation
    assert "work revision" in confirmation


def test_work_revision_shows_persisted_casilla_values(_isolated_cli_backend: Path) -> None:
    """`work revision <id>` shows a stored revision's persisted casilla
    values without recomputing - the operator can re-inspect a saved
    calculation instead of re-running it."""

    _create_profile()
    work_unit_id = _create_calculable_work_unit()

    calculated = _invoke(
        ["--format", "json", "app", "modelo", "work", "calculate", work_unit_id],
    )
    assert calculated.exit_code == 0, calculated.output
    revision_id = _payload(calculated.output)["calculation_revision_id"]
    saved_values = _payload(calculated.output)["casilla_values"]

    shown = _invoke(["--format", "json", "app", "modelo", "work", "revision", revision_id])
    assert shown.exit_code == 0, shown.output
    payload = _payload(shown.output)
    assert payload["operation"] == "modelo.work.revision"
    assert payload["calculation_revision_id"] == revision_id
    # The shown casilla values are exactly the persisted ones.
    assert payload["casilla_values"] == saved_values


def test_work_revision_rejects_an_unknown_revision_id(_isolated_cli_backend: Path) -> None:
    """An absent revision id is refused cleanly, not surfaced as an
    opaque internal error."""

    _create_profile()
    unknown = "0" * 64
    result = _invoke(["app", "modelo", "work", "revision", unknown])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert unknown in result.output


def test_idempotent_work_create_reports_reuse(_isolated_cli_backend: Path) -> None:
    """Re-creating an existing (modelo, year, period, revision) work unit
    must report the reuse plainly - status `reused`, not a silent
    `modelo.work.create` that reads as a fresh creation."""

    _create_profile()
    first = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes", "--name", "First",
        ],
    )  # fmt: skip
    assert first.exit_code == 0, first.output
    first_payload = _payload(first.output)
    assert first_payload["status"] == "created"
    assert first_payload["operation"] == "modelo.work.create"
    assert first_payload["name_applied"] is None

    second = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes", "--name", "First",
        ],
    )  # fmt: skip
    assert second.exit_code == 0, second.output
    second_payload = _payload(second.output)
    assert second_payload["status"] == "reused"
    assert second_payload["operation"] == "modelo.work.reuse"
    assert second_payload["work_unit_id"] == first_payload["work_unit_id"]
    assert second_payload["name_applied"] is None


def test_work_create_without_revision_resumes_existing_visible_target(_isolated_cli_backend: Path) -> None:
    """A natural-key create searches by visible filing target before revision defaults."""

    _create_profile()
    first = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip
    assert first.exit_code == 0, first.output
    first_payload = _payload(first.output)

    second = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert second.exit_code == 0, second.output
    second_payload = _payload(second.output)
    assert second_payload["status"] == "reused"
    assert second_payload["operation"] == "modelo.work.reuse"
    assert second_payload["work_unit_id"] == first_payload["work_unit_id"]


def test_work_create_without_revision_uses_registry_revision_for_supplied_year(
    _isolated_cli_backend: Path,
) -> None:
    """A fresh create without ``--revision`` binds to the law-selected registry revision."""

    register_cli_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "irpf.estimation_regime": "objetiva",
            "identity.tax_id": "12345678Z",
            "identity.name": "Operator",
            "identity.surnames": "Readiness",
            "activities.description": "objective-estimation activity",
        },
    )
    modelos_131, _catalogues_131 = bundled_registry_tree()
    modelo_131 = next(candidate for candidate in modelos_131 if candidate.id == "131")
    expected_revision = select_revision(modelo_131, filing_year=2026, period="2T").id

    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "131", "--year", "2026", "--period", "2T",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert payload["status"] == "created"
    assert payload["modelo"] == "131"
    assert payload["filing_year"] == 2026
    assert payload["period"] == {"filing_year": 2026, "code": "2T"}
    assert payload["revision_id"] == expected_revision


def test_m131_modulos_manual_entry_calculates_without_ledger_observations(
    _isolated_cli_backend: Path,
) -> None:
    register_cli_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "irpf.estimation_regime": "objetiva",
            "identity.tax_id": "12345678Z",
            "identity.name": "Operator",
            "identity.surnames": "Readiness",
            "activities.description": "objective-estimation taxi activity",
        },
    )

    created_work = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "131", "--year", "2026", "--period", "2T",
        ],
    )  # fmt: skip
    assert created_work.exit_code == 0, created_work.output
    work_unit_id = _payload(created_work.output)["work_unit_id"]

    calculated = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "01=12000",
            "--casilla", "02=0",
            "--casilla", "03=0",
            "--casilla", "05=0",
            "--casilla", "08=0",
            "--casilla", "09=0",
            "--casilla", "12=0",
            "--casilla", "14=0",
            "--casilla", "modulos-epigrafe=721.2",
            "--casilla", "modulos-1-unidades=0",
            "--casilla", "modulos-1-unidades-anterior=0",
            "--casilla", "modulos-2-unidades=1",
            "--casilla", "modulos-3-unidades=40",
            "--casilla", "modulos-4-unidades=0",
            "--casilla", "modulos-5-unidades=0",
            "--casilla", "modulos-6-unidades=0",
            "--casilla", "modulos-7-unidades=0",
            "--casilla", "modulos-minoracion-inversion=0",
            "--binding", "modelo-131-2026-resultados-negativos-anteriores=0",
        ],
    )  # fmt: skip
    assert calculated.exit_code == 0, calculated.output
    calculated_payload = _payload(calculated.output)
    revision_id = calculated_payload["calculation_revision_id"]

    shown = _invoke(["--format", "json", "app", "modelo", "work", "revision", revision_id])
    assert shown.exit_code == 0, shown.output
    revision_payload = _payload(shown.output)

    inputs = revision_payload["input_values_by_casilla_id"]
    assert inputs["01"] == "12000"
    assert inputs["modulos-epigrafe"] == "721.2"
    assert inputs["modulos-2-unidades"] == "1"
    assert inputs["modulos-3-unidades"] == "40"
    assert inputs["modulos-minoracion-inversion"] == "0"

    casillas = revision_payload["casilla_values"]
    assert Decimal(casillas["01"]) == Decimal("12000")
    assert Decimal(casillas["modulos-rendimiento-neto-actividad"]) > Decimal("0")
    assert Decimal(casillas["modulos-rendimiento-neto-actividad"]) != Decimal(casillas["01"])


def test_idempotent_work_create_applies_a_new_name_as_a_rename(_isolated_cli_backend: Path) -> None:
    """A different --name supplied on an idempotent re-create is not
    silently dropped: it is applied as a rename and the result says so."""

    _create_profile()
    first = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes", "--name", "Original",
        ],
    )  # fmt: skip
    assert first.exit_code == 0, first.output

    renamed = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes", "--name", "Renamed Unit",
        ],
    )  # fmt: skip
    assert renamed.exit_code == 0, renamed.output
    payload = _payload(renamed.output)
    assert payload["status"] == "reused"
    assert payload["name_applied"] == "Renamed Unit"
    assert payload["name"] == "Renamed Unit"

    # The rename is durable: a fresh status read sees the new name.
    status = _invoke(["--format", "json", "app", "modelo", "work", "status", payload["work_unit_id"]])
    assert status.exit_code == 0, status.output
    assert _payload(status.output)["name"] == "Renamed Unit"


def test_overview_next_step_not_import_after_manual_ledger_entry(_isolated_cli_backend: Path) -> None:
    """M19: after ``ledger add`` records a transaction, ``overview
    status`` next-step guidance must not suggest importing a bank
    statement - the operator already has ledger data."""

    _create_profile()
    added = _invoke(
        [
            "app", "ledger", "add",
            "--date", "2025-01-15", "--amount", "1000.00",
            "--direction", "INCOMING", "--description", "Factura cliente A",
        ],
    )  # fmt: skip
    assert added.exit_code == 0, added.output

    status = _invoke(["app", "overview", "status"])
    assert status.exit_code == 0, status.output
    # The transaction is visible...
    assert "1" in status.output
    # ...and the next-step guidance points forward, never back at import.
    next_section = status.output.split("\n\n")[-1]
    assert "ledger import" not in next_section
    assert "ledger review" in next_section
    assert "modelo work create" in next_section


def test_overview_next_step_does_not_suggest_m210_work_create_for_non_resident(
    _isolated_cli_backend: Path,
) -> None:
    """A non-resident M210 profile gets discovery/Sede guidance, not work-create."""

    _create_gb_non_resident_profile()
    added = _invoke(
        [
            "app", "ledger", "add",
            "--date", "2025-01-15", "--amount", "1000.00",
            "--direction", "INCOMING", "--description", "Spanish-source rent",
            "--source-jurisdiction", "ES",
        ],
    )  # fmt: skip
    assert added.exit_code == 0, added.output

    status = _invoke(["app", "overview", "status"])
    assert status.exit_code == 0, status.output
    next_section = status.output.split("\n\n")[-1]
    assert "ledger import" not in next_section
    assert "ledger review" in next_section
    assert "modelo work create" not in next_section
    assert "modelo describe 210" in next_section
    assert "G320" in next_section


def test_work_create_rejects_revision_that_does_not_cover_filing_year(
    _isolated_cli_backend: Path,
) -> None:
    """Supplying a revision whose period_selector excludes the filing year
    must be refused with a clear error naming both the revision and the
    year, not accepted silently.

    M131 revision ``2026`` has ``period_selector.years = [2026]``.
    Requesting it for ``--year 2024`` crosses that boundary — the 2026
    DANA rules do not apply to a 2024 filing.
    """

    register_cli_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "irpf.estimation_regime": "objetiva",
            "identity.tax_id": "12345678Z",
            "identity.name": "Operator",
            "identity.surnames": "Readiness",
            "activities.description": "objective-estimation activity",
        },
    )
    result = _invoke(
        [
            "app", "modelo", "work", "create",
            "--modelo", "131", "--year", "2024", "--period", "2T",
            "--revision", "2026",
        ],
    )  # fmt: skip
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    # Both the mismatched revision and the filing year must appear in the
    # diagnostic so the operator knows what to fix.
    assert "2026" in result.output
    assert "2024" in result.output


def test_work_calculate_rejects_decimal_override_for_text_casilla(
    _isolated_cli_backend: Path,
) -> None:
    """Supplying a numeric value for a text-type casilla via --casilla must
    be refused before reaching the engine.

    M100 2024 casilla ``0001`` has ``data_type = "text"`` with
    ``semantic_role = "irpf_toma_datos_declarante_selector"``: it names the
    contribuyente who obtains the income (declarante / cónyuge / dependant),
    not a numeric amount. Passing ``--casilla "0001=38000"`` would otherwise
    route the number onto the parallel text channel, store it silently in the
    text slot, and be ignored by the formula chain — surfacing as a wrong base
    imponible. The input-validation guard
    (``_validated_declarante_selector`` in
    ``cadrumo.application.modelo._calculate_input``) fires early with a typed
    ``ModeloCalculateTextInputError`` naming the casilla, its label, its
    ``data_type``, and the numeric casilla channel the amount belongs on, so
    the engine is never reached.
    """

    _create_profile()
    created = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "100", "--year", "2024", "--period", "0A",
            "--revision", "2024",
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    work_unit_id = _payload(created.output)["work_unit_id"]

    result = _invoke(
        [
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "0001=38000",
        ],
    )  # fmt: skip
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    # The diagnostic must name the casilla and its non-numeric data_type.
    assert "0001" in result.output
    assert "text" in result.output
