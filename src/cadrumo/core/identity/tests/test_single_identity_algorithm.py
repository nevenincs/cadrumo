"""There is one implementation of the AEAT identity algorithm, and one leader policy.

Two validators once answered the same question differently. Both lived in this
package, both computed the same Luhn-style CIF check value, and both were
reachable from the apoderamiento path -- and for a CIF whose kind letter is one
of ``ABEH`` with a letter control, one accepted and the other refused. Each
carried a comment declaring the divergence deliberate, and one of them
contradicted its own module docstring, which stated the AEAT rule correctly
while the code beneath it did something laxer.

A divergence that is written down is not thereby resolved. What made it survive
was that neither surface was wrong on its own terms: the string-returning
validator and the enum-returning one have genuinely different RETURN SHAPES, so
a reader comparing them sees two functions that legitimately differ and stops
looking. The shape is the only part that may differ. The algorithm and the
leader policy may not.

This gate is structural rather than a behavioural sample, because a sample
cannot see a validator that no test calls yet. It asserts that the checksum
tables and the kind partition are each DECLARED exactly once in the package,
and that no module outside their home reimplements the arithmetic.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PACKAGE = Path(__file__).resolve().parent.parent

#: The module that owns the algorithm and the kind partition.
_AUTHORITY = "_documents.py"

#: Values whose second declaration would be a second policy. Each is a table or
#: partition the AEAT algorithm reads; a module that spells one out is deciding
#: for itself what the rule is.
_POLICY_LITERALS: dict[str, str] = {
    "TRWAGMYFPDXBNJZSQVHLCKE": "the NIF/NIE check-letter table",
    "JABCDEFGHI": "the CIF letter-control table",
    "ABCDEFGHJNPQRSUVW": "the CIF kind-letter catalogue",
    "ABEH": "the digit-control CIF kinds",
    "PQRSNW": "the letter-control CIF kinds",
}


def _modules() -> list[Path]:
    return [
        path
        for path in sorted(_PACKAGE.rglob("*.py"))
        if "tests" not in path.relative_to(_PACKAGE).parts
    ]


def _string_constants(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.add(node.value)
    return found


def _docstrings(path: Path) -> set[str]:
    """Return the module, class and function docstrings, which may cite a table."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                found.add(doc)
    return found


def test_each_policy_table_is_declared_once() -> None:
    """A second declaration of a table is a second opinion about the rule."""
    offenders: list[str] = []
    for path in _modules():
        if path.name == _AUTHORITY:
            continue
        prose = "\n".join(_docstrings(path))
        for literal, description in _POLICY_LITERALS.items():
            if literal not in _string_constants(path):
                continue
            # Naming a table in prose documents the rule; re-declaring it as a
            # value implements the rule a second time. Only the latter drifts.
            if literal in prose:
                continue
            offenders.append(f"{path.relative_to(_PACKAGE).as_posix()} restates {description}")
    assert not offenders, (
        "these modules declare an identity policy table that "
        f"{_AUTHORITY} already owns; import it instead: {offenders}"
    )


def test_the_checksum_arithmetic_has_one_home() -> None:
    """The ``% 23`` and Luhn expressions must appear only in the authority."""
    offenders: list[str] = []
    for path in _modules():
        if path.name == _AUTHORITY:
            continue
        source = path.read_text(encoding="utf-8")
        body = "\n".join(
            line for line in source.splitlines() if not line.lstrip().startswith("#")
        )
        prose = "\n".join(_docstrings(path))
        for expression in ("% 23", "(10 - "):
            if expression in body and expression not in prose:
                offenders.append(f"{path.relative_to(_PACKAGE).as_posix()} recomputes {expression!r}")
    assert not offenders, (
        "the identity checksum arithmetic must be computed in "
        f"{_AUTHORITY} alone, so both return shapes agree by construction: {offenders}"
    )


def test_the_authority_still_owns_what_the_gate_pins() -> None:
    """A rename must not leave this gate passing over an empty package.

    Without this, moving the tables out of ``_documents.py`` makes every
    assertion above vacuously true: no module would restate a table the gate
    can no longer find anywhere.
    """
    authority = _PACKAGE / _AUTHORITY
    assert authority.exists(), f"{_AUTHORITY} is the pinned authority and must exist"
    declared = _string_constants(authority)
    missing = sorted(literal for literal in _POLICY_LITERALS if literal not in declared)
    assert not missing, (
        f"{_AUTHORITY} no longer declares these policy tables, so the "
        f"single-declaration checks above prove nothing: {missing}"
    )
