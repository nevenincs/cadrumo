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

from aeat.tests.cli_runner import invoke_cached_cli
from aeat.tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _payload(output: str) -> dict:
    """Return the payload from a CLI JSON line, unwrapping the SchemaEnvelope.

    Post-P09.S43 every migrated ``modelo.work.*`` command emits the
    bare payload wrapped in
    ``{"schema_version": ..., "command": ..., "result": ..., "warnings": []}``.
    Tests in this file all hit migrated commands, so the helper
    transparently unwraps to the ``result`` mapping. Bare-payload
    commands (not migrated) pass through unchanged: the envelope-vs-bare
    detection keys on the ``schema_version`` marker which only the
    envelope shape carries.
    """

    raw = json.loads(output)
    if isinstance(raw, dict) and "schema_version" in raw and "result" in raw:
        return raw["result"]
    return raw


def _create_profile() -> None:
    result = _invoke(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--activity", "design",
        ]
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _create_work_unit() -> str:
    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes",
        ]
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return _payload(result.output)["work_unit_id"]


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
        ]
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

    result = _invoke(
        ["app", "modelo", "work", "calculate", work_unit_id, "--casilla", "01=10000"],
    )
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    # A missing previous_filing binding id is named in the error — whichever
    # bound casilla the formula evaluator hits first (modelo-130 has two).
    assert "modelo-130-resultados-negativos-anteriores" in result.output
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
        ]
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
        ]
    )  # fmt: skip
    assert second.exit_code == 0, second.output
    second_payload = _payload(second.output)
    assert second_payload["status"] == "reused"
    assert second_payload["operation"] == "modelo.work.reuse"
    assert second_payload["work_unit_id"] == first_payload["work_unit_id"]
    assert second_payload["name_applied"] is None


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
        ]
    )  # fmt: skip
    assert first.exit_code == 0, first.output

    renamed = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes", "--name", "Renamed Unit",
        ]
    )  # fmt: skip
    assert renamed.exit_code == 0, renamed.output
    payload = _payload(renamed.output)
    assert payload["status"] == "reused"
    assert payload["name_applied"] == "Renamed Unit"
    assert payload["name"] == "Renamed Unit"

    # The rename is durable: a fresh status read sees the new name.
    status = _invoke(
        ["--format", "json", "app", "modelo", "work", "status", payload["work_unit_id"]]
    )
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
        ]
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
