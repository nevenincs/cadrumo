"""Tests for the registry maintenance CLI's exit-code contract.

`dev.quality.module_test_reach` listed `dev/registry/parity/maintenance_cli.py`
as unreached. Three of its four verbs are gates by intent, and only one of them
could fail.

``audit-oracles`` raises ``typer.Exit(1)`` on failures and is the verb CI runs.
Its two siblings in the same file printed their failure signal as JSON and
returned 0: ``workbooks-verify`` ignored ``failed_count``, and ``parity-replay``
ignored a ``status`` of ``mismatch`` - so a replay whose entire purpose is to
detect that the product diverged from an archived tape reported that divergence
and exited successfully. Anything reading the status code could not tell a
divergence from an agreement.

``workbooks-verify`` carried a second, narrower version of the same shape: a
``--root`` naming an empty or moved tree reports ``workbook_count`` and
``failed_count`` both zero, which reads exactly like a clean audit of a real
corpus that happened to have nothing wrong. The report already carries
``backend_exists`` to name that state -- it is asserted directly against the
producer in ``test_workbook_parity.py`` -- but the CLI never read it before
deciding whether to exit zero.

What is NOT covered here, stated rather than implied: a genuine mismatching
replay. Building one needs a valid archived tape, which needs a parity scenario
and an official workbook, and replaying it runs the scenario against the live
registry. That corpus is the subject of the parity suite next door, not of the
CLI's exit-code wiring. These cases pin the wiring - that the failure branch
exists, that the success branch stays 0, and that a missing input refuses
rather than passing.
"""

from __future__ import annotations

import json
import pathlib
from decimal import Decimal

import pytest
from openpyxl import Workbook
from typer.testing import CliRunner

from ..maintenance_cli import app

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _invoke(*arguments: str) -> object:
    return CliRunner().invoke(app, list(arguments))


def _write_formula_workbook(path: pathlib.Path) -> None:
    """One minimal real workbook, scanned with openpyxl alone -- no external tool."""
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = "Modelo"
    worksheet["A1"] = Decimal("10")
    worksheet["A2"] = Decimal("21")
    worksheet["B1"] = "=A1+A2"
    workbook.save(path)


def test_every_maintenance_verb_is_registered() -> None:
    """The commands are reached by name from a workflow file, so the names are contract."""
    result = _invoke("--help")

    assert result.exit_code == 0, result.output
    for verb in ("audit-oracles", "workbooks-verify", "parity-run", "parity-replay"):
        assert verb in result.output


def test_a_verified_non_empty_workbook_root_exits_zero(tmp_path: pathlib.Path) -> None:
    """The success branch must survive the two refusals below.

    A gate that refused unconditionally would be no better than one that never
    refused; this is the half that says the exit code tracks the report.
    """
    _write_formula_workbook(tmp_path / "modelo_390" / "files" / "390-test.xlsx")

    result = _invoke("workbooks-verify", "--root", str(tmp_path))

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["workbook_count"] == 1
    assert payload["failed_count"] == 0


def test_an_empty_workbook_root_refuses_rather_than_reporting_a_clean_audit(tmp_path: pathlib.Path) -> None:
    """A moved or misspelled corpus path must not look like a real, clean audit.

    ``workbook_count`` and ``failed_count`` are both zero here, which is exactly
    what a genuinely clean corpus also reports -- the report's own
    ``backend_exists`` property exists to tell the two apart, and the CLI must
    act on it.
    """
    result = _invoke("workbooks-verify", "--root", str(tmp_path))

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["workbook_count"] == 0
    assert payload["failed_count"] == 0


def test_the_workbook_verdict_and_the_exit_code_agree(tmp_path: pathlib.Path) -> None:
    """The property, stated over whatever the run actually found.

    Written against the report rather than a fixed expectation so it holds for
    any root with something to scan: a run reporting failures must not exit 0,
    and a clean run must not exit non-zero. An empty root is a distinct case,
    pinned above, because it fails closed for a different reason -- nothing was
    scanned at all -- that this property cannot express over ``failed_count``
    alone.
    """
    _write_formula_workbook(tmp_path / "modelo_390" / "files" / "390-test.xlsx")

    result = _invoke("workbooks-verify", "--root", str(tmp_path))
    failed = json.loads(result.output)["failed_count"]

    assert (result.exit_code != 0) == bool(failed)


def test_replaying_a_missing_tape_refuses(tmp_path: pathlib.Path) -> None:
    """An absent tape proves nothing about parity, so it cannot exit 0."""
    result = _invoke("parity-replay", "--tape", str(tmp_path / "absent.json"))

    assert result.exit_code != 0


def test_replaying_an_unparsable_tape_refuses(tmp_path: pathlib.Path) -> None:
    """A tape that is not a tape is not a match either."""
    tape = tmp_path / "broken.json"
    tape.write_text("{not json", encoding="utf-8")

    result = _invoke("parity-replay", "--tape", str(tape))

    assert result.exit_code != 0


def test_auditing_an_empty_registry_root_does_not_report_success(
    tmp_path: pathlib.Path,
) -> None:
    """The verb CI runs, over a root containing no registry at all.

    This is the pattern the two siblings now follow, so it is pinned here as
    the reference: a gate handed nothing must not answer the way a clean audit
    does.
    """
    result = _invoke("audit-oracles", "--registry-root", str(tmp_path))

    assert result.exit_code != 0


def test_a_parity_run_without_its_required_options_refuses() -> None:
    """The scenario and store root have no defensible default."""
    result = _invoke("parity-run")

    assert result.exit_code != 0
