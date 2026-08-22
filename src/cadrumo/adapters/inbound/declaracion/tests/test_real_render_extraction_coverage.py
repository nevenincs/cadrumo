"""Extraction coverage for the ``declaracion_pdf`` profiles, over two families.

Every other extraction test in this package runs against the project's own
generated corpus. That corpus was authored to match the profiles, so it reports
the generator's conventions back rather than AEAT's, and it scores full coverage
at any threshold -- which is precisely how a Modelo 303 profile came to target
six casillas the printed form does not carry, refuse every real render, and stay
green for the entire time it was broken.

This module is the counterweight, and one half of it no longer is. Read that
before reading anything below:

- **The AEAT-published annex specimens** (``manual_annexes/``): the official
  forms filled with AEAT's own worked-example figures and rendered by AEAT's
  publication toolchain. Nothing in this repository authored them, so a profile
  that stops matching them has genuinely drifted from the document. Because the
  figures are AEAT's, these support arithmetic checks against the form's own
  printed totals. This family is unchanged and is now the ONLY externally
  authored evidence the module holds.
- **The replacement specimens** (``justificantes/``): these WERE sanitised real
  filed declarations, and every one of them has been withdrawn. Each carried
  identity the redaction pipeline never wrote -- a checksum-valid IBAN, a
  control-letter-valid tax id, an address, a phone number, and name-shaped
  strings that appear in no sanitiser manifest and nowhere in AEAT's bundled
  normative corpus. What stands in their place are generated reproductions of
  the printed layout, and a reproduction cannot be evidence about a document
  this project did not author, because this project authored it.

So this half has changed what it proves. It was: "the profile can read a real
AEAT render". It is now: "the profile still reads the layout facts somebody
previously established a real AEAT render has". That is a regression gate on a
recorded contract, not external evidence, and it cannot catch AEAT behaviour
nobody has written down. The loss is real and is stated here rather than
absorbed into a passing test.

What is asserted, and why each part earns its place:

- The specimen is what it claims to be. Read from its sidecar before anything
  else -- ``aeat_published_facsimile`` for the annexes, ``synthetic_generated``
  for the replacements -- so neither family can quietly become the other.
- Extraction does not raise. ``_extract_profile_values`` enforces the profile's
  own ``min_coverage`` and ``failure_semantics``, so a non-raising call IS the
  contract "this profile can read this render". Raising the floor above what the
  form yields fails here.
- The extracted casilla set is exactly the expected one. Coverage is a ratio and
  a ratio hides substitution: losing one box and gaining another holds the count
  steady. The set does not.
- The absent boxes are the expected ones. On an annex that is a fact about
  AEAT's worked example; on a replacement it is a fact about the render the
  replacement reproduces -- a box the filer left blank, or one printed on a form
  page the document omits.
- A blank box does not fabricate a value from its own printed box number.
  Exercised on the Modelo 390 replacement, which reproduces the printed-and-blank
  box 662 the withdrawn render carried.
- Across the whole suite at least one specimen is short of full coverage. This
  is the anti-vacuity guard: if every specimen scored 1.0 the assertions above
  would pass against a corpus that had stopped exercising the blank-box
  tolerance at all.

The per-casilla VALUES are no longer checked here. They used to be, against the
sanitiser constant each withdrawn sidecar declared; a generated specimen has no
such declaration, and inventing one in this module would only restate the
generator. The exact printed amounts are asserted instead by the per-modelo
boundary tests, which is the stronger place for it: those replacements print
DISTINCT amounts where the redaction pipeline wrote one constant into every box,
so an exact map now discriminates a cross-line misread where the old constant
check could not.

Modelo 100's coverage floor remains inherited rather than evidenced. Every box
is populated on all three specimens, so they show what a complete Modelo 100
yields, not what the form yields across filings, and a filer legitimately
leaving one optional box blank would still be refused by a floor of 1.

See Also:
    :mod:`~tests.fixtures.manual_annexes.tests.test_manual_annex_provenance`
        The provenance gate over the annex specimens.
    :func:`~adapters.inbound.declaracion.parse_declaracion`
        The full parser boundary. It cannot consume the annex specimens, which
        carry no NIF and are refused at the identity step by design, which is
        why coverage is exercised at the extraction layer for both families
        uniformly. The replacement specimens do carry a synthetic NIF and are
        driven end to end by the per-modelo boundary tests; what those cannot
        express, and this module adds, is the coverage floor a profile declares
        and the provenance premise the measurement rests on.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from .....core import RegistryAuthorityGrade
from .....core.resources import resources
from .....tests import FIXTURES_DIR
from .._parser import _extract_profile_values, _select_extraction_profile, extract_pages_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_ANNEX_DIR = FIXTURES_DIR / "manual_annexes"
_JUSTIFICANTE_DIR = FIXTURES_DIR / "justificantes"
_EXPECTED_PROVENANCE = "aeat_published_facsimile"
_EXPECTED_REPLACEMENT_PROVENANCE = "synthetic_generated"


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


@dataclass(frozen=True)
class _ReplacementSpecimen:
    """A generated reproduction of a withdrawn real render.

    Distinct from :class:`_AnnexSpecimen` in what it can prove, and the gap is
    wider than it looks. An annex is AEAT's own artefact; a replacement is this
    project reproducing the layout facts somebody had already written down about
    an artefact that has been deleted. It regression-gates a recorded contract.
    It is not evidence about AEAT.
    """

    modelo: str
    stem: str
    filing_year: int
    period: str
    absent: frozenset[str]
    """Targets the profile declares that this render legitimately does not carry.

    Read off the printed document: a box the filer left blank, or one printed on
    a form page this render omits.
    """

    count_valued: frozenset[str] = frozenset()
    """Covered targets whose printed value is a count of people, not an amount.

    Membership is read off the printed column header (``N.o de perceptores``,
    ``Numero total de percepciones``). Retained because it records a real
    property of the form -- one of these columns is not money -- which a reader
    of the extracted values needs in order to read them correctly.
    """

    @property
    def pdf(self) -> Path:
        return _JUSTIFICANTE_DIR / self.modelo / f"{self.stem}.pdf"

    @property
    def sidecar(self) -> Path:
        return _JUSTIFICANTE_DIR / self.modelo / f"{self.stem}.json"

    @property
    def label(self) -> str:
        return f"{self.modelo}/{self.stem}"


# Modelo 390: reproduces the withdrawn English-render annual summary -- the only
# render AEAT issued in English rather than Spanish, and the reason the parser
# anchors on both languages at all. It prints a page that opens mid-section on
# "5. Transactions made under the general system (continued)" with no preceding
# start, so the four devengado rate rows and box 47 sit on a form page the
# document does not contain. Box 662 is printed and blank.
_M390_REPLACEMENT_ABSENT = frozenset(
    {
        "iva.anual.repercutido.super-reducido",
        "iva.anual.repercutido.reducido",
        "iva.anual.repercutido.general",
        "iva.anual.aic.bienes.tipo-21.cuota",
        "iva.anual.cuota-devengada-total",
        "iva.anual.compensacion-generada-ejercicio-no-97",
    },
)

# Modelo 111: the filer declared only rendimientos de actividades economicas, so
# boxes 07/08/09 carry values and every other perceptor section is printed blank.
# The fourth quarter is sparser still: it prints casilla 30 alone. Both shapes
# are reproduced, because a render where almost every box is blank is the one
# that exercises the blank-cell arm of the bbox anchor.
_M111_TARGETS = frozenset(f"{n:02d}" for n in range(1, 31)) - {"29"}
_M111_COVERED_QUARTERLY = frozenset({"07", "08", "09", "28", "30"})
_M111_COVERED_FOURTH = frozenset({"30"})

# EVERY specimen in this table is now a generated replacement. The renders they
# reproduce were withdrawn because all seven carried personal data the redaction
# pipeline never wrote: a checksum-valid IBAN on Modelo 100 2021, and across all
# seven a total of seventeen distinct name-shaped strings that appear in no
# sanitiser manifest and nowhere in AEAT's 8.8M-character bundled normative
# corpus. One of those strings recurred across two different modelos, which form
# chrome cannot do.
#
# What that costs, stated plainly: this table no longer holds any externally
# authored evidence. It pins the layout contract that the withdrawn renders
# established -- coverage floors, exact casilla sets, the blank-box guard -- and
# it will catch a profile that drifts from that contract. It will not catch AEAT
# behaviour nobody recorded, which is the thing the real renders were for. The
# annex family above is the only external evidence left in this module.
_REPLACEMENT_SPECIMENS: tuple[_ReplacementSpecimen, ...] = (
    _ReplacementSpecimen("390", "2021-0A", 2021, "0A", _M390_REPLACEMENT_ABSENT),
    _ReplacementSpecimen("111", "2024-1T", 2024, "1T", _M111_TARGETS - _M111_COVERED_QUARTERLY, frozenset({"07"})),
    _ReplacementSpecimen("111", "2024-2T", 2024, "2T", _M111_TARGETS - _M111_COVERED_QUARTERLY, frozenset({"07"})),
    _ReplacementSpecimen("111", "2024-3T", 2024, "3T", _M111_TARGETS - _M111_COVERED_QUARTERLY, frozenset({"07"})),
    _ReplacementSpecimen("111", "2024-4T", 2024, "4T", _M111_TARGETS - _M111_COVERED_FOURTH),
    # Modelo 100: three annual declarations. Every target is populated, so
    # nothing is absent -- these are the only specimens here that exercise a
    # fully-completed form, which is why the anti-vacuity guard below matters.
    _ReplacementSpecimen("100", "2021-0A", 2021, "0A", frozenset()),
    _ReplacementSpecimen("100", "2022-0A", 2022, "0A", frozenset()),
    _ReplacementSpecimen("100", "2023-0A", 2023, "0A", frozenset()),
)


def _declaracion_profile(specimen: _AnnexSpecimen | _ReplacementSpecimen):
    """Select the profile by CALLING :func:`_select_extraction_profile`.

    This gate exists to prove a profile can read a real AEAT render, which is
    only true of the profile production would actually choose. It previously
    re-implemented the selector's filter, so the two could diverge silently and
    the gate would keep certifying a profile the parser no longer selects --
    the assertion would still pass while testing the wrong subject.

    The re-implementation was also a live trap in its own right: selecting on
    ``artefact_kind`` rather than ``surface`` returns nothing for half the tree,
    because that field is a free-form ``str`` the registry splits between
    ``"declaracion"`` and ``"declaration_pdf"``, and the miss reads as "this
    modelo has no declaration profile" rather than as an error. Calling the
    selector removes the opportunity to get that wrong twice.

    A modelo with no declaration profile, or more than one, now raises
    :class:`DeclaracionParseError` from the selector itself rather than a local
    assertion -- the same refusal an operator would meet.
    """
    snapshot = resources().modelos.authority.snapshot(
        specimen.modelo,
        filing_year=specimen.filing_year,
        period=specimen.period,
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )
    revision = snapshot.revision
    return _select_extraction_profile(snapshot, extraction_profile_id=None), revision


def _extracted_amounts(specimen: _AnnexSpecimen | _ReplacementSpecimen) -> dict[str, object]:
    """Run the production extraction path; return casilla id to printed value."""
    profile, revision = _declaracion_profile(specimen)
    pages = extract_pages_text(specimen.pdf)
    values = _extract_profile_values(
        pages,
        profile,
        revision=revision,
        source_pdf_path=specimen.pdf,
    )
    return {str(v.casilla_id): v.printed_value for v in values}


def _as_amount(
    specimen: _AnnexSpecimen | _ReplacementSpecimen,
    amounts: dict[str, object],
    casilla_id: str,
) -> Decimal:
    """Read one extracted target as a money amount, refusing any other shape.

    ``ExtractedCasilla.printed_value`` is widened to carry text and enum targets
    too, so a money box that came back as a raw string would otherwise reach an
    arithmetic comparison and fail there as a type error rather than as the
    parser defect it is.
    """
    value = amounts[casilla_id]
    assert isinstance(value, Decimal), (
        f"{specimen.label}: {casilla_id!r} extracted as {value!r}, which is not a money amount"
    )
    return value


def _extract(specimen: _AnnexSpecimen | _ReplacementSpecimen) -> tuple[frozenset[str], frozenset[str], Decimal]:
    """Run the production extraction path; return (covered, declared, coverage)."""
    profile, _revision = _declaracion_profile(specimen)
    covered = frozenset(_extracted_amounts(specimen))
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
    amounts = _extracted_amounts(specimen)

    devengada = _as_amount(specimen, amounts, "iva.anual.cuota-devengada-total")
    deducible = _as_amount(specimen, amounts, "iva.anual.cuota-deducible-total")
    resultado = _as_amount(specimen, amounts, "iva.anual.resultado-regimen-general")

    assert resultado == devengada - deducible, (
        f"{specimen.label}: printed box 65 {resultado!r} != box 47 {devengada!r} - "
        f"box 64 {deducible!r} = {devengada - deducible!r}"
    )


@pytest.mark.parametrize("specimen", _REPLACEMENT_SPECIMENS, ids=lambda s: s.label)
def test_replacement_specimen_declares_itself_generated(specimen: _ReplacementSpecimen) -> None:
    """The premise of the replacement-family assertions below.

    These specimens ARE generated, and the sidecar must say so. The check runs
    in this direction -- requiring ``synthetic_generated`` where it previously
    required ``real_corpus`` -- because a file silently re-stamped in either
    direction would leave every assertion below reading as something it is not.
    """
    sidecar = json.loads(specimen.sidecar.read_text(encoding="utf-8"))

    assert sidecar["provenance"] == _EXPECTED_REPLACEMENT_PROVENANCE, (
        f"{specimen.label}: provenance is {sidecar['provenance']!r}; this table holds "
        f"generated reproductions of withdrawn renders, and a specimen claiming "
        f"external provenance here would overstate what the coverage below proves"
    )
    assert sidecar["role"] == "parser_anchor", (
        f"{specimen.label}: role is {sidecar['role']!r}. These files exist to hold a layout "
        f"contract, not to carry internally-consistent figures, and a formula_verification "
        f"stamp would invite a reader to treat their probe amounts as calculation evidence"
    )


@pytest.mark.parametrize("specimen", _REPLACEMENT_SPECIMENS, ids=lambda s: s.label)
def test_profile_accepts_the_reproduced_declaration(specimen: _ReplacementSpecimen) -> None:
    """The profile reads the reproduced render without refusing it.

    ``_extract_profile_values`` applies the profile's own ``min_coverage`` and
    ``failure_semantics``, so a non-raising call is the whole claim. Modelo 390
    read one of ten targets on the render this reproduces until its labels were
    widened: AEAT issues the sede justificante in the language the filer chose,
    that render is in English, and the profile's Spanish-only patterns matched
    none of it. The reproduction is in English for exactly that reason.
    """
    profile, _revision = _declaracion_profile(specimen)
    covered, declared, coverage = _extract(specimen)

    assert coverage >= profile.min_coverage, (
        f"{specimen.label}: coverage {coverage} below the profile floor {profile.min_coverage}; "
        f"absent: {sorted(declared - covered)}"
    )


@pytest.mark.parametrize("specimen", _REPLACEMENT_SPECIMENS, ids=lambda s: s.label)
def test_reproduced_declaration_yields_exactly_the_expected_casillas(
    specimen: _ReplacementSpecimen,
) -> None:
    """The extracted set is exactly what the printed document carries.

    Asserted as a set rather than a count because a ratio hides substitution, and
    because every one of these profiles declares a coverage floor that a ratio
    alone cannot police: Modelo 390 and Modelo 111 both floor at zero, which no
    document can fall below.
    """
    covered, declared, _coverage = _extract(specimen)
    expected_covered = declared - specimen.absent

    assert covered == expected_covered, (
        f"{specimen.label}: extracted set drifted from the printed document.\n"
        f"  unexpectedly absent: {sorted(expected_covered - covered)}\n"
        f"  unexpectedly present: {sorted(covered - expected_covered)}"
    )


@pytest.mark.parametrize("specimen", _REPLACEMENT_SPECIMENS, ids=lambda s: s.label)
def test_count_valued_targets_stay_whole_and_non_negative(
    specimen: _ReplacementSpecimen,
) -> None:
    """A perceptor count is a headcount, and must not read as money.

    The surviving half of the withdrawn value check. Its other half compared
    every extracted amount against the constant the sanitiser declared, which a
    generated specimen has no equivalent of; the exact printed amounts are
    asserted by the per-modelo boundary tests instead. This part stays here
    because it is a claim about the FORM -- one of these columns counts people --
    and it fails if a target on that column starts reading a money box.
    """
    amounts = _extracted_amounts(specimen)
    checked = sorted(specimen.count_valued & set(amounts))

    if specimen.count_valued:
        assert checked, (
            f"{specimen.label}: declares count-valued targets {sorted(specimen.count_valued)} "
            f"but none were extracted, so this assertion would be vacuous"
        )

    for casilla_id in checked:
        value = amounts[casilla_id]
        assert isinstance(value, Decimal) and value == value.to_integral_value() and value >= 0, (
            f"{specimen.label}: count target {casilla_id!r} yielded {value!r}, which is not a non-negative whole count"
        )


def test_blank_box_does_not_fabricate_its_own_box_number() -> None:
    """A blank money box is reported absent, not read as its printed box number.

    A named-label amount match captures the last token on the line, and on an
    AEAT form a blank money box leaves its own printed box number as that token.
    The profile therefore anchors box 662 geometrically and looks to its right;
    without that guard it would report 662 euros the filing never declared.

    This is the only specimen in the tree that exercises the guard end to end,
    and it is now a reproduction rather than the render that first surfaced it.
    The property is preserved deliberately: the generator prints box 662 with no
    amount precisely so this arm stays reachable. It became reachable at all only
    once the label was widened to the English wording AEAT printed -- before that
    the target missed on the label and never reached the blank-box arm.
    """
    specimen = next(s for s in _REPLACEMENT_SPECIMENS if s.modelo == "390")
    profile, _revision = _declaracion_profile(specimen)
    target_id = "iva.anual.compensacion-generada-ejercicio-no-97"
    pages = extract_pages_text(specimen.pdf)
    full_text = "\n".join(pages)

    target = next(t for t in profile.target_casillas if str(t.casilla_id) == target_id)
    assert target.bbox_anchor is not None
    assert target.bbox_anchor.box_number_pattern == "^662$"
    assert re.search(r"\b662\b", full_text), (
        f"{specimen.label}: box number for {target_id!r} is not present in this render, so "
        "its absence below would prove nothing about the blank-box guard"
    )

    amounts = _extracted_amounts(specimen)

    assert target_id not in amounts, (
        f"{specimen.label}: {target_id!r} is blank on the printed render but extraction "
        f"yielded {amounts.get(target_id)!r}, fabricated from its own box number"
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
    coverages = {specimen.label: _extract(specimen)[2] for specimen in (*_SPECIMENS, *_REPLACEMENT_SPECIMENS)}

    assert any(coverage < Decimal(1) for coverage in coverages.values()), (
        "no bundled AEAT render exercises a blank optional box any more; the coverage "
        f"floors are no longer evidenced by these specimens: {coverages}"
    )
