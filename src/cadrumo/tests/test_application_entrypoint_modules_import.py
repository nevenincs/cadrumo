"""Every application and entrypoint module must actually import.

The static import-resolution gates parse source and resolve names against
package attributes, which proves the *spelling* of an import but never
executes the importing module. A name imported from a sibling MODULE that
the sibling does not define slips through: the statement is well-formed,
the target module exists, and only the import itself raises.

That is not hypothetical. A refactor replaced a module-level constant with
an accessor spelling that was never added to the defining module, and the
consumer sat broken in the tree because no test imported it -- the defect
reaches an operator the first time the owning command runs.

This gate executes the import for every non-test module in
``cadrumo.application`` and ``cadrumo.entrypoints``.  The checked-in inventory
is generated from those paths and is checked for drift before use, so the
finite static target set and the runtime coverage have the same source.
"""

from __future__ import annotations

import importlib
import sys
import textwrap
from collections.abc import Iterable
from pathlib import Path

import pytest

from .module_target_inventory import assert_target_set_current, load_target_set

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_METADATA_PATH = "dev/quality/metadata/application_entrypoint_modules.json"
_TARGET_SET = "application_entrypoint_modules"


def _import_failures(modules: Iterable[str]) -> list[str]:
    """Import every named module, returning one report line per failure.

    Catches :class:`Exception`, not :class:`ImportError`.  A module that
    raises at import time is broken for the operator whatever the exception
    class: a registry validation error or a ``TypeError`` raised while
    building a module-level constant is exactly the defect this gate exists
    to catch, and narrowing the clause would let the first such module abort
    the scan and hide every module after it.  The exception's type name stays
    in the report so the failure is still identifiable.
    """
    failures: list[str] = []
    for name in modules:
        try:
            importlib.import_module(name)
        except Exception as error:
            failures.append(f"{name}: {type(error).__name__}: {error}")
    return failures


def test_every_application_and_entrypoint_module_imports() -> None:
    """Importing each module raises nothing.

    The failure report names every broken module at once rather than
    stopping at the first, because a dangling name is usually one of a
    cluster left by a single incomplete rename.
    """
    assert_target_set_current(_METADATA_PATH, _TARGET_SET)
    modules = load_target_set(_METADATA_PATH, _TARGET_SET)
    assert modules, "the import scan found no modules, so it proves nothing"

    failures = _import_failures(modules)

    assert not failures, "modules failed to import:\n" + "\n".join(failures)


def test_scan_reports_a_non_import_error_and_keeps_scanning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A module raising a non-``ImportError`` is reported, and the scan continues.

    Two fabricated modules on a temporary path stand in for the production
    inventory: the first raises a ``RuntimeError`` at import, the second an
    ``ImportError``.  Both must appear in the report.  If the scan narrowed
    its clause back to ``ImportError``, the first module's exception would
    propagate and the second would never be reached.
    """
    package = tmp_path / "cadrumo_import_scan_specimen"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "raises_runtime_error.py").write_text(
        textwrap.dedent(
            """
            raise RuntimeError("module-level construction refused this specimen")
            """
        ),
        encoding="utf-8",
    )
    (package / "raises_import_error.py").write_text(
        textwrap.dedent(
            """
            from cadrumo_import_scan_specimen import name_that_is_not_defined  # noqa: F401
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    for name in tuple(sys.modules):
        if name.startswith("cadrumo_import_scan_specimen"):
            monkeypatch.delitem(sys.modules, name, raising=False)

    failures = _import_failures(
        (
            "cadrumo_import_scan_specimen.raises_runtime_error",
            "cadrumo_import_scan_specimen.raises_import_error",
        )
    )

    assert len(failures) == 2, failures
    assert failures[0].startswith("cadrumo_import_scan_specimen.raises_runtime_error: RuntimeError: ")
    assert "module-level construction refused this specimen" in failures[0]
    assert failures[1].startswith("cadrumo_import_scan_specimen.raises_import_error: ImportError: ")
