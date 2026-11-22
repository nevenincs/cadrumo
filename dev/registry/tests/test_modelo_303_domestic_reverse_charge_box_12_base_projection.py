"""Modelo 303 box 12 states the base of the domestic reverse charge whose cuota box 13 states.

The AEAT instructions describe [12] and [13] together: "Se consignarán las
bases imponibles y las cuotas devengadas en el periodo de liquidación por
inversión del sujeto pasivo (artículo 84. Uno. 2.º y 4.º de la Ley del IVA)
cuando tengan su origen en operaciones distintas de las consignadas en las
casillas 10 y 11." Every record design from the support floor prints
"Otras operaciones con inversión del sujeto pasivo (excepto. adq. intracom) -
Base imponible [12]" beside the cuota [13]. Box 13 was computed from the ledger
while box 12 was operator input, so a filing stated the cuota without its base.

The base parity casilla ``iva.autorepercutido.interior.devengado.base`` reads
the same ledger rows as the cuota carrier through a ``base_amount_sum``
binding, and box 12 projects it. The value proof runs the production snapshot
calculation for every year of the registry support envelope.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind

from ..compiler.loader import load_registry_tree
from .authored_edition_support import authored_revisions, revision_covering
from .gate_support import mutate_declaration, scratch_registry_tree
from .ledger_iva_aggregation_support import (
    calculate_303_from_observations,
    deduction_authority,
    deduction_kind,
    ledger_iva_aggregation_category,
    ledger_iva_aggregation_flow,
    ledger_iva_aggregation_observation,
    ledger_iva_aggregation_rate_kind,
)
from .profile_schema_support import committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_CASILLA_BASE = "iva.autorepercutido.interior.devengado.base"
_CASILLA_CUOTA = "iva.autorepercutido.interior.devengado"
_BINDING_BASE = "modelo-303-iva-autorepercutido-interior-devengado-base"
_BINDING_CUOTA = "modelo-303-iva-autorepercutido-interior-devengado-cuota"
_FORMULA_BOX_12 = "modelo-303-dr303-12-projection"
_SUPPORTED_YEARS = committed_supported_filing_years().years
# The first and last quarter of a year reach both editions of a year an
# official design splits within the year.
_QUARTERS = {"1T": 2, "4T": 11}


def _casilla(revision: ModeloRevision, casilla_id: str):
    (casilla,) = (item for item in revision.casillas if str(item.id) == casilla_id)
    return casilla


def _expression(revision: ModeloRevision, formula_id: str) -> object:
    (formula,) = (item for item in revision.formulas if str(item.id) == formula_id)
    return formula.expression.model_dump(mode="json", exclude_none=True, exclude_defaults=True)


def test_box_12_projects_the_base_parity_casilla_in_every_edition() -> None:
    failures: list[str] = []
    for revision in authored_revisions("303"):
        box_12 = _casilla(revision, "12")
        if box_12.input_kind is not InputKind.COMPUTED or str(box_12.formula) != _FORMULA_BOX_12:
            failures.append(f"{revision.id}: box 12 is {box_12.input_kind} / {box_12.formula}")
            continue
        if _expression(revision, _FORMULA_BOX_12) != {"casilla_id": _CASILLA_BASE}:
            failures.append(f"{revision.id}: {_FORMULA_BOX_12} projects {_expression(revision, _FORMULA_BOX_12)!r}")
        if str(_casilla(revision, _CASILLA_BASE).binding) != _BINDING_BASE:
            failures.append(f"{revision.id}: {_CASILLA_BASE} is not bound to {_BINDING_BASE}")
    assert not failures, "\n".join(failures)


def test_box_12_base_and_box_13_cuota_select_one_population_in_every_edition() -> None:
    for revision in authored_revisions("303"):
        providers = {
            str(binding.id): binding.model_dump(mode="json")["provider"]
            for binding in revision.bindings
            if str(binding.id) in {_BINDING_BASE, _BINDING_CUOTA}
        }
        base, cuota = providers[_BINDING_BASE], providers[_BINDING_CUOTA]
        assert base["fact"] == "base_amount_sum", revision.id
        assert cuota["fact"] == "iva_amount_sum", revision.id
        assert str(_casilla(revision, _CASILLA_CUOTA).binding) == _BINDING_CUOTA, revision.id
        for axis in (
            "categories",
            "rate_kinds",
            "flow_direction",
            "observation_roles",
            "cash_accounting_treatments",
            "deduction_fact_kinds",
        ):
            left, right = base.get(axis), cuota.get(axis)
            if isinstance(left, list) and isinstance(right, list):
                left, right = sorted(left), sorted(right)
            assert left == right, (revision.id, axis, left, right)


@pytest.mark.parametrize("period", sorted(_QUARTERS))
@pytest.mark.parametrize("filing_year", _SUPPORTED_YEARS)
def test_a_received_domestic_reverse_charge_reaches_box_12_and_box_13(filing_year: int, period: str) -> None:
    """A 1000,00 service received under art. 84.Uno.2.º at the general rate states 1000,00 and 210,00.

    The expected figures are the operation's own base and its cuota at the
    general rate of art. 90.Uno (21 % of 1000,00), not values read back from
    the registry's formulas.
    """
    txn_date = date(filing_year, _QUARTERS[period], 15)
    received = ledger_iva_aggregation_observation(
        ledger_id="domestic-reverse-charge",
        txn_date=txn_date,
        category=ledger_iva_aggregation_category("domestic_reverse_charge", effective_date=txn_date),
        rate_kind=ledger_iva_aggregation_rate_kind("general", effective_date=txn_date),
        flow=ledger_iva_aggregation_flow("inversion_sujeto_pasivo", effective_date=txn_date),
        applied_rate=Decimal("0.21"),
        base=Decimal("1000.00"),
        iva=Decimal("210.00"),
        deduction_fact_kind=deduction_kind("domestic_current", effective_date=txn_date),
        deduction_authority=deduction_authority("invoice_evidence", effective_date=txn_date),
    )

    values = calculate_303_from_observations(filing_year=filing_year, period=period, observations=(received,)).values

    assert values[validated_casilla_id("12")] == Decimal("1000.00")
    assert values[validated_casilla_id("13")] == Decimal("210.00")


def test_mutation_reverting_box_12_to_manual_reds_the_projection_gate(tmp_path: Path) -> None:
    """Re-introduce the manual box 12 on an isolated scratch copy and confirm it is detected."""
    floor_revision_id = str(revision_covering("303", committed_supported_filing_years().floor).id)
    scratch_root = scratch_registry_tree(tmp_path, "303")
    mutate_declaration(
        scratch_root / "modelos" / "303",
        revision_id=floor_revision_id,
        section="casillas",
        find=f'input_kind = "computed"\nformula = "{_FORMULA_BOX_12}"\n',
        replace="",
    )

    modelos, _catalogues = load_registry_tree(scratch_root)
    mutated = next(modelo for modelo in modelos if modelo.id == "303").revisions[floor_revision_id]
    assert _casilla(mutated, "12").input_kind is not InputKind.COMPUTED

    bundled, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    tracked = next(modelo for modelo in bundled if modelo.id == "303").revisions[floor_revision_id]
    assert _casilla(tracked, "12").input_kind is InputKind.COMPUTED
