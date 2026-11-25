"""Rate boxes whose design format cell is only a note pointer export as that note states.

Modelo 490's Territorio común [24] prints "Ver nota 2" where its siblings print
"3 ent + 2 dec"; Nota 2 reads "Tres enteros y dos decimales" and fills 100,00 as
100000. Read as an unscaled integer the slot wrote the rate a hundred times too
small (00100), so every supported year that prints the box is held to the note's
bytes, and [24] shows its stored percentage on the form.

Modelo 200's Tipo de gravamen [00558] prints "Nota 1", a four-digit code: a single
rate fills its two digits and 00 (25 % as 2500), a double rate its two rates
(18/19 % as 1819). The edition's formula stores that code in the casilla, so the
slot writes the stored value unscaled; scaling it again wrote 250000 into four
positions and refused every export of the edition.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from ....domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition
from ....domain.calculations.registry.tests.published_authority import (
    published_revision,
    published_snapshot,
    published_supported_filing_years,
)
from ..edit_value_grammar import ModeloEditRatioUnit, ratio_unit
from ..value_presentation import format_casilla_value
from ..work_form_field_vocabulary import (
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormOrigin,
    ModeloFormText,
    ModeloFormTextDisclosure,
)
from ..work_form_models import ModeloFormField
from ..work_form_wording import field_value_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EN = OutputLanguage.EN
_M490_BOX = "terr-comun-24"
_M490_PERIOD = "4T"
_M200_BOX = "DP200014:00558"
_M200_PERIOD = "0A"


def _snapshots(modelo: str, period: str, casilla_id: str) -> tuple[tuple[int, RegistrySnapshot], ...]:
    support = published_supported_filing_years()
    assert support is not None
    found: list[tuple[int, RegistrySnapshot]] = []
    for year in sorted(support.years):
        try:
            snapshot = published_snapshot(modelo, filing_year=year, period=period)
        except FilingYearOutsideSupportEnvelopeError:
            continue
        if any(item.id == casilla_id for item in snapshot.revision.casillas):
            found.append((year, snapshot))
    return tuple(found)


def _export_field(modelo: str, snapshot: RegistrySnapshot, casilla_id: str) -> ExportFieldDefinition:
    revision = published_revision(modelo, str(snapshot.revision.id))
    (field,) = (
        field
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.casilla_id == casilla_id
    )
    return field


def _exporting(
    modelo: str, found: tuple[tuple[int, RegistrySnapshot], ...]
) -> tuple[tuple[int, RegistrySnapshot], ...]:
    """Keep the years whose edition publishes an export file at all."""
    return tuple(
        (year, snapshot)
        for year, snapshot in found
        if published_revision(modelo, str(snapshot.revision.id)).export_layouts
    )


_M490 = _snapshots("490", _M490_PERIOD, _M490_BOX)
_M200 = _exporting("200", _snapshots("200", _M200_PERIOD, _M200_BOX))


def test_some_supported_year_prints_each_rate_box() -> None:
    assert _M490
    assert _M200


@pytest.mark.parametrize(("year", "snapshot"), _M490, ids=[str(year) for year, _ in _M490])
def test_m490_territorio_comun_exports_three_integers_and_two_decimals(year: int, snapshot: RegistrySnapshot) -> None:
    field = _export_field("490", snapshot, _M490_BOX)

    assert (field.offset, field.length, field.decimals) == (970, 5, 2), year
    assert render_fixed_width_export_field(field, Decimal("100")) == "10000"
    assert render_fixed_width_export_field(field, Decimal("62.5")) == "06250"


@pytest.mark.parametrize(("year", "snapshot"), _M490, ids=[str(year) for year, _ in _M490])
def test_m490_territorio_comun_shows_the_stored_percentage(year: int, snapshot: RegistrySnapshot) -> None:
    (casilla,) = (item for item in snapshot.revision.casillas if item.id == _M490_BOX)
    assert casilla.data_type == "ratio", year
    assert casilla.constraints is not None, year
    assert ratio_unit("ratio", casilla.constraints.max_value) is ModeloEditRatioUnit.PERCENT

    field = ModeloFormField.model_validate(
        {
            "address": ModeloFormCasillaAddressV1(casilla_id=validated_casilla_id(_M490_BOX)),
            "box": "24",
            "label": ModeloFormText(text="Territorio común", disclosure=ModeloFormTextDisclosure.LOCALIZED),
            "help": None,
            "data_type": "ratio",
            "value": Decimal("100"),
            "origin": ModeloFormOrigin.CALCULATED,
            "editability": ModeloFormEditability.NOT_WRITABLE,
            "not_writable_reason": "computed",
            "required": True,
            "constraints": casilla.constraints,
        }
    )
    shown = field_value_text(field, _EN)

    assert shown == format_casilla_value(
        Decimal("100"), data_type="ratio", language=_EN, ratio_unit=ModeloEditRatioUnit.PERCENT
    )
    assert shown is not None and "100" in shown and "%" in shown


@pytest.mark.parametrize(("year", "snapshot"), _M200, ids=[str(year) for year, _ in _M200])
def test_m200_tipo_de_gravamen_exports_the_stored_nota_1_code(year: int, snapshot: RegistrySnapshot) -> None:
    field = _export_field("200", snapshot, _M200_BOX)

    assert field.length == 4, year
    if field.decimals == 2:
        # Editions whose design prints "2 enteros y 2 decimales" store the percentage itself.
        assert render_fixed_width_export_field(field, Decimal("25")) == "2500"
        assert render_fixed_width_export_field(field, Decimal("15")) == "1500"
        return
    # Editions whose design prints the Nota 1 code store that code, already scaled by the formula.
    assert field.decimals is None or field.decimals == 0, year
    assert render_fixed_width_export_field(field, Decimal("2500")) == "2500"
    assert render_fixed_width_export_field(field, Decimal("1500")) == "1500"
    assert render_fixed_width_export_field(field, Decimal("2122")) == "2122"
