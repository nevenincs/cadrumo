"""Real-AEAT-render extraction coverage for the ``declaracion_pdf`` profiles.

Every other extraction test in this package runs against the project's own
generated corpus. That corpus was authored to match the profiles, so it reports
the generator's conventions back rather than AEAT's, and it scores full coverage
at any threshold -- which is precisely how a Modelo 303 profile came to target
six casillas the printed form does not carry, refuse every real render, and stay
green for the entire time it was broken.

This module is the counterweight. It runs the production extraction path over
the bundled AEAT-published annex specimens, which are the official forms filled
with AEAT's own worked-example figures and rendered by AEAT's publication
toolchain. They are external authority: nothing in this repository authored
their layout, so a profile that stops matching them has genuinely drifted from
the document rather than from a convention.

What is asserted, and why each part earns its place:

- The specimen is still an AEAT publication. Read from its sidecar before
  anything else, so the coverage below cannot quietly become a measurement of a
  regenerated synthetic file.
- Extraction does not raise. ``_extract_profile_values`` enforces the profile's
  own ``min_coverage`` and ``failure_semantics``, so a non-raising call IS the
  contract "this profile can read a real AEAT render". Raising the floor above
  what the form yields fails here.
- The extracted casilla set is exactly the expected one. Coverage is a ratio and
  a ratio hides substitution: losing one box and gaining another holds the count
  steady. The set does not.
- The absent boxes are the expected ones. Their absence is a fact about AEAT's
  worked example -- a box the filer legitimately left blank -- not a parser
  defect, and pinning them keeps a real pattern regression from being waved
  through as "just another optional blank".
- Across the whole suite at least one specimen is short of full coverage. This
  is the anti-vacuity guard: if every specimen scored 1.0 the assertions above
  would pass against a corpus that had stopped exercising the blank-box
  tolerance at all, which is the exact blind spot the generated corpus has.

Expected values are grounded in the printed documents, not computed from the
profile under test: the covered and absent sets were read off the AEAT renders,
so this module fails if the profile drifts and cannot be satisfied by adjusting
the profile to match itself.

See Also:
    :mod:`~tests.fixtures.manual_annexes.tests.test_manual_annex_provenance`
        The provenance gate over the same specimens.
    :func:`~adapters.inbound.declaracion.parse_declaracion`
        The full parser boundary, which cannot consume these specimens: they
        carry no NIF and are refused at the identity step by design, which is
        why coverage is exercised at the extraction layer here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from .....core.resources import resources
from .....tests import FIXTURES_DIR
from .._parser import _extract_profile_values, extract_pages_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_ANNEX_DIR = FIXTURES_DIR / "manual_annexes"
_EXPECTED_PROVENANCE = "aeat_published_facsimile"


@dataclass(frozen=True)
class _AnnexSpecimen:
    """One bundled AEAT-published render and what it is expected to yield."""

    modelo: str
    stem: str
    filing_year: int
    period: str
    absent: frozenset[str]
    """Targets the profile declares that this render legitimately does not carry.

    Read off the printed document. A blank money box terminates its line on its
    own printed box number, which the parser reports as missing rather than
    fabricating a value from the box number.
    """

    @property
    def pdf(self) -> Path:
        return _ANNEX_DIR / self.modelo / f"{self.stem}.pdf"

    @property
    def sidecar(self) -> Path:
        return _ANNEX_DIR / self.modelo / f"{self.stem}.json"

    @property
    def label(self) -> str:
        return f"{self.modelo}/{self.stem}"


# Modelo 303: the four quarterly declarations of the Manual Practico IVA 2024
# supuesto practico. Box 78 (compensacion aplicada en este periodo) is blank in
# 2T-4T, and box 37 is blank in 4T.
_M303_ABSENT_COMPENSACION = frozenset({"iva.compensacion-aplicada-periodo"})

_SPECIMENS: tuple[_AnnexSpecimen, ...] = (
    _AnnexSpecimen("303", "2024-1T", 2024, "1T", frozenset()),
    _AnnexSpecimen("303", "2024-2T", 2024, "2T", _M303_ABSENT_COMPENSACION),
    _AnnexSpecimen("303", "2024-3T", 2024, "3T", _M303_ABSENT_COMPENSACION),
    _AnnexSpecimen("303", "2024-4T", 2024, "4T", _M303_ABSENT_COMPENSACION | {"37"}),
    # Modelo 390: the annual summary for the same worked example. Only the 4%
    # and 10% rate rows are absent, because the supuesto never exercises them.
    _AnnexSpecimen(
        "390",
        "2024-0A",
        2024,
        "0A",
        frozenset(
            {
                "iva.anual.repercutido.super-reducido",
                "iva.anual.repercutido.reducido",
            },
        ),
    ),
)


def _declaracion_profile(specimen: _AnnexSpecimen):
    snapshot = resources().modelos.authority.snapshot(
        specimen.modelo,
        filing_year=specimen.filing_year,
        period=specimen.period,
    )
    revision = snapshot.revision
    profile = next(p for p in revision.extraction_profiles if p.artefact_kind == "declaracion")
    return profile, revision


def _extract(specimen: _AnnexSpecimen) -> tuple[frozenset[str], frozenset[str], Decimal]:
    """Run the production extraction path; return (covered, declared, coverage)."""
    profile, revision = _declaracion_profile(specimen)
    pages = extract_pages_text(specimen.pdf)
    values = _extract_profile_values(
        pages,
        profile,
        revision=revision,
        source_pdf_path=specimen.pdf,
    )
    covered = frozenset(str(v.casilla_id) for v in values)
    declared = frozenset(str(t.casilla_id) for t in profile.target_casillas)
    coverage = Decimal(len(covered)) / Decimal(len(declared))
    return covered, declared, coverage


@pytest.mark.parametrize("specimen", _SPECIMENS, ids=lambda s: s.label)
def test_annex_specimen_is_still_an_aeat_publication(specimen: _AnnexSpecimen) -> None:
    """The premise of the coverage assertions below.

    If a specimen were replaced by generated output, the coverage tests would
    still pass while measuring this project's own conventions again. This fails
    loudly instead.
    """
    sidecar = json.loads(specimen.sidecar.read_text(encoding="utf-8"))

    assert sidecar["provenance"] == _EXPECTED_PROVENANCE, (
        f"{specimen.label}: provenance is {sidecar['provenance']!r}, so the real-render "
        f"coverage below would no longer be measuring an AEAT publication"
    )
    assert sidecar["modelo"] == specimen.modelo


@pytest.mark.parametrize("specimen", _SPECIMENS, ids=lambda s: s.label)
def test_profile_accepts_the_real_aeat_render(specimen: _AnnexSpecimen) -> None:
    """The profile reads a real AEAT render without refusing it.

    ``_extract_profile_values`` applies the profile's own ``min_coverage`` and
    ``failure_semantics``, raising when coverage falls short or when any target
    is malformed or ambiguous. A non-raising call is therefore the whole claim:
    this profile's declared targets are things the AEAT form actually prints.

    Modelo 303 failed this for its entire history before the printed-box
    re-scope, scoring 0.667 / 0.611 / 0.611 / 0.556 against a floor of 1.
    """
    profile, _revision = _declaracion_profile(specimen)
    covered, declared, coverage = _extract(specimen)

    assert coverage >= profile.min_coverage, (
        f"{specimen.label}: coverage {coverage} below the profile floor {profile.min_coverage}; "
        f"absent: {sorted(declared - covered)}"
    )


@pytest.mark.parametrize("specimen", _SPECIMENS, ids=lambda s: s.label)
def test_real_render_yields_exactly_the_expected_casillas(specimen: _AnnexSpecimen) -> None:
    """The extracted set is exactly what the printed document carries.

    Asserted as a set rather than a count because a ratio hides substitution: a
    pattern that stops matching one box while another starts matching leaves
    coverage unchanged.
    """
    covered, declared, _coverage = _extract(specimen)
    expected_covered = declared - specimen.absent

    assert covered == expected_covered, (
        f"{specimen.label}: extracted set drifted from the printed document.\n"
        f"  unexpectedly absent: {sorted(expected_covered - covered)}\n"
        f"  unexpectedly present: {sorted(covered - expected_covered)}"
    )


def test_modelo_390_extracted_totals_satisfy_the_forms_own_printed_arithmetic() -> None:
    """Box 65 must equal box 47 minus box 64, as the form's own label states.

    Checks the extracted values rather than merely their presence. The three
    amounts are printed independently by AEAT, so agreement is evidence the
    parser read the intended boxes; a pattern that silently matched a
    neighbouring figure would satisfy the set assertions above and fail here.

    This box was invisible before: the profile's pattern required the literal
    ``(47 - 64)`` while the real render kerns it to ``(4 7 - 64)``, so box 65
    was dropped from every real render while matching the generated corpus --
    and the profile's ``min_coverage`` of 0 meant nothing refused.

    Grounded authority: the printed label of casilla 65 on the Modelo 390 form.
    """
    specimen = next(s for s in _SPECIMENS if s.modelo == "390")
    profile, revision = _declaracion_profile(specimen)
    pages = extract_pages_text(specimen.pdf)
    values = _extract_profile_values(pages, profile, revision=revision, source_pdf_path=specimen.pdf)
    amounts = {str(v.casilla_id): v.printed_value for v in values}

    devengada = amounts["iva.anual.cuota-devengada-total"]
    deducible = amounts["iva.anual.cuota-deducible-total"]
    resultado = amounts["iva.anual.resultado-regimen-general"]

    assert resultado == devengada - deducible, (
        f"{specimen.label}: printed box 65 {resultado!r} != box 47 {devengada!r} - "
        f"box 64 {deducible!r} = {devengada - deducible!r}"
    )


def test_the_suite_still_exercises_the_blank_box_tolerance() -> None:
    """At least one specimen must fall short of full coverage.

    The anti-vacuity guard. Every assertion above would still pass against a
    corpus in which each specimen scored 1.0, and such a corpus would have
    stopped testing the one thing the generated fixtures cannot express: a
    legitimately blank optional box. If this fails, the specimens have become as
    uninformative as the synthetic corpus and the floors they justify are no
    longer evidenced.
    """
    coverages = {specimen.label: _extract(specimen)[2] for specimen in _SPECIMENS}

    assert any(coverage < Decimal(1) for coverage in coverages.values()), (
        "no bundled AEAT render exercises a blank optional box any more; the coverage "
        f"floors are no longer evidenced by these specimens: {coverages}"
    )
