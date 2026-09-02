"""Detector teeth for bounded object-name transformation proposals."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from dev.audit.object_names import ObjectNameAuditResult, ObjectNameDeclaration, ObjectNameKind, scan, to_json
from dev.quality.object_name_manifest import ObjectNameRenameManifest
from dev.quality.object_name_transform import ObjectNameTransformError, plan_object_name_transformation

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


def test_same_package_module_move_preserves_relative_import(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {
            "src/cadrumo/old/widgets.py": "from .support import VALUE\n",
            "src/cadrumo/old/support.py": "VALUE = 1\n",
        },
    )
    declaration = _declaration(inventory, path="src/cadrumo/old/widgets.py", name="widgets")
    operation = _operation(
        declaration,
        target_name="widget",
        target_path="src/cadrumo/old/widget.py",
        sources={declaration.path: (tmp_path / declaration.path).read_bytes()},
        changed_paths=("src/cadrumo/old/widget.py", "src/cadrumo/old/widgets.py"),
        expected_reference_classes=("definition",),
    )

    result = plan_object_name_transformation(_manifest(inventory, operation), repo_root=tmp_path)

    assert result.content_by_path()["src/cadrumo/old/widget.py"] == b"from .support import VALUE\n"


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


@pytest.mark.parametrize("reference_class", ["dynamic-target", "generated-artifact"])
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
        ("target = 'cadrumo.widgets'\n", "unsupported string reference"),
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
