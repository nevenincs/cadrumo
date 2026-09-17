"""Presentador-NIF extraction across AEAT's Spanish and English receipt renders.

AEAT serves the SAME receipt template in Spanish or English depending on the
sede UI language the filer used. The printed tax id is identical either way;
only the label beside it changes. A filer who downloaded their receipt from an
English-language sede session must be able to reconcile it exactly like anyone
else, so the parser anchors on both renderings.

The anchor fixture is the Modelo 390 2021-0A receipt. It WAS a genuine
sanitised AEAT filing, and that is where every property below came from: it
rendered in English, and it laid the tax id out ABOVE its label rather than
after it. Before it was bundled the parser refused it outright with
``tax_id_unresolved``, because both of its patterns hardcoded the Spanish
``NIF Presentador`` literal, and its detector looked only for
``Modelo``/``Ejercicio``. Two independent single-render assumptions on one
document.

That render has been WITHDRAWN. It carried name-shaped strings the redaction
pipeline never wrote, and it could not stay in the repository. What stands in
its place is a generated reproduction that reproduces those properties
deliberately -- the English markers, the value-above-label order, the English
header stamp, and a NIF-shaped expediente decoy printed above its own label in
exactly the position an unanchored value pattern would grab.

Read the consequence honestly. This module still gates the regression it was
built for, because that regression was written down. It is no longer evidence
that AEAT produces such a render, because the artefact that was that evidence is
gone; if AEAT's English receipt carries some further property nobody recorded,
nothing here will catch it.

These tests still ground themselves in the fixture rather than in assumptions:
the expected tax id is read back from the sidecar's declared replacements, and
the English render is asserted to actually BE English, so the coverage cannot
quietly become vacuous if the fixture is regenerated in Spanish.

See Also:
    :func:`~adapters.inbound.declaracion.parser.parse_declaracion`
        Public parser boundary exercised end to end here.
    :class:`~adapters.inbound.declaracion.InboundDeclaracionObservation`
        Observation aggregate whose ``tax_id`` these tests assert.
"""

from __future__ import annotations

from pathlib import Path

import pdfplumber
import pytest

from .....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from .....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from .....tests.inventory import FIXTURES_DIR
from .._detect import detect_template_revision
from .._parsers.pdfplumber_backend import extract_pages_text
from ..errors import DeclaracionParseError
from ..parser import _extract_tax_id, parse_declaracion

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter, pytest.mark.usefixtures("operation")]

#: Generated reproduction of the withdrawn real AEAT M390 English receipt.
_ENGLISH_RENDER = ("390", "2021-0A", 2021, "0A")
#: Spanish-render M390 receipts covering the same modelo and period.
_SPANISH_RENDERS = (("390", "2022-0A", 2022, "0A"), ("390", "2023-0A", 2023, "0A"))

#: Phrases that appear only on AEAT's English-language render of the receipt.
_ENGLISH_MARKERS = ("Tax identification number", "Surname(s)", "INFORMATION ON FILING THE TAX RETURN")

#: Shape of a Spanish tax id, used only to pick the tax-id replacement out of
#: the sidecar's declared substitutions.
_TAX_ID_LENGTH = 9


def _fixture(modelo: str, stem: str) -> Path:
    return FIXTURES_DIR / "justificantes" / modelo / f"{stem}.pdf"


def _sidecar(modelo: str, stem: str) -> dict[str, object]:
    return STR_KEYED_MAPPING_ADAPTER.validate_json(
        _fixture(modelo, stem).with_suffix(".json").read_text(encoding="utf-8"),
    )


def declared_tax_id(modelo: str, stem: str) -> str:
    """Return the tax id the sanitiser declares it wrote into this fixture.

    Deriving the expectation from the sidecar keeps it grounded in the
    fixture's own provenance record instead of a value copied out of a parser
    run, which would assert only that the parser agrees with itself.
    """
    replacements = _sidecar(modelo, stem)["replacements_applied"]
    assert isinstance(replacements, list)
    candidates = {
        synthetic
        for entry in replacements
        if isinstance(entry, dict)
        and isinstance(synthetic := entry.get("synthetic"), str)
        and len(synthetic) == _TAX_ID_LENGTH
        and synthetic[0].isalpha()
        and synthetic[1:8].isdigit()
    }
    assert len(candidates) == 1, f"expected exactly one tax-id replacement in the sidecar, got {candidates}"
    return candidates.pop()


def _pdf_text(modelo: str, stem: str) -> str:
    with pdfplumber.open(_fixture(modelo, stem)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def test_anchor_fixture_still_renders_in_english() -> None:
    """The premise of this module: the anchor is an ENGLISH receipt.

    Guards the rest of the coverage. Every test below distinguishes the English
    render from the Spanish one, so a fixture regenerated in Spanish would leave
    them all passing while testing nothing — this fails loudly instead.

    The provenance assertion reads ``synthetic_generated`` because the real
    render was withdrawn and this is its reproduction. That is a weaker premise
    than the one it replaces and it is asserted anyway, so a future
    re-stamping cannot quietly reinstate a claim of external provenance this
    file cannot support.
    """
    modelo, stem, _year, _period = _ENGLISH_RENDER
    sidecar = _sidecar(modelo, stem)

    assert sidecar["provenance"] == "synthetic_generated"
    assert sidecar["role"] == "parser_anchor"
    text = _pdf_text(modelo, stem)
    assert all(marker in text for marker in _ENGLISH_MARKERS), (
        "anchor fixture no longer renders in English; the bilingual coverage below would be vacuous"
    )


def _parser_text(modelo: str, stem: str) -> str:
    """The page text exactly as the parser boundary joins it before reading the tax id."""
    return "\n".join(extract_pages_text(_fixture(modelo, stem)))


def test_extracts_the_tax_id_from_the_english_render_receipt() -> None:
    """The English-render receipt yields its tax id instead of refusing.

    This is the regression gate. Tax-id extraction previously raised
    ``DeclaracionParseError`` (``tax_id_unresolved``) on this render, which made
    the receipt unreconcilable for any filer who used the English-language sede.
    The anchor render is a filing year below the support envelope, so the gate
    runs on the text the parser boundary reads rather than through filing
    selection, which refuses the year.
    """
    modelo, stem, _year, _period = _ENGLISH_RENDER

    assert _extract_tax_id(_parser_text(modelo, stem)) == declared_tax_id(modelo, stem)


def test_english_render_below_the_supported_floor_is_refused() -> None:
    """The anchor render's filing year is outside the support envelope, so parsing refuses it."""
    modelo, stem, year, period = _ENGLISH_RENDER
    support = published_supported_filing_years()
    assert support is not None and not support.admits_filing_year(year), (
        "the English anchor render is now inside the support envelope; parse it end to end instead"
    )

    with pytest.raises(DeclaracionParseError):
        parse_declaracion(
            _fixture(modelo, stem),
            modelo_override=modelo,
            año_override=year,
            period_override=period,
        )


@pytest.mark.parametrize("tax_id", ("12345678A", "X1234567A", "B12345678"))
def test_extract_tax_id_refuses_shape_only_identifiers_with_invalid_checksums(tax_id: str) -> None:
    with pytest.raises(DeclaracionParseError):
        _extract_tax_id(f"NIF Presentador: {tax_id}")


@pytest.mark.parametrize(("modelo", "stem", "year", "period"), _SPANISH_RENDERS)
def test_spanish_render_receipts_keep_parsing(modelo: str, stem: str, year: int, period: str) -> None:
    """Accepting the English label must not disturb the Spanish render."""
    observation = parse_declaracion(
        _fixture(modelo, stem),
        modelo_override=modelo,
        año_override=year,
        period_override=period,
    )

    assert observation.tax_id == declared_tax_id(modelo, stem)
    assert observation.modelo == modelo


def test_both_renders_yield_the_same_tax_id() -> None:
    """The render language changes the label, never the identity it labels."""
    english_modelo, english_stem, _english_year, _english_period = _ENGLISH_RENDER
    spanish_modelo, spanish_stem, spanish_year, spanish_period = _SPANISH_RENDERS[0]

    english_tax_id = _extract_tax_id(_parser_text(english_modelo, english_stem))
    spanish = parse_declaracion(
        _fixture(spanish_modelo, spanish_stem),
        modelo_override=spanish_modelo,
        año_override=spanish_year,
        period_override=spanish_period,
    )

    assert english_tax_id == spanish.tax_id


@pytest.mark.parametrize(
    ("label", "text"),
    [
        ("spanish_after_label", "NIF Presentador: 12345678Z"),
        ("spanish_bare_label", "NIF: 12345678Z"),
        ("spanish_before_label", "12345678Z\nNIF Presentador:"),
        ("english_after_label", "Tax identification number(NIF)of filer: 12345678Z"),
        ("english_after_label_spaced", "Tax identification number (NIF) of filer: 12345678Z"),
        ("english_before_label", "Filer\n12345678Z\nTax identification number(NIF)of filer:"),
    ],
)
def test_extracts_across_render_and_layout_combinations(label: str, text: str) -> None:
    """Either render, either value/label order, one extracted identity.

    AEAT varies the label language and — through pdfplumber's left-right
    traversal of column-split layouts — whether the value precedes or follows
    it. All four combinations describe the same printed field.
    """
    assert _extract_tax_id(text) == "12345678Z", label


def test_detects_the_header_stamp_on_the_english_render() -> None:
    """The form code and tax year are read from the English header stamp.

    The header carries "FORM 390" / "Financial year 2021" where the Spanish
    render carries "Modelo 390" / "Ejercicio 2021". Without both alternatives
    the receipt could not be identified at all, so it failed detection before
    tax-id extraction was ever reached — a second, independent single-render
    assumption on the same document.
    """
    modelo, stem, year, _period = _ENGLISH_RENDER

    template = detect_template_revision(_fixture(modelo, stem))

    assert template is not None, "the English header stamp must identify the receipt"
    assert template.modelo == modelo
    assert template.año == year
    assert template.detected_from == "header"


def test_english_render_without_overrides_is_refused_on_its_detected_year() -> None:
    """Detection carries the receipt, and the year it detects is then held to the envelope.

    M390 receipts print no period stamp in either render (the modelo is
    annual-only), so ``period_override`` remains the documented mechanism for
    that field. Everything else is read from the header stamp (asserted by
    :func:`test_detects_the_header_stamp_on_the_english_render`); the detected
    year lies below the support envelope, so the unaided parse must refuse
    rather than resolve a revision.
    """
    modelo, stem, _year, period = _ENGLISH_RENDER

    with pytest.raises(DeclaracionParseError):
        parse_declaracion(_fixture(modelo, stem), period_override=period)


@pytest.mark.parametrize(
    ("label", "text"),
    [
        # The expediente/referencia number ends in a NIF-shaped tail
        # ("202139013520268G" -> "13520268G") and is printed on the same
        # receipt, so an unanchored value pattern would silently mistake it
        # for the filer's identity.
        ("expediente_number_before_english_label", "202139013520268G\nTax identification number(NIF)of filer:"),
        ("expediente_number_before_spanish_label", "202139013520268G\nNIF Presentador:"),
        ("too_few_digits", "Y000001S\nNIF Presentador:"),
        ("not_a_tax_id", "ABC123\nNIF Presentador:"),
        ("label_without_any_value", "Tax identification number(NIF)of filer:"),
    ],
)
def test_refuses_values_that_are_not_a_tax_id(label: str, text: str) -> None:
    """Accepting a second label rendering must not widen the accepted value.

    An over-permissive tax-id pattern is worse than the refusal it replaces:
    the parsed identity flows into a filing-grade reconciliation path, so a
    wrong-but-plausible id is a silent data-integrity failure.
    """
    with pytest.raises(DeclaracionParseError):
        _extract_tax_id(text)
