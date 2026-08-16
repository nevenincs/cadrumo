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
would have been a serious error. The two live-evidence roots used to reach
their settings through ``_resolve_live_output_root(output_root,
"cadrumo_iva_read_evidence_dir")`` -- the field named as a string and resolved
dynamically. An attribute walk alone cannot see that, so an attribute-only
gate would have reported both as writer-less, and someone acting on the
report would have deleted a live category holding regulated filing evidence.
That call site has since collapsed onto a shared resolver that takes the
default as a callable rather than a field-name string, so today's claims are
all backed by attribute-load evidence -- but the third shape stays, proven by
the discrimination test below, because a future dynamic-name lookup is
exactly the pattern that motivated it in the first place.

That shape is the mirror image of the trap this gate is most careful about, so
admitting it must not admit the trap: ``core/auth_session_keys.py`` names a
settings field inside its **module docstring**, precisely to record that it is
deliberately independent of it. A docstring is also an ``ast.Constant``. The
two are distinguished structurally -- every docstring node is collected and
excluded by identity -- rather than by an allowlist entry, and the
discrimination test below proves a docstring mention satisfies nothing. Four
independent passes agreed on a dormancy verdict while sharing one weak method;
a mention is not a consumption, and this is where that lesson is encoded.

A fifth trap, found after the first four: a bare ``ast.Attribute`` load of the
category member's NAME is not enough, because the name alone is not unique to
``StorageCategory``. This gate once accepted 14 references to
an unrelated enum member that happened to share a storage member name as proof
that the storage category was consumed. The category-member shape now requires
the attribute's
receiver to resolve to a name bound to ``StorageCategory`` (see
:func:`_storage_category_binding_names`); the settings-field shape and the
string-constant shape carry no such qualification, because they have no same-
named collision to guard against and qualifying them would only risk a false
negative. See :func:`consumption_evidence` for the full reasoning and the
discrimination tests below for the proof.
"""

from __future__ import annotations

import ast
from functools import cache
from pathlib import Path

import pytest

from .. import scan_directory
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
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            found.add(id(body[0].value))
    return found


def _storage_category_binding_names(tree: ast.AST) -> set[str]:
    """Return every local name bound to the ``StorageCategory`` enum in ``tree``.

    Mirrors the discriminator this project already uses for ``Modelo`` member
    references (``test_generic_module_modelo_carveouts.py``): a bare attribute
    name is not evidence of a reference to a SPECIFIC enum, only its receiver
    resolving to that enum's own bound name is. A module may import the enum
    under an alias, so the alias set -- not the literal string
    ``"StorageCategory"`` alone -- is what a reference must resolve against.
    """
    names = {"StorageCategory"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(alias.asname for alias in node.names if alias.name == "StorageCategory" and alias.asname)
    return names


def consumption_evidence(
    tree: ast.AST,
    *,
    settings_field: str | None,
    category_member: str,
) -> frozenset[str]:
    """Return which of ``settings_field`` / ``category_member`` the module genuinely references.

    A pure function over a parsed tree, so the discrimination tests can hand it
    synthetic source and prove each shape counts or does not.

    The two names are NOT interchangeable evidence. ``category_member`` is a
    bare enum-member name shared with other closed-value enums in this
    codebase. An attribute
    load only counts as evidence of ``category_member`` when its receiver
    resolves to a name bound to ``StorageCategory`` (see
    :func:`_storage_category_binding_names`); a bare ``.AUDIT`` on anything
    else is not evidence. This gate previously accepted unrelated same-named
    enum references as storage consumption before this qualification existed.

    ``settings_field`` carries no such qualification, deliberately: settings
    field names (``cadrumo_live_state_dir``, ...) are prefix-distinctive on their
    own, so requiring the receiver to resolve to a ``Settings`` binding would
    buy nothing and risks a false negative against a legitimate indirect
    access (``getattr(settings, "cadrumo_live_state_dir")``, a root-derivation
    table keyed by field name). A settings field is also, unlike a category
    member, real evidence as a bare string constant -- some live consumers
    resolve the field dynamically by name (see the module docstring) -- so
    the string-constant shape is checked only against ``settings_field``. A
    bare category-member name as a string is not a
    category reference (nothing in this codebase resolves a
    ``StorageCategory`` member dynamically by name) and is not evidence for
    ``category_member``.

    Args:
        tree: The consuming module's parsed AST.
        settings_field: The bound settings field name, or ``None`` when the
            member declares none.
        category_member: The category member's bare enum-member name.

    Returns:
        The subset of ``{settings_field, category_member}`` for which real
        evidence exists.
    """
    docstrings = docstring_nodes(tree)
    category_owners = _storage_category_binding_names(tree)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            is_qualified_category_reference = (
                node.attr == category_member and isinstance(node.value, ast.Name) and node.value.id in category_owners
            )
            is_field_attribute = settings_field is not None and node.attr == settings_field
            if is_qualified_category_reference or is_field_attribute:
                found.add(node.attr)
        elif (
            settings_field is not None
            and isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value == settings_field
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
    """The names that count as evidence for this member, for display in a failure message.

    Not passed to :func:`consumption_evidence` directly -- the category member
    and the settings field are checked under different rules, so a call site
    passes them as the two separate keyword arguments. This stays as the
    flat set a failure message reads naturally.
    """
    names = {location.category.name}
    if location.settings_field is not None:
        names.add(location.settings_field)
    return frozenset(names)


#: The harness ships as its own distribution beside the package, so a consumer
#: living there is not reachable under ``src/cadrumo``. Resolving both roots
#: keeps a TRUE claim expressible; without it the only way to make the gate
#: green is to call a live consumer dormant, which is the lie this gate exists
#: to catch.
_CONSUMER_ROOTS = (SRC_CADRUMO, SRC_CADRUMO.parent / "cadrumo-harness" / "src")


@cache
def _tree_for(module: str) -> ast.AST | None:
    for root in _CONSUMER_ROOTS:
        path = root / module
        if path.is_file():
            return ast.parse(path.read_text(encoding="utf-8"))
    return None


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

    # Totality over an empty taxonomy is vacuous, and a collapsed member set
    # would also make every consumer claim below trivially satisfied -- the
    # gate would report a fully live tree while inspecting nothing. Bounds,
    # not counts, so the floor survives an ordinary new member.
    assert len(STORAGE_TAXONOMY) >= 30, (
        f"the taxonomy declares only {len(STORAGE_TAXONOMY)} member(s); it governs dozens of "
        "locations, so this means the declaration collapsed and every assertion here holds "
        "vacuously"
    )
    claiming = _members_claiming_a_consumer()
    assert len(claiming) >= 20, (
        f"only {len(claiming)} member(s) claim a consumer. Most declared locations are live, so a "
        "number this low means either the claims were stripped or nearly everything was marked "
        "dormant -- and 'everything is dormant' passes this gate while meaning nothing"
    )


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
        if not consumption_evidence(
            tree,
            settings_field=location.settings_field,
            category_member=location.category.name,
        ):
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
        for module, tree in _production_trees():
            if location.settings_field is not None and declares_field(tree, location.settings_field):
                continue
            if consumption_evidence(
                tree,
                settings_field=location.settings_field,
                category_member=location.category.name,
            ):
                contradicted.append(f"{location.category.value} is declared dormant but {module} references it")
                break
    assert not contradicted, (
        f"dormancy claim(s) the tree refutes: {contradicted}. A member that gained a consumer must "
        "trade its dormant_reason for a consumer_module naming that module"
    )


#: The modules that DECLARE the taxonomy, as opposed to consuming it.
_TAXONOMY_DECLARATION_MODULES = frozenset(
    {"core/_storage_taxonomy.py", "core/_storage_taxonomy_locations.py"},
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
    for path in scan_directory(SRC_CADRUMO, pattern="*.py", recursive=True):
        relative = path.relative_to(SRC_CADRUMO).as_posix()
        # Both declaration modules are excluded: a member's own declaration
        # names it by construction, so counting the declaration as consumption
        # refutes every dormancy claim with itself. The locations module was
        # split out of the taxonomy module and inherited that requirement.
        if "/tests/" in f"/{relative}" or relative.startswith("tests/") or relative in _TAXONOMY_DECLARATION_MODULES:
            continue
        try:
            trees.append((relative, ast.parse(path.read_text(encoding="utf-8"))))
        except SyntaxError:  # pragma: no cover - a syntactically broken module fails elsewhere
            continue
    return tuple(trees)


# --------------------------------------------------------------------- #
# Discrimination: what counts as evidence, and what must not             #
# --------------------------------------------------------------------- #

_SETTINGS_FIELD = "cadrumo_inbox_dir"
_CATEGORY_MEMBER = "INBOX"


def _evidence(source: str, *, settings_field: str | None = _SETTINGS_FIELD) -> frozenset[str]:
    return consumption_evidence(ast.parse(source), settings_field=settings_field, category_member=_CATEGORY_MEMBER)


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


def test_an_unrelated_enum_member_of_the_same_name_is_not_a_consumption() -> None:
    """The namespace-qualification proof: ``Other.INBOX`` is not ``StorageCategory.INBOX``.

    This is the real defect this gate shipped with: references to an unrelated
    same-named enum member satisfied a storage consumer claim. An attribute
    name alone is not enough; the receiver has to resolve
    to a name bound to ``StorageCategory``.
    """
    unrelated = consumption_evidence(
        ast.parse("def read():\n    return Other.INBOX\n"),
        settings_field=None,
        category_member="INBOX",
    )
    assert unrelated == frozenset(), "an unrelated enum's same-named member must not count as evidence"

    real = consumption_evidence(
        ast.parse("def read():\n    return StorageCategory.INBOX\n"),
        settings_field=None,
        category_member="INBOX",
    )
    assert real == frozenset({"INBOX"}), "a genuine StorageCategory.INBOX reference must still count"


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


def test_a_bare_category_member_string_is_not_a_consumption() -> None:
    """A category member is not looked up dynamically by name anywhere in this codebase.

    The string-constant shape exists for the settings field, which some live
    consumers DO resolve by name (see the module docstring). Nothing resolves
    a ``StorageCategory`` member that way, so a bare ``"AUDIT"`` string is not
    evidence for the category member -- unlike ``"cadrumo_live_state_dir"``, which
    would be. Proven directly against :func:`consumption_evidence` rather than
    through ``_evidence``, since this member has no settings field to conflate
    the result with.
    """
    evidence = consumption_evidence(
        ast.parse('def read():\n    return getattr(taxonomy, "INBOX")\n'),
        settings_field=None,
        category_member="INBOX",
    )
    assert evidence == frozenset(), "a bare category-member string must not count as consumption"


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
