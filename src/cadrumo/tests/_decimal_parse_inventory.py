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

Why a second rule keyed on the DESTINATION, not the helper
----------------------------------------------------------

The paragraph above names two acceptable destinations, and one of them is
acceptable only for one kind of input. :func:`~core.decimal.coerce_decimal`
does not consult :func:`~core.decimal.european_thousands_reading_is_ambiguous`;
it reaches ``Decimal(str(value))`` directly, so ``coerce_decimal("1.000")``
returns ``Decimal('1.000')`` — one euro, from an operator who meant a thousand.
The ratchet built to stop unvalidated text parses therefore *blesses by name* a
destination that silently resolves the one shape that carries the defect. A new
text boundary could satisfy the rule above and ship exactly what it exists to
catch, and this repo has paid for that twice: the module docstring of
:mod:`~application.invoices._bulk_import` records an operator's ``12.500`` euros
read as twelve fifty on a threshold field, and a live ``--set iva_amount=1.000``
becoming one euro was fixed at the ``--set`` money boundary.

:func:`tolerant_coercion_text_sites` closes it by asking a different question:
not *which helper is called*, but *can the argument be operator text*. The three
separator-safe destinations are named in :data:`SEPARATOR_SAFE_DESTINATIONS`;
:data:`TOLERANT_DECIMAL_COERCERS` names the two that are not. A provably-``str``
argument reaching a tolerant coercer must either be rewritten onto a safe
destination or carry a :data:`DECIMAL_TEXT_RATIONALE_MARKER` declaration AT the
site saying why the separator convention is externally fixed.

The declaration lives at the call site rather than in a path-keyed mapping, and
that is a deliberate divergence from rule 3's ``_STRING_PARSE_EXEMPTIONS``. The
shape is the fixture-provenance one: the artefact declares its own provenance
and the gate cross-checks the declaration against physical evidence — here, the
AST site the marker sits beside. A declaration with no site beneath it fails
:func:`stale_decimal_text_rationale_markers`, so a fixed site cannot leave a
rubber stamp behind, and a path-or-line key cannot rot into one because there is
no key. The operative reason is that reasoning kept away from the code decays:
this campaign hit five separate instances of prose asserting a state the tree no
longer carried, and the arguments that survived did so because their author put
them in a docstring beside the code rather than in a record elsewhere.

A per-symbol grep for ``coerce_decimal`` cannot do this job. Of seven sites
classified by hand, three are correct uses that a symbol sweep reports as
violations — a 43% false-positive rate, which is the rate at which a detector
stops being read. Keying on the argument's provable type instead drops those
three out of the reported set by construction rather than by exemption: the
bank-statement importer's float branch, the bulk-import float branch, and the
integer/float arm of the worksheet coercer are all non-``str`` and never appear.

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
* a loop target over a ``Mapping[..., str]`` / ``Sequence[str]`` iterable;
* a name narrowed by an enclosing ``if isinstance(name, str):`` test, inside that
  branch only. This is a real narrowing rather than a guess, and it is what lets
  the destination rule see the worksheet coercer's text arm while leaving its
  ``isinstance(raw, (int, float))`` arm alone. The negative branch is NOT
  narrowed and an early-return guard (``if not isinstance(v, str): return``) is
  not followed, because both need flow-sensitivity this walk does not have; the
  cost is missed sites, never invented ones.

Integer widening is consequently never reported, so the gate needs no allowlist
entry for the many legitimate ``Decimal(<int>)`` sites.

What this detector does NOT see: attribute access
-------------------------------------------------

**The destination rule inherits this blindness in full, and a green from it is
therefore not a coverage claim.** :func:`tolerant_coercion_text_sites` reuses
:func:`_expression_is_str` unchanged, so it catches a ``str``-annotated parameter
— the shape of the ``--set`` money defect — and is structurally unable to see
``coerce_decimal(record.amount)`` however ``amount`` is declared. Read a passing
run as "no *resolvable* text reaches a tolerant coercer undeclared", never as
"no text does". The measurement below is why the missing branch was not
attempted, and it applies verbatim to the new rule: nothing about asking a
different question makes an attribute's type any more decidable.

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
the docs sequence-build gate, invokes an external engine from a gate — but
its own engine, not a checker's output, so it is precedent for the *shape* and not
for the *dependency*. Permanent cost against a contingent benefit; build it when
there is something to catch.

Why the scope is the call site and not a list of layers
-------------------------------------------------------

This section used to argue the opposite, and the argument was wrong in a way
worth recording rather than deleting. It said the governed set covered
``entrypoints`` and ``application`` only, that this followed from the rule
rather than from inertia because ``adapters/`` carries machine-produced text,
and that widening it would be a change of intent needing its own justification.

A live defect refuted it. ``--descendiente RENTAS=12.500`` was read as twelve
euros fifty by a bare ``Decimal()`` sitting in ``domain`` — an operator-input
parser in a layer the list did not name — so the gate that exists to catch
exactly that stayed green while the misread shipped. The premise was not that
adapters carry machine text, which is true; it was that layer membership tells
you whether operator text arrives, which is false, and this codebase already
contained the counter-example.

So the gate module's ``_CANONICAL_DECIMAL_HOME`` now scopes by CALL SITE
(the constant lives in ``test_decimal_enrollment_inventory``, not here, so it
is named rather than cross-referenced -- an unqualified role pointing at
another module is how the reference this paragraph replaces came to dangle). Constructing a
Decimal from text belongs to ``core.decimal`` wherever the caller lives, and
everything outside that package is in scope by default rather than by
enumeration. The adapters that read machine-produced AEAT artefact text are
still exempt — but by a stated per-site reason rather than by never having been
looked at, which is the difference between a decision and a gap.

The three contracts the canonical home now names are strict operator input
(ambiguity refuses), extraction (ambiguity yields no value), and bounded-range
extraction (ambiguity resolves only where the declared range makes the other
reading impossible, not merely unlikely).

When a local guard is NOT redundant
------------------------------------

Routing a site into the canonical home is right most of the time and wrong when
the local guard carries meaning the general grammar discards. The worked example
is in :mod:`~domain.user_profile._values`: its leading-zero check was retired as
"subsumed by the grammar", and ``08001`` — a Spanish postcode — promptly became
``Decimal("8001")``, losing the zero that carries its meaning. The canonical
grammar accepts that string; it simply answers a different question.

Grant such a site an exemption with the reason stated AT the site, so the next
canonicaliser meets the argument rather than the temptation. The discriminator
is whether the specific case carries information the general authority throws
away — not whether routing it would compile.

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

TOLERANT_DECIMAL_COERCERS: frozenset[str] = frozenset({"coerce_decimal", "coerce_decimal_strict"})
"""Coercers that reach ``Decimal(str(value))`` without a separator judgement.

Both resolve ``"1.000"`` to ``Decimal('1.000')``. They are correct for
machine-produced text, whose separator convention is fixed by the format that
produced it, and wrong for operator text, whose convention is the operator's.
``coerce_decimal_strict`` is here for the same reason as its sibling: it differs
only in raising rather than returning a default, so excluding it would leave the
identical misread reachable under a second name — which is the by-name blessing
this rule exists to remove.
"""

SEPARATOR_SAFE_DESTINATIONS: tuple[str, ...] = (
    "try_parse_canonical_decimal",
    "coerce_finite_european_decimal",
    "_normalise_amount_digits",
)
"""The destinations a provably-``str`` value may reach, and why each is safe.

``try_parse_canonical_decimal`` and ``coerce_finite_european_decimal`` both
consult :func:`~core.decimal.european_thousands_reading_is_ambiguous`, and differ
only in what they do with an ambiguous token: the first refuses so the operator
retypes, the second yields no value so the confirm path asks.
``_normalise_amount_digits`` in the bank-statement importer is the third, and it
is safe for a different reason — it takes ``decimal_sep`` as a parameter rather
than inferring one, so the caller's resolved-or-declared separator governs and
nothing is guessed. It is named here rather than left unlisted because a
destination this rule does not name reads as unsanctioned, and the statement
import path would then be reported on the rule's first run for doing the right
thing.
"""

DECIMAL_TEXT_RATIONALE_MARKER = "DECIMAL-TEXT-RATIONALE-"
"""Marker declaring why a tolerant coercer may receive text at one call site.

Placed on the call line or in the comment block immediately above it, following
the tree's existing ``CAST-RATIONALE-`` convention. Every occurrence must sit
beside a site the detector really reports, or
:func:`stale_decimal_text_rationale_markers` fails.
"""

_CORE_DECIMAL_MODULE_SUFFIX = "core.decimal"
"""Import module suffix identifying the canonical decimal package.

Matched as a suffix because every consumer imports it relatively
(``from ...core.decimal import coerce_decimal``), which
:func:`~tests._inventory.import_binding_map` deliberately does not resolve — a
relative origin depends on the importing module's package position. Matching the
module tail resolves the alias spelling (``coerce_decimal_strict as
_coerce_decimal_strict`` is live in the tree) without inventing an origin.
"""

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


def _isinstance_str_narrowed_names(test: ast.expr) -> set[str]:
    """Return names an ``if`` test proves to be ``str`` throughout its positive branch.

    Only a whole-test conjunction narrows: ``isinstance(v, str) and ...`` does,
    ``isinstance(v, str) or ...`` does not, and ``isinstance(v, (int, float))``
    does not. A tuple of alternatives narrows only when every alternative is
    ``str``.
    """
    narrowed: set[str] = set()
    pending: list[ast.expr] = [test]
    while pending:
        node = pending.pop()
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
            pending.extend(node.values)
            continue
        if not (
            isinstance(node, ast.Call)
            and leaf_name(node.func) == "isinstance"
            and len(node.args) == 2
            and isinstance(node.args[0], ast.Name)
        ):
            continue
        classes = node.args[1]
        options = classes.elts if isinstance(classes, ast.Tuple) else [classes]
        if options and all(isinstance(option, ast.Name) and option.id == "str" for option in options):
            narrowed.add(node.args[0].id)
    return narrowed


def _coercer_bindings(tree: ast.Module) -> dict[str, str]:
    """Return local name -> canonical coercer name for every tolerant-coercer import.

    Resolves the alias spelling, so ``coerce_decimal_strict as
    _coerce_decimal_strict`` is matched by what it *is* rather than by how it is
    spelled — the failure mode the sibling cast ratchet records as its own open
    blind spot.
    """
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if not node.module.endswith(_CORE_DECIMAL_MODULE_SUFFIX):
            continue
        for alias in node.names:
            if alias.name in TOLERANT_DECIMAL_COERCERS:
                bindings[alias.asname or alias.name] = alias.name
    return bindings


def _visit_scope(
    body: Sequence[ast.stmt],
    inherited: frozenset[str],
    node: ast.AST | None,
    found: list[tuple[int, str]],
    coercions: list[tuple[int, str, str]],
    coercer_bindings: Mapping[str, str],
) -> None:
    """Record text-parsing ``Decimal`` and tolerant-coercer calls in one scope.

    Both rules share one walk, one :func:`_expression_is_str` and one narrowing
    set, because they share one type judgement; splitting them would let the two
    drift on what counts as text. The ``isinstance`` narrowing reached the
    coercer rule one change before it reached the ``Decimal`` rule, purely so
    that the six sites it surfaces did not land in a gate that was red for two
    unrelated reasons at the time. Both now consume it.
    """
    str_names = _scope_str_names(body, inherited, node)
    nested: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    def walk(current: ast.AST, narrowed: frozenset[str]) -> None:
        if isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef):
            nested.append(current)
            return
        if isinstance(current, ast.If):
            walk(current.test, narrowed)
            positive = narrowed | _isinstance_str_narrowed_names(current.test)
            for statement in current.body:
                walk(statement, frozenset(positive))
            for statement in current.orelse:
                walk(statement, narrowed)
            return
        if _is_single_argument_decimal_call(current):
            assert isinstance(current, ast.Call)
            argument = current.args[0]
            if not isinstance(argument, ast.Constant) and _expression_is_str(argument, str_names | narrowed):
                found.append((current.lineno, _enclosing_name(node)))
        elif isinstance(current, ast.Call) and current.args:
            coercer = coercer_bindings.get(leaf_name(current.func))
            argument = current.args[0]
            if (
                coercer is not None
                and not isinstance(argument, ast.Constant)
                and _expression_is_str(argument, str_names | narrowed)
            ):
                coercions.append((current.lineno, _enclosing_name(node), coercer))
        for child in ast.iter_child_nodes(current):
            walk(child, narrowed)

    for statement in body:
        walk(statement, frozenset())
    for function in nested:
        _visit_scope(function.body, str_names, function, found, coercions, coercer_bindings)


def _enclosing_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return node.name
    return "<module>"


def _scan_module(tree: ast.AST) -> tuple[list[tuple[int, str]], list[tuple[int, str, str]]]:
    if not isinstance(tree, ast.Module):
        return [], []
    found: list[tuple[int, str]] = []
    coercions: list[tuple[int, str, str]] = []
    _visit_scope(tree.body, frozenset(), None, found, coercions, _coercer_bindings(tree))
    return found, coercions


def string_parse_decimal_sites(tree: ast.AST) -> tuple[tuple[int, str], ...]:
    """Return ``(lineno, enclosing function name)`` for each string-parsing ``Decimal`` call."""
    found, _ = _scan_module(tree)
    return tuple(sorted(set(found)))


def tolerant_coercion_text_sites(tree: ast.AST) -> tuple[tuple[int, str, str], ...]:
    """Return ``(lineno, enclosing function, coercer)`` where text reaches a tolerant coercer.

    The reported set is exactly the provably-``str`` arguments: a float, int or
    already-``Decimal`` argument never appears, which is what keeps the three
    correct machine-numeric call sites out of the report without an exemption.
    """
    _, coercions = _scan_module(tree)
    return tuple(sorted(set(coercions)))


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


def declaration_line_indices(lines: Sequence[str], lineno: int) -> frozenset[int]:
    """Return the zero-based line indices a site's declaration may occupy.

    The site's own line, plus the unbroken run of comment and blank lines
    immediately above it — the same adjacency the tree's ``CAST-RATIONALE-``
    ratchet uses. Returning the index *set* rather than a boolean is what lets
    the staleness check run in the opposite direction: a marker is live exactly
    when some site's set contains it.
    """
    index = lineno - 1
    if index < 0 or index >= len(lines):
        return frozenset[int]()
    covered = {index}
    scan = index - 1
    while scan >= 0:
        stripped = lines[scan].strip()
        if stripped == "" or stripped.startswith("#"):
            covered.add(scan)
            scan -= 1
            continue
        break
    return frozenset(covered)


def _marker_line_indices(lines: Sequence[str]) -> frozenset[int]:
    return frozenset(index for index, line in enumerate(lines) if DECIMAL_TEXT_RATIONALE_MARKER in line)


def tolerant_coercion_text_violations(
    items: Iterable[tuple[Path, ast.AST, Sequence[str]]],
    *,
    display_root: Path,
) -> list[str]:
    """Return ``path:lineno (function, coercer)`` for undeclared text coercions.

    Args:
        items: ``(path, AST, source lines)`` triples to scan.
        display_root: Root the reported paths are made relative to, so the gate's
            own proofs can scan a synthetic module without monkeypatching the
            production scan surface.
    """
    violations: list[str] = []
    for path, tree, lines in items:
        relative = path.relative_to(display_root).as_posix()
        markers = _marker_line_indices(lines)
        for lineno, function, coercer in tolerant_coercion_text_sites(tree):
            if declaration_line_indices(lines, lineno) & markers:
                continue
            violations.append(f"{relative}:{lineno} (in {function}, {coercer})")
    return violations


def stale_decimal_text_rationale_markers(
    items: Iterable[tuple[Path, ast.AST, Sequence[str]]],
    *,
    display_root: Path,
) -> list[str]:
    """Return ``path:lineno`` for every declaration that governs no reported site.

    The cross-check that keeps the at-the-site declaration from becoming the
    path-keyed allowlist it replaces: a marker left behind by a fixed or deleted
    call is a rubber stamp waiting to launder the next one added beside it.
    """
    stale: list[str] = []
    for path, tree, lines in items:
        relative = path.relative_to(display_root).as_posix()
        governed: set[int] = set()
        for lineno, _, _ in tolerant_coercion_text_sites(tree):
            governed |= declaration_line_indices(lines, lineno)
        for index in sorted(_marker_line_indices(lines) - governed):
            stale.append(f"{relative}:{index + 1}")
    return stale


__all__ = [
    "DECIMAL_TEXT_RATIONALE_MARKER",
    "SEPARATOR_SAFE_DESTINATIONS",
    "STRING_ONLY_METHODS",
    "TOLERANT_DECIMAL_COERCERS",
    "annotation_element_is_str",
    "annotation_is_str",
    "declaration_line_indices",
    "stale_decimal_text_rationale_markers",
    "string_parse_decimal_sites",
    "string_parse_decimal_violations",
    "tolerant_coercion_text_sites",
    "tolerant_coercion_text_violations",
]
