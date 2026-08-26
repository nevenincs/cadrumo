"""One gate over every registry module adjudicated keep-public.

The census matrix already records, per module, which disposition its family was
given. This gate holds the ``keep_public`` rows to that decision: what a module
advertises it must define itself, and the registry package must bind none of
it.

The check is AST-based on purpose. Asking an object for its ``__module__``
looks equivalent and is not: a locally defined ``Annotated`` alias reports
``typing``, so an attribute-based check calls ten honest modules liars. What
the claim is really about is where a name is *bound in source*, so that is what
is read.
"""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path
from typing import Final

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ROOT = Path(__file__).resolve().parents[6]
_MATRIX = _ROOT / "dev" / "quality" / "registry_facade_family_census.v1.json"
_PACKAGE = "cadrumo.domain.calculations.registry"


def _borrowed_exports(path: Path) -> list[str]:
    """Return the names a module exports without defining them itself."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    bound: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            bound.add(node.name)
        elif isinstance(node, ast.Assign):
            bound.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            bound.add(node.target.id)
        elif isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
            bound.add(node.name.id)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(getattr(t, "id", "") == "__all__" for t in node.targets)
            and isinstance(node.value, ast.List | ast.Tuple)
        ):
            return [e.value for e in node.value.elts if isinstance(e, ast.Constant) and e.value not in bound]
    return []


def _rows(disposition: str) -> tuple[dict[str, object], ...]:
    """Return every reviewed matrix row carrying one disposition."""
    document = json.loads(_MATRIX.read_text(encoding="utf-8"))
    rows = tuple(row for row in document["rows"] if row["disposition"] == disposition)
    if not rows:
        pytest.fail(f"the census matrix records no {disposition} rows to hold")
    return rows


def _keep_public_paths() -> tuple[str, ...]:
    """Return every module the reviewed matrix adjudicated as keep-public."""
    return tuple(sorted(str(row["new_path"]) for row in _rows("keep_public")))


def _hard_move_pairs() -> tuple[tuple[str, str], ...]:
    """Return each completed hard move as its retired path and its real owner.

    The owner is read from the row's terminal destinations, not from
    ``new_path``. A family that moved out of the registry entirely keeps a
    ``new_path`` nothing occupies, and asserting that path exists would fail an
    honest row for having finished its move.
    """
    pairs: set[tuple[str, str]] = set()
    for row in _rows("hard_move_complete"):
        destinations = row["terminal_destinations"]
        owners = [str(item["path"]) for item in destinations if not item["allowed_absence"]]
        owner = owners[0] if owners else str(row["new_path"])
        pairs.add((str(row["old_path"]), owner))
    return tuple(sorted(pairs))


def _advertising_paths() -> tuple[str, ...]:
    """Return only the keep-public modules that actually declare ``__all__``.

    Parameterizing on this rather than skipping inside the test keeps every
    generated case meaningful: a case exists only where there is something to
    assert.
    """
    advertising = []
    for relative_path in _keep_public_paths():
        dotted = relative_path.removeprefix("src/").removesuffix(".py").replace("/", ".")
        if hasattr(importlib.import_module(dotted), "__all__"):
            advertising.append(relative_path)
    if not advertising:
        pytest.fail("no keep-public module declares __all__; the advertisement check would assert nothing")
    return tuple(advertising)


def _locally_bound_names(path: Path) -> frozenset[str]:
    """Return every name this module binds at its own top level."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
            names.add(node.name.id)
    return frozenset(names)


def _package_bound_names(package: object) -> frozenset[str]:
    """Return every name the package ``__init__`` itself binds.

    Read from source rather than by attribute lookup, so a submodule attribute
    set by the import system is never mistaken for a re-export.
    """
    init = Path(package.__file__ or "")
    tree = ast.parse(init.read_text(encoding="utf-8"), filename=str(init))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom | ast.Import):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return frozenset(names)


@pytest.mark.parametrize("relative_path", _keep_public_paths())
def test_a_keep_public_module_advertises_only_what_it_defines(relative_path: str) -> None:
    """A public module may not re-export a symbol another module owns."""
    path = _ROOT / relative_path
    dotted = relative_path.removeprefix("src/").removesuffix(".py").replace("/", ".")
    module = importlib.import_module(dotted)
    exported = tuple(getattr(module, "__all__", ()))
    local = _locally_bound_names(path)

    borrowed = [name for name in exported if name not in local]

    assert not borrowed, f"{dotted} advertises symbols it does not define: {borrowed}"


@pytest.mark.parametrize("relative_path", _keep_public_paths())
def test_the_registry_package_binds_no_keep_public_symbol(relative_path: str) -> None:
    """Consumers reach these modules directly, never through the package.

    The surface checked is what the module DEFINES publicly, not what it
    advertises. Keying this on ``__all__`` would assert nothing for the 23
    modules that declare none, and those are exactly the ones a stray package
    binding could hide in.
    """
    path = _ROOT / relative_path
    dotted = relative_path.removeprefix("src/").removesuffix(".py").replace("/", ".")
    package = importlib.import_module(_PACKAGE)
    defined_public = {name for name in _locally_bound_names(path) if not name.startswith("_")}

    assert defined_public, f"{dotted} defines no public symbol; the keep-public row describes nothing"

    # What the package BINDS is read from its own source, never by attribute
    # lookup. Importing a submodule makes it an attribute of its package, so
    # attribute lookup invents bindings nobody wrote - and worse, masks a real
    # one whenever a module defines a symbol sharing its own name, which
    # validate_registry_scope does exactly.
    bound = sorted(defined_public & _package_bound_names(package))

    assert not bound, f"the registry package binds {dotted} symbols: {bound}"


@pytest.mark.parametrize("relative_path", _advertising_paths())
def test_a_declared_advertisement_is_real_and_resolvable(relative_path: str) -> None:
    """Where a module declares ``__all__``, every name in it must resolve.

    Only modules that actually declare one are parameterized here, so no case
    exists that could pass without asserting anything. Modules declaring none
    are held by the package-binding check, which reads their defined surface.
    """
    dotted = relative_path.removeprefix("src/").removesuffix(".py").replace("/", ".")
    module = importlib.import_module(dotted)
    advertised = module.__all__

    assert advertised, f"{dotted} declares an empty __all__, which advertises nothing while looking deliberate"

    unresolvable = [name for name in advertised if not hasattr(module, name)]

    assert not unresolvable, f"{dotted} advertises names that do not resolve: {unresolvable}"


def test_every_keep_public_row_names_a_module_that_exists() -> None:
    """A disposition that points at a vanished module proves nothing."""
    missing = [path for path in _keep_public_paths() if not (_ROOT / path).is_file()]

    assert not missing, f"keep-public rows name absent modules: {missing}"


@pytest.mark.parametrize(("retired_path", "surviving_path"), _hard_move_pairs())
def test_a_completed_hard_move_left_no_private_module_behind(retired_path: str, surviving_path: str) -> None:
    """The move is complete only when the private path is gone, not merely unused."""
    retired = _ROOT / retired_path
    surviving = _ROOT / surviving_path

    assert not retired.is_file(), f"the retired private module still exists: {retired_path}"
    assert surviving.is_file(), f"the adjudicated owner is absent: {surviving_path}"


@pytest.mark.parametrize(("retired_path", "surviving_path"), _hard_move_pairs())
def test_a_completed_hard_move_left_no_importable_private_path(retired_path: str, surviving_path: str) -> None:
    """No consumer may still reach the retired module by its old dotted name."""
    del surviving_path
    dotted = retired_path.removeprefix("src/").removesuffix(".py").replace("/", ".")

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(dotted)


#: Census rows whose adjudicated terminal state the tree has not reached yet,
#: each with the reason it is still outstanding. A row that finishes must leave
#: this table, which the staleness test below enforces.
_OUTSTANDING_ROWS: Final[dict[str, str]] = {
    "R35": "privatisation blocked behind a large consumer move",
    "R66": "privatisation blocked behind a consumer move",
}


def _terminal_state_owners(row: dict[str, object]) -> tuple[str, ...]:
    destinations = row.get("terminal_destinations") or []
    owners = tuple(str(item["path"]) for item in destinations if item.get("role") == "defining_owner")
    return owners or ((str(row["new_path"]),) if row.get("new_path") else ())


def _terminal_state_unreached(row: dict[str, object]) -> str | None:
    """Return why a row's adjudicated terminal state is not reached, if so."""
    state = row.get("terminal_state")
    old = str(row["old_path"]) if row.get("old_path") else None
    if state in {"public_local_definitions_only", "schema_local_definitions_only"}:
        for path in _terminal_state_owners(row):
            target = _ROOT / path
            if not target.exists():
                return f"owner missing: {path}"
            if borrowed := _borrowed_exports(target):
                return f"{path} exports borrowed names: {borrowed}"
    elif state == "private_same_package_only":
        for path in _terminal_state_owners(row):
            if not (_ROOT / path).exists():
                return f"owner missing: {path}"
            if not Path(path).name.startswith("_"):
                return f"still public: {path}"
    elif state == "retired_after_hard_move":
        if old and (_ROOT / old).exists():
            return f"retired path still present: {old}"
    elif state == "deleted_no_surface":
        for path in (old, *_terminal_state_owners(row)):
            if path and (_ROOT / path).exists():
                return f"surface still present: {path}"
    return None


def test_the_registry_package_namespace_binds_nothing() -> None:
    """The package marker is inert; consumers name defining modules directly."""
    init = _ROOT / "src" / "cadrumo" / "domain" / "calculations" / "registry" / "__init__.py"
    tree = ast.parse(init.read_text(encoding="utf-8"), filename=str(init))
    bound = {
        alias.asname or alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }

    assert bound == set(), f"the registry package namespace binds project symbols: {sorted(bound)}"


def test_every_census_row_reaches_its_adjudicated_terminal_state() -> None:
    """The registry family reaches its fixed point, save the declared remainder."""
    document = json.loads(_MATRIX.read_text(encoding="utf-8"))
    rows = document["rows"]
    assert len(rows) > 50, f"census collapsed to {len(rows)} rows"

    unreached = {str(row["row_id"]): reason for row in rows if (reason := _terminal_state_unreached(row)) is not None}
    undeclared = {k: v for k, v in unreached.items() if k not in _OUTSTANDING_ROWS}

    assert undeclared == {}, f"census rows regressed from their terminal state: {undeclared}"


def test_every_declared_outstanding_row_is_still_outstanding() -> None:
    """A finished row must leave the table rather than sit here forever."""
    document = json.loads(_MATRIX.read_text(encoding="utf-8"))
    unreached = {str(row["row_id"]) for row in document["rows"] if _terminal_state_unreached(row) is not None}
    settled = sorted(row_id for row_id in _OUTSTANDING_ROWS if row_id not in unreached)

    assert settled == [], f"rows reached their terminal state and must leave the table: {settled}"
    assert all(_OUTSTANDING_ROWS.values()), "every outstanding row states why it is outstanding"
