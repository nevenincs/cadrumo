"""Anti-tautology proof: the M303 engine sums extracted primitive leaves.

Per the engine-and-fixture co-landing rule and the M303-specific
synthetic-generator primitive spec, a synthetic-fixture round trip that depends on the engine
recomputing a total from extracted primitives MUST carry an anti-tautology
test that proves the engine is actually summing the primitives — not, for
example, copying the printed total or silently substituting a zero default.

The probe: parse one M303 corpus PDF, mutate ``iva.repercutido.general``
(the engine's primary devengada-total summand) by a known delta, re-run the
engine on the mutated inputs, and assert ``iva.cuota-devengada-total`` shifted
by exactly that delta. If the engine were copying the printed box-27 total or
ignoring the primitive entirely, the post-mutation devengada-total would be
unchanged and the test would fail loudly.

Grounded authority:
    Orden EHA/3786/2008 art. 1 (box 27 = total cuota devengada).
    2023-y-siguientes ``modelo-303-iva-cuota-devengada-total`` formula
    (revision.toml lines 178-205): add(iva.repercutido.general,
    iva.repercutido.reducido, iva.repercutido.super-reducido,
    iva.autorepercutido.intracomunitaria, iva.autoconsumo.promotor.cuota).
"""

from __future__ import annotations

import pytest

from ._verification_chain_support import (
    _COMPUTED_CASILLAS_M303,
    _M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
    _M303_STATE_ATTRIBUTION_RATIO_CASILLA,
    BindingId,
    CasillaId,
    Decimal,
    _calculate_m303_engine_values_from_inputs,
    _casilla_id,
    _decimal_inputs_from_extracted_values,
    _parse_extracted_declaracion_values,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]

_IVA_REPERCUTIDO_GENERAL_CASILLA: CasillaId = _casilla_id("iva.repercutido.general")


def _run_engine(inputs: dict[CasillaId, Decimal], year: int, period: str) -> dict[CasillaId, Decimal]:
    """Calculate the registry snapshot with ``inputs`` and return engine values."""
    binding_values: dict[BindingId, Decimal] = {
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
    }
    return _calculate_m303_engine_values_from_inputs(
        inputs=inputs,
        year=year,
        period=period,
        binding_values=binding_values,
        label="M303 anti-tautology",
    )


def test_m303_engine_sums_extracted_primitives_not_printed_total() -> None:
    """Mutating ``iva.repercutido.general`` shifts ``iva.cuota-devengada-total`` by the same delta.

    Proves the engine is summing the primitive leaves rather than copying the
    printed box-27 total. A passing test guarantees that the verification-chain
    greens reflect genuine engine recomputation; a regression that lets the
    printed total leak into the engine (e.g. by an extraction profile change
    that bypasses the primitives) will fail this test loudly with a
    devengada-total that did not move under the mutation.
    """
    extracted = _parse_extracted_declaracion_values(modelo="303", fixture_stem="2023-1T", year=2023, period="1T")

    # Confirm the primitive leaf was extracted; otherwise the mutation probe
    # is meaningless (we would be poking a key the engine never reads).
    primitive = extracted.get(_IVA_REPERCUTIDO_GENERAL_CASILLA)
    assert isinstance(primitive, Decimal), (
        "ANTI-TAUTOLOGY-PRECONDITION-FAIL: 'iva.repercutido.general' missing or non-Decimal in extracted "
        "values. The fixture/extraction profile no longer delivers the primitive the engine sums into "
        f"iva.cuota-devengada-total.\n  got: {primitive!r}"
    )

    # Baseline inputs: every extracted non-computed Decimal leaf.
    base_inputs = _decimal_inputs_from_extracted_values(extracted, excluding=_COMPUTED_CASILLAS_M303)
    base_inputs[_M303_STATE_ATTRIBUTION_RATIO_CASILLA] = Decimal("100")

    base_values = _run_engine(base_inputs, 2023, "1T")
    base_devengada = base_values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA]

    # Mutate the primitive by a known delta and re-run.
    delta = Decimal("100.00")
    mutated_inputs = dict(base_inputs)
    mutated_inputs[_IVA_REPERCUTIDO_GENERAL_CASILLA] = primitive + delta
    mutated_values = _run_engine(mutated_inputs, 2023, "1T")
    mutated_devengada = mutated_values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA]

    assert mutated_devengada - base_devengada == delta, (
        "ANTI-TAUTOLOGY-FAIL: mutating iva.repercutido.general by "
        f"{delta} should shift iva.cuota-devengada-total by exactly that amount.\n"
        f"  base iva.repercutido.general    = {primitive!r}\n"
        f"  base iva.cuota-devengada-total  = {base_devengada!r}\n"
        f"  mutated iva.repercutido.general = {primitive + delta!r}\n"
        f"  mutated iva.cuota-devengada-total = {mutated_devengada!r}\n"
        f"  observed delta                  = {mutated_devengada - base_devengada!r}\n"
        "Failure modes covered: extraction profile copies printed total instead of primitive; "
        "engine formula no longer sums the primitive; engine substitutes zero default for the "
        "supplied primitive."
    )
