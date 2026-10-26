"""Tests for the committed Modelo 296 registry foundation."""

from __future__ import annotations

import pytest

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.domain.calculations.registry.relations import relation_prefill_bindings_for_period
from cadrumo.domain.calculations.registry.temporal import select_revision_for_year

from ..conformance.registry_schema_support import committed_modelo as _committed_modelo
from .profile_schema_support import committed_registry_validator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_SOURCE_CASILLA: CasillaId = validated_casilla_id("04", surface="_SOURCE_CASILLA")
_TARGET_CASILLA: CasillaId = validated_casilla_id("05", surface="_TARGET_CASILLA")


def _load_modelo_296():
    return _committed_modelo("296")


def test_modelo_296_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_296()
    assert modelo.id == "296"
    assert modelo.revisions, "296 must declare at least one revision"
    committed_registry_validator(catalogues).validate_modelo(modelo)


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
    revision = modelo.revisions["2024-2025"]

    assert revision.formulas == ()
    assert not any(construct.formulas for construct in revision.constructs)
    assert revision.family_dispositions is not None


def test_modelo_296_casilla_set_is_the_printed_box_set() -> None:
    """02, 03 and 04 are declared; 01 is produced by the export declarante header.

    The input kinds are not uniform and the split is the point. This revision
    declares two ``periodic_to_annual_summary`` relations onto ``relation_prefill``
    slots, and nothing consumed them -- a prior-period value carried into a slot
    with no reader, which the cross-period consumption gate reports as inert. 02
    and 03 now consume them, so they are BOUND; 04 has no modelo 216 source
    declared and stays operator input.
    """
    modelo, _ = _load_modelo_296()
    revision = modelo.revisions["2024-2025"]
    by_id = {str(casilla.id): casilla for casilla in revision.casillas}

    assert tuple(by_id) == ("02", "03", "04")
    assert by_id["02"].binding == "modelo-296-prev-216-base-retenciones"
    assert by_id["03"].binding == "modelo-296-prev-216-retenciones-total"
    assert by_id["02"].input_kind.value == "bound"
    assert by_id["03"].input_kind.value == "bound"
    assert by_id["04"].input_kind.value == "manual"
    assert by_id["04"].binding is None


def test_every_modelo_216_relation_reads_a_casilla_the_source_edition_prints() -> None:
    """Each 296 edition reads from modelo 216 only the casillas the 216 edition of that year prints.

    The modelo 216 design for ejercicios 2020 to 2023 prints unnumbered partidas,
    and only the 2024 redesign numbers casillas [10] and [13]. A relation that
    names them for an earlier year can never resolve, so those years leave boxes
    02 and 03 as operator input.
    """
    modelo, _ = _load_modelo_296()
    source, _ = _committed_modelo("216")
    checked = 0
    for revision in modelo.revisions.values():
        selector = revision.period_selector
        years = range(selector.year_from, (selector.year_to or selector.year_from) + 1)
        for binding, provider in relation_prefill_bindings_for_period(revision):
            if provider.source_modelo != "216":
                continue
            wanted = {provider.source_casilla_id, *provider.source_casilla_ids} - {None}
            for year in years:
                printed = {casilla.id for casilla in select_revision_for_year(source, filing_year=year).casillas}
                assert wanted <= printed, (
                    f"296/{revision.id} binding {binding.id} reads 216 casilla(s) "
                    f"{sorted(map(str, wanted - printed))} that the {year} edition does not print"
                )
                checked += 1
    assert checked, "no modelo 296 edition declares a modelo 216 relation"


@pytest.mark.parametrize("revision_id", ["2022", "2023"])
def test_modelo_296_boxes_02_and_03_are_operator_input_before_the_2024_216_design(revision_id: str) -> None:
    modelo, _ = _load_modelo_296()
    revision = modelo.revisions[revision_id]
    by_id = {str(casilla.id): casilla for casilla in revision.casillas}

    assert relation_prefill_bindings_for_period(revision) == ()
    for casilla_id in ("02", "03"):
        assert by_id[casilla_id].input_kind.value == "manual"
        assert by_id[casilla_id].binding is None
