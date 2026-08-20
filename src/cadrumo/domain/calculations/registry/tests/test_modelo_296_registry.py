"""Tests for the committed Modelo 296 registry foundation."""

from __future__ import annotations

import pytest

from .....core import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SOURCE_CASILLA: CasillaId = validated_casilla_id("04", surface="_SOURCE_CASILLA")
_TARGET_CASILLA: CasillaId = validated_casilla_id("05", surface="_TARGET_CASILLA")


def _load_modelo_296():
    return _committed_modelo("296")


def test_modelo_296_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_296()
    assert modelo.id == "296"
    assert modelo.revisions, "296 must declare at least one revision"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_296_declares_no_formula() -> None:
    """Modelo 296 computes none of its four printed boxes.

    **Correcting what this module asserted.** It required a ``modelo-296-total``
    owned by a construct and claimed "casilla 05 equals casilla 04 per the AEAT
    form's own printed total row". ANEXO II of Orden EHA/3290/2008 prints FOUR
    boxes and no box 05: 01 perceptores, 02 base, 03 retenciones, and 04
    retenciones INGRESADAS. Box 04 is a filtered subset of 03 -- only perceptores
    whose CLAVE is 3 to 25, or whose CLAVE is 1 or 2 with PAGO = 1 -- so copying
    03 into it asserted an identity the diseño explicitly denies, and the export
    wrote that asserted figure into the ingresadas field.

    The formula was deleted and the family declared inapplicable with citations,
    because each box is an aggregation the declarante performs over its own tipo-2
    perceptor records, which this registry does not hold.
    """
    modelo, _ = _load_modelo_296()
    revision = modelo.revisions["2024-y-siguientes"]

    assert revision.formulas == ()
    assert not any(construct.formulas for construct in revision.constructs)
    assert revision.family_dispositions is not None


def test_modelo_296_casilla_set_is_the_printed_box_set() -> None:
    """02, 03 and 04 are declared; 01 is produced by the export declarante header."""
    modelo, _ = _load_modelo_296()
    revision = modelo.revisions["2024-y-siguientes"]

    assert tuple(str(casilla.id) for casilla in revision.casillas) == ("02", "03", "04")
    assert all(casilla.input_kind.value == "manual" for casilla in revision.casillas)
