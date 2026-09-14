"""Static guard for production exception base classes.

Every Cadrumo-owned production exception derives from
:class:`cadrumo.core.errors.CadrumoError` so it binds to the central error
registry. The only direct built-in roots are the canonical root itself and the
source-only Playwright fallback required to mirror a third-party import type.

The declaration replaced a curated allowlist in this module. The allowlist was
a second copy of a fact the class already carried, and it could drift from it:
one entry had been overtaken by its class gaining a registry-bound base, so the
class would have passed without the entry while the entry went on exempting a
name nobody was checking. A declaration cannot drift, because there is nothing
to drift from — and the reciprocal gate below makes the stale state
*unrepresentable* rather than merely detectable: re-basing a class onto
``CadrumoError`` reds the tree until its now-false rationale is deleted in the
same change.

Read per class, never inherited. An inherited rationale would exempt every
subclass of a declaring class, a hole the allowlist did not have.

The gate below reads the production source tree through ASTs, so its subject set
does not depend on which optional modules happen to import successfully. Source
descriptors carry explicit ``module``, ``qualname``, and ``bases`` fields; they
never impersonate Python class metadata. The companion at the end of this module
keeps the optional-import fallback declaration check deliberately source-local,
where a live import walk cannot observe the fallback branch on installations
that provide the optional extra.
"""

from __future__ import annotations

import ast
import builtins
from dataclasses import dataclass
from functools import cache

import pytest

from ....tests.inventory import (
    import_binding_map,
    module_name,
    production_ast_items,
    production_python_files,
    qualified_name,
    repo_relative,
    resolve_dotted_origin,
)
from .optional_extras import describe_optional_extras

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BARE_EXCEPTION_BASES = tuple(
    value for value in vars(builtins).values() if isinstance(value, type) and issubclass(value, BaseException)
)
_PERMITTED_BUILTIN_ROOTS = frozenset(
    {
        "cadrumo.core.errors.hierarchy.CadrumoError",
        "cadrumo.adapters.outbound.aeat._playwright.PlaywrightError",
    }
)

# Anti-vacuity floor. Set far below the measured population (near 630 production
# exception classes) so ordinary churn never trips it, and far enough above zero
# that an import-walk or packaging regression reds the gate instead of greening
# every "no violations found" assertion below by examining nothing.
_MIN_EXCEPTION_CLASSES_SCANNED = 400
_BARE_BASE_RATIONALE_ATTR = "__bare_base_rationale__"


def _declared_bare_base_rationale(error_type: type[BaseException] | _SourceExceptionClass) -> str | None:
    """Return the class's OWN bare-base rationale, or ``None`` when it declares none.

    Read from ``__dict__`` rather than by attribute access, deliberately: an
    inherited rationale would silently exempt every subclass of a declaring
    class, which is the hole a curated allowlist did not have. The exemption is
    per-class because the fact it records — "this class deliberately roots at a
    bare builtin" — is per-class.
    """
    if isinstance(error_type, _SourceExceptionClass):
        return error_type.rationale
    declared = error_type.__dict__.get(_BARE_BASE_RATIONALE_ATTR)
    return declared if isinstance(declared, str) and declared.strip() else None


def _has_only_bare_bases(error_type: type[BaseException] | _SourceExceptionClass) -> bool:
    """Whether every base of ``error_type`` is an unregistered builtin root."""
    if isinstance(error_type, _SourceExceptionClass):
        bases = error_type.bases
        bare = tuple(base for base in bases if base.name.rsplit(".", 1)[-1] in _BARE_BASE_NAMES)
    else:
        bases = error_type.__bases__
        bare = tuple(base for base in bases if base in _BARE_EXCEPTION_BASES)
    return bool(bare) and len(bare) == len(bases)


def _has_mixed_builtin_base(error_type: type[BaseException] | _SourceExceptionClass) -> bool:
    """Whether a registered declaration also names a builtin exception base."""
    if isinstance(error_type, _SourceExceptionClass):
        bases = error_type.bases
        bare_count = sum(base.name.rsplit(".", 1)[-1] in _BARE_BASE_NAMES for base in bases)
    else:
        bases = error_type.__bases__
        bare_count = sum(base in _BARE_EXCEPTION_BASES for base in bases)
    return 0 < bare_count < len(bases)


@dataclass(frozen=True)
class _SourceBase:
    """One class base as written in a production source file."""

    name: str


@dataclass(frozen=True)
class _SourceExceptionClass:
    """Static metadata for an exception class declaration.

    The former implementation imported every discovered module and reflected on
    the resulting class objects.  This descriptor carries exactly the facts the
    gate reads from those objects while keeping the subject set tied to the
    production source tree, including declarations in optional branches.
    """

    module: str
    qualname: str
    bases: tuple[_SourceBase, ...]
    rationale: str | None


def _describe_exception(error_type: type[BaseException] | _SourceExceptionClass) -> str:
    """Return the stable location/base summary used in gate diagnostics."""
    if isinstance(error_type, _SourceExceptionClass):
        location = f"{error_type.module}.{error_type.qualname}"
        base_names = (base.name.rsplit(".", 1)[-1] for base in error_type.bases)
    else:
        location = f"{error_type.__module__}.{error_type.__qualname__}"
        base_names = (base.__name__ for base in error_type.__bases__)
    return f"{location}({', '.join(sorted(base_names))})"


def _exception_identity(error_type: type[BaseException] | _SourceExceptionClass) -> str:
    """Return the exact registry-style identity of one declaration."""
    if isinstance(error_type, _SourceExceptionClass):
        return f"{error_type.module}.{error_type.qualname}"
    return f"{error_type.__module__}.{error_type.__qualname__}"


def _source_class_qualnames(tree: ast.AST) -> dict[int, str]:
    """Return Python-style lexical qualnames for every class declaration.

    ``ast.walk`` discovers classes in control-flow blocks and functions as well
    as classes nested directly in another class body.  Walking only ``body``
    lists of ``ClassDef`` nodes would therefore leave some discovered nodes
    unmapped and make source discovery fail with ``KeyError``.  Control-flow
    containers preserve the surrounding lexical prefix; functions add the
    ``<locals>`` segment used by Python's runtime ``__qualname__``.
    """
    qualnames: dict[int, str] = {}

    def visit(node: ast.AST, prefix: str = "") -> None:
        if isinstance(node, ast.ClassDef):
            qualname = f"{prefix}.{node.name}" if prefix else node.name
            qualnames[id(node)] = qualname
            for statement in node.body:
                visit(statement, qualname)
            return

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_prefix = f"{prefix}.{node.name}" if prefix else node.name
            function_prefix += ".<locals>"
            for statement in node.body:
                visit(statement, function_prefix)
            return

        for child in ast.iter_child_nodes(node):
            visit(child, prefix)

    visit(tree)
    return qualnames


def test_source_class_qualnames_cover_nested_and_control_flow_declarations() -> None:
    """Every ``ClassDef`` reached by the source walk receives a stable name."""
    tree = ast.parse(
        "class Outer:\n"
        "    class Nested(Exception):\n"
        "        pass\n"
        "def factory():\n"
        "    class Local(Exception):\n"
        "        pass\n"
        "if True:\n"
        "    class Conditional(Exception):\n"
        "        pass\n"
        "try:\n"
        "    class Tried(Exception):\n"
        "        pass\n"
        "except Exception:\n"
        "    class Handled(Exception):\n"
        "        pass\n"
    )
    classes = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}

    assert _source_class_qualnames(tree) == {
        id(classes["Outer"]): "Outer",
        id(classes["Nested"]): "Outer.Nested",
        id(classes["Local"]): "factory.<locals>.Local",
        id(classes["Conditional"]): "Conditional",
        id(classes["Tried"]): "Tried",
        id(classes["Handled"]): "Handled",
    }


@cache
def _production_exception_classes() -> tuple[_SourceExceptionClass, ...]:
    """Every exception class declared in the production source tree.

    Class ancestry is resolved conservatively from source names and import
    bindings.  A declaration whose base cannot be resolved is not guessed to be
    an exception; this mirrors the old gate's ``issubclass`` subject boundary
    without executing optional modules merely to discover what they define.
    """
    declarations: list[tuple[str, str, ast.ClassDef, dict[str, str]]] = []
    for path, tree in production_ast_items():
        bindings = import_binding_map(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                declarations.append((module_name(path), _source_class_qualnames(tree)[id(node)], node, bindings))

    by_qualified_name: dict[str, tuple[str, str, ast.ClassDef, dict[str, str]]] = {
        f"{module}.{qualname}": (module, qualname, node, bindings) for module, qualname, node, bindings in declarations
    }
    by_bare_name: dict[str, list[str]] = {}
    for key in by_qualified_name:
        by_bare_name.setdefault(key.rsplit(".", 1)[-1], []).append(key)

    def base_origin(module: str, base: ast.expr, bindings: dict[str, str]) -> str:
        rendered = qualified_name(base) or ast.unparse(base)
        return resolve_dotted_origin(rendered, bindings)

    def resolve_reference(module: str, origin: str) -> str | None:
        if origin in by_qualified_name:
            return origin
        leaf = origin.rsplit(".", 1)[-1]
        local = f"{module}.{leaf}"
        if local in by_qualified_name:
            return local
        candidates = by_bare_name.get(leaf, [])
        return candidates[0] if len(candidates) == 1 else None

    exception_keys = {key for key in by_qualified_name if key.rsplit(".", 1)[-1] in {"BaseException", "Exception"}}
    exception_keys.update(
        key for key in by_qualified_name if key.rsplit(".", 1)[-1] in {base.__name__ for base in _BARE_EXCEPTION_BASES}
    )
    builtin_exception_names = {base.__name__ for base in _BARE_EXCEPTION_BASES} | {"BaseException"}
    changed = True
    while changed:
        changed = False
        for module, qualname, node, bindings in declarations:
            key = f"{module}.{qualname}"
            if key in exception_keys:
                continue
            origins = [base_origin(module, base, bindings) for base in node.bases]
            if any(
                origin.rsplit(".", 1)[-1] in builtin_exception_names
                or resolve_reference(module, origin) in exception_keys
                for origin in origins
            ):
                exception_keys.add(key)
                changed = True

    result: list[_SourceExceptionClass] = []
    for module, qualname, node, bindings in declarations:
        if f"{module}.{qualname}" not in exception_keys:
            continue
        bases = tuple(_SourceBase(base_origin(module, base, bindings)) for base in node.bases)
        rationale: str | None = None
        for statement in node.body:
            targets: list[ast.expr] = []
            if isinstance(statement, ast.Assign):
                targets = list(statement.targets)
            elif isinstance(statement, ast.AnnAssign):
                targets = [statement.target]
            if not any(isinstance(target, ast.Name) and target.id == _BARE_BASE_RATIONALE_ATTR for target in targets):
                continue
            value = statement.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value.strip():
                rationale = value.value
        result.append(_SourceExceptionClass(module, qualname, bases, rationale))
    return tuple(result)


def test_scan_reaches_a_plausible_exception_population() -> None:
    """A collapsed scan must red the gate, not green it by examining nothing.

    Both assertions below are "no violations found" shapes, which pass
    vacuously if the walk returns an empty or tiny population. The floor is set
    far below the measured figure (near 630 classes) so ordinary churn never
    trips it, and far enough above zero that a packaging or import-walk
    regression fails loudly instead of silently.

    The scope line is reported rather than only asserted. Stating the population
    makes source-discovery regressions visible in the log instead of discoverable
    only by a dedicated investigation.
    """
    population = _production_exception_classes()
    print(f"exception-base scope: {len(population)} classes scanned; {describe_optional_extras()}")
    assert len(population) >= _MIN_EXCEPTION_CLASSES_SCANNED, (
        f"only {len(population)} production exception classes discovered (floor "
        f"{_MIN_EXCEPTION_CLASSES_SCANNED}); the source walk collapsed, so a green result below "
        f"would mean 'nothing was examined' rather than 'nothing is wrong'. Scope: "
        f"{describe_optional_extras()}"
    )


def test_production_exception_classes_do_not_introduce_unregistered_builtin_roots() -> None:
    """Only the canonical root and proven external shim may root at builtins."""
    violations = [
        _describe_exception(error_type)
        for error_type in _production_exception_classes()
        if _has_only_bare_bases(error_type) and _exception_identity(error_type) not in _PERMITTED_BUILTIN_ROOTS
    ]
    assert violations == [], (
        "production exception class(es) root only at unregistered builtin bases. Derive from "
        "CadrumoError so each class binds to the error registry; interoperability translations "
        "belong at the narrow external boundary:\n  " + "\n  ".join(violations)
    )


def test_registered_exception_classes_do_not_mix_in_builtin_exception_bases() -> None:
    """Builtin protocol behavior belongs at callbacks, not in registered ancestry."""
    violations = [
        _describe_exception(error_type)
        for error_type in _production_exception_classes()
        if _has_mixed_builtin_base(error_type)
    ]
    assert violations == [], (
        "registered production exception class(es) also inherit builtin exception bases. "
        "Keep the internal failure canonical and translate it only at the narrow external "
        "protocol boundary:\n  " + "\n  ".join(violations)
    )


def test_production_does_not_construct_runtime_error_for_owned_invariants() -> None:
    """Operational invariants use the registered, envelope-safe failure type."""
    violations: list[str] = []
    for path, tree in production_ast_items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "RuntimeError":
                violations.append(f"{repo_relative(path)}:{node.lineno}")
    assert violations == [], (
        "production operational failures raise bare RuntimeError. Use a registered Cadrumo "
        "exception internally; translate only at a proven external protocol boundary:\n  " + "\n  ".join(violations)
    )


def test_no_class_declares_a_rationale_it_does_not_need() -> None:
    """A rationale on a class that no longer roots at a bare builtin must go.

    The reciprocal, and the reason the declaration replaced a curated
    allowlist: a stale entry in a list is invisible, whereas a stale
    declaration sits on the class whose bases contradict it. Re-basing onto
    CadrumoError reds this until the now-false rationale is deleted in the same
    change, so the exemption cannot outlive the condition it describes.
    """
    unnecessary = [
        _describe_exception(error_type)
        for error_type in _production_exception_classes()
        if _declared_bare_base_rationale(error_type) is not None
        and _exception_identity(error_type) not in _PERMITTED_BUILTIN_ROOTS
    ]
    assert unnecessary == [], (
        f"class(es) declaring `{_BARE_BASE_RATIONALE_ATTR}` while NOT rooting only at bare builtin "
        "bases. The declaration records a condition that no longer holds; delete it:\n  " + "\n  ".join(unnecessary)
    )


def test_the_rationale_declaration_is_per_class_and_discriminates() -> None:
    """Drives the real readers over synthetic classes, both ways.

    Pins three properties the assertions above rest on: a declared rationale
    exempts, a blank one does not, and — the property a curated list could not
    have had — an INHERITED rationale never exempts a subclass, because the
    reader consults ``__dict__`` rather than attribute lookup.
    """

    class _DeclaredError(Exception):
        __bare_base_rationale__ = "synthetic: deliberate bare root"

    class _BlankError(Exception):
        __bare_base_rationale__ = "   "

    class _UndeclaredError(Exception):
        pass

    class _InheritsDeclarationError(_DeclaredError):
        pass

    assert _declared_bare_base_rationale(_DeclaredError) == "synthetic: deliberate bare root"
    assert _declared_bare_base_rationale(_BlankError) is None
    assert _declared_bare_base_rationale(_UndeclaredError) is None
    assert _declared_bare_base_rationale(_InheritsDeclarationError) is None, (
        "an inherited rationale must not exempt a subclass; the reader must consult __dict__"
    )

    assert _has_only_bare_bases(_DeclaredError)
    assert not _has_only_bare_bases(_InheritsDeclarationError)

    # Positive control for the reciprocal, shaped exactly like the real stale
    # entry that motivated it: a class that gained a registry-bound base while
    # keeping a builtin one, so its declaration is now false. Both readers must
    # agree it is declared AND no longer needs to be.
    class _RegisteredError(Exception):
        """Stand-in for the registry-bound root, so the mixin is not all-bare."""

    class _DeclaredButNoLongerBareError(_RegisteredError, KeyError):
        __bare_base_rationale__ = "synthetic: declaration overtaken by a registry-bound base"

    assert _declared_bare_base_rationale(_DeclaredButNoLongerBareError) is not None
    assert not _has_only_bare_bases(_DeclaredButNoLongerBareError), (
        "the reciprocal gate must flag a class whose declaration outlived its bare-base condition"
    )
    assert _has_mixed_builtin_base(_DeclaredButNoLongerBareError)
    assert not _has_mixed_builtin_base(_DeclaredError)


# ---------------------------------------------------------------------------
# AST companion: the classes the import walk above structurally cannot see.
# ---------------------------------------------------------------------------

#: Lowest plausible number of production modules the source scan parses. Far
#: below the measured figure so ordinary churn never trips it, far enough above
#: zero that a collapsed scan reds instead of greening vacuously.
_MIN_MODULES_PARSED = 400

_IMPORT_FAILURE_NAMES = frozenset({"ImportError", "ModuleNotFoundError"})
_BARE_BASE_NAMES = frozenset(base.__name__ for base in _BARE_EXCEPTION_BASES)


def _handles_import_failure(handler: ast.ExceptHandler) -> bool:
    """Whether *handler* catches a missing optional dependency."""
    caught = handler.type
    if isinstance(caught, ast.Name):
        return caught.id in _IMPORT_FAILURE_NAMES
    if isinstance(caught, ast.Tuple):
        return any(isinstance(item, ast.Name) and item.id in _IMPORT_FAILURE_NAMES for item in caught.elts)
    return False


def _roots_only_at_bare_builtins_in_source(node: ast.ClassDef) -> bool:
    """Whether every declared base of *node* is a bare builtin, by name.

    Source-level and therefore conservative: a base written as an alias or an
    attribute is not treated as bare, because only the live MRO could say. That
    is the exact limitation which keeps this a companion to the import walk
    rather than a replacement for it.
    """
    bases = node.bases
    return bool(bases) and all(isinstance(base, ast.Name) and base.id in _BARE_BASE_NAMES for base in bases)


def _declares_rationale_in_body(node: ast.ClassDef) -> bool:
    """Whether *node*'s own body assigns a non-blank rationale.

    Body-scoped, mirroring the ``__dict__`` read of the live gate: a rationale
    on a base class must not exempt this one.
    """
    for statement in node.body:
        targets: list[ast.expr] = []
        if isinstance(statement, ast.Assign):
            targets = list(statement.targets)
        elif isinstance(statement, ast.AnnAssign):
            targets = [statement.target]
        else:
            continue
        if not any(isinstance(target, ast.Name) and target.id == _BARE_BASE_RATIONALE_ATTR for target in targets):
            continue
        value = statement.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value.strip():
            return True
    return False


def _classes_defined_in_import_fallbacks() -> tuple[list[tuple[str, ast.ClassDef]], int]:
    """Return ``(fallback-defined classes, modules parsed)`` from source."""
    found: list[tuple[str, ast.ClassDef]] = []
    parsed = 0
    for path in production_python_files():
        try:
            tree = ast.parse(path.read_bytes().decode("utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            # A peer mid-edit in this shared worktree must not red the gate;
            # a mass-skip is caught by the module floor below.
            continue
        parsed += 1
        for handler in (node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)):
            if not _handles_import_failure(handler):
                continue
            found.extend((repo_relative(path), node) for node in ast.walk(handler) if isinstance(node, ast.ClassDef))
    return found, parsed


def test_the_source_scan_finds_optional_import_fallback_classes() -> None:
    """Anti-vacuity for the companion below, on both of its axes.

    The check is a "no violations found" shape over a subject set that is small
    by nature, so it greens identically whether every subject complies or no
    subject was found. Both inputs are therefore pinned: the module corpus must
    not collapse, and at least one fallback-defined class must still exist.

    If a refactor legitimately moves the last such class out of a fallback
    branch, this reds — deliberately. Retiring the companion then becomes a
    decision someone records, rather than a green that quietly means nothing.
    """
    found, parsed = _classes_defined_in_import_fallbacks()
    assert parsed >= _MIN_MODULES_PARSED, (
        f"parsed only {parsed} production modules (floor {_MIN_MODULES_PARSED}); the source scan "
        "collapsed, so the companion below would pass by examining nothing"
    )
    assert found, (
        "no class is defined inside an optional-import fallback branch, so the companion below has "
        "no subjects and passes vacuously. If that is now true by design, retire the companion "
        "explicitly instead of leaving a gate that checks nothing"
    )


def test_optional_import_fallback_classes_declare_their_bare_root_in_source() -> None:
    """A fallback-defined class rooting at a bare builtin declares why, in source.

    This exists because the import walk at the top of this module structurally
    cannot see these classes. A class defined inside ``except ImportError`` is
    only defined when the extra is ABSENT; with the extra installed the name
    binds to the third-party original, so the fallback never executes and the
    live gate examines nothing. ``adapters.outbound.aeat._playwright`` is the
    real instance: with the ``browser`` extra installed, ``PlaywrightError``
    resolves to playwright's own ``Error`` class.

    The declaration on that class is correct today. The hazard the two gates
    together close is not a hidden violation but an unexecuted check: a typo in
    the attribute name would be green on every machine carrying the extra and
    red only on the thinnest install, surfacing at the worst possible moment.
    Reading the declaration from source removes the environment from the
    question entirely.

    Deliberately additive. Source cannot resolve aliased or multi-level bases,
    so this narrower deterministic check supplements the broader live walk
    rather than replacing it.
    """
    found, _ = _classes_defined_in_import_fallbacks()
    violations = [
        f"{relative}:{node.lineno}: {node.name}("
        + ", ".join(base.id for base in node.bases if isinstance(base, ast.Name))
        + ")"
        for relative, node in found
        if _roots_only_at_bare_builtins_in_source(node) and not _declares_rationale_in_body(node)
    ]
    assert violations == [], (
        "class(es) defined inside an optional-import fallback root only at bare builtin bases and "
        f"declare no reason in their own body. The live import walk cannot see these when the extra "
        f"is installed, so declare `{_BARE_BASE_RATIONALE_ATTR}: ClassVar[str]` on the class "
        "itself:\n  " + "\n  ".join(violations)
    )


def test_the_source_readers_discriminate() -> None:
    """Drives both source readers over synthetic classes, both ways.

    Without this, readers that never matched anything would produce an empty
    violation list indistinguishable from readers that work.
    """
    module = ast.parse(
        "try:\n"
        "    from third_party import Boom\n"
        "except ImportError:\n"
        "    class Declared(Exception):\n"
        "        __bare_base_rationale__ = 'deliberate'\n"
        "    class Undeclared(Exception):\n"
        "        pass\n"
        "    class Blank(Exception):\n"
        "        __bare_base_rationale__ = '   '\n"
        "    class Registered(CadrumoError):\n"
        "        pass\n"
        "    class Subclass(Declared):\n"
        "        pass\n"
    )
    handler = next(node for node in ast.walk(module) if isinstance(node, ast.ExceptHandler))
    assert _handles_import_failure(handler)
    classes = {node.name: node for node in ast.walk(handler) if isinstance(node, ast.ClassDef)}

    assert _roots_only_at_bare_builtins_in_source(classes["Undeclared"])
    assert not _roots_only_at_bare_builtins_in_source(classes["Registered"]), (
        "a registry-bound root must not be treated as a bare builtin"
    )
    assert not _roots_only_at_bare_builtins_in_source(classes["Subclass"]), (
        "a non-builtin base must not be treated as bare; only the live MRO could resolve it"
    )
    assert _declares_rationale_in_body(classes["Declared"])
    assert not _declares_rationale_in_body(classes["Undeclared"])
    assert not _declares_rationale_in_body(classes["Blank"]), "a blank rationale must not exempt"
    assert not _declares_rationale_in_body(classes["Subclass"]), (
        "an inherited rationale must not exempt a subclass; the reader is body-scoped"
    )

    non_import = ast.parse("try:\n    pass\nexcept ValueError:\n    class Boom(Exception):\n        pass\n")
    other_handler = next(node for node in ast.walk(non_import) if isinstance(node, ast.ExceptHandler))
    assert not _handles_import_failure(other_handler), "only optional-import fallbacks are in scope"
