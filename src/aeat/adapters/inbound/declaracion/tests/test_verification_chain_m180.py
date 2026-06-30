from __future__ import annotations

import pytest

from .....tests.registry_observations import registry_grounded_observations
from ._verification_chain_support import (
    FIXTURES_DIR,
    BindingId,
    CasillaId,
    Decimal,
    DeclaracionParseError,
    RegistryModeloObservation,
    RegistryValidationError,
    _registry_snapshot,
    calculate_registry_snapshot,
    date,
    parse_declaracion,
    resolve_bound_inputs_by_casilla_id,
    resolve_relation_values_from_observations,
    validated_casilla_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"test fixture casilla key {value!r} is not a canonical casilla.id") from exc


_DECL_TOTAL_PERCEPTORES_CASILLA: CasillaId = _casilla_id("decl.total-perceptores")
_DECL_BASE_TOTAL_CASILLA: CasillaId = _casilla_id("decl.base-total")
_DECL_RETENCIONES_TOTAL_CASILLA: CasillaId = _casilla_id("decl.retenciones-total")
_DECL_MONETARY_SUMMARY_CASILLAS: tuple[CasillaId, ...] = (
    _DECL_BASE_TOTAL_CASILLA,
    _DECL_RETENCIONES_TOTAL_CASILLA,
)
_M115_TOTAL_PERCEPTORES_CASILLA: CasillaId = _casilla_id("01")
_M115_BASE_TOTAL_CASILLA: CasillaId = _casilla_id("02")
_M115_RETENCIONES_CASILLA: CasillaId = _casilla_id("03")
_M180_PERCEPTORES_BINDING: BindingId = "modelo-180-115-perceptores-anual"
_M180_RETIRED_PERCEPTORES_RELATION = "modelo-180-rel-115-perceptores-anual"


def test_verification_chain_m180_engine_recomputes_closure_casillas_from_m115_relations_and_binding() -> None:
    """Engine recomputes M180 annual closure casillas from M115 relations and binding values.

    GROUNDED authority: synthetic M180 fixture at
    src/aeat/tests/fixtures/justificantes/180/2024-0A.pdf, derived from
    AEAT Orden HAP/1732/2014 printed form structure.  The fixture prints:
      decl.total-perceptores = 3       (dedicated annual perceptor binding)
      decl.base-total        = 12000.00 (sum of M115 casilla 02 across 4 quarters)
      decl.retenciones-total =  2280.00 (sum of M115 casilla 03 across 4 quarters)

    Legal grounding: Ley 35/2006 art.99; RD 439/2007 arts.100,108,109;
    Orden HAP/1732/2014 art.2; Orden HFP/1284/2023 art.7.

    Chain:
      1. Parse the 2024-0A M180 fixture -> extracted closure values.
      2. Build M115 quarterly observations whose monetary sums match the M180 totals.
      3. Resolve relation_values via resolve_relation_values_from_observations.
      4. Supply decl.total-perceptores through modelo-180-115-perceptores-anual.
      5. calculate_registry_snapshot(M180 snapshot, bound inputs, binding_values, relation_values).
      6. Assert perceptor count is bound, and monetary totals are relation-derived.

    Verdict: VERIFIED - the M115->M180 monetary relation chain resolves without
    resurrecting the retired quarterly perceptor-count relation.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "180" / "2024-0A.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="180",
            año_override=2024,
            period_override="0A",
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [M180/2024-0A engine]: parse_declaracion raised.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    perceptor_binding_value = Decimal("3")
    extracted_perceptors = extracted.get(_DECL_TOTAL_PERCEPTORES_CASILLA)
    assert extracted_perceptors == perceptor_binding_value, (
        f"PARSER-GAP [M180/2024-0A engine]: fixture printed {_DECL_TOTAL_PERCEPTORES_CASILLA!r} "
        f"as {extracted_perceptors!r}, expected {perceptor_binding_value!r}."
    )

    _m115_quarterly: dict[str, dict[CasillaId, Decimal]] = {
        "1T": {
            _M115_TOTAL_PERCEPTORES_CASILLA: Decimal("1"),
            _M115_BASE_TOTAL_CASILLA: Decimal("3000.00"),
            _M115_RETENCIONES_CASILLA: Decimal("570.00"),
        },
        "2T": {
            _M115_TOTAL_PERCEPTORES_CASILLA: Decimal("1"),
            _M115_BASE_TOTAL_CASILLA: Decimal("3000.00"),
            _M115_RETENCIONES_CASILLA: Decimal("570.00"),
        },
        "3T": {
            _M115_TOTAL_PERCEPTORES_CASILLA: Decimal("1"),
            _M115_BASE_TOTAL_CASILLA: Decimal("3000.00"),
            _M115_RETENCIONES_CASILLA: Decimal("570.00"),
        },
        "4T": {
            _M115_TOTAL_PERCEPTORES_CASILLA: Decimal("0"),
            _M115_BASE_TOTAL_CASILLA: Decimal("3000.00"),
            _M115_RETENCIONES_CASILLA: Decimal("570.00"),
        },
    }
    observations = tuple(
        RegistryModeloObservation(
            modelo="115",
            filing_year=2024,
            period=period,
            observations=registry_grounded_observations(
                modelo="115",
                filing_year=2024,
                period=period,
                casilla_values=casilla_values,
            ),
        )
        for period, casilla_values in sorted(_m115_quarterly.items())
    )

    snapshot = _registry_snapshot("180", 2024, "0A")
    try:
        relation_values = resolve_relation_values_from_observations(
            snapshot.revision,
            observations,
            filing_year=2024,
            period="0A",
        )
    except RegistryValidationError as exc:
        pytest.fail(
            f"BINDING-GAP [M180/2024-0A engine]: resolve_relation_values_from_observations raised "
            f"RegistryValidationError - M115->M180 relation chain is structurally broken.\n"
            f"  error: {exc}",
        )
    assert _M180_RETIRED_PERCEPTORES_RELATION not in relation_values, (
        f"BINDING-GAP [M180/2024-0A engine]: retired quarterly perceptor relation "
        f"{_M180_RETIRED_PERCEPTORES_RELATION!r} was resolved. Perceptor count must flow through "
        f"{_M180_PERCEPTORES_BINDING!r}."
    )

    binding_values: dict[BindingId, Decimal] = {_M180_PERCEPTORES_BINDING: perceptor_binding_value}
    try:
        result = calculate_registry_snapshot(
            snapshot,
            inputs=resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
            date_context={"filing_period": date(2024, 12, 31)},
            binding_values=binding_values,
            relation_values=relation_values,
        )
    except RegistryValidationError as exc:
        pytest.fail(
            f"BINDING-GAP [M180/2024-0A engine]: calculate_registry_snapshot raised "
            f"RegistryValidationError - engine could not recompute from supplied relation_values.\n"
            f"  error: {exc}\n"
            f"  binding_values keys: {sorted(binding_values)}\n"
            f"  relation_values keys: {sorted(relation_values)}",
        )

    engine_values = dict(result.values)
    entries_by_target = {entry.target_casilla_id: entry for entry in result.entries}

    assert _DECL_TOTAL_PERCEPTORES_CASILLA not in entries_by_target, (
        f"FORMULA-MISMATCH [M180/2024-0A engine]: {_DECL_TOTAL_PERCEPTORES_CASILLA!r} was produced "
        "by a formula entry, but this casilla must be bound."
    )
    assert engine_values.get(_DECL_TOTAL_PERCEPTORES_CASILLA) == perceptor_binding_value, (
        f"FORMULA-MISMATCH [M180/2024-0A engine]: engine resolved {_DECL_TOTAL_PERCEPTORES_CASILLA!r} "
        f"as {engine_values.get(_DECL_TOTAL_PERCEPTORES_CASILLA)!r}, expected binding "
        f"{_M180_PERCEPTORES_BINDING!r} value {perceptor_binding_value!r}."
    )

    for casilla_id in _DECL_MONETARY_SUMMARY_CASILLAS:
        extracted_value = extracted.get(casilla_id)
        engine_value = engine_values.get(casilla_id)
        assert extracted_value is not None, (
            f"PARSER-GAP [M180/2024-0A engine]: closure casilla {casilla_id!r} absent from extracted values"
        )
        assert isinstance(extracted_value, Decimal), (
            f"PARSER-GAP [M180/2024-0A engine]: {casilla_id!r} is not Decimal: {type(extracted_value).__name__!r}"
        )
        assert engine_value is not None, (
            f"FORMULA-MISMATCH [M180/2024-0A engine]: casilla {casilla_id!r} absent from engine result - "
            f"formula evaluation order issue or casilla missing from revision."
        )
        assert engine_value == extracted_value, (
            f"FORMULA-MISMATCH [M180/2024-0A engine]: engine recomputed {casilla_id!r} as "
            f"{engine_value!r} but AEAT-printed fixture shows {extracted_value!r}.\n"
            f"  diff: {engine_value - extracted_value!r}\n"
            f"  binding_values supplied: {binding_values}\n"
            f"  relation_values supplied: {relation_values}"
        )
