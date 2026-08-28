"""Regression guard for the retrospective S175 c941 family census."""

from __future__ import annotations

import ast
import json
import subprocess
import sys

import pytest

from ..quality import registry_facade_family_census as census
from ..quality.registry_facade_family_census import (
    DISPOSITIONS,
    MATRIX_PATH,
    RelocatedFamily,
    _annotation_owners,
    _base_category,
    _bound_plan_step,
    _definition_lines,
    _dynamic_import_call,
    _evidence_text,
    _exact_symbol_identity,
    _owner_for_reference,
    _package_attribute_owners,
    _python_import_context,
    _text_reference_owners,
    _transitive_consumer_paths,
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
    document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return cast("dict[str, object]", document)


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
        "import cadrumo.domain.calculations.registry\ncadrumo.domain.calculations.registry.ValidatedRegistryAuthority\n"
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


def _defining_owner_path(row: dict[str, object]) -> str:
    """Return the one path whose source carries this row's reviewed owner.

    A row whose family was already terminally relocated carries its owner at
    the adjudicated destination rather than at the c941 new path, so the
    retired candidate may legitimately be absent from the current tree.
    """
    destinations = row["terminal_destinations"]
    assert isinstance(destinations, list)
    owners = [item["path"] for item in destinations if not item["allowed_absence"]]
    assert len(owners) <= 1
    return str(owners[0]) if owners else str(row["new_path"])


def _adjudicated_paths(row: dict[str, object]) -> set[str]:
    """Return every path this row adjudicates: its c941 path and destinations."""
    destinations = row["terminal_destinations"]
    assert isinstance(destinations, list)
    return {str(row["new_path"])} | {str(item["path"]) for item in destinations}


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
        assert evidence["substitutability"]["result"] == "no_substitutable_owner"


def test_current_measurements_cover_relative_import_and_type_alias_regressions() -> None:
    """The measured relative-import and TypeAlias classes are current-tree derived."""
    document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    measurements = document["evidence_measurements"]

    assert measurements["relative_import_edges"] > 0
    type_alias = getattr(ast, "TypeAlias", None)
    exported_aliases = 0
    for row in document["rows"]:
        owner = _defining_owner_path(row)
        if row.get("disposition") == "delete":
            # A deleted family has no current defining site to measure.
            continue
        tree = ast.parse(_evidence_text(owner))
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


def test_relative_only_import_is_a_direct_production_consumer() -> None:
    """A resolved ``from ..`` edge lands in its direct operational category."""
    relative_consumer = "src/cadrumo/adapters/inbound/declaracion/_parser.py"
    authority_path = "src/cadrumo/domain/calculations/registry/_authority.py"
    source_text = _evidence_text(relative_consumer)
    consumers = _evidence_census().consumers[authority_path]

    # This archive source imports its registry authority relatively, so a
    # text-only candidate sweep cannot identify it as an authority consumer.
    assert "cadrumo.domain.calculations.registry.authority" not in source_text
    assert "cadrumo.domain.calculations.registry._authority" not in source_text
    assert relative_consumer in consumers["production"]
    assert relative_consumer not in consumers["transitive"]


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
    rows = generated_rows()

    assert len(rows) == 78
    assert _evidence_text(exact_relocation_candidates()[0].new_path)
    assert archive_calls
    assert all(call[:4] == ("archive", "--format=tar", EVIDENCE_COMMIT, "--") for call in archive_calls)


def _fresh_semantic_evidence_digest(*, seed: str, cwd: census.Path) -> str:
    """Run the immutable generator in a fresh interpreter from another CWD."""
    program = """
import hashlib
import json
from dev.quality.registry_facade_family_census import generated_rows
payload = [row[\"semantic_evidence\"] for row in generated_rows()]
encoded = json.dumps(payload, ensure_ascii=True, separators=(\",\", \":\"), sort_keys=True).encode()
print(hashlib.sha256(encoded).hexdigest())
"""
    environment = dict(os.environ)
    environment["PYTHONHASHSEED"] = seed
    environment["PYTHONPATH"] = str(census.ROOT)
    completed = subprocess.run(  # noqa: S603  # fixed interpreter and inline immutable-evidence probe
        (sys.executable, "-c", program),
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return completed.stdout.strip()


def test_immutable_semantic_evidence_is_fresh_process_and_foreign_cwd_stable() -> None:
    """Hash randomisation and a non-repository process CWD cannot alter evidence."""
    root_digest = _fresh_semantic_evidence_digest(seed="1", cwd=census.ROOT)
    foreign_cwd_digest = _fresh_semantic_evidence_digest(seed="2", cwd=census.ROOT.parent)

    assert len(root_digest) == 64
    assert root_digest == foreign_cwd_digest


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


def test_reviewed_rows_keep_ast_locators_distinct_from_real_rag_discovery() -> None:
    """Only the two executed semantic searches carry their RAG payloads."""
    document = _document()
    rows = document["rows"]

    assert isinstance(rows, list)
    discovered_pairs = {
        (
            "src/cadrumo/domain/calculations/registry/_aeat_hosts.py",
            "src/cadrumo/domain/calculations/registry/aeat_hosts.py",
        ),
        (
            "src/cadrumo/domain/calculations/registry/_record_spec.py",
            "src/cadrumo/domain/calculations/registry/record_spec.py",
        ),
    }
    actual_discovered_pairs = set()
    for row in rows:
        semantic = row["semantic_evidence"]

        assert isinstance(semantic, dict)
        assert semantic["anchors"]["evidence_commit"] == EVIDENCE_COMMIT
        assert semantic["anchors"]["relocation_pair"] == [row["old_path"], row["new_path"]]
        assert row["semantic_owner"] in row["alternative_owner_evidence"]
        if row["rag_result"] is None:
            assert row["rag_query"] is None
            assert "Vaultspec-RAG" not in row["alternative_owner_evidence"]
            continue
        rag_query = row["rag_query"]
        rag_result = row["rag_result"]
        assert isinstance(rag_query, dict)
        assert isinstance(rag_result, dict)
        assert set(rag_query) == RAG_QUERY_FIELDS
        assert set(rag_result) == RAG_RESULT_FIELDS
        assert rag_query["type"] == "code"
        assert rag_query["domain"] == "prod"
        assert rag_result["source"] == "codebase"
        assert (
            f"{rag_result['path']}:{rag_result['line_start']}-{rag_result['line_end']}"
            in row["alternative_owner_evidence"]
        )
        actual_discovered_pairs.add((row["old_path"], row["new_path"]))

    assert actual_discovered_pairs == discovered_pairs


def test_rag_schema_rejects_an_ast_locator_disguised_as_a_search_result() -> None:
    """RAG record fields cannot be replaced by the immutable AST locator shape."""
    document = deepcopy(_document())
    rows = document["rows"]
    assert isinstance(rows, list)
    target = next(row for row in rows if row["old_path"].endswith("/_aeat_hosts.py"))
    target["rag_result"] = {
        "path": target["new_path"],
        "line_start": 15,
        "line_end": 15,
        "node_type": "ast_top_level_binding",
        "symbol": "REMOTE_READ_SCHEME",
    }

    with pytest.raises(RuntimeError, match="malformed RAG result evidence"):
        check_matrix_document(document)


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
    open_step_ids = report["open_disposition_step_ids"]
    assert isinstance(open_step_ids, list)
    assert len(open_step_ids) == 78


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
        location = f"{result['path']}::{result['symbol']}"

        assert "defining owner" in row["rag_query"]
        assert row["rag_query"].endswith("only:prod")
        # A row's demonstrated definition site may sit outside its own c941
        # path when the historic facade only re-exports the symbol, so the
        # path is proven against the real definition sites in that module
        # rather than against this row's own adjudicated destinations. The
        # earlier disjunct admitted any path that was not the row's own,
        # which an unrelated file satisfied.
        if row.get("disposition") == "delete":
            # A deleted family has no current defining site for its locator to
            # land in; the reviewed record survives as provenance only.
            continue
        assert result["line_start"] in _definition_lines(result["path"], result["symbol"])
        assert location in row["alternative_owner_evidence"]
        assert row["semantic_owner"] in row["alternative_owner_evidence"]
        rationale = row["semantic_evidence"]["substitutability"]["rationale"]
        assert row["rag_query"] in rationale
        assert rationale not in rationales
        rationales.add(rationale)


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
        assert {field: before[field] for field in manual_fields} == {field: after[field] for field in manual_fields}


def test_review_validator_rejects_irrelevant_rag_symbol_and_normalized_templates() -> None:
    """A plausible path cannot launder an unrelated symbol or mass-produced prose."""
    document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    row = document["rows"][0]
    original_symbol = row["rag_result"]["symbol"]
    row["rag_result"]["symbol"] = "irrelevant_symbol"
    row["alternative_owner_evidence"] += f" {row['rag_result']['path']}::irrelevant_symbol"
    row["rag_query"] += " irrelevant_symbol"
    with pytest.raises(RuntimeError, match=r"unrelated to its exported symbols|only re-exports"):
        check_matrix_document(document)
    row["rag_result"]["symbol"] = original_symbol

    document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    first, second = document["rows"][:2]
    template = first["semantic_evidence"]["substitutability"]["rationale"]
    first["semantic_evidence"]["substitutability"]["rationale"] = template.replace(
        first["rag_query"], f"`{first['rag_query']}`"
    )
    second["semantic_evidence"]["substitutability"]["rationale"] = template.replace(
        first["rag_query"], f"`{second['rag_query']}`"
    )
    with pytest.raises(RuntimeError, match=r"normalized rationale template|templated substitutability evidence"):
        check_matrix_document(document)


def test_plan_binding_rejects_an_unrelated_step_that_shares_one_broad_path() -> None:
    """A shared registry path alone cannot make an unrelated plan row authoritative."""
    plan = (
        "- [ ] `W03.P20.S999` - Replace the tax calendar renderer and locale labels; "
        "`src/cadrumo/domain/calculations/registry/authority.py, docs/calendar.md`.\n"
    )

    with pytest.raises(RuntimeError, match=r"scope diverges|action is unrelated"):
        _bound_plan_step(
            "W03.P20.S999",
            "Harden the authority capture comparison domain and generation lifecycle",
            (
                "src/cadrumo/domain/calculations/registry/authority.py, "
                "dev/tests/test_registry_authority_consumer_census.py"
            ),
            plan,
        )


def test_exact_symbol_identity_rejects_wrong_and_ambiguous_definitions() -> None:
    """A same-path wrong symbol or duplicated definition cannot satisfy reviewed evidence."""
    with pytest.raises(RuntimeError, match="does not resolve uniquely"):
        _exact_symbol_identity("src/owner.py", "expected", ["src/owner.py::other"])
    with pytest.raises(RuntimeError, match="does not resolve uniquely"):
        _exact_symbol_identity(
            "src/owner.py",
            "expected",
            ["src/owner.py::expected", "src/owner.py::expected"],
        )


def test_reviewed_rows_are_one_to_one_complete_and_not_grouped() -> None:
    """Every candidate has one disposition, terminal state, and canonical Step."""
    document = _document()
    rows = document["rows"]

    assert all(row["disposition"] in DISPOSITIONS for row in rows)
    assert len(rows) == 78
    assert len({row["follow_on_step_id"] for row in rows}) == 78
    assert all(row["follow_on_predecessors"] == ["W03.P20.S175"] for row in rows)
    assert all("unresolved" not in row["terminal_state"] for row in rows)
    assert all("unresolved" not in row["semantic_owner"] for row in rows)
