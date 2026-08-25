"""A published dictionary row AEAT itself got wrong is corrected on the layout.

AEAT's Modelo 100 dictionary declares ``PH18`` as an element while every AEAT
Modelo 100 XSD declares it an attribute on ``Hijos``. The dictionaries are
official evidence bytes and are never edited -- their value is being exactly what
AEAT published, defects included -- so the correction is declared registry data
instead.

The correction is applied where the dictionary is READ, which is the property
these tests pin hardest: the renderer and :func:`parse_export_payload` resolve
their rows from the same call, so a correction reaching only one of them would
make an exported artefact verify as drift against itself.

It is one declared exception, not a precedence rule. PH18 is the sole
element-versus-attribute disagreement in 12,210 dictionary rows across all six
revisions, so a rule granting the XSD blanket authority over the dictionary would
generalise from a single instance — and, because AEAT republishes these schemas
mid-year, would go on adopting whatever a later publication changes without
anyone reviewing it.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.schema import ExportLayoutDefinition
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_parse import xml_dictionary_entries
from ..export_parse import XmlDictionaryEntry
from ..schema_exports import XmlDictionaryPathOverride
from ._modelo_100_registry_support import _loaded_registry, _source_root

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PH18_ATTRIBUTE_PATH = "/DatosIdentificativos/Hijos/@PH18"


def _modelo_100_layout(filing_year: int) -> ExportLayoutDefinition:
    modelos_by_id, _catalogues = _loaded_registry()
    return modelos_by_id["100"].revisions[str(filing_year)].export_layouts[0]


def _modelo_100_entries(filing_year: int) -> tuple[XmlDictionaryEntry, ...]:
    _modelos_by_id, catalogues = _loaded_registry()
    return xml_dictionary_entries(
        _modelo_100_layout(filing_year),
        source_root=_source_root(),
        sources=catalogues.sources,
    )


def _ph18(filing_year: int) -> XmlDictionaryEntry:
    entry = next((row for row in _modelo_100_entries(filing_year) if row.field_id == "PH18"), None)
    assert entry is not None, f"{filing_year}: the bundled dictionary no longer declares PH18"
    return entry


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_ph18_resolves_to_the_attribute_form_the_xsd_declares(filing_year: int) -> None:
    """Every revision addresses PH18 as an attribute, as AEAT's schema declares."""
    entry = _ph18(filing_year)

    assert entry.path == _PH18_ATTRIBUTE_PATH
    assert entry.path.rsplit("/", 1)[-1].startswith("@"), "the writer keys attribute rendering off the @ leaf"


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_the_published_dictionary_still_says_element(filing_year: int) -> None:
    """The override is still needed, and the corpus is still untouched.

    Two failures share this assertion and both matter. If AEAT corrects the row in
    a future dictionary, this fails and the override should be dropped rather than
    left masking agreement. If someone edits the bundled ``.properties`` to fix it
    there, this also fails -- which is the outcome we want, because that would
    destroy the provenance the corpus exists to carry.
    """
    _modelos_by_id, catalogues = _loaded_registry()
    layout = _modelo_100_layout(filing_year)
    source = catalogues.sources[str(layout.dictionary_source_ref)]
    published = (_source_root() / source.corpus_path).read_text(encoding="latin-1")

    assert "PH18=[/DatosIdentificativos/Hijos/PH18]" in published


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_the_value_rendering_was_never_the_defect(filing_year: int) -> None:
    """Placement was wrong; the declared type was always right.

    ``S_N`` is the one dictionary type the writer renders as ``SI``/``NO``, which
    is what AEAT's ``tipo_SINO_Exclusivo`` accepts. Pinning it here keeps a later
    reader from concluding the override changed how the value is written.
    """
    assert _ph18(filing_year).data_type == "S_N"


def test_no_other_row_is_overridden() -> None:
    """One declared exception, not a reconciliation layer.

    A second override appearing without its own evidence is the drift this design
    is meant to prevent, so the count is pinned rather than the mere presence of
    PH18.
    """
    for filing_year in range(2020, 2026):
        layout = _modelo_100_layout(filing_year)

        assert [override.field_id for override in layout.dictionary_path_overrides] == ["PH18"], filing_year


def test_every_override_records_why_it_overrules_aeat() -> None:
    """The claim that AEAT's own dictionary is wrong has to be auditable.

    "It disagrees with the XSD" is not sufficient grounds on its own — AEAT
    republishes these schemas mid-year, so which of two AEAT artefacts to believe
    is a reviewed judgement about a specific row. The evidence therefore has to
    travel with the override rather than live in a commit message.
    """
    for filing_year in range(2020, 2026):
        for override in _modelo_100_layout(filing_year).dictionary_path_overrides:
            assert len(override.reason) > 80, (filing_year, override.field_id)
            assert "XSD" in override.reason


def test_an_override_naming_an_absent_field_is_refused() -> None:
    """A correction that applies to nothing must not read as a correction.

    Without this, a typo leaves the defect shipping while the registry carries a
    declaration that looks like the fix.
    """
    _modelos_by_id, catalogues = _loaded_registry()
    typo = _modelo_100_layout(2024).model_copy(
        update={
            "dictionary_path_overrides": (
                XmlDictionaryPathOverride(
                    field_id="PH18_TYPO",
                    path="/DatosIdentificativos/Hijos/@PH18",
                    reason="deliberate typo, exercising the refusal that keeps a dead override from looking live",
                ),
            ),
        },
    )

    with pytest.raises(RegistryValidationError, match="PH18_TYPO"):
        xml_dictionary_entries(typo, source_root=_source_root(), sources=catalogues.sources)


def test_a_fixed_width_layout_may_not_declare_an_override() -> None:
    """The mechanism is scoped to the format that reads a dictionary at all.

    The refusal is raised by a model validator, so pydantic re-wraps it; the
    registry message is what carries the reason and is matched here.
    """
    modelos_by_id, _catalogues = _loaded_registry()
    layout = next(layout for revision in modelos_by_id["303"].revisions.values() for layout in revision.export_layouts)

    with pytest.raises(ValidationError, match="reads no dictionary"):
        ExportLayoutDefinition(
            **layout.model_dump()
            | {
                "dictionary_path_overrides": (
                    XmlDictionaryPathOverride(
                        field_id="ANY",
                        path="/x/@y",
                        reason="a fixed-width layout has no dictionary, so an override here could never apply",
                    ),
                ),
            },
        )
