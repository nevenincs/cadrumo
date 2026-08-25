"""End-to-end: M190 "número total de percepciones" resolves via the live withholding source (#28 P05).

Drives the REAL chain (no mocks): persist per-perceptor-clave WithholdingObservation
rows into the encrypted store → the enrolled WithholdingSourceResolver materialises
the DISTINCT (perceptor, clave, subclave) count → the registry engine binds it onto
``decl.total-percepciones`` (now ``input_kind = "bound"`` after the P04 re-point,
replacing the nine op=sum quarterly relations). Proves percepciones > perceptores:
one perceptor under two claves counts as two percepciones.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.withholding_bindings import WithholdingObservation

from ....application.aggregation import WithholdingSourceResolver, persist_percepcion_observations
from ....core import Period, validated_casilla_id
from ....core.aggregation import RetencionClave
from ....core.resources import resources
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import CalculationSourceContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "36363636-3636-4363-8363-363636363636"
_TOTAL_PERCEPCIONES = validated_casilla_id("decl.total-percepciones", surface="test")


def _obs(nif: str, clave: RetencionClave) -> WithholdingObservation:
    return WithholdingObservation(
        source_id=f"row-{nif}-{clave}",
        perceptor_tax_id=nif,
        transaction_date=date(2024, 6, 1),
        clave=clave,
        percibido_dinerario=Decimal("1000"),
        retencion_practicada=Decimal("190"),
    )


def test_m190_percepciones_count_resolves_distinct_from_store_to_bound_casilla(tmp_path: Path) -> None:
    """3 percepciones (one perceptor under 2 claves + a second) -> decl.total-percepciones == 3."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        period = Period.from_year_and_code(2024, "0A")
        persist_percepcion_observations(
            modelo="190",
            filing_year=2024,
            period=period,
            observations=[
                _obs("11111111H", RetencionClave.A),
                _obs("11111111H", RetencionClave.G),
                _obs("22222222J", RetencionClave.A),
            ],
        )
        snapshot = resources().modelos.authority.snapshot("190", filing_year=2024, period="0A")
        resolution = WithholdingSourceResolver().resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="190",
                filing_year=2024,
                period=period,
                revision=snapshot.revision,
            ),
        )
        binding_values = dict(resolution.binding_values)
        # The engine binds the resolved count onto the now-``bound`` casilla. We
        # assert the bound-input resolution (store -> resolver -> binding_values ->
        # decl.total-percepciones) rather than a full M190 calc, to keep the smoke
        # scoped to the percepciones box (the importe formulas need their own
        # relations, out of scope here).
        bound_inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)

        # Distinct percepciones = 3 (distinct perceptores would be 2) — the #28 fix.
        assert bound_inputs[_TOTAL_PERCEPCIONES] == Decimal(3)
        assert resolution.diagnostics == ()
