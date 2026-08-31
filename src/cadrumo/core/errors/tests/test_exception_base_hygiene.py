"""Static guard for production exception base classes.

User/application-facing Cadrumo exceptions must derive from
:class:`cadrumo.core.errors.CadrumoError` so they bind to the central error
registry. A class that deliberately roots at a bare builtin instead declares
why **on itself**, through a ``__bare_base_rationale__`` ClassVar.

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

The gate below walks IMPORTED modules, so its subject set is whatever the
installed environment actually executed. That is deliberate -- resolving a base
through aliases and multiple inheritance needs the live MRO, which source alone
cannot give -- but it means a class defined only inside an optional-import
fallback branch is invisible whenever the extra IS installed. The AST companion
at the end of this module covers exactly that blind spot; see its docstring for
why two gates deliberately overlap here.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
from types import ModuleType

import pytest

from .... import __path__ as _cadrumo_package_path
from ....tests import production_python_files, repo_relative
from .optional_extras import describe_optional_extras

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BARE_EXCEPTION_BASES = (Exception, ValueError, RuntimeError, KeyError, TypeError)

# Anti-vacuity floor. Set far below the measured population (near 630 production
# exception classes) so ordinary churn never trips it, and far enough above zero
# that an import-walk or packaging regression reds the gate instead of greening
# every "no violations found" assertion below by examining nothing.
_MIN_EXCEPTION_CLASSES_SCANNED = 400
_BARE_BASE_RATIONALE_ATTR = "__bare_base_rationale__"


def _declared_bare_base_rationale(error_type: type[BaseException]) -> str | None:
    """Return the class's OWN bare-base rationale, or ``None`` when it declares none.

    Read from ``__dict__`` rather than by attribute access, deliberately: an
    inherited rationale would silently exempt every subclass of a declaring
    class, which is the hole a curated allowlist did not have. The exemption is
    per-class because the fact it records — "this class deliberately roots at a
    bare builtin" — is per-class.
    """
    declared = error_type.__dict__.get(_BARE_BASE_RATIONALE_ATTR)
    return declared if isinstance(declared, str) and declared.strip() else None


def _has_only_bare_bases(error_type: type[BaseException]) -> bool:
    """Whether every base of ``error_type`` is an unregistered builtin root."""
    bare = tuple(base for base in error_type.__bases__ if base in _BARE_EXCEPTION_BASES)
    return bool(bare) and len(bare) == len(error_type.__bases__)


def _iter_imported_cadrumo_modules() -> list[ModuleType]:
    modules: list[ModuleType] = []
    for info in pkgutil.walk_packages(_cadrumo_package_path, prefix="cadrumo."):
        name = info.name
        if ".tests." in name or ".test_" in name or "._test_" in name:
            continue
        modules.append(importlib.import_module(name))
    return modules


def _module_exception_classes(module: ModuleType) -> list[type[BaseException]]:
    module_name = module.__name__
    return [
        error_type
        for _, error_type in inspect.getmembers(module, inspect.isclass)
        if error_type.__module__ == module_name and issubclass(error_type, BaseException)
    ]


def _production_exception_classes() -> list[type[BaseException]]:
    """Every exception class defined by an importable production module."""
    return [
        error_type for module in _iter_imported_cadrumo_modules() for error_type in _module_exception_classes(module)
    ]


def test_scan_reaches_a_plausible_exception_population() -> None:
    """A collapsed scan must red the gate, not green it by examining nothing.

    Both assertions below are "no violations found" shapes, which pass
    vacuously if the walk returns an empty or tiny population. The floor is set
    far below the measured figure (near 630 classes) so ordinary churn never
    trips it, and far enough above zero that a packaging or import-walk
    regression fails loudly instead of silently.

    The scope line is reported rather than only asserted. Because this walk
    imports, its subject set is a property of the installed environment, and a
    green that does not say what it covered invites the reader to assume it
    covered everything. Stating the population and the extras that shaped it
    makes the difference between two machines visible in the log instead of
    discoverable only by a dedicated investigation.
    """
    population = _production_exception_classes()
    print(f"exception-base scope: {len(population)} classes scanned; {describe_optional_extras()}")
    assert len(population) >= _MIN_EXCEPTION_CLASSES_SCANNED, (
        f"only {len(population)} production exception classes discovered (floor "
        f"{_MIN_EXCEPTION_CLASSES_SCANNED}); the import walk collapsed, so a green result below "
        f"would mean 'nothing was examined' rather than 'nothing is wrong'. Scope: "
        f"{describe_optional_extras()}"
    )


def test_production_exception_classes_do_not_introduce_unregistered_builtin_roots() -> None:
    """A class rooting only at bare builtins must declare why, on itself."""
    violations = [
        f"{error_type.__module__}.{error_type.__qualname__}("
        + ", ".join(sorted(base.__name__ for base in error_type.__bases__))
        + ")"
        for error_type in _production_exception_classes()
        if _has_only_bare_bases(error_type) and _declared_bare_base_rationale(error_type) is None
    ]
    assert violations == [], (
        "production exception class(es) root only at unregistered builtin bases and declare no "
        f"reason. Derive from CadrumoError so the class binds to the error registry, or — if the "
        f"bare root is deliberate — declare `{_BARE_BASE_RATIONALE_ATTR}: ClassVar[str]` on the "
        "class itself stating why:\n  " + "\n  ".join(violations)
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
        f"{error_type.__module__}.{error_type.__qualname__}("
        + ", ".join(sorted(base.__name__ for base in error_type.__bases__))
        + ")"
        for error_type in _production_exception_classes()
        if _declared_bare_base_rationale(error_type) is not None and not _has_only_bare_bases(error_type)
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
