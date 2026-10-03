"""Registry loader semantics have one home each, in the compiler module that owns them.

Development tooling that simulates a delta edition before writing it -- the
edition migration above all -- needs the loader's retirement, storage-delta,
merge, reference-default and reference-resolution rules. A copy of those rules
drifts silently: the migration once kept its own retirement rule after the
loader learned that a structural succession withdraws its source lineages, and
planned editions the loader would refuse. So tooling calls the loader's own
functions, and this gate fails when a copy regrows. The same holds for the
keyed-family merge, for carrying a malformed TOML row through to validation,
and for the set of lineage-claim fields an inherited casilla loses: each has
exactly one definition, and nothing forwards to or restates it.

Five checks, each on substance rather than on one spelling:

- *Name monopoly*: no development module other than a subject's home defines a
  function or binds a name that, ignoring leading underscores, is that subject.
- *Value monopoly*: nothing binds a set of strings equal to the lineage-claim
  field set except its one canonical name, whatever the copy is called.
- *Input signature*: no function outside the materialisation module reads the
  raw inputs only the materialiser interprets -- a ``to_revision`` together
  with the casilla evolution or structural succession section is the
  withdrawal rule.
- *Near copy*: no development registry function is a structural near-copy of a
  large protected subject, whatever it is called.
- *Routing*: the edition migration modules import every routed function from
  the canonical module and call it, and hold the canonical objects at runtime.

Where it stops: the checks read Python source under ``dev/`` (tests excluded),
enumerated from the working tree; ``src/`` is not scanned. A paraphrase small
enough to share neither the subject's raw inputs nor its shape is outside the
near-copy check; the routing check is what keeps the migration itself on the
canonical functions.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Final

import pytest

import dev.registry.edition_delta_drop_planning as edition_delta_drop_planning
import dev.registry.edition_delta_row_delta_existing as edition_delta_row_delta_existing
import dev.registry.edition_delta_row_delta_reconstruction as edition_delta_row_delta_reconstruction
import dev.registry.edition_delta_row_delta_selection as edition_delta_row_delta_selection
import dev.registry.edition_delta_source as edition_delta_source
from dev._paths import REPO_ROOT
from dev.registry.compiler import (
    casilla_identity,
    casilla_inheritance,
    keyed_family_inheritance,
    keyed_family_period_scope,
    keyed_family_storage_delta,
    reference_defaults,
    reference_resolution,
)
from dev.source_tree import repository_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SEMANTICS: Final = "dev/registry/compiler/loader_semantics.py"
#: The public functions the edition migration routes its simulation through.
_ROUTED: Final = (
    "default_row_references",
    "resolve_row_references",
    "edition_reference_declarations",
    "retired_lineages",
    "inherit_casillas",
    "without_lineage_claims",
)
_ROUTING_HOMES: Final[Mapping[str, str]] = {
    **dict.fromkeys(
        ("default_row_references",),
        "dev.registry.compiler.reference_defaults",
    ),
    **dict.fromkeys(
        ("resolve_row_references", "edition_reference_declarations"),
        "dev.registry.compiler.reference_resolution",
    ),
    **dict.fromkeys(
        ("retired_lineages", "inherit_casillas", "without_lineage_claims"),
        "dev.registry.compiler.casilla_inheritance",
    ),
}
_ROUTED_BY_MODULE: Final[Mapping[str, tuple[str, ...]]] = {
    module: tuple(name for name, home in _ROUTING_HOMES.items() if home == module)
    for module in set(_ROUTING_HOMES.values())
}
#: Every protected function, by the module that is its one home.
_HOMES: Final[Mapping[str, str]] = {
    **dict.fromkeys(
        ("default_row_references", "_defaulted_references", "_extended_source_default"),
        "dev/registry/compiler/reference_defaults.py",
    ),
    **dict.fromkeys(
        (
            "resolve_row_references",
            "edition_reference_declarations",
            "_resolve_reference",
            "_declarations_by_lineage",
        ),
        "dev/registry/compiler/reference_resolution.py",
    ),
    "retired_lineages": "dev/registry/compiler/casilla_inheritance.py",
    "inherit_casillas": "dev/registry/compiler/casilla_inheritance.py",
    "without_lineage_claims": "dev/registry/compiler/casilla_inheritance.py",
    "_stated_rows_by_lineage": "dev/registry/compiler/casilla_inheritance.py",
    "_apply_casilla_storage_delta": "dev/registry/compiler/casilla_storage_delta.py",
    "_same_casilla_identity": "dev/registry/compiler/casilla_identity.py",
    "_casillas_by_id": "dev/registry/compiler/casilla_identity.py",
    "inherit_keyed_family": "dev/registry/compiler/keyed_family_inheritance.py",
    "_raw_keyed_members": "dev/registry/compiler/keyed_family_inheritance.py",
    "_restated_families": "dev/registry/compiler/keyed_family_inheritance.py",
    "selector_covers": "dev/registry/compiler/keyed_family_period_scope.py",
    "_selector_periods_for_year": "dev/registry/compiler/keyed_family_period_scope.py",
    "_apply_family_storage_delta": "dev/registry/compiler/keyed_family_storage_delta.py",
    "_patch_family_table": "dev/registry/compiler/keyed_family_storage_delta.py",
    "patch_family_sequences": "dev/registry/compiler/keyed_family_storage_delta.py",
    "passthrough_toml_row": _SEMANTICS,
}
_SUBJECTS: Final = tuple(_HOMES)
#: Protected constants, by home. A copy is found by its value as well as its name.
_CONSTANT_HOMES: Final[Mapping[str, str]] = {
    "LINEAGE_CLAIM_FIELDS": "dev/registry/compiler/casilla_identity.py",
}
_MIGRATION_GLOB: Final = "dev/registry/edition_delta*.py"
#: Raw sections whose ``to_revision`` entries withdraw lineages from a successor.
_WITHDRAWAL_SECTIONS: Final = frozenset({"casilla_continuidad_evolutions", "casilla_structural_successions"})
#: The near-copy check compares only subjects at least this large, where shape
#: is distinctive; smaller ones are held by the name and input checks.
_NEAR_COPY_MIN_TOKENS: Final = 100
_NEAR_COPY_RATIO: Final = 0.78
_CONTEXT_NODES: Final = (ast.expr_context,)


@dataclass(frozen=True, slots=True)
class _Function:
    path: str
    node: ast.FunctionDef | ast.AsyncFunctionDef
    constants: Mapping[str, str]


def _body(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.stmt]:
    body = node.body
    first = body[0] if body else None
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        return body[1:]
    return body


def _shape(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    """The function body as a pre-order sequence of node kinds, blind to every identifier and literal."""
    kinds: list[str] = []

    def visit(child: ast.AST) -> None:
        if isinstance(child, _CONTEXT_NODES):
            return
        kinds.append(type(child).__name__)
        for grandchild in ast.iter_child_nodes(child):
            visit(grandchild)

    for statement in _body(node):
        visit(statement)
    return tuple(kinds)


def _module_strings(tree: ast.Module) -> dict[str, str]:
    """Module-level names bound to a string, so a key read through a constant is still seen."""
    constants: dict[str, str] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target, value = statement.targets[0], statement.value
        elif isinstance(statement, ast.AnnAssign):
            target, value = statement.target, statement.value
        else:
            continue
        if isinstance(target, ast.Name) and isinstance(value, ast.Constant) and isinstance(value.value, str):
            constants[target.id] = value.value
    return constants


def _strings(function: _Function, shared: Mapping[str, str]) -> frozenset[str]:
    """Every string the function reads, literally or through a named string constant."""
    found: set[str] = set()
    for node in ast.walk(function.node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.add(node.value)
        elif isinstance(node, ast.Name) and node.id in function.constants:
            found.add(function.constants[node.id])
        elif isinstance(node, ast.Attribute) and node.attr in shared:
            found.add(shared[node.attr])
    return frozenset(found)


def _functions(root: Path, paths: Iterable[str]) -> Iterator[_Function]:
    for path in paths:
        tree = ast.parse((root / path).read_text(encoding="utf-8"), filename=path)
        constants = _module_strings(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                yield _Function(path, node, constants)


def _scanned(paths: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        path
        for path in paths
        if path.endswith(".py") and "/tests/" not in f"/{path}" and not path.rsplit("/", 1)[-1].startswith("test_")
    )


def _canonical_subjects(root: Path) -> dict[str, ast.FunctionDef]:
    """Each protected function's top-level definition in its home."""
    defined: dict[str, ast.FunctionDef] = {}
    for home in sorted(set(_HOMES.values())):
        tree = ast.parse((root / home).read_text(encoding="utf-8"))
        defined.update(
            (node.name, node)
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and _HOMES.get(node.name) == home
        )
    return defined


def _bindings(tree: ast.AST) -> Iterator[tuple[ast.stmt, str, ast.expr]]:
    """Every simple name binding in ``tree``, at any depth, with the value bound."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            yield node, node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            yield node, node.target.id, node.value


def _string_set(value: ast.expr) -> frozenset[str] | None:
    """The strings a literal collection of strings holds, wrapped in ``frozenset``/``set``/``tuple`` or not."""
    if (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id in {"frozenset", "set", "tuple"}
        and len(value.args) == 1
        and not value.keywords
    ):
        value = value.args[0]
    if not isinstance(value, ast.Set | ast.Tuple | ast.List) or not value.elts:
        return None
    items = [element.value for element in value.elts if isinstance(element, ast.Constant)]
    if len(items) != len(value.elts) or not all(isinstance(item, str) for item in items):
        return None
    return frozenset(str(item) for item in items)


def _canonical_constants(root: Path) -> dict[str, frozenset[str]]:
    """Each protected constant's members, read from its top-level binding in its home."""
    values: dict[str, frozenset[str]] = {}
    for name, home in _CONSTANT_HOMES.items():
        tree = ast.parse((root / home).read_text(encoding="utf-8"))
        for statement in tree.body:
            for _node, bound, value in _bindings(statement):
                if bound == name and (members := _string_set(value)) is not None:
                    values[name] = members
    return values


def _constant_copies(root: Path, paths: Iterable[str]) -> list[str]:
    """Every binding other than a constant's canonical one that restates its name or its exact members."""
    canonical = _canonical_constants(root)
    by_name = {name.lstrip("_"): name for name in canonical}
    findings: list[str] = []
    for path in paths:
        tree = ast.parse((root / path).read_text(encoding="utf-8"), filename=path)
        for node, bound, value in _bindings(tree):
            where = f"{path}:{node.lineno} {bound}"
            named = by_name.get(bound.lstrip("_"))
            if named is not None and not (path == _CONSTANT_HOMES[named] and bound == named):
                findings.append(f"{where} re-binds {named}")
                continue
            members = _string_set(value)
            for subject, expected in canonical.items():
                if members == expected and not (path == _CONSTANT_HOMES[subject] and bound == subject):
                    findings.append(f"{where} restates the value of {subject}")
    return findings


def semantic_copies(root: Path, paths: Iterable[str]) -> list[str]:
    """Every development definition that re-defines a protected loader subject, as findings."""
    subjects = _canonical_subjects(root)
    protected = {name.lstrip("_"): name for name in subjects}
    large = {name: shape for name, node in subjects.items() if len(shape := _shape(node)) >= _NEAR_COPY_MIN_TOKENS}
    scanned = _scanned(paths)
    shared: dict[str, str] = {}
    functions = list(_functions(root, scanned))
    for function in functions:
        shared.update(function.constants)
    findings: list[str] = _constant_copies(root, scanned)
    for function in functions:
        where = f"{function.path}:{function.node.lineno} {function.node.name}"
        subject = protected.get(function.node.name.lstrip("_"))
        if subject is not None and not (
            function.path == _HOMES[subject] and function.node.lineno == subjects[subject].lineno
        ):
            findings.append(f"{where} re-defines {subject}")
        if function.path == _HOMES.get(function.node.name):
            continue
        strings = _strings(function, shared)
        if "to_revision" in strings and strings & _WITHDRAWAL_SECTIONS:
            findings.append(f"{where} reads the raw withdrawal inputs retired_lineages interprets")
        if not function.path.startswith("dev/registry/"):
            continue
        shape = _shape(function.node)
        for name, subject_shape in large.items():
            if function.path == _HOMES[name] or not 0.6 <= len(shape) / len(subject_shape) <= 1.6:
                continue
            matcher = SequenceMatcher(None, shape, subject_shape, autojunk=False)
            if matcher.real_quick_ratio() < _NEAR_COPY_RATIO or matcher.quick_ratio() < _NEAR_COPY_RATIO:
                continue
            if (ratio := matcher.ratio()) >= _NEAR_COPY_RATIO:
                findings.append(f"{where} is a {ratio:.2f} structural copy of {name}")
    return findings


def _canonical_imports(path: str, tree: ast.Module, canonical_module: str) -> frozenset[str]:
    """Names ``path`` imports from the canonical module, resolving a relative import against its package."""
    package = path.removesuffix(".py").replace("/", ".").rsplit(".", 1)[0]
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        base = package.rsplit(".", node.level - 1)[0] if node.level > 1 else package
        module = node.module or ""
        absolute = f"{base}.{module}".strip(".") if node.level else module
        if absolute == canonical_module:
            names.update(alias.name for alias in node.names if alias.asname is None)
    return frozenset(names)


def _called(tree: ast.Module) -> frozenset[str]:
    return frozenset(
        node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    )


def routing_gaps(root: Path, paths: Iterable[str]) -> list[str]:
    """Routed functions the migration modules do not import from the canonical module and call."""
    imported: set[str] = set()
    called: set[str] = set()
    for path in paths:
        tree = ast.parse((root / path).read_text(encoding="utf-8"), filename=path)
        calls = _called(tree)
        for canonical_module in set(_ROUTING_HOMES.values()):
            names = _canonical_imports(path, tree, canonical_module)
            imported.update(names)
            called.update(names & calls)
    return [
        f"{name} is {'not called' if name in imported else 'not imported from ' + _ROUTING_HOMES[name]}"
        for name in _ROUTED
        if name not in called
    ]


def _migration_modules(root: Path) -> tuple[str, ...]:
    return tuple(sorted(path.relative_to(root).as_posix() for path in root.glob(_MIGRATION_GLOB)))


# ── the live tree ────────────────────────────────────────────────────────────


def test_every_protected_subject_is_defined_once_in_its_home() -> None:
    subjects = _canonical_subjects(REPO_ROOT)
    constants = _canonical_constants(REPO_ROOT)

    assert sorted(subjects) == sorted(_SUBJECTS), "a protected subject was renamed or removed; update the gate"
    assert len(subjects) >= 15
    assert len(set(_HOMES.values())) == 9
    assert len([name for name, node in subjects.items() if len(_shape(node)) >= _NEAR_COPY_MIN_TOKENS]) >= 5
    assert sorted(constants) == sorted(_CONSTANT_HOMES), "a protected constant was renamed or removed; update the gate"
    assert all(len(members) >= 2 for members in constants.values())
    assert constants["LINEAGE_CLAIM_FIELDS"] == casilla_identity.LINEAGE_CLAIM_FIELDS
    for name in _ROUTED:
        home = _ROUTING_HOMES[name]
        module = {
            "dev.registry.compiler.casilla_inheritance": casilla_inheritance,
            "dev.registry.compiler.reference_defaults": reference_defaults,
            "dev.registry.compiler.reference_resolution": reference_resolution,
        }[home]
        assert callable(getattr(module, name))
    assert callable(keyed_family_inheritance.inherit_keyed_family)
    assert callable(keyed_family_period_scope.selector_covers)
    assert callable(keyed_family_storage_delta.patch_family_sequences)


def test_no_development_module_redefines_registry_loader_semantics() -> None:
    paths = repository_files(REPO_ROOT, under=("dev",))
    scanned = _scanned(paths)
    assert len([path for path in scanned if path.startswith("dev/registry/")]) >= 50

    assert semantic_copies(REPO_ROOT, paths) == []


def test_the_edition_migration_routes_its_simulation_through_the_canonical_module() -> None:
    modules = _migration_modules(REPO_ROOT)
    assert modules, f"no module matches {_MIGRATION_GLOB}"

    assert routing_gaps(REPO_ROOT, modules) == []
    runtime_modules = {
        "dev/registry/edition_delta_drop_planning.py": edition_delta_drop_planning,
        "dev/registry/edition_delta_row_delta_existing.py": edition_delta_row_delta_existing,
        "dev/registry/edition_delta_row_delta_reconstruction.py": edition_delta_row_delta_reconstruction,
        "dev/registry/edition_delta_row_delta_selection.py": edition_delta_row_delta_selection,
        "dev/registry/edition_delta_source.py": edition_delta_source,
    }
    imported_paths = {
        path
        for path in modules
        if any(
            _canonical_imports(
                path,
                ast.parse((REPO_ROOT / path).read_text(encoding="utf-8"), filename=path),
                canonical_module,
            )
            & set(names)
            for canonical_module, names in _ROUTED_BY_MODULE.items()
        )
    }
    assert imported_paths == runtime_modules.keys(), "update the runtime identity census for routed migration modules"
    canonical_modules = {
        "dev.registry.compiler.casilla_inheritance": casilla_inheritance,
        "dev.registry.compiler.reference_defaults": reference_defaults,
        "dev.registry.compiler.reference_resolution": reference_resolution,
    }
    for module in runtime_modules.values():
        for name in _ROUTED:
            if name in vars(module):
                assert vars(module)[name] is getattr(canonical_modules[_ROUTING_HOMES[name]], name), (
                    f"{module.__name__} rebinds {name}"
                )


# ── detector teeth, on an isolated tree ──────────────────────────────────────

#: The retirement rule exactly as the migration once copied it, before the
#: loader added structural successions; renamed so only substance can find it.
_PLANTED_RETIREMENT: Final = """
from collections.abc import Mapping

_LINEAGE = "continuidad_id"
_RETIRED = "retired"


def withdrawn(table, revision_id):
    raw = table.get("casilla_continuidad_evolutions", ())
    return frozenset(
        str(evolution[_LINEAGE])
        for evolution in (raw if isinstance(raw, list | tuple) else ())
        if isinstance(evolution, Mapping)
        and evolution.get("evolution_kind") == _RETIRED
        and evolution.get("to_revision") == revision_id
        and isinstance(evolution.get(_LINEAGE), str)
    )
"""

#: The storage patch exactly as the migration once copied it, renamed.
_PLANTED_PATCH: Final = """
from collections.abc import Mapping


def apply_patch(baseline, fields, removed_fields):
    def patch(old, replacements):
        result = dict(old)
        for key, replacement in replacements.items():
            if isinstance(replacement, Mapping) and isinstance(result.get(key), Mapping):
                result[key] = patch(result[key], replacement)
            else:
                result[key] = thaw(replacement)
        return result

    result = patch(baseline, fields)
    for path in removed_fields:
        segments = path.split(".")
        target = result
        for segment in segments[:-1]:
            child = target.get(segment)
            if not isinstance(child, Mapping):
                raise ValueError(f"generated removed field {path!r} does not exist")
            copied = dict(child)
            target[segment] = copied
            target = copied
        if target.pop(segments[-1], None) is None:
            raise ValueError(f"generated removed field {path!r} does not exist")
    return result
"""

_PLANTED_NAME: Final = """
def _inherit_casillas(context, **kwargs):
    return ()
"""

#: A forwarding wrapper beside the canonical keyed-family merge, as the loader once carried.
_PLANTED_WRAPPER: Final = """
from .keyed_family_inheritance import inherit_keyed_family as _inherit_keyed_family


def inherit_keyed_family(subject, **kwargs):
    return _inherit_keyed_family(subject, **kwargs)
"""

#: A second TOML pass-through, appended to the materialisation module as it once was.
_PLANTED_PASSTHROUGH: Final = """

def _passthrough_toml_row(raw):
    return dict(raw) if isinstance(raw, Mapping) else {"value": raw}
"""

#: The lineage-claim set restated under another name and in another order.
_PLANTED_CLAIMS: Final = """
from typing import Final

_CLAIMS: Final = frozenset({"continuidad_evidence", "continuidad_origin"})
"""

_ROUTED_MIGRATION: Final = """
from .compiler.casilla_inheritance import (
    inherit_casillas,
    retired_lineages,
    without_lineage_claims,
)
from .compiler.reference_defaults import default_row_references
from .compiler.reference_resolution import edition_reference_declarations, resolve_row_references


def simulate(table, row):
    retired_lineages(table, "2025")
    inherit_casillas("c")
    without_lineage_claims(row)
    default_row_references("c", row)
    resolve_row_references("c", row)
    edition_reference_declarations(table, "2025")
"""


def _isolated_tree(tmp_path: Path, planted: Mapping[str, str]) -> tuple[Path, tuple[str, ...]]:
    """A tree holding both homes and a routed migration module; planted text is appended to an existing file."""
    root = tmp_path / "repo"
    for home in sorted(set(_HOMES.values())):
        (root / home).parent.mkdir(parents=True, exist_ok=True)
        (root / home).write_text((REPO_ROOT / home).read_text(encoding="utf-8"), encoding="utf-8")
    (root / "dev/registry/edition_delta_simulation.py").write_text(_ROUTED_MIGRATION, encoding="utf-8")
    for path, text in planted.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        target.write_text(existing + text, encoding="utf-8")
    paths = tuple(sorted(path.relative_to(root).as_posix() for path in root.rglob("*.py")))
    return root, paths


def test_the_clean_isolated_tree_passes(tmp_path: Path) -> None:
    root, paths = _isolated_tree(tmp_path, {})

    assert semantic_copies(root, paths) == []
    assert routing_gaps(root, _migration_modules(root)) == []


@pytest.mark.parametrize(
    ("path", "planted", "expected"),
    [
        ("dev/registry/tooling.py", _PLANTED_RETIREMENT, "withdrawn reads the raw withdrawal inputs"),
        ("dev/registry/tooling.py", _PLANTED_PATCH, "apply_patch is a"),
        ("dev/registry/tooling.py", _PLANTED_NAME, "_inherit_casillas re-defines inherit_casillas"),
        ("dev/registry/compiler/loader.py", _PLANTED_WRAPPER, "inherit_keyed_family re-defines inherit_keyed_family"),
        (
            "dev/registry/compiler/loader_semantics.py",
            _PLANTED_PASSTHROUGH,
            "_passthrough_toml_row re-defines passthrough_toml_row",
        ),
        ("dev/registry/tooling.py", _PLANTED_CLAIMS, "_CLAIMS restates the value of LINEAGE_CLAIM_FIELDS"),
    ],
    ids=[
        "renamed-retirement-copy",
        "renamed-storage-patch-copy",
        "same-name-definition",
        "forwarding-wrapper",
        "second-passthrough-in-another-home",
        "renamed-lineage-claim-set",
    ],
)
def test_a_planted_copy_is_detected(tmp_path: Path, path: str, planted: str, expected: str) -> None:
    root, paths = _isolated_tree(tmp_path, {path: planted})

    findings = semantic_copies(root, paths)

    assert len(findings) >= 1
    assert any(expected in finding for finding in findings), findings


def test_a_migration_module_that_stops_routing_is_detected(tmp_path: Path) -> None:
    root, _paths = _isolated_tree(tmp_path, {})
    module = root / "dev/registry/edition_delta_simulation.py"
    module.write_text(_ROUTED_MIGRATION.replace('    retired_lineages(table, "2025")\n', ""), encoding="utf-8")

    assert routing_gaps(root, _migration_modules(root)) == ["retired_lineages is not called"]
