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
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from types import ModuleType

import pytest

from .... import __path__ as _cadrumo_package_path

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
    """
    population = _production_exception_classes()
    assert len(population) >= _MIN_EXCEPTION_CLASSES_SCANNED, (
        f"only {len(population)} production exception classes discovered (floor "
        f"{_MIN_EXCEPTION_CLASSES_SCANNED}); the import walk collapsed, so a green result below "
        "would mean 'nothing was examined' rather than 'nothing is wrong'"
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
