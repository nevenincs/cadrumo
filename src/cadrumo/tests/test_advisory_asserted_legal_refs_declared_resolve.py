"""Every advisory that DECLARES an asserted provision must declare one that resolves.

A sibling gate proves the resolution helper works when it is called. This one
removes the "when it is called" — it finds every production site that declares
``CalculationSourceDiagnostic.asserted_legal_refs`` and resolves the declared
ids against the live legal catalogue, so a site cannot decline the check by
simply not invoking it.

**Why a source scan rather than registry build.** The originating requirement
says "refuse at registry build". Registry build validates the compiled TOML
tree, and ``asserted_legal_refs`` has no TOML surface at all: the field lives on
a runtime model that application code constructs in Python, so every declaration
is a keyword argument in a call expression. The source tree is therefore the
enforcement point, and a scan of it is the strongest available form of the
requirement rather than a weaker substitute for it. Were the field ever given a
registry-authored surface, that surface would become the right home and this
gate would be the wrong shape.

**A declaration must be readable to be checkable.** A declared value that is
computed at runtime cannot be resolved by any static gate, so a computed
declaration is refused here rather than skipped. That is not merely mechanical
convenience. The field's own contract says declaring an id is a tax review
against the provision the message states, never a derivation from a casilla or
binding already in hand — so a value assembled by an expression is the exact
shape the field exists to prevent, and refusing it enforces the contract as well
as the checkability.

The population is EMPTY today, which is why this lands green and why the
anti-vacuity proof below is the part that carries the weight: with no declaring
site in the tree, a scan that silently matched nothing would be
indistinguishable from a scan that worked. The proofs run the real scanner over
real files written outside the repository and require it to find, resolve and
refuse.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import pytest

from ..domain.calculations.registry.authority import bundled_authority
from ..domain.calculations.registry.errors import RegistryValidationError
from ..domain.calculations.registry.legal import assert_legal_ref_ids_resolve
from ._inventory import production_ast_items, repo_relative

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from ..domain.calculations.registry.schema_references import LegalReference

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The keyword whose value is a claim about law. Kept as one constant because
#: the scanner matches it in two syntactic positions.
_DECLARATION_KEYWORD = "asserted_legal_refs"

#: Sites permitted to declare a value this gate cannot resolve statically, keyed
#: by ``(repository-relative path, enclosing function)`` — never by line number,
#: which drifts on any edit above it. Each entry states its reason. Empty by
#: construction: no production site declares the field yet, and the first one to
#: do so should declare literals rather than earn an exemption.
_UNRESOLVABLE_DECLARATION_EXEMPTIONS: Mapping[tuple[str, str], str] = dict[tuple[str, str], str]()


def _display_path(path: Path) -> str:
    """Return a repository-relative path, or the plain path when outside the tree.

    The scanner is root-agnostic so the proofs can run it over files written
    outside the repository, and the reporting has to be too: a path helper that
    raises on an out-of-tree file would make the anti-vacuity proofs impossible
    to write, which is how a gate ends up with none.
    """
    try:
        return repo_relative(path)
    except ValueError:
        return path.as_posix()


class _Declaration(NamedTuple):
    """One production site declaring provisions an advisory asserts about itself."""

    path: Path
    function: str
    lineno: int
    ref_ids: tuple[str, ...] | None
    """Declared ids, or ``None`` when the value is not a static literal."""

    @property
    def site(self) -> tuple[str, str]:
        """Return the ``(path, enclosing function)`` key this site is exempted by."""
        return (_display_path(self.path), self.function)


def _string_tuple(node: ast.expr) -> tuple[str, ...] | None:
    """Return the string constants of a literal tuple or list, else ``None``."""
    if not isinstance(node, ast.Tuple | ast.List):
        return None
    values: list[str] = []
    for element in node.elts:
        if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
            return None
        values.append(element.value)
    return tuple(values)


def _module_level_literals(tree: ast.AST) -> dict[str, tuple[str, ...]]:
    """Return module-level names bound to a literal tuple or list of strings.

    A declaring site that hoists its ids into a module constant is still
    declaring literals, and reading that binding keeps the gate from pushing
    authors toward inlining ids purely to satisfy it.
    """
    literals: dict[str, tuple[str, ...]] = {}
    if not isinstance(tree, ast.Module):
        return literals
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        else:
            continue
        value = _string_tuple(node.value) if node.value is not None else None
        if value is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                literals[target.id] = value
    return literals


def _declared_value(node: ast.expr, module_literals: Mapping[str, tuple[str, ...]]) -> tuple[str, ...] | None:
    """Resolve a declaration's value to literal ids, or ``None`` if computed."""
    direct = _string_tuple(node)
    if direct is not None:
        return direct
    if isinstance(node, ast.Name):
        return module_literals.get(node.id)
    return None


def _declaration_values(node: ast.AST) -> Iterable[ast.expr]:
    """Yield the expressions *node* itself assigns to the declaration keyword.

    Two syntactic positions carry a declaration: the keyword argument of a
    constructor call, and an ``"asserted_legal_refs"`` key inside a dict
    literal, which is how an update mapping would carry one.
    """
    if isinstance(node, ast.Call):
        for keyword in node.keywords:
            if keyword.arg == _DECLARATION_KEYWORD:
                yield keyword.value
    elif isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values, strict=True):
            if isinstance(key, ast.Constant) and key.value == _DECLARATION_KEYWORD:
                yield value


def _descend(
    node: ast.AST,
    *,
    path: Path,
    scope: str,
    module_literals: Mapping[str, tuple[str, ...]],
    out: list[_Declaration],
) -> None:
    """Collect declarations under *node*, attributing each to its innermost scope.

    Scope is tracked on the way down rather than recovered afterwards, so a
    declaration inside a nested function is keyed by that function rather than
    by the module — the exemption key is ``(path, enclosing function)`` and it
    is only stable if the attribution is the innermost one.
    """
    for child in ast.iter_child_nodes(node):
        child_scope = child.name if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) else scope
        for value in _declaration_values(child):
            out.append(
                _Declaration(
                    path=path,
                    function=child_scope,
                    lineno=value.lineno,
                    ref_ids=_declared_value(value, module_literals),
                ),
            )
        _descend(child, path=path, scope=child_scope, module_literals=module_literals, out=out)


def collect_asserted_legal_ref_declarations(
    items: Iterable[tuple[Path, ast.AST]],
) -> tuple[_Declaration, ...]:
    """Return every site in *items* declaring provisions an advisory asserts.

    Pure and root-agnostic so the anti-vacuity proofs can run the identical
    scanner over files written outside the repository. A gate whose proof
    exercises a different code path than its production run proves nothing about
    the production run.
    """
    declarations: list[_Declaration] = []
    for path, tree in items:
        _descend(
            tree,
            path=path,
            scope="<module>",
            module_literals=_module_level_literals(tree),
            out=declarations,
        )
    return tuple(declarations)


def _legal_catalogue() -> Mapping[str, LegalReference]:
    """Return the live bundled legal catalogue every declaration resolves against."""
    return bundled_authority().catalogues.legal


def _resolve_all(
    declarations: Iterable[_Declaration],
    *,
    catalogue: Mapping[str, LegalReference],
) -> None:
    """Refuse any declaration that is unreadable or names an absent provision.

    The catalogue is a parameter rather than a lookup so the checking logic is
    one function with one code path: the tree run and every proof below call
    exactly this, differing only in which declarations they hand it.
    """
    unresolvable = [
        declaration
        for declaration in declarations
        if declaration.ref_ids is None and declaration.site not in _UNRESOLVABLE_DECLARATION_EXEMPTIONS
    ]
    if unresolvable:
        sites = ", ".join(
            f"{_display_path(d.path)}:{d.lineno} in {d.function}()"
            for d in sorted(unresolvable, key=lambda d: d.lineno)
        )
        raise RegistryValidationError(
            f"{_DECLARATION_KEYWORD} must be declared as string literals so the provisions it "
            f"claims can be resolved against the legal catalogue; computed at: {sites}",
        )
    for declaration in declarations:
        if declaration.ref_ids is None:
            continue
        assert_legal_ref_ids_resolve(
            declaration.ref_ids,
            legal=catalogue,
            subject=f"{_display_path(declaration.path)}:{declaration.lineno} in {declaration.function}()",
        )


def test_every_declared_asserted_provision_resolves(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """No production site declares a provision the legal catalogue does not carry.

    Gated on the property rather than on a tally: the declaring population is
    expected to grow as advisories are adjudicated one by one, and a count
    baked in here would only train the next author to bump it.
    """
    _resolve_all(
        collect_asserted_legal_ref_declarations(production_ast_items(source_tree_ast)),
        catalogue=_legal_catalogue(),
    )


def test_the_scanned_surface_reaches_the_module_declarations_will_live_in(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """The scan surface actually covers where a declaration would be written.

    The proofs below run the scanner over scratch files, which shows it can
    find a declaration but not that the TREE run looks anywhere useful. A
    detector that is correct on synthetic input and never reaches the real site
    is the failure mode an anti-tautology proof alone cannot catch, so this
    asserts reachability of the module that DEFINES the field — resolved from
    the class rather than hardcoded, so a relocation moves the anchor with it
    instead of quietly emptying the gate.
    """
    from ..application.aggregation import CalculationSourceDiagnostic

    defining_module = sys.modules[CalculationSourceDiagnostic.__module__]
    defining_file = Path(defining_module.__file__ or "").resolve()
    scanned = {path.resolve() for path, _ in production_ast_items(source_tree_ast)}

    assert defining_file in scanned, (
        f"the production scan surface does not include {defining_file}, which defines the field this "
        "gate checks; a declaration written beside it would never be seen and the gate would pass vacuously"
    )


def _scratch_module(tmp_path: Path, name: str, body: str) -> tuple[Path, ast.AST]:
    """Write a scratch declaring site outside the repository and parse it."""
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return (path, ast.parse(body, filename=str(path)))


def test_the_scanner_finds_a_declaration_it_is_pointed_at(tmp_path: Path) -> None:
    """Anti-vacuity: the scanner is not blind.

    With no declaring site in the tree, the gate above passes whether or not the
    scanner works. This proof runs the same scanner over a file that does
    declare, in each syntactic position it claims to cover, and requires it to
    come back with the ids.
    """
    keyword_site = _scratch_module(
        tmp_path,
        "keyword_site.py",
        "def advisory():\n"
        "    return Diagnostic(\n"
        "        message='x',\n"
        "        asserted_legal_refs=('ley-35-2006:art-81-2', 'ley-35-2006:art-81-3'),\n"
        "    )\n",
    )
    hoisted_site = _scratch_module(
        tmp_path,
        "hoisted_site.py",
        "_REFS = ('ley-37-1992:art-103',)\n\n\ndef advisory():\n    return Diagnostic(asserted_legal_refs=_REFS)\n",
    )
    mapping_site = _scratch_module(
        tmp_path,
        "mapping_site.py",
        "def advisory():\n    return base.model_copy(update={'asserted_legal_refs': ('ley-37-1992:art-104',)})\n",
    )

    found = collect_asserted_legal_ref_declarations([keyword_site, hoisted_site, mapping_site])

    assert {declaration.ref_ids for declaration in found} == {
        ("ley-35-2006:art-81-2", "ley-35-2006:art-81-3"),
        ("ley-37-1992:art-103",),
        ("ley-37-1992:art-104",),
    }
    assert {declaration.function for declaration in found} == {"advisory"}


def test_a_fabricated_declared_provision_is_refused(tmp_path: Path) -> None:
    """The gate BITES: a declaring site naming an absent provision refuses.

    The refusal names the offending site, so a failure points at the
    declaration rather than at the gate.
    """
    site = _scratch_module(
        tmp_path,
        "fabricated.py",
        "def eligibility_advisory():\n    return Diagnostic(asserted_legal_refs=('ley-99-9999:art-0',))\n",
    )

    with pytest.raises(RegistryValidationError, match="ley-99-9999:art-0"):
        _resolve_all(collect_asserted_legal_ref_declarations([site]), catalogue=_legal_catalogue())


def test_a_real_declared_provision_passes(tmp_path: Path) -> None:
    """The other direction: a gate that refused everything would pass the bite proof alone.

    The id is drawn from the measured population an advisory would legitimately
    declare, so this also holds the catalogue to carrying it.
    """
    site = _scratch_module(
        tmp_path,
        "legitimate.py",
        "def eligibility_advisory():\n    return Diagnostic(asserted_legal_refs=('ley-35-2006:art-81-3',))\n",
    )

    _resolve_all(collect_asserted_legal_ref_declarations([site]), catalogue=_legal_catalogue())


def test_the_tree_run_itself_reds_when_one_bad_declaration_joins_it(
    source_tree_ast: Mapping[Path, ast.AST],
    tmp_path: Path,
) -> None:
    """The definitive bite proof: the REAL tree run, plus one bad site, refuses.

    The scratch proofs show the scanner and the resolver each work in
    isolation. This composes them with the production scan surface itself —
    the same ``production_ast_items`` call the tree gate makes — so what is
    exercised is the whole chain the gate runs, not a rehearsal of it. Nothing
    is written into the repository: the offending site is a file outside the
    tree appended to the real scan, which is what the tree gate would see the
    moment such a declaration were committed.
    """
    offending = _scratch_module(
        tmp_path,
        "unadjudicated_advisory.py",
        "def eligibility_advisory():\n    return Diagnostic(asserted_legal_refs=('ley-35-2006:art-9999',))\n",
    )
    real_items = production_ast_items(source_tree_ast)

    # The real surface alone is green, so the refusal below is attributable to
    # the added site rather than to something already in the tree.
    _resolve_all(collect_asserted_legal_ref_declarations(real_items), catalogue=_legal_catalogue())

    with pytest.raises(RegistryValidationError, match="ley-35-2006:art-9999"):
        _resolve_all(
            collect_asserted_legal_ref_declarations([*real_items, offending]),
            catalogue=_legal_catalogue(),
        )


def test_a_computed_declaration_is_refused(tmp_path: Path) -> None:
    """A value no static reader can resolve is refused rather than skipped.

    Skipping it would leave the one shape that defeats the gate entirely
    available, and it is also the shape the field's contract forbids: ids are a
    tax review, not a derivation from a casilla already in hand.
    """
    site = _scratch_module(
        tmp_path,
        "computed.py",
        "def advisory(casilla):\n    return Diagnostic(asserted_legal_refs=tuple(casilla.legal_refs))\n",
    )

    with pytest.raises(RegistryValidationError, match="must be declared as string literals"):
        _resolve_all(collect_asserted_legal_ref_declarations([site]), catalogue=_legal_catalogue())
