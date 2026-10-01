from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from ..errors import FilingYearOutsideSupportEnvelopeError
from ..formula_runtime import calculate_registry_snapshot
from ..relations import (
    relation_prefill_bindings_for_period,
    relation_source_requirements,
    resolve_relation_values_from_observations,
)
from ..schema import RegistrySnapshot
from ._cross_dependency_calculation_support import (
    _M200_CUOTA_DIFERENCIAL_CASILLA,
    _M202_CUOTA_BASE_CASILLA,
    _casilla_inputs,
    _observations_from_requirements,
    source_editions_calculate,
)
from .authored_editions import authored_revisions
from .published_authority import (
    PublishedGovernedFactSource,
    published_authored_revision,
    published_revision,
    published_supported_filing_years,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


@pytest.mark.parametrize("period", ["1P", "2P", "3P"])
def test_modelo_202_modalidad_chains_calculate_for_synthetic_inputs(
    period: str,
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("202", 2026, period)
    revision = snapshot.revision
    assert revision.id == "2025-y-siguientes"
    # The casilla POPULATION is not the subject here and is no longer pinned by
    # tally: it counted 50 when written and the revision declares 61 now, so the
    # constant only ever recorded a moment. What must hold is that every casilla
    # the synthetic inputs feed, and every casilla a formula targets, is actually
    # declared by the selected revision.
    declared_ids = {str(casilla.id) for casilla in revision.casillas}
    formula_targets = {formula.target_casilla_id for formula in revision.formulas}
    assert formula_targets == {"03", "13", "16", "18", "22", "25", "26", "32", "34", "38", "39", "63", "66"}

    inputs = _casilla_inputs(
        {
            "01": Decimal("10000"),
            "02": Decimal("0"),
            "04": Decimal("50000"),
            "05": Decimal("2000"),
            "06": Decimal("1000"),
            "07": Decimal("500"),
            "08": Decimal("300"),
            "37": Decimal("200"),
            "67": Decimal("100"),
            "14": Decimal("4200"),
            "44": Decimal("0"),
            "45": Decimal("0"),
            "46": Decimal("0"),
            "17": Decimal("17"),
            "47": Decimal("0"),
            "40": Decimal("0"),
            "48": Decimal("0"),
            "49": Decimal("0"),
            "27": Decimal("200"),
            "28": Decimal("500"),
            "29": Decimal("100"),
            "31": Decimal("0"),
            "33": Decimal("0"),
            "20": Decimal("0"),
            "21": Decimal("0"),
            "23": Decimal("0"),
            "24": Decimal("0"),
            "42": Decimal("0"),
            "50": Decimal("0"),
            "51": Decimal("0"),
            "52": Decimal("0"),
            "61": Decimal("0"),
            "62": Decimal("0"),
            "64": Decimal("0"),
            "65": Decimal("0"),
        }
    )

    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": date(2026, 12, 31)},
        binding_values={
            "modelo-202-pagos-fraccionados-anteriores": Decimal("3000"),
            "modelo-202-cuota-base-ejercicio-anterior": inputs[_M202_CUOTA_BASE_CASILLA],
        },
    )
    assert {str(casilla_id) for casilla_id in inputs} <= declared_ids
    assert formula_targets <= declared_ids

    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert entries["03"].operand_refs == ("01", "is.modalidad_cuota.percentage", "02")
    assert entries["16"].operand_refs == ("13", "44", "14", "45", "46")
    assert entries["18"].operand_refs == ("16", "17", "47", "48", "40", "49")
    assert entries["34"].operand_refs == ("32", "33")


@pytest.mark.parametrize(
    ("filing_year", "expected_revision"),
    [
        (2022, "2019-2022"),
        (2023, "2023-2024"),
        (2024, "2023-2024"),
        (2025, "2025-y-siguientes"),
        (2026, "2025-y-siguientes"),
    ],
)
def test_modelo_202_revision_selection_resolves_for_filing_year_boundaries(
    filing_year: int,
    expected_revision: str,
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("202", filing_year, "1P")
    assert snapshot.revision.id == expected_revision
    # Not a tally. The correcciones block 61..66 plus casilla 67 are what the 2025
    # diseno ADDS over the earlier spans, so asserting the selected revision
    # carries them exactly when it is the 2025 span proves the selection landed on
    # the right CONTENT. A casilla count never did: it read 43 and 50 when written
    # and the revisions declare 54 and 61 now.
    declared_ids = {str(casilla.id) for casilla in snapshot.revision.casillas}
    correcciones_block = {"61", "62", "63", "64", "65", "66", "67"}
    if expected_revision == "2025-y-siguientes":
        assert correcciones_block <= declared_ids
    else:
        assert correcciones_block.isdisjoint(declared_ids)


def test_modelo_202_revision_selection_refuses_years_below_the_supported_floor(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    supported_years = published_supported_filing_years()
    assert supported_years is not None
    below_floor = supported_years.floor - 1
    # The 2019-2022 revision still authors this year; the refusal is the floor's.
    assert published_authored_revision("202", year=below_floor).id == "2019-2022"
    with pytest.raises(FilingYearOutsideSupportEnvelopeError) as excinfo:
        registry_snapshot("202", below_floor, "1P")
    assert "2019-2022" in excinfo.value.covering_revision_ids


def test_modelo_202_pre_b2_revision_total_correcciones_aumentos_excludes_complementario_column(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    # The B2 tramos arrive with the first revision that declares casilla 67; the revision
    # the registry authors right before it keeps the pre-B2 shape for every supported
    # exercise it covers.
    revisions = authored_revisions("202")
    first_b2 = next(
        index
        for index, metadata in enumerate(revisions)
        if "67" in {casilla.id for casilla in published_revision("202", str(metadata.id)).casillas}
    )
    assert first_b2 > 0
    revision_window = revisions[first_b2 - 1]
    covered_years = tuple(
        year
        for year in PublishedGovernedFactSource().supported_filing_years().years
        if revision_window.valid_from.year <= year
        and (revision_window.valid_to is None or year <= revision_window.valid_to.year)
    )
    assert covered_years
    for filing_year in covered_years:
        _assert_pre_b2_correcciones_shape(registry_snapshot, filing_year, str(revision_window.id))


def _assert_pre_b2_correcciones_shape(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot], filing_year: int, revision_id: str
) -> None:
    snapshot = registry_snapshot("202", filing_year, "2P")
    revision = snapshot.revision
    assert revision.id == revision_id
    casilla_ids = {casilla.id for casilla in revision.casillas}
    assert "67" not in casilla_ids
    assert {"61", "62", "63", "64", "65", "66"}.isdisjoint(casilla_ids)

    inputs = _casilla_inputs(
        {
            "05": Decimal("2000"),
            "07": Decimal("500"),
            "06": Decimal("1000"),
            "37": Decimal("200"),
            "08": Decimal("300"),
            "04": Decimal("50000"),
        }
    )
    calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": date(filing_year, 12, 31)},
        binding_values={
            "modelo-202-pagos-fraccionados-anteriores": Decimal("0"),
        },
    )


def test_modelo_200_cuota_a_ingresar_aggregates_modelo_202_pagos_fraccionados(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> None:
    # The first supported year whose Modelo 200 edition calculates and whose fold
    # sources -- the prior year's Modelo 200 and the year's Modelo 202 -- calculate
    # too, so every observation below is grounded in an edition that computes it.
    # An earlier year answered by an applicability-grade edition refuses the
    # calculation this test drives.
    support = published_supported_filing_years()
    assert support is not None
    editions = {
        year: registry_snapshot("200", year, "0A", grade=RegistryAuthorityGrade.APPLICABILITY).revision
        for year in support.years
    }
    filing_year = next(
        year
        for year, edition in editions.items()
        if edition.effective_authority_grade is not RegistryAuthorityGrade.APPLICABILITY
        and source_editions_calculate(relation_source_requirements(edition, filing_year=year, period="0A"))
    )
    snapshot = registry_snapshot("200", filing_year, "0A", grade=RegistryAuthorityGrade.CALCULATION)
    revision = snapshot.revision
    relation_ids = {binding.id for binding, _ in relation_prefill_bindings_for_period(revision, period="0A")}
    assert relation_ids == {
        "modelo-200-pagos-fraccionados-anuales",
        "modelo-200-pagos-fraccionados-anuales-40-2",
        "modelo-200-bin-pendiente-ejercicios-anteriores",
        "modelo-200-dotaciones-deterioro-creditos-saldo-cumplido-anteriores",
        "modelo-200-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores",
    }
    classifications = {
        classification.source_modelo: classification for classification in revision.dependency_classifications
    }
    assert classifications["202"].treatment == "direct_annual_settlement"
    assert classifications["200"].treatment == "factual_evidence"

    requirements = relation_source_requirements(revision, filing_year=filing_year, period="0A")
    observations = _observations_from_requirements(
        requirements,
        lambda _requirement, period_index: (
            Decimal("1200"),
            Decimal("1500"),
            Decimal("1800"),
        )[period_index],
        target_modelo="200",
        fallback_revision=revision,
    )

    relation_values = resolve_relation_values_from_observations(
        revision,
        observations,
        filing_year=filing_year,
        period="0A",
    )
    assert set(relation_values) == relation_ids

    diferencial_formula = next(
        formula for formula in revision.formulas if formula.target_casilla_id == _M200_CUOTA_DIFERENCIAL_CASILLA
    )
    assert diferencial_formula.id == "modelo-200-cuota-diferencial"
    assert diferencial_formula.expression.op == "subtract"
    assert "ley-27-2014:art-41" in diferencial_formula.legal_refs

    result = calculate_registry_snapshot(
        snapshot,
        inputs=_casilla_inputs(
            {
                "DP200012:00501": Decimal("48000"),
                "DP200013:00417": Decimal("0"),
                "DP200013:00418": Decimal("0"),
                "01032": Decimal("0"),
                "DP200014:00547": Decimal("0"),
                "DP200014:01033": Decimal("0"),
                "DP200014:01034": Decimal("0"),
            },
        ),
        enum_binding_values={"modelo-200-profile-legal-entity-form": "sl"},
        binding_values={
            "modelo-200-profile-new-entity-flag": Decimal("0"),
            "modelo-200-profile-incn-prior-12-months": Decimal("10000000"),
            "modelo-200-profile-tributacion-estado-porcentaje": Decimal("100"),
        },
        date_context={"filing_period": date(filing_year, 12, 31)},
        relation_values=relation_values,
    )
    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert "DP200014B:00599" in entries
    assert "DP200014B:00611" in entries
    diferencial_entry = entries["DP200014B:00611"]
    assert diferencial_entry.formula_id == "modelo-200-cuota-diferencial"
    assert diferencial_entry.op == "subtract"
    assert set(diferencial_entry.operand_refs) == {
        "DP200014B:00599",
        "modelo-200-pagos-fraccionados-anuales",
        "modelo-200-pagos-fraccionados-anuales-40-2",
    }
    assert diferencial_entry.operand_refs == (
        "DP200014B:00599",
        "modelo-200-pagos-fraccionados-anuales",
        "modelo-200-pagos-fraccionados-anuales-40-2",
    )
    assert diferencial_entry.operand_values[1] == relation_values["modelo-200-pagos-fraccionados-anuales"]
    assert diferencial_entry.operand_values[2] == relation_values["modelo-200-pagos-fraccionados-anuales-40-2"]
