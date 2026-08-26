"""Structural guard for the retrospective S175 c941 family census."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from collections import Counter

import pytest

import dev.quality.registry_facade_family_census as census
from dev.quality.registry_facade_family_census import (
    MATRIX_PATH,
    RelocatedFamily,
    _annotation_owners,
    _base_category,
    _dynamic_import_call,
    _evidence_census,
    _evidence_text,
    _owner_for_reference,
    _package_attribute_owners,
    _python_import_context,
    _text_reference_owners,
    _transitive_consumer_paths,
    check_matrix_document,
    exact_relocation_candidates,
    generated_rows,
    mechanical_relocation_pairs,
    refresh_reviewed_matrix_document,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_c941_registry_relocation_family_is_the_fixed_78_row_set() -> None:
    """The retrospective audit must not silently scan a different relocation family."""
    candidates = exact_relocation_candidates()

    assert len(candidates) == 78
    assert len({candidate.old_path for candidate in candidates}) == 78
    assert len({candidate.new_path for candidate in candidates}) == 78


def test_relative_imports_fixture_precedence_annotations_and_type_aliases_are_resolved() -> None:
    """The census resolves relative references before categorizing every annotation form."""
    authority = RelocatedFamily(
        similarity=100,
        old_path="src/cadrumo/domain/calculations/registry/_authority.py",
        new_path="src/cadrumo/domain/calculations/registry/authority.py",
    )
    tree = ast.parse(
        """
from .. import authority as authority_module
from typing import TypeAlias
AuthorityAlias: TypeAlias = authority_module.ValidatedRegistryAuthority
def consume(value: authority_module.ValidatedRegistryAuthority) -> AuthorityAlias: ...
"""
    )
    imports, aliases, _ = _python_import_context(
        tree,
        current_module="cadrumo.domain.calculations.registry.tests.test_consumer",
        is_package=False,
    )

    assert "cadrumo.domain.calculations.registry.authority" in imports
    assert aliases["authority_module"] == "cadrumo.domain.calculations.registry.authority"
    assert _annotation_owners(tree, aliases=aliases, by_new_module={authority.new_module: authority}) == {
        authority.old_path
    }
    assert _base_category("src/cadrumo/domain/calculations/registry/tests/conftest.py") == "fixture"
    assert _base_category("src/cadrumo/domain/calculations/registry/tests/fixtures/authority.py") == "fixture"


def test_package_attributes_have_one_member_owner_and_transitive_closure_crosses_direct_nodes() -> None:
    """Facade member and reverse-graph attribution cannot broaden or truncate a row."""
    package = "cadrumo.domain.calculations.registry"
    tree = ast.parse("import cadrumo.domain.calculations.registry as registry\nregistry.Authority")
    owners = _package_attribute_owners(
        tree,
        aliases={"registry": package},
        from_members=(),
        member_owners={"Authority": "old-authority", "Other": "old-other"},
    )

    assert owners == {"old-authority"}
    from_tree = ast.parse("from cadrumo.domain.calculations.registry import Authority")
    _, from_aliases, from_members = _python_import_context(
        from_tree,
        current_module="application.consumer",
        is_package=False,
    )
    assert _package_attribute_owners(
        from_tree,
        aliases=from_aliases,
        from_members=from_members,
        member_owners={"Authority": "old-authority", "Other": "old-other"},
    ) == {"old-authority"}
    bare_tree = ast.parse("import cadrumo.domain.calculations.registry")
    assert not _package_attribute_owners(
        bare_tree,
        aliases={"cadrumo": "cadrumo"},
        from_members=(),
        member_owners={"Authority": "old-authority", "Other": "old-other"},
    )
    leaf_tree = ast.parse("from cadrumo.domain.calculations.registry.authority import Authority")
    _, leaf_aliases, leaf_members = _python_import_context(
        leaf_tree, current_module="application.consumer", is_package=False
    )
    assert not _package_attribute_owners(
        leaf_tree,
        aliases=leaf_aliases,
        from_members=leaf_members,
        member_owners={"Authority": "old-authority", "authority": "old-authority"},
    )
    assert _transitive_consumer_paths(
        "registry.authority",
        direct_modules={"application.bridge"},
        importers={"registry.authority": {"application.bridge"}, "application.bridge": {"entrypoint"}},
        module_paths={"application.bridge": {"src/application/bridge.py"}, "entrypoint": {"src/entrypoint.py"}},
    ) == {"src/entrypoint.py"}


def test_dynamic_imports_keep_literal_and_nonliteral_sites_distinct() -> None:
    """A computed dynamic target is retained as unresolved evidence, never dropped."""
    tree = ast.parse(
        "from importlib import import_module as load\n"
        "literal = load('cadrumo.domain.calculations.registry.authority')\n"
        "computed = load(target)\n"
    )
    _, aliases, _ = _python_import_context(tree, current_module="application.consumer", is_package=False)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]

    assert [_dynamic_import_call(call, aliases) for call in calls] == ["importlib.import_module"] * 2
    document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    dynamic_imports = document["dynamic_imports"]

    assert isinstance(dynamic_imports, dict)
    assert {"literal", "unresolved"} == set(dynamic_imports)
    assert all({"site", "callee", "expression"} == set(site) for site in dynamic_imports["unresolved"])
    keyword_tree = ast.parse(
        "import importlib\nimportlib.import_module(name='cadrumo.domain.calculations.registry.authority')"
    )
    _, keyword_aliases, _ = _python_import_context(
        keyword_tree, current_module="application.consumer", is_package=False
    )
    keyword_call = next(node for node in ast.walk(keyword_tree) if isinstance(node, ast.Call))
    assert _dynamic_import_call(keyword_call, keyword_aliases) == "importlib.import_module"


def test_package_symbol_and_leaf_references_have_exact_family_owners() -> None:
    """A public package symbol is not confused with a leaf-module import route."""
    authority = RelocatedFamily(100, "old-authority", "src/cadrumo/domain/calculations/registry/authority.py")
    assert (
        _owner_for_reference(
            "cadrumo.domain.calculations.registry.parse_export_payload",
            by_new_module={authority.new_module: authority},
            member_owners={"parse_export_payload": "old-export"},
        )
        == "old-export"
    )


def test_non_python_package_symbol_targets_are_attributed_to_the_exporting_row() -> None:
    """TOML/JSON/YAML package targets retain symbol-level ownership."""
    export = RelocatedFamily(
        100,
        "src/cadrumo/domain/calculations/registry/_export.py",
        "src/cadrumo/domain/calculations/registry/export.py",
    )
    calculation = RelocatedFamily(
        100,
        "src/cadrumo/domain/calculations/registry/_formula_runtime.py",
        "src/cadrumo/domain/calculations/registry/formula_runtime.py",
    )
    text = (
        'parser = "cadrumo.domain.calculations.registry.parse_export_payload"\n'
        'consumer = "cadrumo.domain.calculations.registry.calculate_registry_snapshot"\n'
    )

    assert _text_reference_owners(
        text,
        candidates=(export, calculation),
        member_owners={
            "parse_export_payload": export.old_path,
            "calculate_registry_snapshot": calculation.old_path,
        },
    ) == {export.old_path, calculation.old_path}


def test_fully_qualified_package_access_and_aliased_registration_keep_exact_provenance() -> None:
    """Package-object spelling and register aliases resolve to the referenced family only."""
    qualified = ast.parse(
        "import cadrumo.domain.calculations.registry\n"
        "cadrumo.domain.calculations.registry.ValidatedRegistryAuthority\n"
    )
    _, qualified_aliases, qualified_members = _python_import_context(
        qualified,
        current_module="application.consumer",
        is_package=False,
    )
    assert _package_attribute_owners(
        qualified,
        aliases=qualified_aliases,
        from_members=qualified_members,
        member_owners={"ValidatedRegistryAuthority": "old-authority"},
    ) == {"old-authority"}

    registration = ast.parse(
        "from registrar import register as enroll\n"
        "from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority as Authority\n"
        "enroll(Authority)\n"
    )
    _, aliases, _ = _python_import_context(
        registration,
        current_module="application.consumer",
        is_package=False,
    )
    call = next(node for node in ast.walk(registration) if isinstance(node, ast.Call))
    references = [census._resolve_import_alias(census._dotted_name(call.func) or "", aliases)]
    references.extend(
        census._resolve_import_alias(reference, aliases)
        for reference in (census._dotted_name(argument) for argument in call.args)
        if reference
    )
    authority = RelocatedFamily(
        100,
        "old-authority",
        "src/cadrumo/domain/calculations/registry/authority.py",
    )
    assert {
        owner
        for reference in references
        if (
            owner := _owner_for_reference(
                reference,
                by_new_module={authority.new_module: authority},
                member_owners={"ValidatedRegistryAuthority": "old-authority"},
            )
        )
    } == {"old-authority"}
    assert (
        _owner_for_reference(
            authority.new_module,
            by_new_module={authority.new_module: authority},
            member_owners={"authority": "wrong-owner"},
        )
        == "old-authority"
    )


def test_reviewed_rows_record_anchored_structured_semantic_evidence() -> None:
    """Each row records owner, competing-site, and substitutability evidence."""
    document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    rows = document["rows"]

    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        evidence = row["semantic_evidence"]
        assert isinstance(evidence, dict)
        assert evidence["anchors"] == {
            "census_root": "current_worktree",
            "relocation_pair": [row["old_path"], row["new_path"]],
        }
        assert isinstance(evidence["owner_definition_locators"], list)
        assert isinstance(evidence["competing_site_census"], dict)
        assert evidence["substitutability"]["result"] == "no_substitutable_c941_owner"


def test_current_measurements_cover_relative_import_and_type_alias_regressions() -> None:
    """The measured relative-import and TypeAlias classes are current-tree derived."""
    document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    measurements = document["evidence_measurements"]

    assert measurements == _evidence_census().measurements
    assert measurements["relative_import_edges"] > 0
    type_alias = getattr(ast, "TypeAlias", None)
    exported_aliases = 0
    for row in document["rows"]:
        tree = ast.parse(_evidence_text(row["new_path"]))
        aliases: set[str] = set()
        for node in tree.body:
            name = getattr(node, "name", None) if type_alias is not None and isinstance(node, type_alias) else None
            if isinstance(name, ast.Name):
                aliases.add(name.id)
        exported_aliases += len(aliases & set(row["facade_exported_symbols"]))
    assert exported_aliases > 0


def test_generation_uses_one_current_tree_snapshot() -> None:
    """The generator snapshots current sources once per process."""
    census._EVIDENCE_FILE_CACHE = None
    census._EVIDENCE_CENSUS_CACHE = None
    assert len(generated_rows()) == 78
    assert census._EVIDENCE_FILE_CACHE is not None
    assert _evidence_text("src/cadrumo/domain/calculations/registry/authority.py")


def test_mechanical_delta_pairs_are_the_checked_matrix_denominator() -> None:
    """The matrix denominator is c941 history, not a current filename scan."""
    document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))

    assert mechanical_relocation_pairs() == tuple((row["old_path"], row["new_path"]) for row in document["rows"])


def test_generated_rows_preserve_one_row_per_exact_c941_candidate() -> None:
    """Every template row remains tied to one historic rename and its derived census."""
    rows = generated_rows()

    assert len(rows) == 78
    assert [row["row_id"] for row in rows] == [f"R{number:02d}" for number in range(1, 79)]
    assert len({(row["old_path"], row["new_path"]) for row in rows}) == 78
    for row in rows:
        consumers = row["consumers"]
        locators = row["current_symbol_locators"]
        exported_symbols = row["facade_exported_symbols"]

        assert isinstance(consumers, dict)
        assert isinstance(locators, dict)
        assert isinstance(exported_symbols, list)
        assert set(consumers) >= {"production", "test", "documentation", "tooling"}
        assert set(locators) == set(exported_symbols)


def test_documented_direct_script_invocation_does_not_shadow_stdlib_types() -> None:
    """The repository-local quality/types.py cannot break direct CLI startup."""
    completed = subprocess.run(  # noqa: S603  # fixed interpreter and repository-owned script
        [sys.executable, str(census.__file__), "--help"],
        cwd=census.ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--refresh-reviewed" in completed.stdout
    assert "--check-current-terminal" not in completed.stdout


def test_reviewed_rows_retain_per_row_rag_and_alternative_owner_evidence() -> None:
    """Every reviewed family row remains independently traceable to its RAG result."""
    document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    rows = document["rows"]

    assert isinstance(rows, list)
    rationales: set[str] = set()
    for row in rows:
        assert isinstance(row, dict)
        result = row["rag_result"]
        assert isinstance(result, dict)
        location = f"{result['path']}:{result['line_start']}"

        assert row["rag_query"].endswith("public defining owner")
        assert result["path"] == row["new_path"]
        assert location in row["alternative_owner_evidence"]
        assert row["semantic_owner"] in row["alternative_owner_evidence"]
        rationale = row["semantic_evidence"]["substitutability"]["rationale"]
        assert row["rag_query"] in rationale
        assert rationale not in rationales
        rationales.add(rationale)


def test_reviewed_matrix_passes_its_exact_census_and_canonical_step_gate() -> None:
    """The checked-in adjudication remains complete and linked to real plan Steps."""
    check_matrix_document(json.loads(MATRIX_PATH.read_text(encoding="utf-8")))


def test_checked_matrix_is_byte_stable() -> None:
    """Check mode verifies the reviewed artifact without rewriting it."""
    before = MATRIX_PATH.read_bytes()

    check_matrix_document(json.loads(before))

    assert MATRIX_PATH.read_bytes() == before


def test_reviewed_refresh_preserves_every_manual_adjudication_field() -> None:
    """A census refresh cannot erase the independently reviewed row decisions."""
    document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    refreshed = refresh_reviewed_matrix_document(document)
    reviewed_fields = {
        "semantic_owner",
        "semantic_evidence",
        "rag_query",
        "rag_result",
        "alternative_owner_evidence",
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
        assert isinstance(before, dict)
        assert isinstance(after, dict)
        assert {field: before[field] for field in reviewed_fields} == {field: after[field] for field in reviewed_fields}


def test_review_validator_rejects_irrelevant_rag_symbol_and_normalized_templates() -> None:
    """A plausible path cannot launder an unrelated symbol or mass-produced prose."""
    document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    row = document["rows"][0]
    original_symbol = row["rag_result"]["symbol"]
    row["rag_result"]["symbol"] = "irrelevant_symbol"
    with pytest.raises(RuntimeError, match="unrelated to its exported symbols"):
        check_matrix_document(document)
    row["rag_result"]["symbol"] = original_symbol

    document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    first, second = document["rows"][:2]
    second["semantic_evidence"]["substitutability"]["rationale"] = first["semantic_evidence"][
        "substitutability"
    ]["rationale"].replace(first["rag_query"], second["rag_query"])
    with pytest.raises(RuntimeError, match=r"normalized rationale template|templated substitutability evidence"):
        check_matrix_document(document)


def test_reviewed_rows_are_one_to_one_complete_and_not_grouped() -> None:
    """Every historical candidate has one reviewed terminal state and one Step."""
    document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    rows = document["rows"]

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
