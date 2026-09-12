"""Compile and consume declared finite Python-module target inventories.

The artifact format deliberately names its path-only source selection beside
the generated targets.  Consumers can therefore prove that an inventory still
matches the tree without importing or reading any selected application module.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
UTF_8: Final = "utf-8"

SCHEMA_VERSION: Final = 1
TARGET_KIND: Final = "python-module-names"


class MetadataTargetSetError(ValueError):
    """Raised when a declared finite target-set artifact is malformed."""


def load_target_set(
    metadata_path: str | Path, target_set: str, *, repository: Path = REPO_ROOT
) -> tuple[str, ...]:
    """Return the named, declared finite target set from *metadata_path*."""
    document = _read_document(_resolve_metadata_path(metadata_path, repository=repository))
    return _target_set(document, target_set)["targets"]


def load_all_target_sets(
    metadata_path: str | Path, *, repository: Path = REPO_ROOT
) -> tuple[str, ...]:
    """Return the sorted union of every target set in one authority artifact."""
    document = _read_document(_resolve_metadata_path(metadata_path, repository=repository))
    targets = {target for item in document["target_sets"].values() for target in item["targets"]}
    return tuple(sorted(targets))


def assert_target_set_current(
    metadata_path: str | Path, target_set: str, *, repository: Path = REPO_ROOT
) -> None:
    """Refuse an inventory whose named target set has drifted from its source tree."""
    path = _resolve_metadata_path(metadata_path, repository=repository)
    document = _read_document(path)
    target = _target_set(document, target_set)
    actual = _enumerate_modules(target["source"], repository=repository)
    if target["targets"] != actual:
        raise AssertionError(
            f"metadata target set {target_set!r} is stale; "
            f"regenerate {path.relative_to(repository.resolve()).as_posix()}"
        )


def assert_all_target_sets_current(
    metadata_path: str | Path, *, repository: Path = REPO_ROOT
) -> None:
    """Refuse any stale target set in one multi-root authority artifact."""
    path = _resolve_metadata_path(metadata_path, repository=repository)
    document = _read_document(path)
    for name, target in document["target_sets"].items():
        actual = _enumerate_modules(target["source"], repository=repository)
        if target["targets"] != actual:
            raise AssertionError(
                f"metadata target set {name!r} is stale; "
                f"regenerate {path.relative_to(repository.resolve()).as_posix()}"
            )


def compile_inventory(*, package: str, source_root: str, subpackages: Sequence[str], target_set: str) -> dict[str, Any]:
    """Compile one reproducible metadata document from path-only source facts."""
    source = {
        "package": _dotted(package, subject="package"),
        "source_root": _relative_path(source_root, subject="source_root"),
        "subpackages": _subpackages(subpackages),
        "exclude_test_packages": True,
        "exclude_test_module_prefixes": ["test_", "_test_", "conftest"],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "target_sets": {
            target_set: {
                "kind": TARGET_KIND,
                "source": source,
                "targets": list(_enumerate_modules(source)),
            }
        },
    }


def rendered_inventory(document: Mapping[str, object]) -> str:
    """Render one validated document with a fresh path-only target enumeration."""
    normalized = _validated_document(document)
    target_sets: dict[str, object] = {}
    for name, target in normalized["target_sets"].items():
        target_sets[name] = {
            "kind": TARGET_KIND,
            "source": target["source"],
            "targets": list(_enumerate_modules(target["source"])),
        }
    payload = {"schema_version": SCHEMA_VERSION, "target_sets": target_sets}
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """Generate, or ``--check``, one declared finite-module inventory."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, required=True, help="checked-in JSON metadata artifact")
    parser.add_argument("--package", default="cadrumo", help="dotted package rooted at --source-root")
    parser.add_argument("--source-root", default="src/cadrumo", help="repository-relative package directory")
    parser.add_argument(
        "--subpackages",
        nargs="*",
        default=(),
        help="package-relative directories to enumerate; omit to enumerate the complete package root",
    )
    parser.add_argument("--target-set", required=True, help="declared target-set identifier")
    parser.add_argument("--check", action="store_true", help="refuse a missing or stale checked-in artifact")
    args = parser.parse_args(argv)
    output = _resolve_metadata_path(args.output)
    document = compile_inventory(
        package=args.package,
        source_root=args.source_root,
        subpackages=args.subpackages,
        target_set=args.target_set,
    )
    rendered = json.dumps(document, indent=2, sort_keys=True) + "\n"
    try:
        existing = output.read_text(encoding=UTF_8)
    except FileNotFoundError:
        existing = None
    if args.check:
        if existing != rendered:
            print(f"module target inventory is stale: {output.relative_to(REPO_ROOT).as_posix()}", file=sys.stderr)
            return 1
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding=UTF_8, newline="\n")
    return 0


def _resolve_metadata_path(value: str | Path, *, repository: Path = REPO_ROOT) -> Path:
    path = Path(value)
    root = repository.resolve()
    resolved = (path if path.is_absolute() else root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise MetadataTargetSetError(f"metadata path escapes the repository: {value!r}") from exc
    return resolved


def _read_document(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding=UTF_8))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MetadataTargetSetError(f"cannot read metadata target inventory {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise MetadataTargetSetError("metadata target inventory must be a JSON object")
    return _validated_document(payload)


def _validated_document(document: Mapping[str, object]) -> dict[str, Any]:
    if document.get("schema_version") != SCHEMA_VERSION:
        raise MetadataTargetSetError(f"unsupported metadata target inventory schema: {document.get('schema_version')!r}")
    raw_sets = document.get("target_sets")
    if not isinstance(raw_sets, dict) or not raw_sets:
        raise MetadataTargetSetError("metadata target inventory has no target_sets")
    target_sets: dict[str, Any] = {}
    for name, raw_target in raw_sets.items():
        if not isinstance(name, str) or not name:
            raise MetadataTargetSetError("metadata target-set name must be a non-empty string")
        if not isinstance(raw_target, dict) or raw_target.get("kind") != TARGET_KIND:
            raise MetadataTargetSetError(f"metadata target set {name!r} is not {TARGET_KIND!r}")
        source = _validated_source(raw_target.get("source"))
        raw_targets = raw_target.get("targets")
        if not isinstance(raw_targets, list) or not raw_targets:
            raise MetadataTargetSetError(f"metadata target set {name!r} has no targets")
        targets = tuple(_dotted(target, subject=f"target in {name!r}") for target in raw_targets)
        if tuple(sorted(set(targets))) != targets:
            raise MetadataTargetSetError(f"metadata target set {name!r} targets must be sorted and unique")
        target_sets[name] = {"kind": TARGET_KIND, "source": source, "targets": targets}
    return {"schema_version": SCHEMA_VERSION, "target_sets": target_sets}


def _target_set(document: Mapping[str, object], name: str) -> dict[str, Any]:
    target = document["target_sets"].get(name)
    if target is None:
        raise MetadataTargetSetError(f"metadata target set is not declared: {name!r}")
    return target


def _validated_source(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise MetadataTargetSetError("metadata target set has no source selection")
    package = _dotted(value.get("package"), subject="source package")
    source_root = _relative_path(value.get("source_root"), subject="source_root")
    raw_subpackages = value.get("subpackages")
    if not isinstance(raw_subpackages, list):
        raise MetadataTargetSetError("source subpackages must be a list")
    subpackages = _subpackages(raw_subpackages)
    prefixes = value.get("exclude_test_module_prefixes")
    if value.get("exclude_test_packages") is not True or prefixes != ["test_", "_test_", "conftest"]:
        raise MetadataTargetSetError("source selection must use the standard non-test module exclusion")
    return {
        "package": package,
        "source_root": source_root,
        "subpackages": list(subpackages),
        "exclude_test_packages": True,
        "exclude_test_module_prefixes": ["test_", "_test_", "conftest"],
    }


def _dotted(value: object, *, subject: str) -> str:
    if not isinstance(value, str) or not value or any(not item.isidentifier() for item in value.split(".")):
        raise MetadataTargetSetError(f"{subject} must be a dotted Python name")
    return value


def _relative_path(value: object, *, subject: str) -> str:
    if not isinstance(value, str) or not value:
        raise MetadataTargetSetError(f"{subject} must be a non-empty repository-relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise MetadataTargetSetError(f"{subject} must stay below the repository root")
    return path.as_posix()


def _subpackages(values: Sequence[object]) -> tuple[str, ...]:
    result = tuple(_dotted(value, subject="source subpackage") for value in values)
    if tuple(sorted(set(result))) != result:
        raise MetadataTargetSetError("source subpackages must be sorted and unique")
    return result


def _enumerate_modules(source: Mapping[str, object], *, repository: Path = REPO_ROOT) -> tuple[str, ...]:
    root = _resolve_metadata_path(str(source["source_root"]), repository=repository)
    package = str(source["package"])
    names: set[str] = set()
    subpackages = source["subpackages"]
    selections = tuple(subpackages) if subpackages else (None,)
    for subpackage in selections:
        directory = root if subpackage is None else root.joinpath(*str(subpackage).split("."))
        if not directory.is_dir():
            raise MetadataTargetSetError(f"source subpackage directory does not exist: {directory}")
        for path in directory.rglob("*.py"):
            relative = path.relative_to(root).with_suffix("")
            parts = relative.parts
            if "tests" in parts or path.stem.startswith(("test_", "_test_", "conftest")):
                continue
            dotted = parts[:-1] if parts[-1] == "__init__" else parts
            names.add(".".join((package, *dotted)))
    return tuple(sorted(names))


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "MetadataTargetSetError",
    "assert_all_target_sets_current",
    "assert_target_set_current",
    "compile_inventory",
    "load_all_target_sets",
    "load_target_set",
    "main",
    "rendered_inventory",
]
