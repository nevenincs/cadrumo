"""Regression guard for the retrospective S175 c941 family census."""

from __future__ import annotations

import ast
import json
from collections import Counter
from copy import deepcopy

import pytest

import dev.quality.registry_facade_family_census as census
from dev.quality.registry_facade_family_census import (
    EVIDENCE_COMMIT,
    MATRIX_PATH,
    RelocatedFamily,
    _annotation_owners,
    _base_category,
    _dynamic_import_call,
    _evidence_census,
    _evidence_text,
    _package_attribute_owners,
    _python_import_context,
    _resolve_dynamic_target,
    _resolve_relative_import,
    check_matrix_document,
    current_terminal_state_report,
    exact_relocation_candidates,
    generated_rows,
    mechanical_relocation_pairs,
    refresh_reviewed_matrix_document,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _document() -> dict[str, object]:
    """Read the checked reviewed artifact once for a test assertion."""
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _candidate(stem: str = "authority") -> RelocatedFamily:
    """Build one exact-shaped candidate for parser-level tests."""
    return RelocatedFamily(
        100,
        f"src/cadrumo/domain/calculations/registry/_{stem}.py",
        f"src/cadrumo/domain/calculations/registry/{stem}.py",
    )


def test_c941_registry_relocation_family_is_the_fixed_78_row_set() -> None:
    """The denominator is the c941 delta, never a mutable filename scan."""
    candidates = exact_relocation_candidates()

    assert len(candidates) == 78
    assert len({candidate.old_path for candidate in candidates}) == 78
    assert len({candidate.new_path for candidate in candidates}) == 78


def test_mechanical_delta_pairs_are_the_checked_matrix_denominator() -> None:
    """Every reviewed row has one exact historic rename pair."""
    document = _document()
    rows = document["rows"]

    assert isinstance(rows, list)
    assert mechanical_relocation_pairs() == tuple((row["old_path"], row["new_path"]) for row in rows)


def test_relative_imports_type_aliases_and_fixture_order_are_resolved() -> None:
    """Relative edges and both TypeAlias forms retain their real owner."""
    candidate = _candidate()
    source = """
from .. import authority
from typing import TypeAlias

AuthorityAlias: TypeAlias = authority.Authority
type ModernAuthorityAlias = authority.Authority
"""
    tree = ast.parse(source)
    imports, aliases, from_members = _python_import_context(
        tree,
        current_module="cadrumo.domain.calculations.registry.tests.consumer",
        is_package=False,
    )

    assert (
        _resolve_relative_import(
            "cadrumo.domain.calculations.registry.tests.consumer",
            is_package=False,
            level=2,
            module=None,
        )
        == "cadrumo.domain.calculations.registry"
    )
    assert "cadrumo.domain.calculations.registry.authority" in imports
    assert ("cadrumo.domain.calculations.registry", "authority") in from_members
    assert _annotation_owners(tree, aliases=aliases, by_new_module={candidate.new_module: candidate}) == {
        candidate.old_path
    }
    assert _base_category("src/cadrumo/tests/fixtures/registry/receipt.toml") == "fixture"
    assert _base_category("dev/quality/tests/test_registry.py") == "test"


def test_package_module_attribute_access_is_precisely_member_owned() -> None:
    """A package import does not attribute every facade row to one consumer."""
    authority = _candidate("authority")
    schema = _candidate("schema")
    tree = ast.parse(
        """
import cadrumo.domain.calculations.registry as registry
from cadrumo.domain.calculations.registry import Authority

registry.Authority()
Authority()
"""
    )
    _, aliases, from_members = _python_import_context(
        tree,
        current_module="cadrumo.application.consumer",
        is_package=False,
    )

    assert _package_attribute_owners(
        tree,
        aliases=aliases,
        from_members=from_members,
        member_owners={"Authority": authority.old_path, "Schema": schema.old_path},
    ) == {authority.old_path}


def test_dynamic_imports_keep_literal_and_nonliteral_sites_distinct() -> None:
    """A nonliteral dynamic import is explicit unresolved evidence, never dropped."""
    tree = ast.parse(
        """
from importlib import import_module as load

literal = load("cadrumo.domain.calculations.registry.authority")
computed = load(target)
"""
    )
    _, aliases, _ = _python_import_context(tree, current_module="cadrumo.consumer", is_package=False)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    document = _document()
    dynamic_imports = document["dynamic_imports"]

    assert [_dynamic_import_call(call, aliases) for call in calls] == ["importlib.import_module"] * 2
    assert (
        _resolve_dynamic_target(".authority", module="cadrumo.registry", is_package=True)
        == "cadrumo.registry.authority"
    )
    assert isinstance(dynamic_imports, dict)
    assert dynamic_imports["literal"]
    assert dynamic_imports["unresolved"]
    assert all({"site", "callee", "expression"} == set(item) for item in dynamic_imports["unresolved"])


def test_immutable_measurements_anchor_relative_import_and_type_alias_regressions() -> None:
    """The JSON records source measurements derived from the immutable tree.

    The relative-import count is intentionally not duplicated as a test literal:
    source evolution must update the committed evidence, while the checked JSON
    still pins the measured relative-edge class at the reviewed evidence commit.
    """
    document = _document()
    measurements = document["evidence_measurements"]

    assert document["evidence_commit"] == EVIDENCE_COMMIT
    assert measurements == _evidence_census().measurements
    assert isinstance(measurements, dict)
    assert measurements["relative_import_edges"] > 0
    assert measurements["type_alias_nodes"] >= 24


def test_generation_is_reproducible_from_the_clean_immutable_git_object(monkeypatch: pytest.MonkeyPatch) -> None:
    """Generation reads Git archive objects, not dirty-worktree file contents."""
    assert census._git("rev-parse", f"{EVIDENCE_COMMIT}^{{commit}}").strip() == EVIDENCE_COMMIT
    original_git_bytes = census._git_bytes
    archive_calls: list[tuple[str, ...]] = []

    def record_archive(*arguments: str) -> bytes:
        archive_calls.append(arguments)
        return original_git_bytes(*arguments)

    def fail_if_worktree_text_is_read(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("immutable evidence must not call Path.read_text")

    monkeypatch.setattr(census, "_git_bytes", record_archive)
    monkeypatch.setattr(census.Path, "read_text", fail_if_worktree_text_is_read)
    census._EVIDENCE_FILE_CACHE = None
    census._EVIDENCE_CENSUS_CACHE = None
    first = generated_rows()
    census._EVIDENCE_FILE_CACHE = None
    census._EVIDENCE_CENSUS_CACHE = None
    second = generated_rows()

    assert first == second
    assert _evidence_text(exact_relocation_candidates()[0].new_path)
    assert archive_calls
    assert all(call[:4] == ("archive", "--format=tar", EVIDENCE_COMMIT, "--") for call in archive_calls)


def test_generated_rows_preserve_one_row_per_exact_c941_candidate() -> None:
    """Generated evidence remains one-to-one and has source/import locators."""
    rows = generated_rows()

    assert len(rows) == 78
    assert [row["row_id"] for row in rows] == [f"R{number:02d}" for number in range(1, 79)]
    assert len({(row["old_path"], row["new_path"]) for row in rows}) == 78
    for row in rows:
        symbols = row["facade_exported_symbols"]
        locators = row["current_symbol_locators"]
        semantic = row["semantic_evidence"]

        assert isinstance(symbols, list)
        assert isinstance(locators, dict)
        assert isinstance(semantic, dict)
        assert set(locators) == set(symbols)
        assert semantic["anchors"]["evidence_commit"] == EVIDENCE_COMMIT
        assert {"owner_definition_locators", "competing_site_census", "substitutability", "anchors"} == set(semantic)


def test_reviewed_rows_record_anchored_structured_semantic_and_rag_evidence() -> None:
    """Every row retains review query, defining locator, and competitor rationale."""
    document = _document()
    rows = document["rows"]

    assert isinstance(rows, list)
    for row in rows:
        semantic = row["semantic_evidence"]
        rag_result = row["rag_result"]

        assert isinstance(semantic, dict)
        assert semantic["anchors"]["evidence_commit"] == EVIDENCE_COMMIT
        assert semantic["anchors"]["relocation_pair"] == [row["old_path"], row["new_path"]]
        module = row["new_path"].removeprefix("src/").removesuffix(".py").replace("/", ".")
        assert row["rag_query"].endswith(module)
        assert rag_result["path"] == row["new_path"]
        assert f"{rag_result['path']}:{rag_result['line_start']}" in row["alternative_owner_evidence"]
        assert row["semantic_owner"] in row["alternative_owner_evidence"]


def test_current_terminal_report_allows_future_hard_move_privatization_and_deletion() -> None:
    """Later absence is a valid terminal candidate, without a compatibility shim."""
    document = deepcopy(_document())
    report = current_terminal_state_report(document, exists=lambda _path: False)
    rows = document["rows"]
    report_rows = report["rows"]

    assert isinstance(rows, list)
    assert isinstance(report_rows, list)
    disposition_by_step = {row["follow_on_step_id"]: row["disposition"] for row in rows}
    has_retired_candidate = {
        row["follow_on_step_id"]: any(destination["allowed_absence"] for destination in row["terminal_destinations"])
        for row in rows
    }
    status_by_step = {row["step_id"]: row["status"] for row in report_rows}
    for step_id, disposition in disposition_by_step.items():
        if disposition in {"hard_move_complete", "privatize_external_elimination", "delete"}:
            expected = (
                "terminal_candidate_absent_pending_step_proof"
                if has_retired_candidate[step_id]
                else "terminal_destination_missing_pending_step"
            )
            assert status_by_step[step_id] == expected
    assert len(report["open_disposition_step_ids"]) == 78


def test_reviewed_matrix_passes_its_exact_census_and_canonical_step_gate() -> None:
    """The checked-in adjudication remains complete and plan-bound."""
    check_matrix_document(_document())


def test_checked_matrix_is_byte_stable() -> None:
    """Check mode verifies the artifact without rewriting it."""
    before = MATRIX_PATH.read_bytes()

    check_matrix_document(json.loads(before))

    assert MATRIX_PATH.read_bytes() == before


def test_reviewed_refresh_preserves_manual_dispositions_and_plan_bindings() -> None:
    """Refreshing evidence cannot erase the independently reviewed decisions."""
    document = _document()
    refreshed = refresh_reviewed_matrix_document(document)
    manual_fields = {
        "semantic_owner",
        "disposition",
        "terminal_state",
        "follow_on_step_id",
        "follow_on_action",
        "follow_on_scope",
        "follow_on_predecessors",
    }
    reviewed_rows = document["rows"]
    refreshed_rows = refreshed["rows"]

    assert isinstance(reviewed_rows, list)
    assert isinstance(refreshed_rows, list)
    for before, after in zip(reviewed_rows, refreshed_rows, strict=True):
        assert {field: before[field] for field in manual_fields} == {field: after[field] for field in manual_fields}


def test_reviewed_rows_are_one_to_one_complete_and_not_grouped() -> None:
    """Every candidate has one disposition, terminal state, and canonical Step."""
    document = _document()
    rows = document["rows"]

    assert isinstance(rows, list)
    assert Counter(row["disposition"] for row in rows) == {
        "keep_public": 54,
        "hard_move_complete": 9,
        "privatize_external_elimination": 13,
        "delete": 2,
    }
    assert len({row["follow_on_step_id"] for row in rows}) == 78
    assert all(row["follow_on_predecessors"] == ["W03.P20.S175"] for row in rows)
    assert all("unresolved" not in row["terminal_state"] for row in rows)
    assert all("unresolved" not in row["semantic_owner"] for row in rows)
