"""Generate the deterministic consumer census for the registry authority owner."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Final

if __package__:
    from .stable_tree_generation import refuse_if_tree_moves
else:  # Direct execution has no parent package, and this directory is not a usable
    # search root: the local types.py would shadow the stdlib module. Reach the
    # sibling through the repository root, which carries no such shadowing file.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from dev.quality.stable_tree_generation import refuse_if_tree_moves

ROOT: Final = Path(__file__).resolve().parents[2]
TARGET_PATH: Final = "src/cadrumo/domain/calculations/registry/authority.py"
TARGET_MODULE: Final = "cadrumo.domain.calculations.registry.authority"
PACKAGE_MODULE: Final = "cadrumo.domain.calculations.registry"
SCHEMA_VERSION: Final = 1
CATEGORIES: Final = (
    "production",
    "test",
    "fixture",
    "documentation",
    "tooling",
    "annotation",
    "registration",
    "dynamic_target",
    "package_attribute",
    "transitive",
)
OUTPUT_PATH: Final = ROOT / "dev/quality/registry_authority_consumer_census.v1.json"


def _tracked_paths() -> frozenset[str]:
    """Return the repository-tracked paths the census may count.

    A census of repository content must read what the repository carries.
    A gitignored mirror of the source tree, left behind by an interrupted
    benchmark run, once contributed 4,478 phantom consumer paths to the
    committed artifact -- entries no reviewer could act on and no other
    checkout could reproduce.  Untracked peer scratch moving a shared
    census number is the same defect in a quieter form.
    """
    listed = subprocess.run(  # fixed read-only git subcommand assembled only by this module
        ("git", "ls-files", "-z", "--", "src", "dev", "docs"),  # noqa: S607  # repository tool is fixed
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return frozenset(entry for entry in listed.split(chr(0)) if entry)


def _files() -> tuple[Path, ...]:
    tracked = _tracked_paths()
    paths: list[Path] = []
    for root_name in ("src", "dev", "docs"):
        paths.extend(
            path
            for path in (ROOT / root_name).rglob("*")
            if path.is_file()
            and path.suffix in {".py", ".pyi", ".md", ".rst"}
            and path.relative_to(ROOT).as_posix() in tracked
        )
    return tuple(sorted(paths))


def _base_category(path: str) -> str:
    if path.startswith("docs/"):
        return "documentation"
    if path.endswith("conftest.py") or "/fixtures/" in path or path.endswith("_fixtures.py"):
        return "fixture"
    if path.startswith("dev/"):
        return "test" if "/tests/" in path else "tooling"
    if "/tests/" in path:
        return "test"
    return "production"


def _module_for(path: str) -> tuple[str, bool] | None:
    if not path.endswith((".py", ".pyi")):
        return None
    module = path.removeprefix("src/").removesuffix(".py").removesuffix(".pyi").replace("/", ".")
    is_package = module.endswith(".__init__")
    return (module.removesuffix(".__init__"), is_package)


def _resolve_import(current: str, is_package: bool, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module
    package = current if is_package else current.rpartition(".")[0]
    parts = package.split(".")
    climb = node.level - 1
    if not package or climb >= len(parts):
        return None
    base = ".".join(parts[: len(parts) - climb])
    return f"{base}.{node.module}" if node.module else base


def _dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None


def _definition_inventory() -> list[dict[str, object]]:
    tree = ast.parse((ROOT / TARGET_PATH).read_text(encoding="utf-8"), filename=TARGET_PATH)
    definitions: list[dict[str, object]] = []
    for node in tree.body:
        names: list[tuple[str, str]] = []
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append((node.name, type(node).__name__))
        elif isinstance(node, ast.Assign):
            names.extend((target.id, "Assign") for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append((node.target.id, "AnnAssign"))
        for name, kind in names:
            definitions.append({"kind": kind, "locator": f"{TARGET_PATH}:{node.lineno}", "name": name})
    return sorted(definitions, key=lambda item: (str(item["name"]), int(str(item["locator"]).rsplit(":", 1)[1])))


def census_document() -> dict[str, object]:
    """Derive the complete schema-versioned authority definition and consumer inventory."""
    hits: dict[str, set[str]] = {category: set() for category in CATEGORIES}
    importers: dict[str, set[str]] = defaultdict(set)
    module_paths: dict[str, str] = {}
    direct_modules: set[str] = set()
    for path in _files():
        relative = path.relative_to(ROOT).as_posix()
        if relative == TARGET_PATH or relative == "dev/quality/registry_authority_consumer_census.py":
            continue
        text = path.read_text(encoding="utf-8")
        module_info = _module_for(relative)
        if module_info is None:
            if TARGET_MODULE in text:
                hits[_base_category(relative)].add(relative)
            continue
        module, is_package = module_info
        module_paths[module] = relative
        try:
            tree = ast.parse(text, filename=relative)
        except SyntaxError as exc:
            raise RuntimeError(f"authority census cannot parse {relative}") from exc
        aliases: dict[str, str] = {}
        direct = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    importers[alias.name].add(module)
                    aliases[alias.asname or alias.name.split(".")[0]] = alias.name
                    direct |= alias.name == TARGET_MODULE
            elif isinstance(node, ast.ImportFrom):
                imported = _resolve_import(module, is_package, node)
                if imported is None:
                    continue
                importers[imported].add(module)
                for alias in node.names:
                    aliases[alias.asname or alias.name] = f"{imported}.{alias.name}"
                direct |= imported == TARGET_MODULE
                if imported == PACKAGE_MODULE and any(alias.name == "authority" for alias in node.names):
                    hits["package_attribute"].add(relative)
        for node in ast.walk(tree):
            dotted = _dotted(node)
            if dotted:
                first, dot, remainder = dotted.partition(".")
                resolved = f"{aliases.get(first, first)}{dot}{remainder}" if dot else aliases.get(first, first)
                if resolved == TARGET_MODULE or resolved.startswith(f"{TARGET_MODULE}."):
                    direct = True
                    if dotted.startswith(f"{PACKAGE_MODULE}.") or aliases.get(first) == PACKAGE_MODULE:
                        hits["package_attribute"].add(relative)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and TARGET_MODULE in node.value:
                hits["dynamic_target"].add(relative)
            if isinstance(node, ast.Call) and "register" in (_dotted(node.func) or "").lower():
                registration_references = (name for item in ast.walk(node) if (name := _dotted(item)) is not None)
                if any(
                    aliases.get(name.split(".")[0], name).startswith(TARGET_MODULE) for name in registration_references
                ):
                    hits["registration"].add(relative)
        annotation_nodes: list[ast.AST] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign):
                annotation_nodes.append(node.annotation)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                annotation_nodes.extend(
                    argument.annotation
                    for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
                    if argument.annotation is not None
                )
                if node.returns is not None:
                    annotation_nodes.append(node.returns)
        annotation_references = (
            name
            for annotation in annotation_nodes
            for item in ast.walk(annotation)
            if (name := _dotted(item)) is not None
        )
        if any(aliases.get(name.split(".")[0], name).startswith(TARGET_MODULE) for name in annotation_references):
            hits["annotation"].add(relative)
        if direct:
            hits[_base_category(relative)].add(relative)
            direct_modules.add(module)
    frontier = [TARGET_MODULE, *sorted(direct_modules)]
    visited = set(frontier)
    while frontier:
        imported = frontier.pop()
        for importer in sorted(importers.get(imported, ())):
            if importer in visited:
                continue
            visited.add(importer)
            frontier.append(importer)
            if importer not in direct_modules and importer in module_paths:
                hits["transitive"].add(module_paths[importer])
    return {
        "consumer_categories": list(CATEGORIES),
        "consumers": {category: sorted(hits[category]) for category in CATEGORIES},
        "definitions": _definition_inventory(),
        "schema_version": SCHEMA_VERSION,
        "target_module": TARGET_MODULE,
        "target_path": TARGET_PATH,
    }


def check_document(document: object) -> None:
    """Refuse any checked artifact that differs from current derived evidence."""
    expected = census_document()
    if document != expected:
        raise RuntimeError("registry authority consumer census drifted; regenerate the checked artifact")


def main(argv: list[str] | None = None) -> int:
    """Write or check the deterministic authority census artifact."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    # Bracketed by the tree fingerprint: this census walks the source tree, and
    # a peer landing a relocation mid-walk yields an artefact naming a module
    # that no longer exists. That happened on 2026-08-31 -- seventeen references
    # to a deleted module, and the next `--check` failed on the missing file
    # rather than on the race that produced it. Refusing costs a re-run;
    # absorbing the race writes it into the artefact as fact.
    with refuse_if_tree_moves(ROOT):
        document = census_document()
    if args.write:
        OUTPUT_PATH.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.check:
        check_document(json.loads(OUTPUT_PATH.read_text(encoding="utf-8")))
    if not args.write and not args.check:
        print(json.dumps(document, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
