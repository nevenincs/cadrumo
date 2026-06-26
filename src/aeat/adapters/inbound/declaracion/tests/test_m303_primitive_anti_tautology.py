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

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import resources
from .....domain.calculations.registry import (
    BindingId,
    CasillaId,
    RegistryValidationError,
    calculate_registry_snapshot,
    validated_casilla_id,
)
from .....tests import FIXTURES_DIR
from .. import DeclaracionParseError, parse_declaracion

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]

def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test_m303_primitive_anti_tautology.casilla")
    except ValueError as exc:
        raise AssertionError(f"M303 primitive test casilla key {value!r} is not a canonical casilla.id") from exc


def _casilla_ids(*values: object) -> frozenset[CasillaId]:
    return frozenset(_casilla_id(value) for value in values)


_IVA_REPERCUTIDO_GENERAL_CASILLA: CasillaId = _casilla_id("iva.repercutido.general")
_IVA_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = _casilla_id("iva.cuota-devengada-total")
_M303_STATE_ATTRIBUTION_RATIO_CASILLA: CasillaId = _casilla_id("65")

_COMPUTED_CASILLAS_M303: frozenset[CasillaId] = _casilla_ids(
    "iva.cuota-devengada-total",
    "iva.cuota-deducible-total",
    "iva.resultado-regimen-general",
    "03",
    "06",
    "09",
    "11",
    "13",
    "27",
    "29",
    "33",
    "37",
    "45",
    "64",
    "66",
    "iva.compensacion-aplicada-periodo",
    "iva.compensacion-pendiente-periodos-posteriores",
    "iva.resultado",
    "71",
    "iva.compensacion-generada-periodo",
    "iva.compensacion-disponible-fin-periodo",
)


def _run_engine(inputs: dict[CasillaId, Decimal], year: int, period: str) -> dict[CasillaId, Decimal]:
    """Calculate the registry snapshot with ``inputs`` and return engine values."""
    _period_month = {"1T": 1, "2T": 4, "3T": 7, "4T": 10}[period]
    snapshot = resources().modelos.authority.snapshot("303", filing_year=year, period=period)
    binding_values: dict[BindingId, Decimal] = {
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
    }
    try:
        result = calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            date_context={"filing_period": date(year, _period_month, 1)},
            binding_values=binding_values,
        )
    except RegistryValidationError as exc:  # pragma: no cover - diagnostic
        pytest.fail(
            "BINDING-GAP: calculate_registry_snapshot raised RegistryValidationError.\n"
            f"  error: {exc}\n"
            f"  inputs supplied: {sorted(inputs)}",
        )
    return dict(result.values)


def test_m303_engine_sums_extracted_primitives_not_printed_total() -> None:
    """Mutating ``iva.repercutido.general`` shifts ``iva.cuota-devengada-total`` by the same delta.

    Proves the engine is summing the primitive leaves rather than copying the
    printed box-27 total. A passing test guarantees that the verification-chain
    greens reflect genuine engine recomputation; a regression that lets the
    printed total leak into the engine (e.g. by an extraction profile change
    that bypasses the primitives) will fail this test loudly with a
    devengada-total that did not move under the mutation.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "303" / "2023-1T.pdf"
    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="303",
            año_override=2023,
            period_override="1T",
        )
    except DeclaracionParseError as exc:  # pragma: no cover - diagnostic
        pytest.fail(f"PARSER-GAP: parse_declaracion raised — M303 extraction failed.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    # Confirm the primitive leaf was extracted; otherwise the mutation probe
    # is meaningless (we would be poking a key the engine never reads).
    primitive = extracted.get(_IVA_REPERCUTIDO_GENERAL_CASILLA)
    assert isinstance(primitive, Decimal), (
        "ANTI-TAUTOLOGY-PRECONDITION-FAIL: 'iva.repercutido.general' missing or non-Decimal in extracted "
        "values. The fixture/extraction profile no longer delivers the primitive the engine sums into "
        f"iva.cuota-devengada-total.\n  got: {primitive!r}"
    )

    # Baseline inputs: every extracted non-computed Decimal leaf.
    base_inputs: dict[CasillaId, Decimal] = {}
    for casilla_id, value in extracted.items():
        if casilla_id in _COMPUTED_CASILLAS_M303:
            continue
        if not isinstance(value, Decimal):
            continue
        base_inputs[casilla_id] = value
    base_inputs[_M303_STATE_ATTRIBUTION_RATIO_CASILLA] = Decimal("100")

    base_values = _run_engine(base_inputs, 2023, "1T")
    base_devengada = base_values[_IVA_CUOTA_DEVENGADA_TOTAL_CASILLA]

    # Mutate the primitive by a known delta and re-run.
    delta = Decimal("100.00")
    mutated_inputs = dict(base_inputs)
    mutated_inputs[_IVA_REPERCUTIDO_GENERAL_CASILLA] = primitive + delta
    mutated_values = _run_engine(mutated_inputs, 2023, "1T")
    mutated_devengada = mutated_values[_IVA_CUOTA_DEVENGADA_TOTAL_CASILLA]

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
