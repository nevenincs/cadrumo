"""Calculation-order seam for ``prorrata_regularizacion`` source materialisation.

The live source resolver needs current-period registry values that do not all
exist until the Modelo 303 formula graph has run: annual prorrata volumes are
operator-declared seed casillas, while the definitive percentage and deductible
total are computed registry outputs. These tests pin the no-persist engine pass
that exposes those values without copying formula business logic into the
resolver layer.

See Also:
    :func:`~application.modelo._calculation_source_staging.materialise_prorrata_regularizacion_current_year_values`
        No-persist engine materialisation seam under test.
    :data:`~application.modelo._calculation_source_staging._PRORRATA_REGULARIZACION_CURRENT_YEAR_CASILLA_IDS`
        Canonical source-value order consumed by the resolver.
    :class:`~domain.calculations.registry._bindings._ProrrataRegularizacionSelector`
        Registry selector contract that declares the source casilla set.
    :class:`~application.calculations._prorrata_regularizacion.ProrrataRegularizacionSourceResolver`
        Downstream resolver that consumes these materialised values.
    ``2026-07-06-cross-period-prorrata-audit`` and
    ``2026-07-06-cross-period-prorrata-plan``
        S45 review and W07.P11 calculation-order plan context.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....core import Period
from ....core.resources import bundled_path, resources
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....domain.modelos import WorkUnit, derive_work_unit_id
from .._calculation_source_staging import (
    _PRORRATA_REGULARIZACION_CURRENT_YEAR_CASILLA_IDS,
    materialise_prorrata_regularizacion_current_year_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ORACLE_PATH = Path(
    bundled_path("corpus", "manual_oracles", "modelo-303-prorrata-general-regularizacion.json"),
)
_BUCKET_ID = "prorrata-source-timing"
_FILING_YEAR = 2025
_PERIOD = Period.from_year_and_code(_FILING_YEAR, "4T")
_CREATED_AT = datetime(2026, 1, 20, 9, 0, tzinfo=UTC)

_CUOTA_DEDUCIBLE_TOTAL_ID: CasillaId = validated_casilla_id(
    "iva.cuota-deducible-total",
    surface="test casilla id",
)
_SOPORTADO_INTERIORES_ID: CasillaId = validated_casilla_id("iva.soportado.interiores", surface="test casilla id")
_VOLUMEN_CON_DERECHO_ID: CasillaId = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="test casilla id",
)
_VOLUMEN_TOTAL_ID: CasillaId = validated_casilla_id("iva.prorrata-volumen-total", surface="test casilla id")
_PORCENTAJE_ID: CasillaId = validated_casilla_id("iva.prorrata-porcentaje", surface="test casilla id")

# AEAT Manual practico IVA 2025, Capitulo 5 prorrata general example, pages
# 137-138: the fourth quarter supports 160 EUR of input IVA before applying the
# definitive 56% prorrata. This is copied from the bundled oracle notes.
_MANUAL_FOURTH_QUARTER_INPUT_IVA = Decimal("160.00")


def _oracle_payload() -> dict[str, Any]:
    return json.loads(_ORACLE_PATH.read_text(encoding="utf-8"))


def _oracle_expected(casilla_id: CasillaId) -> Decimal:
    raw = _oracle_payload()["expected_by_casilla_id"][str(casilla_id)]
    return Decimal(str(raw))


def _work_unit(*, revision_id: str) -> WorkUnit:
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=_FILING_YEAR,
            period=_PERIOD,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_FILING_YEAR,
        period=_PERIOD,
        revision_id=revision_id,
        name="303-2025-4T",
        created_at=_CREATED_AT,
        updated_at=_CREATED_AT,
    )


def test_prorrata_regularizacion_source_values_are_materialised_by_registry_engine() -> None:
    """The seam exposes manual volume seeds and computed values from one engine pass."""
    snapshot = resources().modelos.authority.snapshot("303", filing_year=_FILING_YEAR, period="4T")
    work_unit = _work_unit(revision_id=snapshot.revision.id)

    materialised = materialise_prorrata_regularizacion_current_year_values(
        registry_snapshot=snapshot,
        work_unit=work_unit,
        casilla_inputs={
            _SOPORTADO_INTERIORES_ID: _MANUAL_FOURTH_QUARTER_INPUT_IVA,
            _VOLUMEN_CON_DERECHO_ID: _oracle_expected(_VOLUMEN_CON_DERECHO_ID),
            _VOLUMEN_TOTAL_ID: _oracle_expected(_VOLUMEN_TOTAL_ID),
        },
        backend_casilla_inputs=None,
        binding_values={"modelo-303-compensacion-pendiente-anteriores": Decimal("0.00")},
        filing_period_date=datetime(2026, 1, 20, tzinfo=UTC).date(),
    )

    assert tuple(materialised.values) == _PRORRATA_REGULARIZACION_CURRENT_YEAR_CASILLA_IDS
    assert materialised.missing_casilla_ids == ()
    assert materialised.unresolved_casilla_ids == ()
    assert materialised.values[_VOLUMEN_CON_DERECHO_ID] == _oracle_expected(_VOLUMEN_CON_DERECHO_ID)
    assert materialised.values[_VOLUMEN_TOTAL_ID] == _oracle_expected(_VOLUMEN_TOTAL_ID)
    assert materialised.values[_PORCENTAJE_ID] == _oracle_expected(_PORCENTAJE_ID)
    assert materialised.values[_CUOTA_DEDUCIBLE_TOTAL_ID] == _MANUAL_FOURTH_QUARTER_INPUT_IVA
    assert _VOLUMEN_CON_DERECHO_ID in materialised.initial_casilla_ids
    assert _VOLUMEN_TOTAL_ID in materialised.initial_casilla_ids
    assert _PORCENTAJE_ID not in materialised.initial_casilla_ids
    assert _CUOTA_DEDUCIBLE_TOTAL_ID not in materialised.initial_casilla_ids
