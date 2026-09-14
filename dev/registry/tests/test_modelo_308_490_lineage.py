"""Official-design declaration gaps and regularization-table continuity."""

from __future__ import annotations

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.casilla_lineage_totality import lineage_totality
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ..compiler.loader import load_modelo_directory
from ..compiler.validate_cross_revision import strict_cross_revision_casilla_continuity_failures

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_200_new_cohorts_do_not_hide_predecessor_declaration_gaps() -> None:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "200"))
    current = {row.id: row for row in modelo.revisions["2025-y-siguientes"].casillas}
    assert lineage_totality((modelo,), ()).uncovered == ()
    for identifier in ("DP200011:00417", "DP200011:00569", "DP200001:00082"):
        assert current[identifier].continuidad_origin is CasillaLineageOrigin.PREDECESSOR_EDITION_SILENT
        assert current[identifier].continuidad_id is None
    for identifier in ("03401", "03402", "03594", "03642", "03647"):
        assert current[identifier].continuidad_origin is CasillaLineageOrigin.NEW_ON_FORM
        assert "aeat-dr-200-2024" in current[identifier].continuidad_evidence


@pytest.fixture(scope="module")
def modelo_490() -> ModeloDefinition:
    return load_modelo_directory(bundled_path("registry", "aeat", "modelos", "490"))


def test_200_withdrawals_preserve_surviving_detail_total() -> None:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "200"))
    before = {row.id: row for row in modelo.revisions["2024"].casillas}
    after_revision = modelo.revisions["2025-y-siguientes"]
    after = {row.id: row for row in after_revision.casillas}
    retired = {
        evolution.continuidad_id
        for evolution in after_revision.casilla_continuidad_evolutions
        if evolution.evolution_kind == "retired"
    }
    # The AIE/UTE amount column disappears, but its base remains; the
    # donation subperiod disappears, but its pre-existing annual row remains.
    for withdrawn, surviving in (("00067", "00066"), ("02471", "00369")):
        assert before[withdrawn].continuidad_id in retired
        assert withdrawn not in after
        assert surviving in after
    # The incentive-detail total moves to page 18 bis: it is not a retirement
    # and does not become the simultaneously printed liquidation instance.
    chain = before["DP200018:00588"].continuidad_id
    assert chain == after["DP200018B:00588"].continuidad_id
    assert chain not in retired
    assert chain != after["DP200014B:00588"].continuidad_id
    assert strict_cross_revision_casilla_continuity_failures((modelo,)) == ()


def test_308_existing_official_fields_are_declaration_gaps() -> None:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "308"))
    current = {row.id: row for row in modelo.revisions["2019-y-siguientes"].casillas}
    assert lineage_totality((modelo,), ()).uncovered == ()
    assert current["decl.devolucion-iban"].continuidad_origin is CasillaLineageOrigin.PREDECESSOR_EDITION_SILENT
    assert current["decl.tipo-solicitud"].continuidad_origin is CasillaLineageOrigin.NOT_ON_FORM
    # Both official M30801 designs identify the rates after acquisition and
    # sale prices as [02] and [05], distinct from their adjacent prices.
    assert current["decl.mtn-tipo-01"].form_number == "02"
    assert current["decl.mtn-tipo-04"].form_number == "05"


def test_490_regularization_survives_new_numbering_and_page_movement(modelo_490: ModeloDefinition) -> None:
    before = {row.id: row for row in modelo_490.revisions["2022-1t"].casillas}
    after = {row.id: row for row in modelo_490.revisions["2022-2t-4t"].casillas}
    # BOE-A-2021-9721 and BOE-A-2022-8830: second exercise, 2T;
    # third exercise, 1T; fourth exercise, 4T. New numbers above the old
    # maximum do not turn these existing table cells into introductions.
    for predecessor, successor in (
        ("reg21-base-positiva-33", "reg-base-positiva-133"),
        ("reg21-base-positiva-51", "reg-base-positiva-196"),
        ("reg21-cuota-total-100", "reg-cuota-total-349"),
    ):
        assert before[predecessor].continuidad_id == after[successor].continuidad_id
        assert after[successor].continuidad_origin is CasillaLineageOrigin.GROUNDED
    assert lineage_totality((modelo_490,), ()).uncovered == ()
    assert strict_cross_revision_casilla_continuity_failures((modelo_490,)) == ()


def test_490_repeated_printed_rate_keeps_four_quarter_identities(modelo_490: ModeloDefinition) -> None:
    before = {row.id: row for row in modelo_490.revisions["2022-1t"].casillas}
    after = {row.id: row for row in modelo_490.revisions["2022-2t-4t"].casillas}
    # The original form repeats [4] for all quarter rates. Its four named
    # quarter columns, not that repeated number, establish correspondence.
    pairs = (
        ("reg21-tipo-4-221", "reg-tipo-31"),
        ("reg21-tipo-4-224", "reg-tipo-52"),
        ("reg21-tipo-4-227", "reg-tipo-73"),
        ("reg21-tipo-4-230", "reg-tipo-94"),
    )
    chains = []
    for predecessor, successor in pairs:
        assert before[predecessor].continuidad_id == after[successor].continuidad_id
        chains.append(after[successor].continuidad_id)
    assert len(set(chains)) == len(pairs)
