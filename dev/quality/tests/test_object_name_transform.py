"""Detector teeth for bounded object-name transformation proposals."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from ...audit.object_names import ObjectNameAuditResult, ObjectNameDeclaration, ObjectNameKind, scan, to_json
from ..object_name_manifest import ObjectNameRenameManifest
from ..object_name_transform import ObjectNameTransformError, plan_object_name_transformation

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write_source(repo_root: Path, relative: str, source: str) -> None:
    path = repo_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(source.encode("utf-8"))


def _inventory(repo_root: Path, sources: dict[str, str]) -> ObjectNameAuditResult:
    (repo_root / "src").mkdir(parents=True, exist_ok=True)
    (repo_root / "dev").mkdir(parents=True, exist_ok=True)
    for relative, source in sources.items():
        _write_source(repo_root, relative, source)
    return scan((repo_root / "src", repo_root / "dev"), repo_root)


def _declaration(
    inventory: ObjectNameAuditResult, *, path: str, name: str, occurrence: int = 1
) -> ObjectNameDeclaration:
    return next(
        item
        for item in inventory.declarations
        if item.path == path and item.name == name and item.binding_occurrence == occurrence
    )


def _digest(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _tree_bytes(repo_root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(repo_root).as_posix(): path.read_bytes()
        for root in (repo_root / "src", repo_root / "dev")
        for path in root.rglob("*")
        if path.is_file()
    }


def _operation(
    declaration: ObjectNameDeclaration,
    *,
    target_name: str,
    sources: dict[str, bytes],
    changed_paths: tuple[str, ...] | None = None,
    expected_reference_classes: tuple[str, ...] = ("definition", "static-import"),
    target_path: str | None = None,
) -> dict[str, Any]:
    module = declaration.kind is ObjectNameKind.MODULE
    new_path = target_path or declaration.path
    new_locator = replace(declaration, name=target_name, path=new_path).qualified_locator
    reviewed_paths = changed_paths or tuple(sorted({declaration.path, new_path, *sources}))
    return {
        "operation_id": f"rename-{declaration.name.lower()}-{declaration.binding_occurrence}",
        "finding_id": f"sha256:{'1' * 64}",
        "operation_kind": "module-rename" if module else "symbol-rename",
        "disposition": "lexical-singular",
        "lifecycle": "reviewed",
        "old_locator": declaration.qualified_locator,
        "old_path": declaration.path,
        "new_locator": new_locator,
        "new_path": new_path,
        "owner": "dev-quality",
        "rationale": "Use one exact singular object name.",
        "preconditions": tuple({"path": path, "sha256": _digest(payload)} for path, payload in sorted(sources.items())),
        "expected_reference_classes": expected_reference_classes,
        "moves": (({"source": declaration.path, "target": new_path},) if module else ()),
        "changed_paths": reviewed_paths,
        "generator_commands": (("just", "generate"),) if "generated-artifact" in expected_reference_classes else (),
        "focused_gates": (("uv", "run", "pytest", "focused.py"),),
    }


def _manifest(inventory: ObjectNameAuditResult, operation: dict[str, Any]) -> ObjectNameRenameManifest:
    return ObjectNameRenameManifest.model_validate(
        {"schema_version": 1, "inventory_digest": to_json(inventory)["inventory_digest"], "operations": (operation,)}
    )


def test_symbol_proposal_renames_definition_import_alias_qualified_and_local_references(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {
            "src/cadrumo/widget_contract.py": (
                "class Widgets:\n    pass\n\ndef build() -> Widgets:\n    return Widgets()\n"
            ),
            "dev/consumer.py": (
                "import cadrumo.widget_contract as contract\n"
                "from cadrumo.widget_contract import Widgets as ImportedWidgets\n\n"
                "value = contract.Widgets()\nother = ImportedWidgets()\n"
            ),
        },
    )
    sources = _tree_bytes(tmp_path)
    declaration = _declaration(inventory, path="src/cadrumo/widget_contract.py", name="Widgets")
    manifest = _manifest(inventory, _operation(declaration, target_name="Widget", sources=sources))
    before = _tree_bytes(tmp_path)

    result = plan_object_name_transformation(manifest, repo_root=tmp_path)

    assert result.changed_paths == ("dev/consumer.py", "src/cadrumo/widget_contract.py")
    assert result.content_by_path() == {
        "dev/consumer.py": (
            b"import cadrumo.widget_contract as contract\n"
            b"from cadrumo.widget_contract import Widget as ImportedWidgets\n\n"
            b"value = contract.Widget()\nother = ImportedWidgets()\n"
        ),
        "src/cadrumo/widget_contract.py": (b"class Widget:\n    pass\n\ndef build() -> Widget:\n    return Widget()\n"),
    }
    assert result.moves == ()
    assert _tree_bytes(tmp_path) == before


def test_module_proposal_returns_exact_move_and_rewrites_import_forms_without_mutation(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {
            "src/cadrumo/widgets.py": "VALUE = 1\n",
            "dev/consumer.py": (
                "import cadrumo.widgets\nimport cadrumo.widgets as source\nfrom cadrumo import widgets as alias\n"
                "value = cadrumo.widgets.VALUE + source.VALUE + alias.VALUE\n"
            ),
        },
    )
    sources = _tree_bytes(tmp_path)
    declaration = _declaration(inventory, path="src/cadrumo/widgets.py", name="widgets")
    operation = _operation(
        declaration,
        target_name="widget",
        target_path="src/cadrumo/widget.py",
        sources=sources,
        changed_paths=("dev/consumer.py", "src/cadrumo/widget.py", "src/cadrumo/widgets.py"),
    )
    before = _tree_bytes(tmp_path)

    result = plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)

    assert result.changed_paths == ("dev/consumer.py", "src/cadrumo/widget.py", "src/cadrumo/widgets.py")
    assert result.moves[0].source == "src/cadrumo/widgets.py"
    assert result.moves[0].target == "src/cadrumo/widget.py"
    assert result.content_by_path()["src/cadrumo/widgets.py"] is None
    assert result.content_by_path()["src/cadrumo/widget.py"] == b"VALUE = 1\n"
    assert result.content_by_path()["dev/consumer.py"] == (
        b"import cadrumo.widget\nimport cadrumo.widget as source\nfrom cadrumo import widget as alias\n"
        b"value = cadrumo.widget.VALUE + source.VALUE + alias.VALUE\n"
    )
    assert _tree_bytes(tmp_path) == before
    outputs = {output.path: output for output in result.outputs}
    assert outputs["src/cadrumo/widgets.py"].original_sha256 == _digest(b"VALUE = 1\n")
    assert outputs["src/cadrumo/widgets.py"].content is None
    assert outputs["src/cadrumo/widget.py"].original_sha256 is None
    assert _digest(outputs["src/cadrumo/widget.py"].content or b"") == _digest(b"VALUE = 1\n")


def test_same_package_module_move_preserves_relative_import(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {
            "src/cadrumo/old/widgets.py": "from .support import VALUE\n",
            "src/cadrumo/old/support.py": "VALUE = 1\n",
            "src/cadrumo/old/consumer.py": "from .widgets import VALUE\n",
        },
    )
    declaration = _declaration(inventory, path="src/cadrumo/old/widgets.py", name="widgets")
    operation = _operation(
        declaration,
        target_name="widget",
        target_path="src/cadrumo/old/widget.py",
        sources={
            declaration.path: (tmp_path / declaration.path).read_bytes(),
            "src/cadrumo/old/consumer.py": (tmp_path / "src/cadrumo/old/consumer.py").read_bytes(),
        },
        changed_paths=(
            "src/cadrumo/old/consumer.py",
            "src/cadrumo/old/widget.py",
            "src/cadrumo/old/widgets.py",
        ),
    )

    result = plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)

    assert result.content_by_path()["src/cadrumo/old/widget.py"] == b"from .support import VALUE\n"
    assert result.content_by_path()["src/cadrumo/old/consumer.py"] == b"from .widget import VALUE\n"


def test_cross_package_module_move_preserves_absolute_import(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {
            "src/cadrumo/old/widgets.py": "from cadrumo.support import VALUE\n",
            "src/cadrumo/support.py": "VALUE = 1\n",
        },
    )
    declaration = _declaration(inventory, path="src/cadrumo/old/widgets.py", name="widgets")
    operation = _operation(
        declaration,
        target_name="widget",
        target_path="src/cadrumo/new/widget.py",
        sources={declaration.path: (tmp_path / declaration.path).read_bytes()},
        changed_paths=("src/cadrumo/new/widget.py", "src/cadrumo/old/widgets.py"),
        expected_reference_classes=("definition",),
    )

    result = plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)

    assert result.content_by_path()["src/cadrumo/new/widget.py"] == b"from cadrumo.support import VALUE\n"


def test_locator_renames_only_the_selected_distinct_declaration(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {"src/cadrumo/contracts.py": "class Widgets:\n    pass\n\nclass Other:\n    pass\n"},
    )
    sources = _tree_bytes(tmp_path)
    declaration = _declaration(inventory, path="src/cadrumo/contracts.py", name="Widgets")
    operation = _operation(
        declaration,
        target_name="Widget",
        sources=sources,
        expected_reference_classes=("definition",),
    )

    result = plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)

    assert result.content_by_path()[declaration.path] == b"class Widget:\n    pass\n\nclass Other:\n    pass\n"


@pytest.mark.parametrize("reference_class", ["generated-artifact"])
def test_unsupported_reference_class_is_refused(tmp_path: Path, reference_class: str) -> None:
    inventory = _inventory(tmp_path, {"src/cadrumo/contracts.py": "class Widgets:\n    pass\n"})
    declaration = _declaration(inventory, path="src/cadrumo/contracts.py", name="Widgets")
    operation = _operation(
        declaration,
        target_name="Widget",
        sources=_tree_bytes(tmp_path),
        expected_reference_classes=("definition", reference_class),
    )

    with pytest.raises(ObjectNameTransformError, match="unsupported reference classes"):
        plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)


@pytest.mark.parametrize(
    ("consumer", "message"),
    [
        ("from cadrumo.widgets import *\n", "unsupported star import"),
        ("target = f'cadrumo.widgets'\n", "unsupported string reference"),
    ],
)
def test_opaque_or_star_module_reference_is_refused(tmp_path: Path, consumer: str, message: str) -> None:
    inventory = _inventory(
        tmp_path,
        {"src/cadrumo/widgets.py": "VALUE = 1\n", "dev/consumer.py": consumer},
    )
    declaration = _declaration(inventory, path="src/cadrumo/widgets.py", name="widgets")
    operation = _operation(
        declaration,
        target_name="widget",
        target_path="src/cadrumo/widget.py",
        sources=_tree_bytes(tmp_path),
        changed_paths=("dev/consumer.py", "src/cadrumo/widget.py", "src/cadrumo/widgets.py"),
    )

    with pytest.raises(ObjectNameTransformError, match=message):
        plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)


def test_exact_module_string_target_is_renamed_and_classified(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {"src/cadrumo/widgets.py": "VALUE = 1\n", "dev/consumer.py": "target = 'cadrumo.widgets'\n"},
    )
    declaration = _declaration(inventory, path="src/cadrumo/widgets.py", name="widgets")
    operation = _operation(
        declaration,
        target_name="widget",
        target_path="src/cadrumo/widget.py",
        sources=_tree_bytes(tmp_path),
        expected_reference_classes=("definition", "dynamic-target"),
        changed_paths=("dev/consumer.py", "src/cadrumo/widget.py", "src/cadrumo/widgets.py"),
    )

    result = plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)

    assert result.content_by_path()["dev/consumer.py"] == b"target = 'cadrumo.widget'\n"


def test_near_match_module_string_remains_unsupported(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {"src/cadrumo/widgets.py": "VALUE = 1\n", "dev/consumer.py": "target = 'load cadrumo.widgets'\n"},
    )
    declaration = _declaration(inventory, path="src/cadrumo/widgets.py", name="widgets")
    operation = _operation(
        declaration,
        target_name="widget",
        target_path="src/cadrumo/widget.py",
        sources=_tree_bytes(tmp_path),
        changed_paths=("dev/consumer.py", "src/cadrumo/widget.py", "src/cadrumo/widgets.py"),
    )

    with pytest.raises(ObjectNameTransformError, match="unsupported string reference"):
        plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)


def test_cross_package_move_with_relative_import_is_refused(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {"src/cadrumo/old/widgets.py": "from .helper import VALUE\n", "src/cadrumo/old/helper.py": "VALUE = 1\n"},
    )
    declaration = _declaration(inventory, path="src/cadrumo/old/widgets.py", name="widgets")
    operation = _operation(
        declaration,
        target_name="widget",
        target_path="src/cadrumo/new/widget.py",
        sources={declaration.path: (tmp_path / declaration.path).read_bytes()},
        changed_paths=tuple(sorted((declaration.path, "src/cadrumo/new/widget.py"))),
    )

    with pytest.raises(ObjectNameTransformError, match="moves relative-import source across packages"):
        plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)


def test_ambiguous_qualified_symbol_reference_is_refused(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {
            "src/cadrumo/contracts.py": "class Widgets:\n    pass\n",
            "dev/consumer.py": (
                "from cadrumo.contracts import Widgets\nif flag:\n    Widgets = object\nvalue = Widgets()\n"
            ),
        },
    )
    declaration = _declaration(inventory, path="src/cadrumo/contracts.py", name="Widgets")
    operation = _operation(declaration, target_name="Widget", sources=_tree_bytes(tmp_path))

    with pytest.raises(ObjectNameTransformError, match="ambiguous qualified name reference"):
        plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)


def test_unparseable_affected_source_is_refused(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, {"src/cadrumo/contracts.py": "class Widgets:\n    pass\n"})
    declaration = _declaration(inventory, path="src/cadrumo/contracts.py", name="Widgets")
    sources = _tree_bytes(tmp_path)
    _write_source(tmp_path, "dev/broken.py", "def broken(:\n")
    broken = (tmp_path / "dev/broken.py").read_bytes()
    operation = _operation(
        declaration,
        target_name="Widget",
        sources={**sources, "dev/broken.py": broken},
        changed_paths=("dev/broken.py", declaration.path),
    )

    with pytest.raises(ObjectNameTransformError, match="cannot parse affected Python source"):
        plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)


def test_stale_byte_precondition_is_refused_before_proposal(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, {"src/cadrumo/contracts.py": "class Widgets:\n    pass\n"})
    declaration = _declaration(inventory, path="src/cadrumo/contracts.py", name="Widgets")
    manifest = _manifest(inventory, _operation(declaration, target_name="Widget", sources=_tree_bytes(tmp_path)))
    _write_source(tmp_path, declaration.path, "class Widgets:\n    changed = True\n")

    with pytest.raises(ObjectNameTransformError, match="byte precondition is stale"):
        plan_object_name_transformation(manifest, repo_root=tmp_path)


def test_unsafe_precondition_path_and_link_component_are_refused(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, {"src/cadrumo/contracts.py": "class Widgets:\n    pass\n"})
    declaration = _declaration(inventory, path="src/cadrumo/contracts.py", name="Widgets")
    operation = _operation(declaration, target_name="Widget", sources=_tree_bytes(tmp_path))
    operation["preconditions"] = ({"path": "../outside.py", "sha256": _digest(b"")},)
    with pytest.raises(ValueError, match="normalized repository-relative"):
        _manifest(inventory, operation)

    outside = tmp_path / "outside"
    outside.mkdir()
    linked = tmp_path / "linked"
    try:
        linked.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    linked_source = b"value = 1\n"
    (outside / "consumer.py").write_bytes(linked_source)
    sources = _tree_bytes(tmp_path) | {"linked/consumer.py": linked_source}
    operation = _operation(
        declaration,
        target_name="Widget",
        sources=sources,
        changed_paths=("linked/consumer.py", declaration.path),
    )
    with pytest.raises(ObjectNameTransformError, match="link-like component"):
        plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)


def test_occupied_module_target_is_refused(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {"src/cadrumo/widgets.py": "VALUE = 1\n", "src/cadrumo/widget.py": "VALUE = 2\n"},
    )
    declaration = _declaration(inventory, path="src/cadrumo/widgets.py", name="widgets")
    operation = _operation(
        declaration,
        target_name="widget",
        target_path="src/cadrumo/widget.py",
        sources={declaration.path: (tmp_path / declaration.path).read_bytes()},
    )

    with pytest.raises(ObjectNameTransformError, match="move target already exists"):
        plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)


def test_changed_path_allowlist_mismatch_is_refused(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, {"src/cadrumo/contracts.py": "class Widgets:\n    pass\n"})
    declaration = _declaration(inventory, path="src/cadrumo/contracts.py", name="Widgets")
    operation = _operation(
        declaration,
        target_name="Widget",
        sources=_tree_bytes(tmp_path),
        changed_paths=tuple(sorted((declaration.path, "dev/reviewed_but_unchanged.py"))),
        expected_reference_classes=("definition",),
    )

    with pytest.raises(ObjectNameTransformError, match="proposed changed paths differ from the reviewed allowlist"):
        plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)


def test_proposal_is_deterministic_read_only_and_returns_fresh_content_views(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, {"src/cadrumo/contracts.py": "class Widgets:\n    pass\n"})
    declaration = _declaration(inventory, path="src/cadrumo/contracts.py", name="Widgets")
    manifest = _manifest(
        inventory,
        _operation(
            declaration,
            target_name="Widget",
            sources=_tree_bytes(tmp_path),
            expected_reference_classes=("definition",),
        ),
    )
    before = _tree_bytes(tmp_path)

    first = plan_object_name_transformation(manifest, repo_root=tmp_path)
    second = plan_object_name_transformation(manifest, repo_root=tmp_path)
    mutable_view = first.content_by_path()
    assert isinstance(mutable_view, dict)
    mutable_view.clear()

    assert first == second
    assert first.content_by_path() == {declaration.path: b"class Widget:\n    pass\n"}
    assert _tree_bytes(tmp_path) == before


def test_overload_family_is_renamed_as_one_binding(tmp_path: Path) -> None:
    source = (
        "from typing import overload\n\n"
        "@overload\ndef widgets(value: int) -> int: ...\n"
        "@overload\ndef widgets(value: str) -> str: ...\n"
        "def widgets(value: object) -> object:\n    return value\n"
    )
    inventory = _inventory(tmp_path, {"src/cadrumo/contracts.py": source})
    declarations = [item for item in inventory.declarations if item.name == "widgets"]
    assert len(declarations) == 3
    assert {item.qualified_locator for item in declarations} == {declarations[0].qualified_locator}
    operation = _operation(
        declarations[0],
        target_name="widget",
        sources=_tree_bytes(tmp_path),
        expected_reference_classes=("definition",),
    )

    result = plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)

    assert result.content_by_path()[declarations[0].path] == source.replace("widgets", "widget").encode()


def test_repeated_binding_with_unprovable_reference_is_refused(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {"src/cadrumo/contracts.py": "class Widgets:\n    pass\n\nvalue = Widgets()\n\nclass Widgets:\n    pass\n"},
    )
    declaration = _declaration(inventory, path="src/cadrumo/contracts.py", name="Widgets", occurrence=1)
    operation = _operation(
        declaration,
        target_name="Widget",
        sources=_tree_bytes(tmp_path),
        expected_reference_classes=("definition",),
    )

    with pytest.raises(ObjectNameTransformError, match="reference across ambiguous rebindings"):
        plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)


def test_repeated_binding_without_reference_renames_only_selected_declaration(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {"src/cadrumo/contracts.py": "class Widgets:\n    pass\n\nclass Widgets:\n    pass\n"},
    )
    declaration = _declaration(inventory, path="src/cadrumo/contracts.py", name="Widgets", occurrence=1)
    operation = _operation(
        declaration,
        target_name="Widget",
        sources=_tree_bytes(tmp_path),
        expected_reference_classes=("definition",),
    )

    result = plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)

    assert result.content_by_path()[declaration.path] == b"class Widget:\n    pass\n\nclass Widgets:\n    pass\n"


def test_ambiguous_qualified_attribute_reference_is_refused(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {
            "src/cadrumo/contracts.py": "class Widgets:\n    pass\n",
            "dev/consumer.py": (
                "import cadrumo.contracts as contract\nif flag:\n    contract = fallback\nvalue = contract.Widgets()\n"
            ),
        },
    )
    declaration = _declaration(inventory, path="src/cadrumo/contracts.py", name="Widgets")
    operation = _operation(declaration, target_name="Widget", sources=_tree_bytes(tmp_path))

    with pytest.raises(ObjectNameTransformError, match="ambiguous qualified attribute reference"):
        plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)


def test_declared_reference_class_must_have_actual_evidence(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, {"src/cadrumo/contracts.py": "class Widgets:\n    pass\n"})
    declaration = _declaration(inventory, path="src/cadrumo/contracts.py", name="Widgets")
    operation = _operation(declaration, target_name="Widget", sources=_tree_bytes(tmp_path))

    with pytest.raises(ObjectNameTransformError, match=r"did not prove expected reference classes.*static-import"):
        plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)


@pytest.mark.parametrize(
    ("consumer_path", "consumer", "reference_class"),
    [
        (
            "dev/consumer.py",
            "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from cadrumo.contracts import Widgets\n",
            "type-only-import",
        ),
        ("src/cadrumo/__init__.py", "from .contracts import Widgets\n", "export"),
    ],
)
def test_declared_special_reference_class_is_proven(
    tmp_path: Path, consumer_path: str, consumer: str, reference_class: str
) -> None:
    inventory = _inventory(
        tmp_path,
        {"src/cadrumo/contracts.py": "class Widgets:\n    pass\n", consumer_path: consumer},
    )
    declaration = _declaration(inventory, path="src/cadrumo/contracts.py", name="Widgets")
    operation = _operation(
        declaration,
        target_name="Widget",
        sources=_tree_bytes(tmp_path),
        expected_reference_classes=("definition", reference_class),
    )

    result = plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)

    assert b"Widget" in (result.content_by_path()[consumer_path] or b"")


def test_shared_consumer_reference_class_is_proven_for_each_operation(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {
            "src/cadrumo/alpha.py": "class Widgets:\n    pass\n",
            "src/cadrumo/beta.py": "class Gadgets:\n    pass\n",
            "dev/consumer.py": (
                "from cadrumo.alpha import Widgets\nfrom cadrumo.beta import Gadgets\nvalue = (Widgets(), Gadgets())\n"
            ),
        },
    )
    sources = _tree_bytes(tmp_path)
    operations = [
        _operation(
            _declaration(inventory, path="src/cadrumo/alpha.py", name="Widgets"),
            target_name="Widget",
            sources={
                "dev/consumer.py": sources["dev/consumer.py"],
                "src/cadrumo/alpha.py": sources["src/cadrumo/alpha.py"],
            },
            expected_reference_classes=("definition", "shared-consumer", "static-import"),
        ),
        _operation(
            _declaration(inventory, path="src/cadrumo/beta.py", name="Gadgets"),
            target_name="Gadget",
            sources={
                "dev/consumer.py": sources["dev/consumer.py"],
                "src/cadrumo/beta.py": sources["src/cadrumo/beta.py"],
            },
            expected_reference_classes=("definition", "shared-consumer", "static-import"),
        ),
    ]
    manifest = ObjectNameRenameManifest.model_validate(
        {
            "schema_version": 1,
            "inventory_digest": to_json(inventory)["inventory_digest"],
            "operations": tuple(sorted(operations, key=lambda item: item["operation_id"])),
        }
    )

    result = plan_object_name_transformation(manifest, repo_root=tmp_path)

    assert result.content_by_path()["dev/consumer.py"] == (
        b"from cadrumo.alpha import Widget\nfrom cadrumo.beta import Gadget\nvalue = (Widget(), Gadget())\n"
    )


def test_conflicting_byte_preconditions_are_refused(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {
            "src/cadrumo/alpha.py": "class Widgets:\n    pass\n",
            "src/cadrumo/beta.py": "class Gadgets:\n    pass\n",
        },
    )
    sources = _tree_bytes(tmp_path)
    first = _operation(
        _declaration(inventory, path="src/cadrumo/alpha.py", name="Widgets"),
        target_name="Widget",
        sources=sources,
        expected_reference_classes=("definition",),
    )
    second = _operation(
        _declaration(inventory, path="src/cadrumo/beta.py", name="Gadgets"),
        target_name="Gadget",
        sources=sources,
        expected_reference_classes=("definition",),
    )
    second["preconditions"] = tuple(
        {**item, "sha256": _digest(b"conflict")} if item["path"] == "src/cadrumo/alpha.py" else item
        for item in second["preconditions"]
    )
    second["operation_id"] = "rename-gadgets-1"
    manifest = ObjectNameRenameManifest.model_validate(
        {
            "schema_version": 1,
            "inventory_digest": to_json(inventory)["inventory_digest"],
            "operations": tuple(sorted((first, second), key=lambda item: item["operation_id"])),
        }
    )

    with pytest.raises(ObjectNameTransformError, match="disagree on the byte precondition"):
        plan_object_name_transformation(manifest, repo_root=tmp_path)


def test_missing_and_non_python_precondition_paths_are_refused(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, {"src/cadrumo/contracts.py": "class Widgets:\n    pass\n"})
    declaration = _declaration(inventory, path="src/cadrumo/contracts.py", name="Widgets")
    operation = _operation(declaration, target_name="Widget", sources=_tree_bytes(tmp_path))
    operation["preconditions"] = tuple(
        sorted(
            (*operation["preconditions"], {"path": "dev/missing.py", "sha256": _digest(b"")}),
            key=lambda item: item["path"],
        )
    )
    operation["changed_paths"] = ("dev/missing.py", declaration.path)
    with pytest.raises(ObjectNameTransformError, match="not a regular file"):
        plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)

    readme = tmp_path / "dev" / "notes.txt"
    readme.write_bytes(b"Widgets\n")
    operation = _operation(
        declaration,
        target_name="Widget",
        sources={**_tree_bytes(tmp_path), "dev/notes.txt": readme.read_bytes()},
        changed_paths=("dev/notes.txt", declaration.path),
    )
    with pytest.raises(ObjectNameTransformError, match="unsupported non-Python changed path"):
        plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)


def test_crlf_formatting_and_terminal_newline_are_preserved(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, {"src/cadrumo/contracts.py": "class Widgets:\n    pass\n"})
    path = tmp_path / "src/cadrumo/contracts.py"
    raw = b"@decorator(  1 )\r\nclass Widgets:  # exact\r\n    pass"
    path.write_bytes(raw)
    inventory = scan((tmp_path / "src", tmp_path / "dev"), tmp_path)
    declaration = _declaration(inventory, path="src/cadrumo/contracts.py", name="Widgets")
    operation = _operation(
        declaration,
        target_name="Widget",
        sources=_tree_bytes(tmp_path),
        expected_reference_classes=("definition",),
    )

    result = plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)

    assert result.content_by_path()[declaration.path] == raw.replace(b"Widgets", b"Widget")


def test_output_original_digest_and_mutation_method_canary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inventory = _inventory(tmp_path, {"src/cadrumo/contracts.py": "class Widgets:\n    pass\n"})
    declaration = _declaration(inventory, path="src/cadrumo/contracts.py", name="Widgets")
    original = (tmp_path / declaration.path).read_bytes()
    manifest = _manifest(
        inventory,
        _operation(
            declaration,
            target_name="Widget",
            sources=_tree_bytes(tmp_path),
            expected_reference_classes=("definition",),
        ),
    )

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("planner attempted a live filesystem mutation")

    for method in ("write_bytes", "write_text", "unlink", "rename", "replace"):
        monkeypatch.setattr(Path, method, forbidden)

    result = plan_object_name_transformation(manifest, repo_root=tmp_path)

    assert result.outputs[0].original_sha256 == _digest(original)
    assert _digest(result.outputs[0].content or b"") == _digest(b"class Widget:\n    pass\n")
