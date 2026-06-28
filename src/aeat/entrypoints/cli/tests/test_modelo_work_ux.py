"""End-to-end CLI verification for the modelo-work UX cluster.

Drives the real ``aeat`` CLI against an isolated encrypted backend to
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

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql.engine import dispose_engine

# Importing the wizard catalogue + persistence modules triggers
# register_wizard_catalogue() at import time, exactly as the production CLI
# startup does (cli.__init__ registers it for profile-key resolution). Without
# this, an in-process `modelo work create` reaches _guard_modelo_applicability ->
# projection_for_taxpayer -> get_setup_flow() and raises
# WizardCatalogueNotRegisteredError (the catalogue is a process-global the real
# CLI registers at startup; the in-process test must do the same).
from ....application.wizard import _catalogue as _wizard_catalogue
from ....application.wizard import _persistence as _wizard_persistence
from ....core import Modelo
from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WIZARD_REGISTRATION_MODULES = (_wizard_catalogue, _wizard_persistence)

#: Profile id every test in this module creates via the CLI inside the span.
_PROFILE_ID = "operator"


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path) -> Iterator[None]:
    """Isolated storage root; each invoke opens the active UUID bucket session."""
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
    ):
        try:
            yield
        finally:
            dispose_engine()


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _create_profile(*, activity_start_date: str | None = None) -> None:
    args = [
        "config", "profile", "create", "operator",
        "--quiet", "--accept-defaults",
        "--entity-type", "natural_person",
        "--irpf-income-categories", "actividad_economica",
        "--tax-id", "12345678Z",
        "--name", "Operator",
        "--surnames", "Readiness",
        "--activity", "design",
    ]
    if activity_start_date is not None:
        args.extend(["--activity-start-date", activity_start_date])
    result = _invoke(args)  # fmt: skip
    assert result.exit_code == 0, result.output


def _set_gb_non_resident_axes() -> None:
    result = _invoke(
        [
            "config", "profile", "edit", "operator",
            "--quiet",
            "--fiscal-residency", "non_resident_irnr",
            "--country-of-fiscal-residence", "GB",
            "--representante-fiscal-nif", "12345678Z",
            "--representante-fiscal-nombre", "Test Representative",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "success"
    assert payload["result"]["active_profile"] == _PROFILE_ID
    assert "profile-key registry" not in result.output
    assert "Traceback" not in result.output


def _attempt_incomplete_profile_create():
    return _invoke(
        [
            "--format", "json",
            "config", "profile", "create", _PROFILE_ID,
            "--quiet", "--accept-defaults",
            "--tax-id", "12345678Z",
            "--activity", "design",
        ],
    )  # fmt: skip


def _create_work_unit() -> str:
    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return _payload(result.output)["work_unit_id"]


def test_profile_create_refuses_incomplete_profile_before_modelo_work() -> None:
    """Incomplete profiles must fail before a modelo work unit can exist."""
    from ....application.workflow._profile_bucket_scan import read_profile_bucket

    result = _attempt_incomplete_profile_create()

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "REFUSED_WIZARD_MISSING_FLAG"
    assert payload["error"]["category"] == "REFUSED"
    message = payload["error"]["message"]
    assert "--entity-type" in message
    assert "--name" in message
    assert "--surnames" in message
    assert read_profile_bucket(_PROFILE_ID) is None
    assert "work_unit_id" not in result.output
    assert "Traceback" not in result.output


def test_work_create_refuses_pre_activity_m303_and_creates_no_unit() -> None:
    _create_profile(activity_start_date="2026-05-01")

    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "303",
            "--year", "2026",
            "--period", "1T",
        ],
    )  # fmt: skip

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "REFUSED_MODELO_PROFILE_READINESS"
    message = payload["error"]["message"]
    assert "pre-activity period" in message
    assert "2026-05-01" in message
    assert "2026-03-31" in message
    assert "Traceback" not in result.output

    listed = _invoke(["--format", "json", "app", "modelo", "work", "list"])
    assert listed.exit_code == 0, listed.output
    assert _payload(listed.output)["work_unit_count"] == 0


def test_work_create_refuses_pre_activity_m130_and_creates_no_unit() -> None:
    _create_profile(activity_start_date="2026-07-15")

    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", Modelo.M130.value,
            "--year", "2026",
            "--period", "2T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "REFUSED_MODELO_PROFILE_READINESS"
    message = payload["error"]["message"]
    assert f"Modelo {Modelo.M130.value} 2026 2T is before" in message
    assert "pre-activity period" in message
    assert "2026-07-15" in message
    assert "2026-06-30" in message
    assert "Traceback" not in result.output

    listed = _invoke(["--format", "json", "app", "modelo", "work", "list"])
    assert listed.exit_code == 0, listed.output
    assert _payload(listed.output)["work_unit_count"] == 0


def _create_calculable_work_unit() -> str:
    """Create a modelo 111 work unit whose `work calculate` succeeds with
    no operator-supplied inputs - 111 has only manual casillas and formulas,
    no source bindings that require ledger, profile, or prior-period data."""

    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "111", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return _payload(result.output)["work_unit_id"]


def test_work_history_records_creation_event(_isolated_cli_backend: Path) -> None:
    """M17: a freshly-created work unit's history starts with a
    ``modelo.work_unit.created`` event - not an empty stream."""

    _create_profile()
    work_unit_id = _create_work_unit()

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


def test_first_work_calculate_binding_error_guides_the_operator(_isolated_cli_backend: Path) -> None:
    """M18: the first ``work calculate`` that hits an unsatisfied binding
    fails with guidance toward ``--binding KEY=VALUE`` and the
    bindings-list discovery command - not a bare refusal."""

    _create_profile()
    work_unit_id = _create_work_unit()

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
    work_unit_id = _create_work_unit()

    result = _invoke(["--format", "json", "app", "modelo", "work", "revisions", work_unit_id])
    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert payload["work_unit_id_filter"] == work_unit_id


def test_work_status_resolves_a_visible_filing_target(_isolated_cli_backend: Path) -> None:
    """`work status` accepts the operator-facing modelo/year/period target."""

    _create_profile()
    work_unit_id = _create_work_unit()

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
        ],
    )  # fmt: skip
    assert result.exit_code != 0
    assert "file requires a verified-complete revision" not in result.output
    assert "filing-obligation window is not open" in result.output or "NO_PENDING_OBLIGATION" in result.output


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

    create = _invoke(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--activity", "design",
            "--activity-start-date", "2025-01-01",
        ],
    )  # fmt: skip
    assert create.exit_code == 0, create.output

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

    _create_profile()
    _set_gb_non_resident_axes()
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

    _create_profile()
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

    M100 2024 casilla ``0001`` has ``data_type = "text"`` (it names the
    declarante, not a numeric income amount).  Passing ``--casilla "0001=38000"``
    silently stored Decimal(38000) in the text slot, which the formula chain
    ignores, producing a negative base imponible when combined with a
    subtraction-convention casilla like ``0006``.  The guard must fire early
    with a diagnostic naming the casilla, its label, its data_type, and the
    correct input channel.

    tracked: #53 — this test currently fails at ``_create_profile()`` with
    REFUSED_PROFILE_NOT_FOUND: the held ``profile_create_storage_span`` and the
    in-process CLI ``profile create`` disagree on the bucket-manifest
    registration for the ``operator`` profile (the UUID-vs-display-name /
    manifest-registration in-process resolution class split into task #53,
    distinct from the #52 bucket-session bootstrap this module's other tests
    needed). Left failing loudly per the #52 brief until #53's
    profile-resolution fix lands.
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
