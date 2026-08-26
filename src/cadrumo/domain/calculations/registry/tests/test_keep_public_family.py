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
import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ROOT = Path(__file__).resolve().parents[6]
_MATRIX = _ROOT / "dev" / "quality" / "registry_facade_family_census.v1.json"
_PLAN = _ROOT / ".vault" / "plan" / "2026-08-11-tui-architecture-plan.md"
_PACKAGE = "cadrumo.domain.calculations.registry"


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
    """Consumers reach these modules directly, never through the package."""
    dotted = relative_path.removeprefix("src/").removesuffix(".py").replace("/", ".")
    module = importlib.import_module(dotted)
    package = importlib.import_module(_PACKAGE)

    bound = [name for name in getattr(module, "__all__", ()) if hasattr(package, name)]

    assert not bound, f"the registry package binds {dotted} symbols: {bound}"


def test_every_keep_public_row_names_a_module_that_exists() -> None:
    """A disposition that points at a vanished module proves nothing."""
    missing = [path for path in _keep_public_paths() if not (_ROOT / path).is_file()]

    assert not missing, f"keep-public rows name absent modules: {missing}"


def test_the_gate_covers_every_open_keep_public_disposition_step() -> None:
    """No keep-public row may close without this gate actually holding it."""
    document = json.loads(_MATRIX.read_text(encoding="utf-8"))
    plan = _PLAN.read_text(encoding="utf-8")
    step_ids = set(re.findall(r"^- \[[ x]\] `(W03\.P20\.S\d+)`", plan, flags=re.MULTILINE))

    unbound = [
        row["follow_on_step_id"]
        for row in document["rows"]
        if row["disposition"] == "keep_public" and row["follow_on_step_id"] not in step_ids
    ]

    assert not unbound, f"keep-public rows name Steps the plan does not carry: {unbound}"


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
