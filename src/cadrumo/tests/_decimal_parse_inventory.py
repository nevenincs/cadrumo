"""Structural detection of unvalidated string-to-:class:`~decimal.Decimal` parses.

The sibling :mod:`~tests._inventory` surface answers "which files do structural
ratchets scan"; this module answers the narrower question "does this
``Decimal(...)`` call parse *text*". A bare ``Decimal(text)`` silently admits
scientific notation, a leading ``+``, an underscore digit separator, and the
non-finite ``NaN``/``Infinity`` — and a ``NaN`` monetary value compares ``False``
to every threshold, so an under-declaration advisory keyed on ``> 0`` never fires
for it. Every such call must route through the canonical grammar
(:func:`~core.decimal.try_parse_canonical_decimal`) or the tolerant coercion
helper (:func:`~core.decimal.coerce_decimal`) instead.

Why the argument's *type* is the discriminator
----------------------------------------------

``Decimal(len(rows))`` and ``Decimal(self.runs)`` widen an integer: no grammar is
involved, the result cannot be non-finite, and nothing can be misread. Only a
*string* argument carries a grammar, so only a string argument can misparse.
This module therefore reports a violation exactly when the single argument is
provably string-typed by structure. That is decidable from the AST alone for a
*name*, through the rules below. It is NOT decidable for an attribute, and the
tree is not annotated densely enough at those sites for it to become so — see
"What this detector does NOT see" for the measurement:

* a ``str(...)`` call, an f-string, or a string literal concatenation;
* a call to a string-only method (``.strip()``, ``.replace()``, …) — the receiver
  need not be resolvable, because no non-string type in this tree exposes them;
* a name bound to a ``str`` / ``str | None`` / ``Annotated[str, ...]`` parameter
  or annotated assignment of an enclosing scope;
* a name assigned from any of the above (folded to a fixed point, so
  ``text = raw.strip()`` then ``Decimal(text)`` is still seen);
* a loop target over a ``Mapping[..., str]`` / ``Sequence[str]`` iterable.

Integer widening is consequently never reported, so the gate needs no allowlist
entry for the many legitimate ``Decimal(<int>)`` sites.

What this detector does NOT see: attribute access
-------------------------------------------------

Every rule above resolves a *name*. ``Decimal(casilla.value)`` resolves nothing:
:func:`_expression_is_str` has no ``ast.Attribute`` branch, so an attribute falls
through to ``False`` however the field is declared. That is a real limitation, not
an oversight, and the reason is measurable rather than rhetorical.

Bucketing every ``Decimal(<Attribute>)`` site in the tree by whether the
receiver's type is knowable from the scanned file alone gives **8 of 20**:
five ``self.X`` where the class is in-file, three annotated locals whose type is
also in-file — and twelve that are not, being eight unannotated locals (loop
targets and plain bindings, which no in-file analysis reaches) and four annotated
with an imported type. So an honest attribute branch could cover at most 40%,
and the remaining 60% needs cross-file resolution, which is a type checker.

The obvious alternative was measured and refused. Keying an ``ast.Attribute``
branch on the attribute NAME fires on all twenty at an **~86% false-positive
rate**: ``selected_amount`` is ``Decimal | None`` on one class and ``str | None``
on an unrelated one, ``entry.value`` is a ``Decimal`` alias, and two more sites
are already guarded by ``isinstance``. A gate that cries wolf at that rate
accumulates exemptions until it means nothing, so **loud and wrong is worse than
blind** — this detector stays narrow deliberately.

The escape hatch, if a live instance ever recurs
------------------------------------------------

A type checker resolves what the AST cannot. Measured, not assumed:
``reveal_type(casilla.value)`` reports ``str`` under ``ty``, on the exact site
this module cannot see. The mechanism is to copy the tree outside the repo,
insert ``reveal_type()`` at each ``Decimal(...)`` argument, run ``ty``, and read
the revealed types — no mutation of the real tree, no name matching, and no false
positives by construction.

It is recorded rather than built because at the time of writing the blind spot has
**zero live instances**: the three that existed were each closed at the call site.
The true price is higher than the mechanism suggests, and is recorded here so
whoever revives it inherits the estimate rather than repeating it. Nothing in the
tree invokes ``ty`` or uses ``reveal_type``, so such a gate would be the first of
its kind: no pattern to copy, no established way to pin checker-version drift (the
revealed-type text is the checker's output format, not a contract), a checker run
added to every invocation, and its own anti-tautology proof and exemption
discipline to build from scratch. The nearest analogue,
``dev/docs/sequence_build_gate.py``, invokes an external engine from a gate — but
its own engine, not a checker's output, so it is precedent for the *shape* and not
for the *dependency*. Permanent cost against a contingent benefit; build it when
there is something to catch.

Why ``adapters/`` is out of scope
---------------------------------

:data:`_STRING_PARSE_LAYERS` covers ``entrypoints`` and ``application`` only, and
that follows from the rule rather than from inertia: operator-typed text belongs
to :func:`~core.decimal.try_parse_canonical_decimal` and machine-produced text to
:func:`~core.decimal.coerce_decimal`, and ``adapters/`` carries machine-produced
AEAT artefact text. Widening the scope is therefore a change of intent needing its
own justification, not a bug fix.

None of this means the detector is weak where it does reach. It correctly reports
a resolvable ``Decimal(str(...))`` — it has been red on exactly such a site while
blind to an attribute one file away. The edge is precise: it resolves names, not
attribute types.

Stating a detector's blind spot in its own docstring is the house pattern, not an
apology for this one: :mod:`~tests.test_storage_provenance_gate` opens by naming
what its predecessor structurally could not reach (a literal census cannot see a
path built by joining onto the storage root) and gives the structural reason. A
reader who finds a limitation recorded here should expect to find the same
discipline there.

See Also:
    :func:`~core.decimal.try_parse_canonical_decimal`
        Strict grammar for operator-typed text.
    :func:`~core.decimal.coerce_decimal`
        Tolerant coercion for machine-produced text.
    :mod:`~tests._inventory`
        Shared production AST inventory surface.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from ._inventory import leaf_name

STRING_ONLY_METHODS: frozenset[str] = frozenset(
    {
        "strip",
        "lstrip",
        "rstrip",
        "replace",
        "lower",
        "upper",
        "casefold",
        "removeprefix",
        "removesuffix",
        "zfill",
        "title",
        "swapcase",
        "expandtabs",
    },
)
"""Methods no non-string type in this tree exposes, so their result is a ``str``."""

_ALIAS_FOLD_PASSES = 4
"""Fixed-point bound for ``a = raw.strip(); b = a`` rebinding chains."""

_FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda
"""Scopes that bind parameter names. A lambda cannot annotate its parameters, so
it contributes nothing to the ``str``-name set, but including it keeps the
parameter walk total over every callable form."""


def annotation_is_str(node: ast.expr | None) -> bool:
    """Return True when *node* annotates a plain ``str`` (optionally wrapped)."""
    if node is None:
        return False
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        # A stringised annotation (``"str | None"``) under future annotations.
        return node.value.strip().split("|")[0].strip() == "str"
    if isinstance(node, ast.Name):
        return node.id == "str"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return annotation_is_str(node.left) or annotation_is_str(node.right)
    if isinstance(node, ast.Subscript):
        base = leaf_name(node.value)
        if base == "Annotated":
            target = node.slice
            if isinstance(target, ast.Tuple) and target.elts:
                return annotation_is_str(target.elts[0])
            return annotation_is_str(target)
        if base == "Optional":
            return annotation_is_str(node.slice)
    return False


def annotation_element_is_str(node: ast.expr | None) -> bool:
    """Return True when *node* annotates a container whose element type is ``str``.

    ``Mapping[CasillaId, str]`` and ``Sequence[str]`` both qualify: iterating the
    former's ``.items()`` or the latter directly binds a ``str``.
    """
    if node is None:
        return False
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return annotation_element_is_str(node.left) or annotation_element_is_str(node.right)
    if not isinstance(node, ast.Subscript):
        return False
    target = node.slice
    elements = target.elts if isinstance(target, ast.Tuple) else [target]
    return bool(elements) and annotation_is_str(elements[-1])


def _expression_is_str(node: ast.expr, str_names: frozenset[str]) -> bool:
    """Return True when *node* provably evaluates to a ``str``."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.Name):
        return node.id in str_names
    if isinstance(node, ast.Call):
        if leaf_name(node.func) == "str":
            return True
        return isinstance(node.func, ast.Attribute) and node.func.attr in STRING_ONLY_METHODS
    if isinstance(node, ast.Subscript):
        return _expression_is_str(node.value, str_names)
    if isinstance(node, ast.BoolOp):
        return any(_expression_is_str(value, str_names) for value in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _expression_is_str(node.left, str_names) or _expression_is_str(node.right, str_names)
    if isinstance(node, ast.IfExp):
        return _expression_is_str(node.body, str_names) or _expression_is_str(node.orelse, str_names)
    return False


def _annotated_str_parameters(node: _FunctionNode) -> set[str]:
    args = node.args
    parameters = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    if args.vararg is not None:
        parameters.append(args.vararg)
    if args.kwarg is not None:
        parameters.append(args.kwarg)
    return {parameter.arg for parameter in parameters if annotation_is_str(parameter.annotation)}


def _loop_target_str_names(node: ast.For | ast.AsyncFor, str_containers: Mapping[str, bool]) -> set[str]:
    iterated = node.iter
    if isinstance(iterated, ast.Call) and isinstance(iterated.func, ast.Attribute):
        if iterated.func.attr not in {"items", "values"}:
            return set()
        iterated = iterated.func.value
    while isinstance(iterated, ast.BoolOp) and iterated.values:
        iterated = iterated.values[0]
    if not isinstance(iterated, ast.Name) or not str_containers.get(iterated.id, False):
        return set()
    target = node.target
    bound = target.elts if isinstance(target, ast.Tuple) else [target]
    return {bound[-1].id} if bound and isinstance(bound[-1], ast.Name) else set()


def _str_container_names(node: ast.AST | None) -> dict[str, bool]:
    """Return parameter names annotated as a container of ``str``.

    Annotated *assignments* of the same shape are folded in by
    :func:`_scope_str_names`, which walks the whole scope body rather than only
    its top-level statements.
    """
    containers: dict[str, bool] = {}
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        args = node.args
        for parameter in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
            if annotation_element_is_str(parameter.annotation):
                containers[parameter.arg] = True
    return containers


def _scope_str_names(
    body: Sequence[ast.stmt],
    inherited: frozenset[str],
    node: ast.AST | None,
) -> frozenset[str]:
    """Return every provably-``str`` name visible in one scope."""
    names = set(inherited)
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
        names |= _annotated_str_parameters(node)
    containers = _str_container_names(node)

    statements = [child for statement in body for child in ast.walk(statement)]
    for statement in statements:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            if annotation_is_str(statement.annotation):
                names.add(statement.target.id)
            if annotation_element_is_str(statement.annotation):
                containers[statement.target.id] = True
        elif isinstance(statement, ast.For | ast.AsyncFor):
            names |= _loop_target_str_names(statement, containers)

    for _ in range(_ALIAS_FOLD_PASSES):
        grew = False
        for statement in statements:
            if isinstance(statement, ast.Assign):
                targets: list[ast.expr] = list(statement.targets)
                value: ast.expr = statement.value
            elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
                targets = [statement.target]
                value = statement.value
            else:
                continue
            if not _expression_is_str(value, frozenset(names)):
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in names:
                    names.add(target.id)
                    grew = True
        if not grew:
            break
    return frozenset(names)


def _is_single_argument_decimal_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call) and leaf_name(node.func) == "Decimal" and len(node.args) == 1 and not node.keywords
    )


def _visit_scope(
    body: Sequence[ast.stmt],
    inherited: frozenset[str],
    node: ast.AST | None,
    found: list[tuple[int, str]],
) -> None:
    """Record string-parsing ``Decimal`` calls in one scope, then recurse into nested ones."""
    str_names = _scope_str_names(body, inherited, node)
    nested: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    def walk(current: ast.AST) -> None:
        if isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef):
            nested.append(current)
            return
        if _is_single_argument_decimal_call(current):
            assert isinstance(current, ast.Call)
            argument = current.args[0]
            if not isinstance(argument, ast.Constant) and _expression_is_str(argument, str_names):
                found.append((current.lineno, _enclosing_name(node)))
        for child in ast.iter_child_nodes(current):
            walk(child)

    for statement in body:
        walk(statement)
    for function in nested:
        _visit_scope(function.body, str_names, function, found)


def _enclosing_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return node.name
    return "<module>"


def string_parse_decimal_sites(tree: ast.AST) -> tuple[tuple[int, str], ...]:
    """Return ``(lineno, enclosing function name)`` for each string-parsing ``Decimal`` call."""
    if not isinstance(tree, ast.Module):
        return ()
    found: list[tuple[int, str]] = []
    _visit_scope(tree.body, frozenset(), None, found)
    return tuple(sorted(set(found)))


def string_parse_decimal_violations(
    items: Iterable[tuple[Path, ast.AST]],
    *,
    display_root: Path,
    exempt: Mapping[tuple[str, str], str] = {},
) -> list[str]:
    """Return ``path:lineno (function)`` strings for non-exempt string-parsing sites.

    Args:
        items: ``(path, AST)`` pairs to scan.
        display_root: Root the reported paths are made relative to. Injecting a
            temporary root is how the gate's own anti-tautology proof scans a
            synthetic module without monkeypatching the production surface.
        exempt: ``(relative path, enclosing function name) -> reason`` entries.
            Keyed by function rather than line number so an unrelated edit in the
            same file does not silently move a site out of its exemption.
    """
    violations: list[str] = []
    for path, tree in items:
        relative = path.relative_to(display_root).as_posix()
        for lineno, function in string_parse_decimal_sites(tree):
            if (relative, function) in exempt:
                continue
            violations.append(f"{relative}:{lineno} (in {function})")
    return violations


__all__ = [
    "STRING_ONLY_METHODS",
    "annotation_element_is_str",
    "annotation_is_str",
    "string_parse_decimal_sites",
    "string_parse_decimal_violations",
]
