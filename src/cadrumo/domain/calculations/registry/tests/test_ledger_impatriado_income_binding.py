"""Tests for the ledger-backed Modelo 151 impatriado income registry binding.

Complements the application-layer end-to-end regression
(``application/aggregation/tests/test_impatriado_income_ledger.py::
test_registry_binding_resolves_es_source_total_into_base``), which grounds
the committed ``ingresos_integros_sum`` fact (the only fact the real M151
binding declares) through the full ES/foreign-source classifier. That
coverage never exercises the resolver's ``gross_income_sum`` branch — no
committed binding uses it — so
:func:`resolve_ledger_impatriado_income_aggregation_binding_values`'s
fact-dispatch ``else`` arm had zero test coverage before this file. This
test constructs a synthetic binding declaring ``gross_income_sum`` (a
structural wiring check, not a legal-grounding claim: it asserts the
dispatch reads ``gross_amount`` unconditionally, ignoring a declared
``taxable_base_amount``, which is what distinguishes it from
``ingresos_integros_sum``) and serves as part of the F15 regression net for
this family's refactor onto the shared
:func:`~....registry._ledger_binding_resolution.resolve_ledger_family_binding_values`
skeleton.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from .....core.resources import bundled_path
from .. import (
    CasillaId,
    build_snapshot,
    resolve_ledger_impatriado_income_aggregation_binding_values,
    validated_casilla_id,
)
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_IMPATRIADO_BINDING = "modelo-151-impatriado-base-liquidable-general"
_M151_BASE_CASILLA: CasillaId = validated_casilla_id(
    "impatriado.base-liquidable-general",
    surface="_M151_BASE_CASILLA",
)


@dataclass(frozen=True)
class _ImpatriadoIncomeObservation:
    """Minimal stand-in satisfying ``ImpatriadoIncomeObservationProtocol``."""

    target_casilla_id: CasillaId
    gross_amount: Decimal
    taxable_base_amount: Decimal | None


def _modelo_151_snapshot():
    modelo, catalogues = _committed_modelo("151")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2020,
        period="0A",
    )


def test_gross_income_sum_fact_reads_gross_amount_unconditionally() -> None:
    """A ``gross_income_sum`` binding sums gross_amount even when taxable_base_amount is declared.

    Reuses the committed binding's casilla and selector shape but swaps
    ``fact`` to ``gross_income_sum`` (a fact the real M151 registry never
    declares) to exercise the dispatch's other arm. A tagged row's
    IVA-exclusive base (1000.00) and its gross transfer amount (1210.00)
    are deliberately unequal so a regression collapsing onto the
    ``ingresos_integros_sum`` behaviour (base-preferring) is caught: it
    would report 1000.00 + 500.00 = 1500.00 instead of the expected
    1210.00 + 500.00 = 1710.00.
    """
    revision = _modelo_151_snapshot().revision
    committed_binding = next(binding for binding in revision.bindings if binding.id == _IMPATRIADO_BINDING)
    gross_binding = committed_binding.model_copy(
        update={
            "id": "test-impatriado-gross-income-sum",
            "selector": {
                "modelo": "151",
                "target_casilla_id": _M151_BASE_CASILLA,
                "fact": "gross_income_sum",
            },
        },
    )
    revision_with_gross_binding = revision.model_copy(update={"bindings": (*revision.bindings, gross_binding)})

    tagged = _ImpatriadoIncomeObservation(
        target_casilla_id=_M151_BASE_CASILLA,
        gross_amount=Decimal("1210.00"),
        taxable_base_amount=Decimal("1000.00"),
    )
    untagged = _ImpatriadoIncomeObservation(
        target_casilla_id=_M151_BASE_CASILLA,
        gross_amount=Decimal("500.00"),
        taxable_base_amount=None,
    )

    resolved = resolve_ledger_impatriado_income_aggregation_binding_values(
        revision_with_gross_binding,
        (tagged, untagged),
    )

    assert resolved[gross_binding.id] == Decimal("1710.00")
    assert resolved[gross_binding.id] != Decimal("1500.00"), (
        "gross_income_sum must not fall back to the ingresos_integros_sum base-preferring behaviour"
    )
