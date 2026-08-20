"""No name this boundary exports is a contract nothing ever uses.

Six pydantic command and result contracts were exported from this package and
constructed by nothing -- not the CLI, not another layer, not a test, not even
the module declaring them. ``RegisterProfileCommand``, ``CompleteSetupCommand``,
``EditProfileFieldCommand``, ``EditProfileSectionCommand``,
``ProfileLifecycleResult`` and ``ProfileSnapshotRequest`` described a
command-object boundary the application never grew: the behaviour they named
shipped through repository methods taking plain arguments, and the contracts
were left standing.

They were not obviously dead. Vault records show verbs described as "routed
through ``EditProfileSectionCommand``" and a ``complete_setup`` service arm
added -- so reading the intent alone suggested live wiring. Both behaviours DO
exist; they simply never went through these types. That is the shape this gate
catches: a contract whose NAME is load-bearing in the project's own records while
its CODE is referenced nowhere.

WHAT THIS CHECKS, AND WHAT IT DOES NOT. It requires each exported name to be
LOADED somewhere -- constructed, annotated with, subclassed, imported by
another module. A definition is not a use, which is the whole point: a class
statement plus an ``__all__`` entry is exactly what the six had.

It deliberately does NOT require a consumer outside the defining module.
Thirteen further exports are used only within the module that defines them --
over-exported rather than dead -- and that is a facade-narrowing judgement to
be made per symbol, not a defect to fail a build over. Conflating the two
would bury the real finding in a list of harmless ones.

Scoped to this package on purpose: it is the surface this work owns, and a
tree-wide version would need every other package's owners to answer for their
own exports.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....tests import non_test_package_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FACADE = "src/cadrumo/application/user_profile/__init__.py"


def _exported_names() -> tuple[str, ...]:
    """Return every name in the boundary's ``__all__``."""
    tree = ast.parse(Path(_FACADE).read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            continue
        return tuple(
            element.value
            for element in getattr(node.value, "elts", [])
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        )
    return ()


def _loaded_names() -> set[str]:
    """Return every identifier LOADED anywhere in production code.

    A load is a use: construction, annotation, subclassing, an import naming
    it. Definitions are excluded by construction -- ``ast.Name`` in a class or
    function statement is not a load, and that asymmetry is what separates a
    live contract from a declared-and-abandoned one.

    The facade itself is skipped: its ``__all__`` strings and re-export lines
    mention every name it exports, so counting them would make the check
    tautological -- every export would appear used because it is exported.
    """
    loaded: set[str] = set()
    for path in non_test_package_python_files():
        if repo_relative(path) == _FACADE:
            continue
        try:
            tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - unparsable file is its own failure
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                loaded.add(node.id)
            elif isinstance(node, ast.Attribute):
                loaded.add(node.attr)
            elif isinstance(node, ast.alias):
                loaded.add(node.asname or node.name.rsplit(".", 1)[-1])
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                # A name reachable only through a lazy __getattr__ mapping or a
                # dynamic import string is still a use.
                loaded.add(node.value)
    return loaded


def test_the_facade_actually_exports_something() -> None:
    """ANTI-VACUITY: an empty export list would pass every assertion below.

    If ``__all__`` moves, is built dynamically, or stops parsing, this file
    goes green while checking nothing at all.
    """
    assert len(_exported_names()) > 100, "the boundary's __all__ no longer parses; the gate is checking nothing"


#: Exported names that production code never loads, with what is known about
#: each. An entry is a RECORD, not a clearance: it says someone looked and
#: states what they found, so the next reader does not re-derive it. None of
#: these was deleted, because each carries a declared relationship somewhere
#: that a bare reference count does not see.
_EXPORTED_BUT_UNCONSTRUCTED: dict[str, str] = {
    "ProfileSnapshot": (
        "Enrolled by NAME in the dev identifier-namespace gate, which asserts its identifier "
        "contract against the core spelling. The gate is a real consumer; production constructs "
        "no instance."
    ),
    "ProfileStaleCheckReport": "Enrolled by name in the same identifier-namespace gate as ProfileSnapshot.",
    "ProfileImportResult": (
        "Named only by a docstring in the CLI payload module that says it projects this class "
        "down to a wire shape. The module imports nothing of the sort, so the stated relationship "
        "is prose rather than code -- recorded here rather than silently trusted."
    ),
    "register_imported_profile_bundle": (
        "Documents itself as the sanctioned entry point for the operator-facing import verb, and "
        "there is no import verb. The EXPORT half of the same subsystem is live -- the TUI profile "
        "manager exports through it and `aeat app maintenance reconcile` cleans up its crash "
        "orphans -- so this is not dormant scaffolding around an unused feature. It is the missing "
        "half of a working one: the product writes passphrase-encrypted bundles and nothing in it "
        "reads them back, which the symbols show plainly (encrypt_* is live, decrypt_* is not). "
        "Kept because deleting it would remove the only code that could make those exports "
        "restorable."
    ),
}


def test_no_exported_name_is_used_nowhere() -> None:
    """A declared contract that nothing constructs is not a boundary."""
    loaded = _loaded_names()
    unused = sorted(
        name
        for name in _exported_names()
        if name not in loaded and name not in _EXPORTED_BUT_UNCONSTRUCTED
    )

    assert not unused, (
        f"these names are exported by the boundary and loaded nowhere in production code: {unused}. "
        "A class statement plus an __all__ entry is a design-only shell, not a contract -- either "
        "wire it to the behaviour it describes, or delete it and let the live path stand alone."
    )


def test_the_detector_does_not_count_a_definition_as_a_use() -> None:
    """DISCRIMINATING: the asymmetry the whole gate rests on.

    The six removed contracts were each defined exactly once and used never.
    If a class or function statement counted as a load, every one of them
    would have passed and this gate would certify the defect it exists to
    catch.
    """
    tree = ast.parse("class OnlyDefined:\n    pass\n\n\ndef only_defined():\n    return None\n")
    loaded = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }

    assert "OnlyDefined" not in loaded
    assert "only_defined" not in loaded


def test_no_record_outlives_the_name_it_describes() -> None:
    """The half that rots: an entry for a name now constructed, or gone.

    A record that outlives its subject reads as a known gap that is not there,
    which is how an inventory drifts into describing a tree it no longer
    matches.
    """
    loaded = _loaded_names()
    exported = set(_exported_names())
    stale = sorted(
        name
        for name in _EXPORTED_BUT_UNCONSTRUCTED
        if name in loaded or name not in exported
    )

    assert not stale, f"these records no longer describe an exported-but-unconstructed name: {stale}"


def test_every_record_states_something() -> None:
    """An empty reason reads as reviewed while recording nothing."""
    empty = sorted(name for name, reason in _EXPORTED_BUT_UNCONSTRUCTED.items() if not reason.strip())

    assert not empty, f"records with no stated reason: {empty}"
