"""Each custody size ceiling is defined once, in one module.

``PROFILE_CUSTODY_DATA_FILE_MAX_BYTES`` and ``PROFILE_CUSTODY_DATA_MAX_ENTRIES``
were each defined TWICE, with equal values, in ``_filesystem`` and
``_inventory``. Two halves of one contract read different copies: the capsule
data reader enforced the ``_filesystem`` pair, while the inventory that
produces a capsule's integrity manifest enforced its own.

Equal values are what made it survive. Nothing failed, nothing diverged, and
the duplication was invisible precisely because the copies agreed -- until
someone raised one of them. Then a capsule could be inventoried and not
readable, or readable and not inventoriable, and the disagreement would surface
as a corrupt-looking capsule rather than as a constant someone edited.

A ceiling is not a value that gets independently rediscovered. It is a decision
about what this format admits, and a decision has one home.

The check reads MODULE-LEVEL ASSIGNMENTS rather than resolved attributes: after
an import the second module's attribute is the same object, so comparing values
-- or even identity -- would pass over exactly the state this forbids. What
must be unique is the DEFINITION.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

#: Ceilings that must have exactly one defining module in this package.
_SINGLE_HOME_CEILINGS = (
    "PROFILE_CUSTODY_DATA_FILE_MAX_BYTES",
    "PROFILE_CUSTODY_DATA_MAX_ENTRIES",
)

_CUSTODY_PACKAGE = Path(__file__).resolve().parent.parent


def _defining_modules(name: str) -> tuple[str, ...]:
    """Return every module in this package that ASSIGNS ``name`` at module level."""
    homes: list[str] = []
    for path in sorted(_CUSTODY_PACKAGE.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - unparsable file is its own failure
            continue
        for node in tree.body:
            targets = node.targets if isinstance(node, ast.Assign) else ([node.target] if isinstance(node, ast.AnnAssign) else [])
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                homes.append(path.name)
    return tuple(homes)


def test_the_scan_finds_the_real_package() -> None:
    """ANTI-VACUITY: an empty scan would report every ceiling as single-homed."""
    modules = sorted(path.name for path in _CUSTODY_PACKAGE.glob("*.py"))

    assert len(modules) > 10, f"the custody package scan found only {len(modules)} modules"
    assert "_filesystem.py" in modules, "the scan is not seeing the module that owns these ceilings"


@pytest.mark.parametrize("ceiling", _SINGLE_HOME_CEILINGS)
def test_a_ceiling_is_defined_in_exactly_one_module(ceiling: str) -> None:
    """DISCRIMINATING: the duplication that agreed with itself until it did not."""
    homes = _defining_modules(ceiling)

    assert len(homes) == 1, (
        f"{ceiling} is defined in {len(homes)} modules ({list(homes)}). Two halves of one contract "
        "then enforce different copies, and equal values hide it until someone raises one. Import "
        "it from its owning module instead of redeclaring it."
    )


def test_the_detector_counts_definitions_not_imports() -> None:
    """The distinction the whole check rests on.

    A module that IMPORTS the ceiling exposes it as an attribute identical to
    the original, so a value or identity comparison would see one ceiling where
    two definitions exist. Only the assignment is evidence of a second home --
    asserted here so the parametrised checks above cannot be satisfied by a
    weaker reading later.
    """
    importing = ast.parse("from ._filesystem import PROFILE_CUSTODY_DATA_FILE_MAX_BYTES\n")
    defining = ast.parse("PROFILE_CUSTODY_DATA_FILE_MAX_BYTES = 1\n")

    def assigns(tree: ast.Module) -> bool:
        return any(
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "PROFILE_CUSTODY_DATA_FILE_MAX_BYTES" for t in node.targets)
            for node in tree.body
        )

    assert not assigns(importing)
    assert assigns(defining)
