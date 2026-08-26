"""Deterministically census the exact registry family mechanically relocated by c941.

This is deliberately not a general import scanner.  Its only candidate set is
the rename set recorded by c94133f295; the checked-in matrix then receives a
separate, human-reviewed semantic adjudication for every one of those rows.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Final

RELOCATION_COMMIT: Final = "c94133f29516b12e3529f3d154c31592562f6198"
REGISTRY_PATH: Final = "src/cadrumo/domain/calculations/registry"
MATRIX_VERSION: Final = 1
DISPOSITIONS: Final = (
    "keep_public",
    "hard_move_complete",
    "privatize_external_elimination",
    "delete",
)
TERMINAL_STATES: Final = {
    "keep_public": frozenset({"public_local_definitions_only"}),
    "hard_move_complete": frozenset(
        {
            "public_local_definitions_only",
            "retired_after_hard_move",
            "schema_local_definitions_only",
        },
    ),
    "privatize_external_elimination": frozenset({"private_same_package_only"}),
    "delete": frozenset({"deleted_no_surface"}),
}
CONSUMER_CATEGORIES: Final = (
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
ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / "dev/quality/registry_facade_family_census.v1.json"
PLAN_PATH = ROOT / ".vault/plan/2026-08-11-tui-architecture-plan.md"


@dataclass(frozen=True, slots=True)
class RelocatedFamily:
    """One exact c941 private-to-public module rename."""

    similarity: int
    old_path: str
    new_path: str

    @property
    def old_module(self) -> str:
        """Return the old Python module name."""
        return _module_name(self.old_path)

    @property
    def new_module(self) -> str:
        """Return the current Python module name."""
        return _module_name(self.new_path)


def _git(*arguments: str) -> str:
    """Run one fixed, repository-local read-only git query."""
    return subprocess.run(  # noqa: S603  # fixed read-only git subcommand assembled only by this module
        ("git", *arguments),  # noqa: S607  # repository tool is fixed; only literal call sites supply arguments
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _module_name(path: str) -> str:
    """Convert a source path under ``src/`` to its importable Python name."""
    if not path.startswith("src/") or not path.endswith(".py"):
        raise ValueError(f"not a Python source path: {path!r}")
    return path.removeprefix("src/").removesuffix(".py").replace("/", ".")


def exact_relocation_candidates() -> tuple[RelocatedFamily, ...]:
    """Return exactly the rename candidates recorded in the c941 diff."""
    output = _git(
        "diff-tree",
        "-r",
        "-M",
        "--name-status",
        "--format=",
        f"{RELOCATION_COMMIT}^",
        RELOCATION_COMMIT,
        "--",
        REGISTRY_PATH,
    )
    candidates: list[RelocatedFamily] = []
    for line in output.splitlines():
        match = re.fullmatch(r"R(\d+)\t([^\t]+)\t([^\t]+)", line)
        if match is None:
            continue
        similarity, old_path, new_path = match.groups()
        candidates.append(RelocatedFamily(int(similarity), old_path, new_path))
    candidates.sort(key=lambda candidate: candidate.old_path)
    if len(candidates) != 78:
        raise RuntimeError(f"c941 registry family must contain exactly 78 renames, found {len(candidates)}")
    if (
        len({candidate.old_path for candidate in candidates}) != 78
        or len({candidate.new_path for candidate in candidates}) != 78
    ):
        raise RuntimeError("c941 registry rename family is not one-to-one")
    return tuple(candidates)


def mechanical_relocation_pairs() -> tuple[tuple[str, str], ...]:
    """Return the exact historical rename pairs as the mechanical-delta proof."""
    return tuple((candidate.old_path, candidate.new_path) for candidate in exact_relocation_candidates())


def _historic_facade_exports() -> dict[str, tuple[str, ...]]:
    """Derive c941-parent ``__all__`` symbols by their private defining module."""
    source = _git("show", f"{RELOCATION_COMMIT}^:{REGISTRY_PATH}/__init__.py")
    tree = ast.parse(source, filename="c941-parent-registry-__init__.py")
    public_names: set[str] | None = None
    lazy_exports: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name, value = node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            name, value = node.target.id, node.value
        else:
            continue
        if name == "__all__":
            public_names = set(ast.literal_eval(value))
        elif name == "_LAZY_EXPORTS":
            lazy_exports = ast.literal_eval(value)
    if public_names is None:
        raise RuntimeError("c941-parent registry facade has no literal __all__")
    exports: dict[str, list[str]] = defaultdict(list)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level != 1 or not node.module:
            continue
        old_path = f"{REGISTRY_PATH}/{node.module}.py"
        for alias in node.names:
            exported_name = alias.asname or alias.name
            if exported_name in public_names:
                exports[old_path].append(exported_name)
    for exported_name, lazy_module in lazy_exports.items():
        if exported_name in public_names:
            exports[f"{REGISTRY_PATH}/{lazy_module.removeprefix('.')}.py"].append(exported_name)
    return {path: tuple(sorted(set(names))) for path, names in exports.items()}


def _base_category(relative_path: str) -> str:
    """Classify a consumer's operational home without guessing its semantics."""
    if relative_path.startswith("docs/"):
        return "documentation"
    if relative_path.startswith("dev/"):
        return "test" if "/tests/" in relative_path else "tooling"
    if "/tests/" in relative_path:
        return "test"
    if relative_path.endswith("conftest.py") or "/fixtures/" in relative_path:
        return "fixture"
    return "production"


def _consumer_files() -> tuple[Path, ...]:
    """Return all authored source, tooling, test, and documentation files in scope."""
    paths: list[Path] = []
    for root_name in ("src", "dev", "docs"):
        root = ROOT / root_name
        paths.extend(path for path in root.rglob("*") if path.is_file() and path.suffix in {".py", ".rst", ".md"})
    return tuple(sorted(paths))


def _python_imports(tree: ast.AST) -> tuple[str, ...]:
    """Return fully named imports from an AST without resolving relative imports."""
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imports.append(node.module)
    return tuple(imports)


_CONSUMER_CACHE: dict[str, dict[str, tuple[str, ...]]] | None = None


def _all_current_consumers(
    candidates: tuple[RelocatedFamily, ...],
) -> dict[str, dict[str, tuple[str, ...]]]:
    """Census every fixed family member in one AST walk of the consumer corpus."""
    hits = {candidate.old_path: {category: set() for category in CONSUMER_CATEGORIES} for candidate in candidates}
    direct_modules = {candidate.old_path: set() for candidate in candidates}
    importers: dict[str, set[str]] = defaultdict(set)
    by_new_module = {candidate.new_module: candidate for candidate in candidates}
    for path in _consumer_files():
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        base = _base_category(relative)
        for candidate in candidates:
            if candidate.old_module in text or candidate.new_module in text:
                hits[candidate.old_path][base].add(relative)
        if path.suffix != ".py":
            continue
        tree = ast.parse(text, filename=relative)
        imports = _python_imports(tree)
        module = (
            _module_name(relative) if relative.startswith("src/") else relative.removesuffix(".py").replace("/", ".")
        )
        for imported in imports:
            importers[imported].add(module)
            candidate = by_new_module.get(imported)
            if candidate is not None:
                direct_modules[candidate.old_path].add(module)
            if imported == "cadrumo.domain.calculations.registry":
                for candidate in candidates:
                    hits[candidate.old_path]["package_attribute"].add(relative)
        strings = {
            node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        annotations = {ast.unparse(node.annotation) for node in ast.walk(tree) if isinstance(node, ast.AnnAssign)}
        registrations = {
            ast.unparse(node)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("register")
        }
        for candidate in candidates:
            if any(candidate.old_module in value or candidate.new_module in value for value in strings):
                hits[candidate.old_path]["dynamic_target"].add(relative)
            if any(candidate.new_module in annotation for annotation in annotations):
                hits[candidate.old_path]["annotation"].add(relative)
            if any(candidate.new_module in registration for registration in registrations):
                hits[candidate.old_path]["registration"].add(relative)
    for candidate in candidates:
        frontier = list(direct_modules[candidate.old_path])
        transitive: set[str] = set()
        while frontier:
            imported = frontier.pop()
            for importer in importers.get(imported, ()):
                if importer not in transitive and importer not in direct_modules[candidate.old_path]:
                    transitive.add(importer)
                    frontier.append(importer)
        for module in transitive:
            path = ROOT / (
                "src/" + module.replace(".", "/") + ".py"
                if module.startswith("cadrumo.")
                else module.replace(".", "/") + ".py"
            )
            if path.is_file():
                hits[candidate.old_path]["transitive"].add(path.relative_to(ROOT).as_posix())
    return {
        old_path: {category: tuple(sorted(paths)) for category, paths in categories.items()}
        for old_path, categories in hits.items()
    }


def _current_consumers(candidate: RelocatedFamily) -> dict[str, tuple[str, ...]]:
    """Return this exact family member's cached, one-pass consumer census."""
    global _CONSUMER_CACHE
    if _CONSUMER_CACHE is None:
        _CONSUMER_CACHE = _all_current_consumers(exact_relocation_candidates())
    return _CONSUMER_CACHE[candidate.old_path]


def _current_symbol_locators(candidate: RelocatedFamily, symbols: tuple[str, ...]) -> dict[str, list[str]]:
    """Locate every historic facade symbol in its current renamed module."""
    source_path = ROOT / candidate.new_path
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=candidate.new_path)
    locations: dict[str, list[str]] = {symbol: [] for symbol in symbols}
    for node in tree.body:
        names: set[str] = set()
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or alias.name for alias in node.names)
        for symbol in sorted(names & locations.keys()):
            locations[symbol].append(f"{candidate.new_path}:{node.lineno}")
    return locations


def generated_rows() -> list[dict[str, object]]:
    """Produce the exact c941 family rows without inventing their adjudications."""
    facade_exports = _historic_facade_exports()
    rows: list[dict[str, object]] = []
    for candidate in exact_relocation_candidates():
        exported_symbols = facade_exports.get(candidate.old_path, ())
        rows.append(
            {
                "old_path": candidate.old_path,
                "new_path": candidate.new_path,
                "rename_similarity": candidate.similarity,
                "facade_exported_symbols": list(exported_symbols),
                "current_symbol_locators": _current_symbol_locators(candidate, exported_symbols),
                "consumers": _current_consumers(candidate),
                "semantic_owner": None,
                "semantic_evidence": None,
                "disposition": None,
                "follow_on_step_id": None,
            }
        )
    return rows


def matrix_document() -> dict[str, object]:
    """Return the schema-versioned, intentionally unadjudicated S175 matrix template."""
    return {
        "schema_version": MATRIX_VERSION,
        "relocation_commit": RELOCATION_COMMIT,
        "consumer_categories": list(CONSUMER_CATEGORIES),
        "review_status": "pending_independent_architecture_review",
        "rows": generated_rows(),
        "final_package_gate": None,
    }


def _canonical_plan_step_ids() -> frozenset[str]:
    """Read the canonical Step IDs owned by the reviewed TUI architecture plan."""
    return frozenset(re.findall(r"`(W\d{2}\.P\d{2}\.S\d+)`", PLAN_PATH.read_text(encoding="utf-8")))


def check_matrix_document(document: dict[str, object]) -> None:
    """Fail closed on census drift or an incomplete/many-to-one adjudication."""
    if document.get("schema_version") != MATRIX_VERSION or document.get("relocation_commit") != RELOCATION_COMMIT:
        raise RuntimeError("registry facade matrix has the wrong schema or relocation commit")
    rows = document.get("rows")
    if not isinstance(rows, list) or len(rows) != 78:
        raise RuntimeError("registry facade matrix must contain exactly 78 rows")
    expected = generated_rows()
    expected_pairs = {(row["old_path"], row["new_path"]) for row in expected}
    actual_pairs = {(row.get("old_path"), row.get("new_path")) for row in rows if isinstance(row, dict)}
    if actual_pairs != expected_pairs:
        raise RuntimeError("registry facade matrix is missing, extra, duplicate, or unrelated c941 rows")
    steps: set[str] = set()
    canonical_step_ids = _canonical_plan_step_ids()
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("registry facade matrix rows must be objects")
        pair = (row["old_path"], row["new_path"])
        generated = next(item for item in expected if (item["old_path"], item["new_path"]) == pair)
        if (
            row.get("facade_exported_symbols") != generated["facade_exported_symbols"]
            or row.get("consumers") != generated["consumers"]
        ):
            raise RuntimeError(f"registry facade consumer census drifted for {pair[0]}")
        for field in ("semantic_owner", "semantic_evidence", "disposition", "follow_on_step_id"):
            if not isinstance(row.get(field), str) or not row[field]:
                raise RuntimeError(f"registry facade row {pair[0]} lacks reviewed {field}")
        if row["disposition"] not in {"keep_public", "hard_move_complete", "privatize_external_elimination", "delete"}:
            raise RuntimeError(f"registry facade row {pair[0]} has an invalid disposition")
        if row["follow_on_step_id"] in steps:
            raise RuntimeError("registry facade matrix maps more than one row to one follow-on Step")
        if row["follow_on_step_id"] not in canonical_step_ids:
            raise RuntimeError(f"registry facade row {pair[0]} names a non-canonical follow-on Step")
        steps.add(row["follow_on_step_id"])


def main(argv: list[str] | None = None) -> int:
    """Write the deterministic template or verify a fully reviewed matrix."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-template", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.write_template:
        MATRIX_PATH.write_text(json.dumps(matrix_document(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.check:
        check_matrix_document(json.loads(MATRIX_PATH.read_text(encoding="utf-8")))
    if not args.write_template and not args.check:
        print(json.dumps(matrix_document(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
