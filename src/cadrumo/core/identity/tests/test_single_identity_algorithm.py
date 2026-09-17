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
cannot see a validator that no test calls yet. The checksum tables and
control-kind partitions are governed registry facts supplied to the kernel as a
``SpanishTaxIdFormat``, so no module in this package may declare one, and the
checksum arithmetic may be computed only in the kernel module.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PACKAGE = Path(__file__).resolve().parent.parent

#: The module that owns the checksum arithmetic.
_AUTHORITY = "documents.py"

#: Values whose second declaration would be a second policy. Each is a table or
#: partition the AEAT algorithm reads; a module that spells one out is deciding
#: for itself what the rule is.
_POLICY_LITERALS: dict[str, str] = {
    "TRWAGMYFPDXBNJZSQVHLCKE": "the NIF/NIE check-letter table",
    "JABCDEFGHI": "the CIF letter-control table",
    "ABEH": "the digit-control CIF kinds",
    "PQRSNW": "the letter-control CIF kinds",
}


def _modules(package: Path = _PACKAGE) -> list[Path]:
    return [path for path in sorted(package.rglob("*.py")) if "tests" not in path.relative_to(package).parts]


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


def _policy_table_offenders(package: Path) -> list[str]:
    offenders: list[str] = []
    for path in _modules(package):
        prose = "\n".join(_docstrings(path))
        for literal, description in _POLICY_LITERALS.items():
            if literal not in _string_constants(path):
                continue
            # Naming a table in prose documents the rule; re-declaring it as a
            # value implements the rule a second time. Only the latter drifts.
            if literal in prose:
                continue
            offenders.append(f"{path.relative_to(package).as_posix()} restates {description}")
    return offenders


def test_no_module_declares_a_policy_table() -> None:
    """A declared table is an opinion about the rule the governed fact already states."""
    offenders = _policy_table_offenders(_PACKAGE)
    assert not offenders, (
        f"these modules declare an identity policy table the governed tax-ID format fact owns: {offenders}"
    )


def test_a_restated_policy_table_is_detected(tmp_path: Path) -> None:
    """The scan must find a table spelled as a value, and ignore one named in prose."""
    (tmp_path / "restating.py").write_text('LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"\n', encoding="utf-8")
    (tmp_path / "documenting.py").write_text(
        '"""Kinds ``ABEH`` carry a digit control."""\n\nKINDS = "ABEH"\n', encoding="utf-8"
    )

    assert _policy_table_offenders(tmp_path) == ["restating.py restates the NIF/NIE check-letter table"]


def test_the_checksum_arithmetic_has_one_home() -> None:
    """The ``% 23`` and Luhn expressions must appear only in the authority."""
    offenders: list[str] = []
    for path in _modules():
        if path.name == _AUTHORITY:
            continue
        source = path.read_text(encoding="utf-8")
        body = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
        prose = "\n".join(_docstrings(path))
        for expression in ("% 23", "(10 - "):
            if expression in body and expression not in prose:
                offenders.append(f"{path.relative_to(_PACKAGE).as_posix()} recomputes {expression!r}")
    assert not offenders, (
        "the identity checksum arithmetic must be computed in "
        f"{_AUTHORITY} alone, so both return shapes agree by construction: {offenders}"
    )


def test_the_authority_still_computes_what_the_gate_pins() -> None:
    """A rename must not leave the arithmetic gate passing over an empty package."""
    authority = _PACKAGE / _AUTHORITY
    assert authority.exists(), f"{_AUTHORITY} is the pinned authority and must exist"
    assert "(10 - " in authority.read_text(encoding="utf-8")
