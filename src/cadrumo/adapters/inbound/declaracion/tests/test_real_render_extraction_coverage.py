"""Real-AEAT-render extraction coverage for the ``declaracion_pdf`` profiles.

Every other extraction test in this package runs against the project's own
generated corpus. That corpus was authored to match the profiles, so it reports
the generator's conventions back rather than AEAT's, and it scores full coverage
at any threshold -- which is precisely how a Modelo 303 profile came to target
six casillas the printed form does not carry, refuse every real render, and stay
green for the entire time it was broken.

This module is the counterweight. It runs the production extraction path over
two families of externally-authored render, and nothing in this repository
authored the layout of either, so a profile that stops matching them has
genuinely drifted from the document rather than from a convention:

- The AEAT-published annex specimens: the official forms filled with AEAT's own
  worked-example figures and rendered by AEAT's publication toolchain. Because
  the figures are AEAT's, these support arithmetic checks against the form's own
  printed totals.
- The sanitised real-corpus specimens: genuine filed declarations retrieved from
  the sede, redacted for identity. Their layout, their printed labels and their
  blank boxes are AEAT's, but every monetary amount was overwritten by the
  sanitiser, which is length-preserving and so renders its replacement in more
  than one printed width. They are therefore layout and label evidence, not value
  evidence: no printed arithmetic holds across them, and the amounts the
  specimen's own sidecar accounts for are the external authority the extracted
  values are checked against instead.

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
- Every extracted amount on a sanitised render is one the specimen's sidecar
  accounts for. This is the substitution detector for the family that has no
  printed arithmetic: a pattern that drifted onto a neighbouring token, or that
  captured a box number merged into the amount, yields something the sidecar
  does not account for and fails here even though the casilla set and the
  coverage ratio both hold.
- A blank box on a real render does not fabricate a value from its own printed
  box number. Exercised on the one bundled real render that carries such a box.
- Across the whole suite at least one specimen is short of full coverage. This
  is the anti-vacuity guard: if every specimen scored 1.0 the assertions above
  would pass against a corpus that had stopped exercising the blank-box
  tolerance at all, which is the exact blind spot the generated corpus has.

Expected values are grounded in the printed documents, not computed from the
profile under test: the covered and absent sets were read off the AEAT renders,
and the accepted amounts are read from the specimen's sidecar rather than from
the profile, so this module fails if the profile drifts and cannot be satisfied
by adjusting the profile to match itself.

Modelo 100 is deliberately absent from the real-corpus specimen table. Its three
real renders print the box number in a smaller font overlapping the amount's own
x-range, the two merge into one token, and every one of its 21 targets therefore
yields a value that is neither the printed amount nor a parse failure -- while
coverage scores 1.0 and satisfies the profile's floor of 1. Listing it here with
weakened assertions would reproduce the green-suite-over-a-broken-profile
pathology this module exists to end, so it is excluded, and the exclusion is
asserted below rather than merely described here.

The merge happens in text extraction, not in the word path: these targets are
``named_label``, which reads page text. Separating the two fonts is necessary but
not sufficient, because the box number is printed after the value and
``named_label`` captures the last token on the line, so the separated form yields
the box number instead. Repairing it needs a second, estate-wide change to what
"the value on this line" means, which is why it is not done here.

See Also:
    :mod:`~tests.fixtures.manual_annexes.tests.test_manual_annex_provenance`
        The provenance gate over the same specimens.
    :func:`~adapters.inbound.declaracion.parse_declaracion`
        The full parser boundary. It cannot consume the annex specimens, which
        carry no NIF and are refused at the identity step by design, which is
        why coverage is exercised at the extraction layer for both families
        uniformly. The real-corpus specimens do carry a sanitised NIF and are
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

from .....core.resources import resources
from .....tests import FIXTURES_DIR
from ...pdf import parse_spanish_decimal
from .._parser import _extract_profile_values, _select_extraction_profile, extract_pages_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_ANNEX_DIR = FIXTURES_DIR / "manual_annexes"
_JUSTIFICANTE_DIR = FIXTURES_DIR / "justificantes"
_EXPECTED_PROVENANCE = "aeat_published_facsimile"
_EXPECTED_REAL_PROVENANCE = "real_corpus"


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
class _RealRenderSpecimen:
    """One sanitised real filed declaration and what it is expected to yield.

    Distinct from :class:`_AnnexSpecimen` in what it can prove. AEAT authored the
    layout, the printed labels and the blank boxes, but the sanitiser overwrote
    every monetary amount with one constant, so these specimens ground label and
    layout claims and cannot ground arithmetic ones.
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

    The sanitiser rewrites amounts only, so a count is exempt from the constant
    check below. Membership is read off the printed column header (``N.o de
    perceptores``, ``Numero total de percepciones``).
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


# Modelo 390: the only bundled real annual summary, and the only bundled render
# AEAT issued in English rather than Spanish. It prints form pages 1, 3, 4 and 6
# only -- page 3 opens on "5. Transactions made under the general system
# (continued)" with no preceding start -- so the four devengado rate rows and box
# 47 sit on a page this document does not contain. Box 662 is printed and blank.
_M390_REAL_ABSENT = frozenset(
    {
        "iva.anual.repercutido.super-reducido",
        "iva.anual.repercutido.reducido",
        "iva.anual.repercutido.general",
        "iva.anual.autorepercutido.intracomunitaria",
        "iva.anual.cuota-devengada-total",
        "iva.anual.compensacion-generada-ejercicio-no-97",
    },
)

# Modelo 111: this filer declared only rendimientos de actividades economicas, so
# boxes 07/08/09 carry values and every other perceptor section is printed blank.
# The fourth quarter is sparser still: its sidecar declares a single amount
# replacement, against six for each of the first three.
_M111_TARGETS = frozenset(f"{n:02d}" for n in range(1, 31)) - {"29"}
_M111_COVERED_QUARTERLY = frozenset({"07", "08", "09", "28", "30"})
_M111_COVERED_FOURTH = frozenset({"30"})

_REAL_SPECIMENS: tuple[_RealRenderSpecimen, ...] = (
    _RealRenderSpecimen("390", "2021-0A", 2021, "0A", _M390_REAL_ABSENT),
    _RealRenderSpecimen("111", "2024-1T", 2024, "1T", _M111_TARGETS - _M111_COVERED_QUARTERLY, frozenset({"07"})),
    _RealRenderSpecimen("111", "2024-2T", 2024, "2T", _M111_TARGETS - _M111_COVERED_QUARTERLY, frozenset({"07"})),
    _RealRenderSpecimen("111", "2024-3T", 2024, "3T", _M111_TARGETS - _M111_COVERED_QUARTERLY, frozenset({"07"})),
    _RealRenderSpecimen("111", "2024-4T", 2024, "4T", _M111_TARGETS - _M111_COVERED_FOURTH),
    _RealRenderSpecimen("190", "2024-0A", 2024, "0A", frozenset(), frozenset({"decl.total-percepciones"})),
)


def _declaracion_profile(specimen: _AnnexSpecimen | _RealRenderSpecimen):
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
    )
    revision = snapshot.revision
    return _select_extraction_profile(snapshot, extraction_profile_id=None), revision


def _extracted_amounts(specimen: _AnnexSpecimen | _RealRenderSpecimen) -> dict[str, object]:
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
    specimen: _AnnexSpecimen | _RealRenderSpecimen,
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


def _extract(specimen: _AnnexSpecimen | _RealRenderSpecimen) -> tuple[frozenset[str], frozenset[str], Decimal]:
    """Run the production extraction path; return (covered, declared, coverage)."""
    profile, _revision = _declaracion_profile(specimen)
    covered = frozenset(_extracted_amounts(specimen))
    declared = frozenset(str(t.casilla_id) for t in profile.target_casillas)
    coverage = Decimal(len(covered)) / Decimal(len(declared))
    return covered, declared, coverage


def _sanitiser_amount_constants(specimen: _RealRenderSpecimen) -> frozenset[Decimal]:
    """Every amount the specimen's own manifest accounts for.

    Read from the sidecar, which is authored by the redaction tooling and not by
    any extraction profile, so agreement with it is evidence the parser read the
    intended token rather than a neighbour.

    Two sources, because the sanitiser's own record is not a complete
    description of the document. ``replacements_applied`` names the nominal
    constant it wrote; the sanitiser is length-preserving, so writing that
    constant into fields of differing printed width renders more than one form.
    A sidecar that carries ``rendered_amount_forms`` declares the forms measured
    on the page, and both are accepted -- treating the nominal constant as the
    only legitimate value is how a genuine printed amount comes to look like a
    parser defect.

    Among the bundled specimens only Modelo 100 renders a form its
    ``replacements_applied`` does not name; every other one matches exactly, and
    for those this reduces to the single declared constant.
    """
    sidecar = json.loads(specimen.sidecar.read_text(encoding="utf-8"))
    declared = {str(entry["synthetic"]) for entry in sidecar["replacements_applied"]}
    rendered = {str(form["value"]) for form in sidecar.get("rendered_amount_forms", {}).get("forms", ())}
    parsed = {parse_spanish_decimal(token) for token in declared | rendered}
    constants = frozenset(value for value in parsed if isinstance(value, Decimal))
    assert constants, (
        f"{specimen.label}: sidecar accounts for no amount at all, so the extracted "
        f"amounts below would have no external authority to be checked against"
    )
    return constants


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


@pytest.mark.parametrize("specimen", _REAL_SPECIMENS, ids=lambda s: s.label)
def test_real_corpus_specimen_is_still_a_sanitised_aeat_filing(specimen: _RealRenderSpecimen) -> None:
    """The premise of the real-corpus assertions below.

    These specimens are the only bundled evidence of how AEAT lays out a filed
    declaration. If one were replaced by generated output the assertions below
    would keep passing while measuring this project's own conventions again.
    """
    sidecar = json.loads(specimen.sidecar.read_text(encoding="utf-8"))

    assert sidecar["provenance"] == _EXPECTED_REAL_PROVENANCE, (
        f"{specimen.label}: provenance is {sidecar['provenance']!r}, so the coverage "
        f"below would no longer be measuring a real AEAT render"
    )


@pytest.mark.parametrize("specimen", _REAL_SPECIMENS, ids=lambda s: s.label)
def test_profile_accepts_the_real_filed_declaration(specimen: _RealRenderSpecimen) -> None:
    """The profile reads a genuine filed declaration without refusing it.

    ``_extract_profile_values`` applies the profile's own ``min_coverage`` and
    ``failure_semantics``, so a non-raising call is the whole claim. Modelo 390
    read one of ten targets here until its labels were widened: AEAT issues the
    sede justificante in the language the filer chose, this render is in English,
    and the profile's Spanish-only patterns matched none of it.
    """
    profile, _revision = _declaracion_profile(specimen)
    covered, declared, coverage = _extract(specimen)

    assert coverage >= profile.min_coverage, (
        f"{specimen.label}: coverage {coverage} below the profile floor {profile.min_coverage}; "
        f"absent: {sorted(declared - covered)}"
    )


@pytest.mark.parametrize("specimen", _REAL_SPECIMENS, ids=lambda s: s.label)
def test_real_filed_declaration_yields_exactly_the_expected_casillas(
    specimen: _RealRenderSpecimen,
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


@pytest.mark.parametrize("specimen", _REAL_SPECIMENS, ids=lambda s: s.label)
def test_real_render_amounts_equal_the_constant_the_sanitiser_declares(
    specimen: _RealRenderSpecimen,
) -> None:
    """Every extracted amount is the value the redaction manifest says is there.

    The substitution detector for renders that carry no usable arithmetic. The
    casilla set and the coverage ratio both survive a pattern that captured the
    wrong token on the right line; this does not, because the sanitiser's
    constant is declared in the specimen's sidecar and is not something an
    extraction profile can influence.

    Count-valued targets are exempt and named per specimen: the sanitiser
    rewrites monetary amounts only, so a perceptor count is printed unchanged.
    """
    constants = _sanitiser_amount_constants(specimen)
    amounts = _extracted_amounts(specimen)

    drifted = {
        casilla_id: value
        for casilla_id, value in amounts.items()
        if casilla_id not in specimen.count_valued and value not in constants
    }

    assert not drifted, (
        f"{specimen.label}: extracted amounts are not the sanitiser constant "
        f"{sorted(str(c) for c in constants)}, so these targets read a token the "
        f"redaction manifest does not account for: {drifted}"
    )

    for casilla_id in sorted(specimen.count_valued & set(amounts)):
        value = amounts[casilla_id]
        assert isinstance(value, Decimal) and value == value.to_integral_value() and value >= 0, (
            f"{specimen.label}: count target {casilla_id!r} yielded {value!r}, which is not a non-negative whole count"
        )


def test_blank_box_on_a_real_render_does_not_fabricate_its_own_box_number() -> None:
    """A blank money box is reported absent, not read as its printed box number.

    ``named_label`` captures the last token on the line, and on a real AEAT form
    a blank money box leaves its own printed box number as that token. Modelo 390
    box 662 is printed and blank on the bundled real render, so without the
    guard the profile would report 662 euros of cuotas pendientes de compensacion
    that the filing never declared.

    This is the only bundled real render that exercises the guard end to end. It
    became reachable only once the label was widened to the English wording AEAT
    printed here: before that the target missed on the label and never reached
    the blank-box arm at all.
    """
    specimen = next(s for s in _REAL_SPECIMENS if s.modelo == "390")
    profile, _revision = _declaracion_profile(specimen)
    target_id = "iva.anual.compensacion-generada-ejercicio-no-97"
    pages = extract_pages_text(specimen.pdf)
    full_text = "\n".join(pages)

    target = next(t for t in profile.target_casillas if str(t.casilla_id) == target_id)
    assert target.label_pattern is not None
    assert re.search(target.label_pattern, full_text, re.IGNORECASE), (
        f"{specimen.label}: the label for {target_id!r} is not present in this render, so "
        f"its absence below would prove nothing about the blank-box guard"
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
    coverages = {specimen.label: _extract(specimen)[2] for specimen in (*_SPECIMENS, *_REAL_SPECIMENS)}

    assert any(coverage < Decimal(1) for coverage in coverages.values()), (
        "no bundled AEAT render exercises a blank optional box any more; the coverage "
        f"floors are no longer evidenced by these specimens: {coverages}"
    )


_M100_EXCLUDED_REVISIONS: tuple[tuple[str, int, str], ...] = (
    ("100", 2021, "0A"),
    ("100", 2022, "0A"),
    ("100", 2023, "0A"),
)
"""The Modelo 100 revisions that have a real render, and are excluded anyway."""


@pytest.mark.parametrize("modelo,filing_year,period", _M100_EXCLUDED_REVISIONS, ids=lambda v: str(v))
def test_modelo_100_is_excluded_because_its_values_are_not_the_printed_amounts(
    modelo: str,
    filing_year: int,
    period: str,
) -> None:
    """Modelo 100 is absent from the table above, and this is why.

    Its three real renders print the box number in a six-point font whose x-range
    overlaps the nine-point amount. Word assembly merges the two, so every target
    yields a number that is neither the printed amount nor a parse failure --
    casilla ``0545`` extracts as ``10010000.50405`` where the form prints
    ``1.001.000,00`` and the box number ``0545``. Coverage scores 1.0 and
    satisfies the profile's floor of 1 while not one value is the one on the page.

    This is not a pass, and it must not be readable as one. What is asserted is
    the *limitation*: the extracted values do not agree with what the sanitiser
    declares it wrote, so this profile cannot be enrolled above. An author who
    enrols Modelo 100 has to delete this test, and deleting it means reading why.

    It is a deliberately weak claim, and weak in a single direction. If the merge
    is repaired the values become the printed amounts, this test fails, and the
    correct response is to enrol Modelo 100 in ``_REAL_SPECIMENS`` and delete
    this. Failure here is the good outcome.

    Its sensitivity is measured rather than assumed, and it was re-measured after
    the sidecars were corrected. Driving a repaired extraction over each of the
    three specimens now makes all 19 recovered targets agree, so any of them
    failing to be merged would trip this. It was one of 19 beforehand: the other
    18 print ``1.001.000,00``, a form the manifests did not declare because the
    sanitiser is length-preserving and recorded only the eight-character variant
    it nominally wrote. A gate resting on one target has been widened to rest on
    all of them by fixing the description of the corpus rather than the gate.

    See the campaign record for the measurements: no ``bbox_anchored`` value
    offset can express the overlapping layout, and the merge happens in text
    extraction rather than in the word path the profile's strategy would reach.
    """
    specimen = _RealRenderSpecimen(modelo, f"{filing_year}-{period}", filing_year, period, frozenset())
    constants = _sanitiser_amount_constants(specimen)
    amounts = _extracted_amounts(specimen)

    assert amounts, (
        f"{specimen.label}: extraction returned nothing, so the exclusion below describes "
        f"a state this profile is no longer in"
    )

    agreeing = {c: v for c, v in amounts.items() if v in constants}

    assert not agreeing, (
        f"{specimen.label}: {len(agreeing)} target(s) now extract the amount the sanitiser "
        f"declares it wrote ({agreeing}). The box-number merge this exclusion documents may "
        f"be fixed -- re-measure, and if so enrol Modelo 100 in the real-render table above "
        f"and delete this test rather than adjusting it"
    )
