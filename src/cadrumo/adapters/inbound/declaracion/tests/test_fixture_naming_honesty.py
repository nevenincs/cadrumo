"""A fixture constant's name must match the provenance its sidecar declares.

Two constants in this package were named for real redacted declaration copies
while pointing at output of this project's own fixture generator. Both were
found by hand, months apart, and neither was found by a failing test -- the
Modelo 303 one surfaced during a printed-box census and the Modelo 130 one only
because that census prompted a sweep of the class. In the M130 case the
consuming test's own docstring already said "synthetic" while its name still
said "real", so the contradiction sat in a single file and was still missed.

A name is not decoration here. ``_REAL_...`` asserts that a fixture is external
authority -- a sanitised genuine AEAT filing -- and that claim is what makes a
test using it evidence of anything. When the name is wrong the test looks like
grounding and is not, which is the same shape as a profile claiming to read
boxes the form does not print.

So the naming is bound to the declared provenance mechanically rather than by
review. Each fixture-path constant in the shared support module must carry a
marker naming its class, and that marker must agree with what the fixture's
sidecar declares. Renaming a fixture without re-checking it, or regenerating a
real-corpus specimen as synthetic output, fails here.

The sidecar is trusted as the declaration but is not the last word on physical
truth: sibling gates cross-check it against the PDF's own ``/Producer`` DocInfo
and, for the annex specimens, against the absence of an extractable NIF. This
module closes the remaining gap between that declaration and the name a test
author reads.

See Also:
    :mod:`~adapters.inbound.declaracion.tests._parser_boundary_support`
        The module whose fixture constants are audited here.
    :mod:`~tests.fixtures.manual_annexes.tests.test_manual_annex_provenance`
        The provenance gate over the AEAT-published annex specimens.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .....tests import FIXTURES_DIR
from . import _parser_boundary_support

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_REAL_MARKER = "_REAL_"
_SYNTHETIC_MARKER = "_SYNTHETIC_"

_PROVENANCE_FOR_MARKER = {
    _REAL_MARKER: "real_corpus",
    _SYNTHETIC_MARKER: "synthetic_generated",
}


def _fixture_constants() -> list[tuple[str, Path]]:
    """Every module-level constant naming a justificante fixture PDF."""
    justificantes = FIXTURES_DIR / "justificantes"
    found: list[tuple[str, Path]] = []
    for name in dir(_parser_boundary_support):
        value = getattr(_parser_boundary_support, name)
        if not isinstance(value, Path) or value.suffix != ".pdf":
            continue
        if justificantes not in value.parents:
            continue
        found.append((name, value))
    return sorted(found)


def _marker(name: str) -> str | None:
    # _REAL_ is checked first: a name carrying both markers is ambiguous rather
    # than real, and is caught by the classification test below.
    for marker in (_REAL_MARKER, _SYNTHETIC_MARKER):
        if marker in name:
            return marker
    return None


def test_the_audit_finds_fixture_constants_to_audit() -> None:
    """Guards every assertion below against a silent no-op.

    All of the tests here iterate the discovered constants, so a refactor that
    moved or renamed them out of reach would leave this module passing while
    auditing nothing.
    """
    constants = _fixture_constants()

    assert len(constants) >= 10, (
        f"expected the shared support module to hold the justificante fixture constants; "
        f"found {len(constants)}: {[n for n, _ in constants]}"
    )


def test_every_fixture_constant_declares_its_class_in_its_name() -> None:
    """A constant must say whether it points at real or generated evidence.

    An unmarked name is not a neutral one. A reader has no way to tell whether
    a test built on it is externally grounded, which is the question the name
    exists to answer.
    """
    unmarked = [name for name, _ in _fixture_constants() if _marker(name) is None]

    assert not unmarked, (
        f"fixture constants name neither {_REAL_MARKER!r} nor {_SYNTHETIC_MARKER!r}, so their "
        f"grounding cannot be read from the name: {unmarked}"
    )


def test_every_fixture_constant_points_at_a_fixture_that_declares_provenance() -> None:
    """The claim in the name has to be checkable against something."""
    missing = [name for name, pdf in _fixture_constants() if not pdf.with_suffix(".json").is_file()]

    assert not missing, (
        f"fixture constants point at PDFs with no provenance sidecar, so their naming "
        f"claim cannot be verified: {missing}"
    )


def test_fixture_constant_names_match_their_declared_provenance() -> None:
    """The gate. A name claiming real evidence must point at real evidence.

    This is what neither the Modelo 303 nor the Modelo 130 misnaming had to get
    past. Both would have failed here on the commit that introduced them.
    """
    mismatches: list[str] = []
    for name, pdf in _fixture_constants():
        marker = _marker(name)
        if marker is None:
            continue  # reported by the classification test
        sidecar = pdf.with_suffix(".json")
        if not sidecar.is_file():
            continue  # reported by the sidecar test
        declared = json.loads(sidecar.read_text(encoding="utf-8")).get("provenance")
        expected = _PROVENANCE_FOR_MARKER[marker]
        if declared != expected:
            mismatches.append(
                f"{name} -> {pdf.parent.name}/{pdf.name}: name implies {expected!r}, sidecar declares {declared!r}",
            )

    assert not mismatches, "fixture constant names contradict their sidecars:\n  " + "\n  ".join(
        mismatches,
    )


def test_the_provenance_comparison_rejects_a_mismatch() -> None:
    """Anti-tautology proof for the gate above.

    The gate is a comparison, and a comparison that cannot fail is not a gate.
    Rather than assert the two provenance values differ -- which would prove
    nothing about the code -- this drives the real classifier: a name carrying
    the real marker must not resolve to the synthetic provenance, and the
    markers must be distinguishable in the first place.
    """
    assert _marker("_REAL_MODELO_999_DECLARATION_COPY") == _REAL_MARKER
    assert _marker("_MODELO_999_SYNTHETIC_FIXTURE") == _SYNTHETIC_MARKER
    assert _marker("_MODELO_999_FIXTURE") is None

    assert _PROVENANCE_FOR_MARKER[_REAL_MARKER] != _PROVENANCE_FOR_MARKER[_SYNTHETIC_MARKER]

    # The exact shape both historical defects took: a real-marked name over a
    # sidecar declaring generated output must be classified as a mismatch.
    declared = "synthetic_generated"
    assert declared != _PROVENANCE_FOR_MARKER[_marker("_REAL_MODELO_999_DECLARATION_COPY")]
