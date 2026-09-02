"""Detector teeth for the reviewed object-name rename-manifest authority."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import rtoml
from pydantic import ValidationError

from cadrumo.core.hashing import prefixed_digest

from ...audit.object_names import (
    ObjectNameAuditResult,
    ObjectNameDeclaration,
    ObjectNameFinding,
    ObjectNameFindingKind,
    ObjectNameKind,
    scan,
    to_json,
)
from ..object_name_manifest import (
    ObjectNameManifestError,
    ObjectNameRenameManifest,
    load_object_name_manifest,
    load_validated_object_name_manifest,
    object_name_manifest_digest,
    select_object_name_execution,
    validate_object_name_manifest,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write_source(repo_root: Path, relative: str, source: str) -> Path:
    path = repo_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def _inventory(repo_root: Path, sources: dict[str, str]) -> ObjectNameAuditResult:
    (repo_root / "src").mkdir(parents=True, exist_ok=True)
    (repo_root / "dev").mkdir(parents=True, exist_ok=True)
    for relative, source in sources.items():
        _write_source(repo_root, relative, source)
    return scan((repo_root / "src", repo_root / "dev"), repo_root)


def _finding(inventory: ObjectNameAuditResult, *, name: str, kind: ObjectNameFindingKind) -> ObjectNameFinding:
    return next(item for item in inventory.enforced_findings if item.name == name and item.kind is kind)


def _declaration(
    inventory: ObjectNameAuditResult,
    *,
    name: str,
    kind: ObjectNameKind,
    path: str | None = None,
) -> ObjectNameDeclaration:
    return next(
        item
        for item in inventory.declarations
        if item.name == name and item.kind is kind and (path is None or item.path == path)
    )


def _operation(
    declaration: ObjectNameDeclaration,
    finding: ObjectNameFinding,
    *,
    operation_id: str = "rename-widgets",
    target_name: str = "Widget",
    target_path: str | None = None,
    disposition: str = "lexical-singular",
    lifecycle: str = "reviewed",
) -> dict[str, Any]:
    new_path = target_path or declaration.path
    new_locator = replace(declaration, name=target_name, path=new_path).qualified_locator
    module = declaration.kind is ObjectNameKind.MODULE
    return {
        "operation_id": operation_id,
        "finding_id": finding.id,
        "operation_kind": "module-rename" if module else "symbol-rename",
        "disposition": disposition,
        "lifecycle": lifecycle,
        "old_locator": declaration.qualified_locator,
        "old_path": declaration.path,
        "new_locator": new_locator,
        "new_path": new_path,
        "owner": "dev-quality",
        "rationale": "The singular target states the distinct responsibility.",
        "expected_reference_classes": ("definition",),
        "changed_paths": tuple(sorted({declaration.path, new_path})),
        "generator_commands": (),
        "focused_gates": (("uv", "run", "pytest", "focused.py"),),
        "moves": (({"source": declaration.path, "target": new_path},) if module else ()),
        "preconditions": ({"path": declaration.path, "sha256": declaration.source_hash},),
    }


def _manifest_payload(inventory: ObjectNameAuditResult, *operations: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "inventory_digest": to_json(inventory)["inventory_digest"],
        "operations": tuple(operations),
    }


def _model(inventory: ObjectNameAuditResult, *operations: dict[str, Any]) -> ObjectNameRenameManifest:
    return ObjectNameRenameManifest.model_validate(_manifest_payload(inventory, *operations))


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    serializable = deepcopy(payload)
    for operation in serializable.get("operations", ()):
        moves = operation.pop("moves", ())
        preconditions = operation.pop("preconditions")
        operation["preconditions"] = preconditions
        if moves:
            operation["moves"] = moves
    path.write_text(rtoml.dumps(serializable), encoding="utf-8")


def _symbol_fixture(repo_root: Path) -> tuple[ObjectNameAuditResult, ObjectNameDeclaration, ObjectNameFinding]:
    inventory = _inventory(repo_root, {"src/cadrumo/widget_contract.py": "class Widgets:\n    pass\n"})
    return (
        inventory,
        _declaration(inventory, name="Widgets", kind=ObjectNameKind.CLASS),
        _finding(inventory, name="Widgets", kind=ObjectNameFindingKind.PLURAL),
    )


def _module_fixture(repo_root: Path) -> tuple[ObjectNameAuditResult, ObjectNameDeclaration, ObjectNameFinding]:
    inventory = _inventory(repo_root, {"src/cadrumo/widgets.py": "VALUE = 1\n"})
    return (
        inventory,
        _declaration(inventory, name="widgets", kind=ObjectNameKind.MODULE),
        _finding(inventory, name="widgets", kind=ObjectNameFindingKind.PLURAL),
    )


def test_real_toml_symbol_manifest_loads_and_binds_to_current_bytes(tmp_path: Path) -> None:
    inventory, declaration, finding = _symbol_fixture(tmp_path)
    payload = _manifest_payload(inventory, _operation(declaration, finding))
    manifest_path = tmp_path / "rename.toml"
    _write_manifest(manifest_path, payload)

    manifest = load_validated_object_name_manifest(manifest_path, inventory=inventory, repo_root=tmp_path)

    assert manifest.schema_version == 1
    assert tuple(operation.operation_id for operation in select_object_name_execution(manifest)) == ("rename-widgets",)


def test_real_toml_module_manifest_carries_one_exact_move(tmp_path: Path) -> None:
    inventory, declaration, finding = _module_fixture(tmp_path)
    operation = _operation(
        declaration,
        finding,
        operation_id="rename-widgets-module",
        target_name="widget",
        target_path="src/cadrumo/widget.py",
    )
    manifest_path = tmp_path / "rename.toml"
    _write_manifest(manifest_path, _manifest_payload(inventory, operation))

    manifest = load_validated_object_name_manifest(manifest_path, inventory=inventory, repo_root=tmp_path)

    assert manifest.operations[0].moves[0].source == "src/cadrumo/widgets.py"
    assert manifest.operations[0].moves[0].target == "src/cadrumo/widget.py"


def test_manifest_digest_is_deterministic_and_binds_authored_intent(tmp_path: Path) -> None:
    inventory, declaration, finding = _symbol_fixture(tmp_path)
    assert declaration.source_hash is not None
    manifest = _model(inventory, _operation(declaration, finding))

    first = object_name_manifest_digest(manifest)
    second = object_name_manifest_digest(ObjectNameRenameManifest.model_validate(manifest.model_dump()))

    assert first == second
    assert first == prefixed_digest(
        b'{"inventory_digest":"'
        + manifest.inventory_digest.encode()
        + b'","operations":'
        + b'[{"changed_paths":["src/cadrumo/widget_contract.py"],"disposition":"lexical-singular",'
        + b'"expected_reference_classes":["definition"],"finding_id":"'
        + finding.id.encode()
        + b'","focused_gates":[["uv","run","pytest","focused.py"]],"generator_commands":[],'
        + b'"lifecycle":"reviewed","moves":[],"new_locator":"class:cadrumo.widget_contract.Widget#binding=1",'
        + b'"new_path":"src/cadrumo/widget_contract.py",'
        + b'"old_locator":"class:cadrumo.widget_contract.Widgets#binding=1",'
        + b'"old_path":"src/cadrumo/widget_contract.py","operation_id":"rename-widgets",'
        + b'"operation_kind":"symbol-rename","owner":"dev-quality","preconditions":[{"path":'
        + b'"src/cadrumo/widget_contract.py","sha256":"'
        + declaration.source_hash.encode()
        + b'"}],"rationale":"The singular target states the distinct responsibility."}],"schema_version":1}',
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda payload: payload.update(schema_version="1"), "Input should be 1"),
        (lambda payload: payload.update(unknown=True), "Extra inputs are not permitted"),
        (lambda payload: payload["operations"][0].update(lifecycle=True), "proposed.*reviewed.*retired"),
        (lambda payload: payload["operations"][0].update(operation_id="Bad_Id"), "String should match pattern"),
    ),
)
def test_loader_refuses_strict_schema_coercion_and_unknown_fields(
    tmp_path: Path,
    mutation: Any,
    message: str,
) -> None:
    inventory, declaration, finding = _symbol_fixture(tmp_path)
    payload = deepcopy(_manifest_payload(inventory, _operation(declaration, finding)))
    mutation(payload)
    manifest_path = tmp_path / "rename.toml"
    _write_manifest(manifest_path, payload)

    with pytest.raises(ObjectNameManifestError, match=message):
        load_object_name_manifest(manifest_path)


def test_loader_refuses_prohibited_keep_distinct_disposition(tmp_path: Path) -> None:
    inventory, declaration, finding = _symbol_fixture(tmp_path)
    operation = _operation(declaration, finding, disposition="keep-distinct")

    with pytest.raises(ValidationError, match=r"lexical-singular.*rename-distinct.*merge-authority"):
        _model(inventory, operation)


def test_loader_refuses_linked_manifest(tmp_path: Path) -> None:
    inventory, declaration, finding = _symbol_fixture(tmp_path)
    real_manifest = tmp_path / "real.toml"
    _write_manifest(real_manifest, _manifest_payload(inventory, _operation(declaration, finding)))
    linked_manifest = tmp_path / "linked.toml"
    try:
        linked_manifest.symlink_to(real_manifest)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")

    with pytest.raises(ObjectNameManifestError, match="regular file"):
        load_object_name_manifest(linked_manifest)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("old_path", "../escape.py"),
        ("old_path", "/src/cadrumo/widget_contract.py"),
        ("old_path", "C:/src/cadrumo/widget_contract.py"),
        ("old_path", "src\\cadrumo\\widget_contract.py"),
        ("old_path", "docs/widget_contract.py"),
        ("changed_paths", (".git/config", "src/cadrumo/widget_contract.py")),
        ("changed_paths", ("src/cadrumo/../escape.py", "src/cadrumo/widget_contract.py")),
    ),
)
def test_model_refuses_hostile_or_noncanonical_paths(tmp_path: Path, field: str, value: object) -> None:
    inventory, declaration, finding = _symbol_fixture(tmp_path)
    operation = _operation(declaration, finding)
    operation[field] = value

    with pytest.raises(ValidationError, match=r"normalized repository-relative POSIX path|below src/ or dev/|metadata"):
        _model(inventory, operation)


def test_manifest_allows_multiple_operations_for_one_collision_with_one_disposition(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {
            "src/cadrumo/alpha.py": "class Widget:\n    pass\n",
            "src/cadrumo/beta.py": "class Widget:\n    pass\n",
            "src/cadrumo/gamma.py": "class Widget:\n    pass\n",
        },
    )
    finding = _finding(inventory, name="Widget", kind=ObjectNameFindingKind.DUPLICATE)
    alpha = _declaration(inventory, name="Widget", kind=ObjectNameKind.CLASS, path="src/cadrumo/alpha.py")
    beta = _declaration(inventory, name="Widget", kind=ObjectNameKind.CLASS, path="src/cadrumo/beta.py")
    operations = (
        _operation(
            alpha, finding, operation_id="rename-alpha", target_name="AlphaWidget", disposition="rename-distinct"
        ),
        _operation(beta, finding, operation_id="rename-beta", target_name="BetaWidget", disposition="rename-distinct"),
    )

    manifest = _model(inventory, *operations)

    assert validate_object_name_manifest(manifest, inventory=inventory, repo_root=tmp_path) is manifest
    assert len(select_object_name_execution(manifest)) == 2


@pytest.mark.parametrize(
    ("mutate", "message"),
    (
        (
            lambda operations: operations[1].update(operation_id="rename-alpha"),
            "operation ids must be sorted and unique",
        ),
        (lambda operations: operations[1].update(old_locator=operations[0]["old_locator"]), "source locator"),
        (lambda operations: operations[1].update(new_locator=operations[0]["new_locator"]), "target locators"),
        (lambda operations: operations[1].update(disposition="lexical-singular"), "one disposition"),
    ),
)
def test_manifest_refuses_ambiguous_or_conflicting_operation_claims(
    tmp_path: Path,
    mutate: Any,
    message: str,
) -> None:
    inventory = _inventory(
        tmp_path,
        {
            "src/cadrumo/alpha.py": "class Widget:\n    pass\n",
            "src/cadrumo/beta.py": "class Widget:\n    pass\n",
        },
    )
    finding = _finding(inventory, name="Widget", kind=ObjectNameFindingKind.DUPLICATE)
    operations = [
        _operation(
            _declaration(inventory, name="Widget", kind=ObjectNameKind.CLASS, path="src/cadrumo/alpha.py"),
            finding,
            operation_id="rename-alpha",
            target_name="AlphaWidget",
            disposition="rename-distinct",
        ),
        _operation(
            _declaration(inventory, name="Widget", kind=ObjectNameKind.CLASS, path="src/cadrumo/beta.py"),
            finding,
            operation_id="rename-beta",
            target_name="BetaWidget",
            disposition="rename-distinct",
        ),
    ]
    mutate(operations)

    with pytest.raises(ValidationError, match=message):
        _model(inventory, *operations)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda operation: operation.update(lifecycle="proposed"), "reviewed lifecycle"),
        (lambda operation: operation.update(new_locator=None), "require new_locator"),
        (lambda operation: operation.update(new_locator=operation["old_locator"]), "locator must change"),
        (lambda operation: operation.update(operation_kind="module-rename"), "module locators"),
        (lambda operation: operation.update(new_path="src/cadrumo/other.py"), "stay in one file"),
        (lambda operation: operation.update(expected_reference_classes=()), "at least 1 item"),
        (lambda operation: operation.update(changed_paths=("docs/generated.md",)), "include every rename"),
    ),
)
def test_symbol_operation_shape_and_lifecycle_are_fail_closed(
    tmp_path: Path,
    mutation: Any,
    message: str,
) -> None:
    inventory, declaration, finding = _symbol_fixture(tmp_path)
    operation = _operation(declaration, finding)
    mutation(operation)

    with pytest.raises(ValidationError, match=message):
        _model(inventory, operation)


def test_merge_authority_is_retained_for_adjudication_but_never_selected(tmp_path: Path) -> None:
    inventory, declaration, finding = _symbol_fixture(tmp_path)
    operation = _operation(declaration, finding, disposition="merge-authority", lifecycle="proposed")
    operation.update(new_locator=None, new_path=None, moves=())
    manifest = _model(inventory, operation)

    assert validate_object_name_manifest(manifest, inventory=inventory, repo_root=tmp_path) is manifest
    assert select_object_name_execution(manifest) == ()


def test_validator_refuses_stale_inventory_finding_locator_and_advisory_selection(tmp_path: Path) -> None:
    inventory, declaration, finding = _symbol_fixture(tmp_path)
    operation = _operation(declaration, finding)

    stale_inventory = _model(inventory, operation).model_copy(update={"inventory_digest": "sha256:" + "0" * 64})
    with pytest.raises(ObjectNameManifestError, match="inventory is stale"):
        validate_object_name_manifest(stale_inventory, inventory=inventory, repo_root=tmp_path)

    unknown_finding = deepcopy(operation)
    unknown_finding["finding_id"] = "sha256:" + "1" * 64
    with pytest.raises(ObjectNameManifestError, match="stale or unknown finding"):
        validate_object_name_manifest(_model(inventory, unknown_finding), inventory=inventory, repo_root=tmp_path)

    wrong_locator = deepcopy(operation)
    wrong_locator["old_locator"] = replace(declaration, binding_occurrence=2).qualified_locator
    with pytest.raises(ObjectNameManifestError, match="not a site"):
        validate_object_name_manifest(_model(inventory, wrong_locator), inventory=inventory, repo_root=tmp_path)

    advisory = replace(finding, enforced=False)
    advisory_inventory = ObjectNameAuditResult(inventory.declarations, (advisory,))
    advisory_operation = deepcopy(operation)
    advisory_operation["finding_id"] = advisory.id
    advisory_manifest = _model(advisory_inventory, advisory_operation)
    with pytest.raises(ObjectNameManifestError, match="selects an advisory finding"):
        validate_object_name_manifest(advisory_manifest, inventory=advisory_inventory, repo_root=tmp_path)


def test_validator_refuses_stale_source_and_affected_file_bytes(tmp_path: Path) -> None:
    inventory, declaration, finding = _symbol_fixture(tmp_path)
    support = _write_source(tmp_path, "docs/consumer.md", "Widgets\n")
    operation = _operation(declaration, finding)
    operation["changed_paths"] = ("docs/consumer.md", declaration.path)
    operation["preconditions"] = (
        {"path": "docs/consumer.md", "sha256": f"sha256:{prefixed_digest(support.read_bytes()).split(':', 1)[1]}"},
        operation["preconditions"][0],
    )
    manifest = _model(inventory, operation)
    validate_object_name_manifest(manifest, inventory=inventory, repo_root=tmp_path)

    support.write_text("changed\n", encoding="utf-8")
    with pytest.raises(ObjectNameManifestError, match="byte precondition is stale"):
        validate_object_name_manifest(manifest, inventory=inventory, repo_root=tmp_path)

    source = tmp_path / declaration.path
    source.write_text("class Widgets:\n    changed = True\n", encoding="utf-8")
    with pytest.raises(ObjectNameManifestError, match="byte precondition is stale"):
        validate_object_name_manifest(
            _model(inventory, _operation(declaration, finding)), inventory=inventory, repo_root=tmp_path
        )


def test_validator_refuses_existing_name_and_module_path_targets(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {"src/cadrumo/widget_contract.py": "class Widgets:\n    pass\n\nclass Widget:\n    pass\n"},
    )
    plural = _finding(inventory, name="Widgets", kind=ObjectNameFindingKind.PLURAL)
    source = _declaration(inventory, name="Widgets", kind=ObjectNameKind.CLASS)
    with pytest.raises(ObjectNameManifestError, match="targets already exist"):
        validate_object_name_manifest(
            _model(inventory, _operation(source, plural)), inventory=inventory, repo_root=tmp_path
        )

    module_inventory, module, module_finding = _module_fixture(tmp_path / "module")
    occupied = _write_source(tmp_path / "module", "src/cadrumo/widget.py", "VALUE = 2\n")
    assert occupied.is_file()
    module_operation = _operation(
        module,
        module_finding,
        operation_id="rename-widgets-module",
        target_name="widget",
        target_path="src/cadrumo/widget.py",
    )
    module_operation["preconditions"] = (
        {"path": "src/cadrumo/widget.py", "sha256": prefixed_digest(occupied.read_bytes())},
        *module_operation["preconditions"],
    )
    with pytest.raises(ObjectNameManifestError, match="module target already exists"):
        validate_object_name_manifest(
            _model(module_inventory, module_operation),
            inventory=module_inventory,
            repo_root=tmp_path / "module",
        )


def test_module_move_without_name_change_is_refused(tmp_path: Path) -> None:
    inventory, declaration, finding = _module_fixture(tmp_path)
    operation = _operation(
        declaration,
        finding,
        operation_id="move-without-rename",
        target_name="widgets",
        target_path="src/other/widgets.py",
    )

    with pytest.raises(ObjectNameManifestError, match="must change the audited object name"):
        validate_object_name_manifest(_model(inventory, operation), inventory=inventory, repo_root=tmp_path)


@pytest.mark.parametrize(
    "new_locator",
    (
        "class:cadrumo.other.Widget#binding=1",
        "class:cadrumo.widget_contract.Widget#binding=2",
    ),
)
def test_validator_refuses_symbol_target_locator_disagreement(tmp_path: Path, new_locator: str) -> None:
    inventory, declaration, finding = _symbol_fixture(tmp_path)
    operation = _operation(declaration, finding)
    operation["new_locator"] = new_locator

    with pytest.raises(ObjectNameManifestError, match="target path and locator disagree"):
        validate_object_name_manifest(_model(inventory, operation), inventory=inventory, repo_root=tmp_path)


def test_validator_refuses_module_package_mismatch_and_non_python_target(tmp_path: Path) -> None:
    inventory, declaration, finding = _module_fixture(tmp_path)
    mismatched = _operation(
        declaration,
        finding,
        operation_id="rename-widgets-module",
        target_name="widget",
        target_path="src/cadrumo/widget.py",
    )
    mismatched["new_locator"] = "module:cadrumo.other#binding=1"
    with pytest.raises(ObjectNameManifestError, match="target path and locator disagree"):
        validate_object_name_manifest(_model(inventory, mismatched), inventory=inventory, repo_root=tmp_path)

    non_python = _operation(
        declaration,
        finding,
        operation_id="rename-widgets-module",
        target_name="widget",
        target_path="src/cadrumo/widget.txt",
    )
    with pytest.raises(ValidationError, match="Python source files"):
        _model(inventory, non_python)


def test_validator_refuses_symlinked_affected_path_component(tmp_path: Path) -> None:
    inventory, declaration, finding = _symbol_fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = tmp_path / "docs"
    try:
        linked.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    operation = _operation(declaration, finding)
    operation["changed_paths"] = ("docs/consumer.md", declaration.path)

    with pytest.raises(ObjectNameManifestError, match="link-like component"):
        validate_object_name_manifest(_model(inventory, operation), inventory=inventory, repo_root=tmp_path)


@pytest.mark.parametrize(
    ("references", "commands", "message"),
    (
        (("definition", "generated-artifact"), (), "declared together"),
        (("definition",), (("uv", "run", "generator"),), "declared together"),
        (("definition", "generated-artifact"), ((),), "non-empty argv"),
        (("definition", "generated-artifact"), (("",),), "non-empty argv"),
    ),
)
def test_generated_artifact_owner_and_argv_contracts(
    tmp_path: Path,
    references: tuple[str, ...],
    commands: tuple[tuple[str, ...], ...],
    message: str,
) -> None:
    inventory, declaration, finding = _symbol_fixture(tmp_path)
    operation = _operation(declaration, finding)
    operation["expected_reference_classes"] = references
    operation["generator_commands"] = commands

    with pytest.raises(ValidationError, match=message):
        _model(inventory, operation)


def test_generated_artifact_with_explicit_argv_is_valid(tmp_path: Path) -> None:
    inventory, declaration, finding = _symbol_fixture(tmp_path)
    operation = _operation(declaration, finding)
    operation["expected_reference_classes"] = ("definition", "generated-artifact")
    operation["generator_commands"] = (("uv", "run", "python", "-m", "dev.docs.apidocs.manager"),)

    manifest = _model(inventory, operation)

    assert validate_object_name_manifest(manifest, inventory=inventory, repo_root=tmp_path) is manifest
