"""Tests for the repository-only registry parity maintenance wiring.

The module is a thin layer over the domain's live-parity functions, and its own
behaviour is the wiring: which arguments it forwards, when it writes, and
whether what it writes can be read back. `dev.quality.module_test_reach` listed
it as an untested module that writes to the tree, which is what brought it here.

Nothing is mocked. The workbook verification runs against a constructed root and
returns a real report in hundredths of a second when there is nothing to scan,
so the wiring can be exercised end to end without standing up a backend - and a
test that patched the domain function would be asserting the patch.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from ..parity.maintenance import verify_registry_workbooks

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_no_output_path_means_no_write(tmp_path: pathlib.Path) -> None:
    """The safety property: the report is returned, nothing is persisted.

    This module was listed as an untested module that writes to the tree, and
    the write is conditional on an argument. A conditional write is only safe if
    the other branch is proven.
    """
    root = tmp_path / "registry"
    root.mkdir()

    report = verify_registry_workbooks(root=root, limit=1, per_file_timeout_seconds=2.0)

    assert report is not None
    assert list(tmp_path.rglob("*.json")) == []


def test_an_output_path_receives_the_report_as_readable_json(tmp_path: pathlib.Path) -> None:
    """What is written must be what a later run can resume from."""
    root = tmp_path / "registry"
    root.mkdir()
    output = tmp_path / "reports" / "workbooks.json"

    report = verify_registry_workbooks(root=root, limit=1, per_file_timeout_seconds=2.0, output=output)

    assert output.is_file(), "the parent directory was not created"
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written == json.loads(report.model_dump_json())


def test_the_written_report_round_trips_through_resume(tmp_path: pathlib.Path) -> None:
    """``resume_from`` parses what ``output`` produced, which is the pair's contract.

    The two arguments are only useful together: a run writes a report and a later
    run continues from it. Asserted by doing exactly that rather than by reading
    the model, because a serialisation the resume path cannot parse would satisfy
    a field-by-field comparison and still break the workflow.
    """
    root = tmp_path / "registry"
    root.mkdir()
    first = tmp_path / "first.json"
    verify_registry_workbooks(root=root, limit=1, per_file_timeout_seconds=2.0, output=first)

    resumed = verify_registry_workbooks(root=root, limit=1, per_file_timeout_seconds=2.0, resume_from=first)

    assert resumed is not None


def test_the_report_names_the_root_it_was_given(tmp_path: pathlib.Path) -> None:
    """A report that named a different tree would be evidence about nothing."""
    root = tmp_path / "registry"
    root.mkdir()

    report = verify_registry_workbooks(root=root, limit=1, per_file_timeout_seconds=2.0)

    assert pathlib.Path(str(report.root)) == root


def test_an_empty_root_produces_an_honest_empty_report(tmp_path: pathlib.Path) -> None:
    """Nothing scanned is reported as nothing scanned, not as nothing wrong.

    The distinction this campaign keeps returning to: a clean verdict over an
    empty population is not a clean verdict.
    """
    root = tmp_path / "registry"
    root.mkdir()

    report = verify_registry_workbooks(root=root, limit=1, per_file_timeout_seconds=2.0)

    assert report.formula_workbook_count == 0
    assert report.failed_count == 0
    assert list(report.reports) == []
