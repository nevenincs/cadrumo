"""Grounding coverage for current Modelo 136 registry entries."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import bundled_path
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REFS = frozenset(
    {
        "ley-35-2006:da-33",
        "orden-hap-70-2013:art-5",
        "orden-hap-70-2013:art-6",
        "orden-hap-70-2013:art-7",
        "orden-hap-70-2013:art-10",
        "orden-hap-70-2013:art-11",
        "orden-hap-70-2013:art-12",
        "orden-hac-763-2018:art-tercero",
        "orden-hac-763-2018:df-unica",
    },
)

_SOURCE_REFS = frozenset(
    {
        "aeat-modelo-136-procedure",
        "aeat-modelo-136-procedure-record",
        "boe-lirpf-lottery-prize-special-levy",
        "boe-modelo-136-base-order",
        "boe-modelo-136-2018-amendment-hac-763",
        "boe-modelo-136-current-form-text",
        "boe-modelo-136-current-form",
    },
)


def test_modelo_136_current_revision_is_grounded_in_model_specific_catalogues() -> None:
    modelo, catalogues = _committed_modelo("136")

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    assert modelo.calculation_class == "filing"
    assert set(modelo.legal_refs) == _LEGAL_REFS
    assert set(modelo.source_refs) == _SOURCE_REFS
    assert set(modelo.revisions) == {"2026"}

    revision = modelo.revisions["2026"]
    assert revision.period_selector.years == (2026,)
    assert revision.period_selector.periods == ("1T", "2T", "3T", "4T")
    assert set(revision.legal_refs) == _LEGAL_REFS
    assert set(revision.source_refs) == _SOURCE_REFS
    assert all("enrolled-modelo-136" not in source_ref for source_ref in revision.source_refs)
    assert revision.completeness_manifest is not None
    assert {casilla.casilla_id for casilla in revision.completeness_manifest.casillas} == {
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
    }
    assert revision.completeness_manifest.source_ref == "boe-modelo-136-current-form-text"

    assert set(catalogues.legal) >= _LEGAL_REFS
    assert set(catalogues.sources) >= _SOURCE_REFS

    windows = {window.id: window for window in revision.deadline_windows}
    assert set(windows) == {
        "modelo-136-2026-1t",
        "modelo-136-2026-2t",
        "modelo-136-2026-3t",
        "modelo-136-2026-4t",
    }
    assert windows["modelo-136-2026-1t"].closes_on == date(2026, 4, 20)
    assert windows["modelo-136-2026-2t"].closes_on == date(2026, 7, 20)
    assert windows["modelo-136-2026-3t"].closes_on == date(2026, 10, 20)
    assert windows["modelo-136-2026-4t"].closes_on == date(2027, 1, 20)


def test_modelo_136_formula_graph_matches_current_form_rows() -> None:
    modelo, _catalogues = _committed_modelo("136")
    revision = modelo.revisions["2026"]

    casillas = {casilla.id: casilla for casilla in revision.casillas}
    formulas = {formula.id: formula for formula in revision.formulas}

    assert casillas["03"].input_kind == "manual"
    assert casillas["04"].formula == "modelo-136-base-imponible"
    assert casillas["05"].formula == "modelo-136-cuota-gravamen-especial"
    assert casillas["07"].formula == "modelo-136-resultado-ingresar"

    base = formulas["modelo-136-base-imponible"]
    assert base.target_casilla_id == "04"
    assert base.expression.op == "subtract"
    assert [arg.casilla_id for arg in base.expression.args] == ["02", "03"]
    assert {citation.source_ref for citation in base.source_citations} == {
        "boe-lirpf-lottery-prize-special-levy",
        "boe-modelo-136-current-form-text",
    }

    cuota = formulas["modelo-136-cuota-gravamen-especial"]
    assert cuota.target_casilla_id == "05"
    assert cuota.expression.op == "percent"
    assert cuota.expression.args[0].casilla_id == "04"
    # The 20% rate is a registry PARAMETER now, not a formula literal, which is
    # where a year-versioned regulatory value belongs -- a literal bakes it into
    # the call site and cannot move when the rate does. Asserting the reference
    # alone would be weaker than the literal it replaced, so the indirection is
    # followed: the named parameter must exist on this revision and resolve to 20.
    rate_ref = cuota.expression.args[1].parameter
    assert rate_ref == "irpf.lottery_prize_special_levy_rate"
    assert cuota.expression.args[1].literal is None, "the rate must not be declared twice"
    parameter = next(item for item in revision.parameters if item.id == rate_ref)
    assert {value.value for value in parameter.values} == {Decimal("20")}
    assert {citation.source_ref for citation in cuota.source_citations} == {
        "boe-lirpf-lottery-prize-special-levy",
        "boe-modelo-136-current-form-text",
    }

    resultado = formulas["modelo-136-resultado-ingresar"]
    assert resultado.target_casilla_id == "07"
    assert resultado.expression.op == "subtract"
    assert [arg.casilla_id for arg in resultado.expression.args] == ["05", "06"]
    assert {citation.source_ref for citation in resultado.source_citations} == {
        "boe-modelo-136-current-form-text",
    }
