"""A declared location nothing touches is a decision nobody has taken.

Four categories in this taxonomy have no production consumer whatsoever. They
were found by audit, late, and only because someone went looking; nothing in
the suite could have said so, because a declaration is satisfied by being
written down. This gate makes the condition loud at the point of declaration
instead of discoverable at the point of audit.

**Declare, then verify.** Each member states either a ``consumer_module`` or a
``dormant_reason``, the model refuses a member that states both or neither, and
this gate checks the claim structurally against the named module's AST. The
declaration alone never satisfies the gate -- "it has a consumer because it says
it has one" is exactly the shape being rejected.

Why not whole-program write-reachability: tracing statically from an attribute
load to a filesystem write produces a false negative on every indirection, and
a gate that blocks legitimate changes is one somebody switches off the first
time it is inconvenient. Consumption is weaker in theory and far stronger in
practice, because a location no module touches cannot be written to.

Three evidence shapes, and why the third is here
------------------------------------------------
A claim is satisfied by an ``ast.Attribute`` load of the bound settings field,
an ``ast.Attribute`` load of the category member, **or** the field name as a
non-docstring string constant.

The third shape was added on measurement, not on principle, and omitting it
would have been a serious error. The two live-evidence roots reach their
settings through ``_resolve_live_output_root(output_root,
"cadrumo_iva_read_evidence_dir")`` -- the field named as a string and resolved
dynamically. An attribute walk cannot see that, so an attribute-only gate
reports both as writer-less, and someone acting on the report deletes a live
category holding regulated filing evidence.

That shape is the mirror image of the trap this gate is most careful about, so
admitting it must not admit the trap: ``core/auth_session_keys.py`` names a
settings field inside its **module docstring**, precisely to record that it is
deliberately independent of it. A docstring is also an ``ast.Constant``. The
two are distinguished structurally -- every docstring node is collected and
excluded by identity -- rather than by an allowlist entry, and the
discrimination test below proves a docstring mention satisfies nothing. Four
independent passes agreed on a dormancy verdict while sharing one weak method;
a mention is not a consumption, and this is where that lesson is encoded.
"""

from __future__ import annotations

import ast
from functools import cache
from pathlib import Path

import pytest

from .._storage_taxonomy import STORAGE_TAXONOMY, StorageLocation

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

SRC_CADRUMO = Path(__file__).resolve().parents[2]


def docstring_nodes(tree: ast.AST) -> set[int]:
    """Return the ``id()`` of every string constant serving as a docstring.

    Collected by structure -- the first statement of a module, class, or
    function body when that statement is a bare string expression -- so a
    docstring can never be mistaken for a reference.
    """
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        body = node.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            if isinstance(body[0].value.value, str):
                found.add(id(body[0].value))
    return found


def consumption_evidence(tree: ast.AST, names: frozenset[str]) -> frozenset[str]:
    """Return which of ``names`` the module genuinely references.

    A pure function over a parsed tree, so the discrimination tests can hand it
    synthetic source and prove each shape counts or does not.

    Args:
        tree: The consuming module's parsed AST.
        names: The bound settings field and the category member name.

    Returns:
        The subset of ``names`` for which real evidence exists.
    """
    docstrings = docstring_nodes(tree)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in names:
            found.add(node.attr)
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in names
            and id(node) not in docstrings
        ):
            found.add(node.value)
    return frozenset(found)


def declares_field(tree: ast.AST, field_name: str) -> bool:
    """Whether this module *declares* ``field_name`` as an annotated attribute.

    The settings model and its field mixins name every field they define, and
    the root-derivation table names them again as string constants. Neither is
    a consumption -- it is the declaration and the machinery that gives it a
    default. Derived structurally from an ``ast.AnnAssign`` target rather than
    listed as excluded modules, so a field mixin added later needs no entry
    anywhere.
    """
    return any(
        isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == field_name
        for node in ast.walk(tree)
    )


def _claim_names(location: StorageLocation) -> frozenset[str]:
    """The names that count as evidence for this member."""
    names = {location.category.name}
    if location.settings_field is not None:
        names.add(location.settings_field)
    return frozenset(names)


@cache
def _tree_for(module: str) -> ast.AST | None:
    path = SRC_CADRUMO / module
    if not path.is_file():
        return None
    return ast.parse(path.read_text(encoding="utf-8"))


def _members_claiming_a_consumer() -> tuple[StorageLocation, ...]:
    return tuple(location for location in STORAGE_TAXONOMY.values() if location.consumer_module is not None)


def test_the_taxonomy_declares_a_liveness_claim_for_every_member() -> None:
    """Totality, enforced on the model so a new member cannot skip the question."""
    unclaimed = sorted(
        category.value
        for category, location in STORAGE_TAXONOMY.items()
        if location.consumer_module is None and location.dormant_reason is None
    )
    assert not unclaimed, (
        f"storage taxonomy member(s) {unclaimed} declare neither a consumer_module nor a "
        "dormant_reason. Name the production module that consumes the location, or state why "
        "nothing does -- a member that answers neither is a location the application creates and "
        "may never use"
    )
    assert _members_claiming_a_consumer(), "no member claims a consumer; discovery, not the tree, is broken"


def test_every_named_consumer_module_exists() -> None:
    """A claim pointing at a module that is gone is not a claim."""
    missing = sorted(
        f"{location.category.value} -> {location.consumer_module}"
        for location in _members_claiming_a_consumer()
        if _tree_for(location.consumer_module or "") is None
    )
    assert not missing, (
        f"consumer_module claim(s) naming a module that does not exist: {missing}. Re-point the "
        "claim in the same change that moves or deletes the module"
    )


def test_every_consumer_claim_is_backed_by_a_real_reference() -> None:
    """The verification half. A mention in prose satisfies nothing."""
    unbacked: list[str] = []
    for location in _members_claiming_a_consumer():
        module = location.consumer_module or ""
        tree = _tree_for(module)
        if tree is None:
            continue
        if not consumption_evidence(tree, _claim_names(location)):
            unbacked.append(
                f"{location.category.value} claims {module}, which references neither {sorted(_claim_names(location))}"
            )
    assert not unbacked, (
        f"consumer_module claim(s) the named module does not back: {unbacked}. Either the "
        "consumption moved -- re-point the claim at the module that now reads the location -- or "
        "it was removed, in which case the member is dormant and must say so with a reason. This "
        "is the event no other check catches: the field quietly became dead"
    )


def test_every_dormant_member_states_a_reason_and_really_is_dormant() -> None:
    """A dormant claim is refuted by any module that consumes the member.

    The converse direction, and the one that keeps the dormancy list honest: if
    someone wires a category up, its declaration must stop calling it dormant
    rather than sitting there contradicting the code.
    """
    contradicted: list[str] = []
    for location in STORAGE_TAXONOMY.values():
        if location.dormant_reason is None:
            continue
        assert location.dormant_reason.strip(), f"{location.category.value} declares an empty dormant reason"
        names = _claim_names(location)
        for module, tree in _production_trees():
            if location.settings_field is not None and declares_field(tree, location.settings_field):
                continue
            if consumption_evidence(tree, names):
                contradicted.append(f"{location.category.value} is declared dormant but {module} references it")
                break
    assert not contradicted, (
        f"dormancy claim(s) the tree refutes: {contradicted}. A member that gained a consumer must "
        "trade its dormant_reason for a consumer_module naming that module"
    )


@cache
def _production_trees() -> tuple[tuple[str, ast.AST], ...]:
    """Every production module, parsed once.

    Test modules are excluded deliberately: a fixture that sets a field proves
    only that the field can be set, not that anything reads it back. Three of
    the four dormant members are set by test fixtures and consumed by nothing,
    which is precisely the shape a test-inclusive sweep would have missed.
    """
    trees: list[tuple[str, ast.AST]] = []
    for path in sorted(SRC_CADRUMO.rglob("*.py")):
        relative = path.relative_to(SRC_CADRUMO).as_posix()
        if "/tests/" in f"/{relative}" or relative.startswith("tests/") or relative == "core/_storage_taxonomy.py":
            continue
        try:
            trees.append((relative, ast.parse(path.read_text(encoding="utf-8"))))
        except SyntaxError:  # pragma: no cover - a syntactically broken module fails elsewhere
            continue
    return tuple(trees)


# --------------------------------------------------------------------- #
# Discrimination: what counts as evidence, and what must not             #
# --------------------------------------------------------------------- #

_NAMES = frozenset({"cadrumo_inbox_dir", "INBOX"})


def _evidence(source: str) -> frozenset[str]:
    return consumption_evidence(ast.parse(source), _NAMES)


def test_a_docstring_mention_is_not_a_consumption() -> None:
    """The single most important assertion in this module.

    A module naming a settings field in its docstring -- often precisely to
    record that it does *not* use it -- must not satisfy a consumer claim. This
    is the trap four independent passes fell into, encoded so a fifth cannot.
    """
    assert _evidence('"""This module is deliberately independent of cadrumo_inbox_dir."""\n') == frozenset()
    assert _evidence('def read():\n    """Nothing here touches cadrumo_inbox_dir."""\n    return None\n') == frozenset()
    assert (
        _evidence('class Reader:\n    """Unrelated to cadrumo_inbox_dir and to INBOX."""\n\n    x = 1\n') == frozenset()
    )


@pytest.mark.parametrize(
    ("label", "source"),
    [
        ("an attribute load of the field", "def read():\n    return settings.cadrumo_inbox_dir\n"),
        ("an attribute load of the category", "def read():\n    return storage_path(StorageCategory.INBOX)\n"),
        (
            "the field named as a string constant",
            'def read():\n    return _resolve_root(value, "cadrumo_inbox_dir")\n',
        ),
        ("a getattr by name", 'def read():\n    return getattr(settings, "cadrumo_inbox_dir")\n'),
    ],
)
def test_each_real_reference_shape_counts_as_consumption(label: str, source: str) -> None:
    """Every way a module genuinely reaches the location is evidence."""
    assert _evidence(source), f"the {label} shape was not counted as consumption"


def test_consumption_is_found_below_module_level() -> None:
    """A member consumed inside a method, not at module top level, stays green."""
    source = (
        "class Writer:\n"
        "    def persist(self, settings):\n"
        '        target = settings.cadrumo_inbox_dir / "doc.pdf"\n'
        "        return target\n"
    )
    assert _evidence(source) == frozenset({"cadrumo_inbox_dir"})


def test_an_unrelated_module_yields_no_evidence() -> None:
    """The positive control: a detector that fired on everything would be useless."""
    assert _evidence("def read(settings):\n    return settings.cadrumo_drafts_dir\n") == frozenset()
