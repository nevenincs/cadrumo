"""A help entry that only says which box of which modelo and year a casilla is counts as absent.

The sentence is recognised by rendering the catalogue's own locator sentences
for the casilla's modelo, so the recognition follows the catalogue's wording:
rewording a sentence in the catalogue rewords what is recognised, and nothing
else in the code has to change. The box and the year are taken as written,
as figures, because inherited help names the year of the edition that stated
it and some help names a box by its record positions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core.external_constants import OutputLanguage
from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.modelo_localization import resolve_modelo_localization
from ....tests.locales_root_fixture import locales_root_scope
from ..work_form import build_modelo_work_form
from ..work_form_localization import names_only_its_box, render_box_locator_patterns
from ..work_form_models import ModeloFormCasillaAddressV1
from ..work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "151"
_YEAR = 2025
_PERIOD = "0A"


def _names_only_its_box_of(text: str, modelo: str = _MODELO) -> bool:
    return names_only_its_box(text, render_box_locator_patterns(modelo))


@pytest.mark.parametrize(
    "text",
    [
        "Casilla 03 del modelo 151, ejercicio 2025.",
        "Casilla 121-122 del modelo 151, ejercicio 2004-2015.",
        "Casilla 692-708 del modelo 151, ejercicio 2023 y siguientes.",
        "Box 01 of modelo 151, tax year 2025.",
        "Box 94-94 of Modelo 151, tax years 2004-2015.",
        "Box 692-708 of Modelo 151, tax years 2023 onwards.",
        "Casella 03 del model 151, exercici 2025.",
        "Casella 94-94 del model 151, exercicis 2004-2015.",
        "Casella 692-708 del model 151, exercicis 2023 i posteriors.",
        "A Modelo 151 nyomtatvány 03. rovata, 2025. adóév.",
        "A Modelo 151 nyomtatvány 94-94. mezője, 2004-2015. adóév.",
        "A Modelo 151 nyomtatvány 692-708. mezője, 2023. és az azt követő adóévek.",
        "  Box 01 of modelo 151, tax year 2025.\n",
    ],
)
def test_a_sentence_that_only_locates_the_box_is_recognised_in_every_language(text: str) -> None:
    assert _names_only_its_box_of(text)


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("Box 01 of modelo 303, tax year 2025.", "it locates a box of another modelo"),
        ("Box 01 of modelo 151, tax year 2025. Gross amount paid.", "it says more than where the box is"),
        ("Casilla ejercicio del modelo 151, ejercicio 2015.", "it names the box with a word, not a figure"),
        ("Box 01 of modelo 151.", "it is not one of the catalogue's sentences"),
        ("Gross amount paid in the tax year.", "it is an explanation"),
    ],
)
def test_a_sentence_that_says_anything_else_is_kept(text: str, why: str) -> None:
    assert not _names_only_its_box_of(text), why


def test_a_reworded_catalogue_sentence_is_followed_rather_than_missed(tmp_path: Path) -> None:
    """The recognition reads the catalogue, so a reworded locator is still absent help and the old words are not."""
    (tmp_path / "es.yml").write_text(
        "application:\n"
        "  modelo:\n"
        "    work_form:\n"
        "      box_locator_help:\n"
        "        one_year: Recuadro {box} del modelo {modelo} para el año {years}.\n"
        "        year_span: Recuadro {box} del modelo {modelo} para los años {years}.\n"
        "        onwards: Recuadro {box} del modelo {modelo} desde el año {years}.\n",
        encoding="utf-8",
    )

    with locales_root_scope(tmp_path):
        assert _names_only_its_box_of("Recuadro 03 del modelo 151 para el año 2025.")
        assert _names_only_its_box_of("Recuadro 94-94 del modelo 151 para los años 2004-2015.")
        assert _names_only_its_box_of("Recuadro 692-708 del modelo 151 desde el año 2023.")
        assert not _names_only_its_box_of("Casilla 03 del modelo 151, ejercicio 2025.")
        # The languages the fixture leaves alone still read the packaged catalogue.
        assert _names_only_its_box_of("Box 01 of modelo 151, tax year 2025.")


_LOCATED = "impatriado.anexo-transmision-iic.tipo-renta"
_EXPLAINED = "impatriado.anexo-transmision-iic.nif-entidad"
_STATED: dict[OutputLanguage, tuple[str, str]] = {
    OutputLanguage.ES: (
        "Casilla 01 del modelo 151, ejercicio 2025.",
        "Dato del anexo de transmisión de acciones o participaciones de IIC del modelo 151.",
    ),
    OutputLanguage.EN: (
        "Box 01 of modelo 151, tax year 2025.",
        "Field of modelo 151's annex for transfers of shares or units in collective investment undertakings.",
    ),
    OutputLanguage.CA: (
        "Casella 01 del model 151, exercici 2025.",
        "Dada de l'annex de transmissió d'accions o participacions d'IIC del model 151.",
    ),
    OutputLanguage.HU: (
        "A Modelo 151 nyomtatvány 01. rovata, 2025. adóév.",
        "A Modelo 151 nyomtatvány kollektív befektetési jegyek átruházásáról szóló mellékletének adata.",
    ),
}
"""What modelo 151's catalogue states as help for one box it only locates and one it explains."""


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_a_published_locator_help_reaches_the_form_as_no_help(
    operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    snapshot = operation.snapshot(_MODELO, filing_year=_YEAR, period=_PERIOD)
    casillas = {str(casilla.id): casilla for casilla in snapshot.revision.casillas}
    located, explained = _STATED[language]
    for casilla_id, stated in ((_LOCATED, located), (_EXPLAINED, explained)):
        keys = tuple(f"{key.removesuffix('.label')}.help" for key in casillas[casilla_id].localization_keys)
        assert resolve_modelo_localization(keys, locale=language.value) == stated
    review = ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000151",
        modelo=_MODELO,
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _PERIOD),
        registry_revision_id=snapshot.revision.id,
        work_unit_id="b" * 64,
        calculation_revision_id=None,
        lifecycle_state=None,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation),
        findings=(),
        blockers=(),
    )
    form = build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=None,
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=None,
        overridden_binding_ids=None,
        language=language,
    )
    helps = {
        str(field.address.casilla_id): field.help
        for field in form.fields()
        if isinstance(field.address, ModeloFormCasillaAddressV1)
    }

    assert helps[_LOCATED] is None
    assert helps[_EXPLAINED] == explained
