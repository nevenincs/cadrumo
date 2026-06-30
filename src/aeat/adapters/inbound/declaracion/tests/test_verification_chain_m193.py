from __future__ import annotations

import pytest

from ._verification_chain_support import (
    FIXTURES_DIR,
    BindingId,
    CasillaId,
    Decimal,
    DeclaracionParseError,
    RegistryValidationError,
    _casilla_id,
    _registry_modelo_observations_from_values,
    _registry_snapshot,
    calculate_registry_snapshot,
    date,
    parse_declaracion,
    resolve_bound_inputs_by_casilla_id,
    resolve_relation_values_from_observations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


_DECL_TOTAL_PERCEPTORES_CASILLA: CasillaId = _casilla_id("decl.total-perceptores")
_DECL_BASE_TOTAL_CASILLA: CasillaId = _casilla_id("decl.base-total")
_DECL_RETENCIONES_TOTAL_CASILLA: CasillaId = _casilla_id("decl.retenciones-total")
_DECL_MONETARY_SUMMARY_CASILLAS: tuple[CasillaId, ...] = (
    _DECL_BASE_TOTAL_CASILLA,
    _DECL_RETENCIONES_TOTAL_CASILLA,
)
_M123_TOTAL_RENTAS_CASILLA: CasillaId = _casilla_id("03")
_M123_TOTAL_BASE_CASILLA: CasillaId = _casilla_id("06")
_M123_TOTAL_RETENCIONES_CASILLA: CasillaId = _casilla_id("09")
_M193_PERCEPTORES_BINDING: BindingId = "modelo-193-123-perceptores-anual"
_M193_RETIRED_PERCEPTORES_RELATION = "modelo-193-rel-123-perceptores-anual"


def test_verification_chain_m193_engine_recomputes_closure_casillas_from_m123_relations_and_binding() -> None:
    """Engine recomputes M193 annual closure casillas from M123 relations and binding values.

    GROUNDED authority: synthetic M193 fixture at
    src/aeat/tests/fixtures/justificantes/193/2024-0A.pdf.  The fixture prints:
      decl.total-perceptores = 2      (dedicated annual perceptor binding)
      decl.base-total        = 8000.00 (sum of M123 casilla 06 across 4 quarters)
      decl.retenciones-total = 1520.00 (sum of M123 casilla 09 across 4 quarters)

    Legal grounding: Ley 35/2006 art.25, art.99; RD 439/2007 art.109, art.108,
    art.90, art.101; Orden EHA/3377/2011 art.1; Ley 58/2003 art.93.

    Chain:
      1. Parse the 2024-0A M193 fixture -> extracted closure values.
      2. Build M123 quarterly observations whose monetary sums match the M193 totals.
      3. Resolve relation_values via resolve_relation_values_from_observations.
      4. Supply decl.total-perceptores through modelo-193-123-perceptores-anual.
      5. calculate_registry_snapshot(M193 snapshot, bound inputs, binding_values, relation_values).
      6. Assert perceptor count is bound, and monetary totals are relation-derived.

    NOTE: The relation uses M123 2024-y-siguientes casillas 03, 06, 09 which are
    all computed by the engine (not manual inputs). The observations must supply
    them directly as CasillaObservation (representing engine-computed outputs from
    prior quarterly filing runs), not as engine inputs for the current run.

    Verdict: VERIFIED - the M123->M193 monetary relation chain resolves without
    resurrecting the retired quarterly perceptor-count relation.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "193" / "2024-0A.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="193",
            año_override=2024,
            period_override="0A",
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [M193/2024-0A engine]: parse_declaracion raised.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    perceptor_binding_value = Decimal("2")
    extracted_perceptors = extracted.get(_DECL_TOTAL_PERCEPTORES_CASILLA)
    assert extracted_perceptors == perceptor_binding_value, (
        f"PARSER-GAP [M193/2024-0A engine]: fixture printed {_DECL_TOTAL_PERCEPTORES_CASILLA!r} "
        f"as {extracted_perceptors!r}, expected {perceptor_binding_value!r}."
    )

    _m123_quarterly: dict[str, dict[CasillaId, Decimal]] = {
        "1T": {
            _M123_TOTAL_RENTAS_CASILLA: Decimal("2"),
            _M123_TOTAL_BASE_CASILLA: Decimal("2000.00"),
            _M123_TOTAL_RETENCIONES_CASILLA: Decimal("380.00"),
        },
        "2T": {
            _M123_TOTAL_RENTAS_CASILLA: Decimal("0"),
            _M123_TOTAL_BASE_CASILLA: Decimal("2000.00"),
            _M123_TOTAL_RETENCIONES_CASILLA: Decimal("380.00"),
        },
        "3T": {
            _M123_TOTAL_RENTAS_CASILLA: Decimal("0"),
            _M123_TOTAL_BASE_CASILLA: Decimal("2000.00"),
            _M123_TOTAL_RETENCIONES_CASILLA: Decimal("380.00"),
        },
        "4T": {
            _M123_TOTAL_RENTAS_CASILLA: Decimal("0"),
            _M123_TOTAL_BASE_CASILLA: Decimal("2000.00"),
            _M123_TOTAL_RETENCIONES_CASILLA: Decimal("380.00"),
        },
    }
    observations = _registry_modelo_observations_from_values(
        modelo="123",
        filing_year=2024,
        period_values=_m123_quarterly,
    )

    snapshot = _registry_snapshot("193", 2024, "0A")
    try:
        relation_values = resolve_relation_values_from_observations(
            snapshot.revision,
            observations,
            filing_year=2024,
            period="0A",
        )
    except RegistryValidationError as exc:
        pytest.fail(
            f"BINDING-GAP [M193/2024-0A engine]: resolve_relation_values_from_observations raised "
            f"RegistryValidationError - M123->M193 relation chain is structurally broken.\n"
            f"  error: {exc}",
        )
    assert _M193_RETIRED_PERCEPTORES_RELATION not in relation_values, (
        f"BINDING-GAP [M193/2024-0A engine]: retired quarterly perceptor relation "
        f"{_M193_RETIRED_PERCEPTORES_RELATION!r} was resolved. Perceptor count must flow through "
        f"{_M193_PERCEPTORES_BINDING!r}."
    )

    binding_values: dict[BindingId, Decimal] = {_M193_PERCEPTORES_BINDING: perceptor_binding_value}
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
            f"BINDING-GAP [M193/2024-0A engine]: calculate_registry_snapshot raised "
            f"RegistryValidationError - engine could not recompute from supplied relation_values.\n"
            f"  error: {exc}\n"
            f"  binding_values keys: {sorted(binding_values)}\n"
            f"  relation_values keys: {sorted(relation_values)}",
        )

    engine_values = dict(result.values)
    entries_by_target = {entry.target_casilla_id: entry for entry in result.entries}

    assert _DECL_TOTAL_PERCEPTORES_CASILLA not in entries_by_target, (
        f"FORMULA-MISMATCH [M193/2024-0A engine]: {_DECL_TOTAL_PERCEPTORES_CASILLA!r} was produced "
        "by a formula entry, but this casilla must be bound."
    )
    assert engine_values.get(_DECL_TOTAL_PERCEPTORES_CASILLA) == perceptor_binding_value, (
        f"FORMULA-MISMATCH [M193/2024-0A engine]: engine resolved {_DECL_TOTAL_PERCEPTORES_CASILLA!r} "
        f"as {engine_values.get(_DECL_TOTAL_PERCEPTORES_CASILLA)!r}, expected binding "
        f"{_M193_PERCEPTORES_BINDING!r} value {perceptor_binding_value!r}."
    )

    for casilla_id in _DECL_MONETARY_SUMMARY_CASILLAS:
        extracted_value = extracted.get(casilla_id)
        engine_value = engine_values.get(casilla_id)
        assert extracted_value is not None, (
            f"PARSER-GAP [M193/2024-0A engine]: closure casilla {casilla_id!r} absent from extracted values"
        )
        assert isinstance(extracted_value, Decimal), (
            f"PARSER-GAP [M193/2024-0A engine]: {casilla_id!r} is not Decimal: {type(extracted_value).__name__!r}"
        )
        assert engine_value is not None, (
            f"FORMULA-MISMATCH [M193/2024-0A engine]: casilla {casilla_id!r} absent from engine result - "
            f"formula evaluation order issue or casilla missing from revision."
        )
        assert engine_value == extracted_value, (
            f"FORMULA-MISMATCH [M193/2024-0A engine]: engine recomputed {casilla_id!r} as "
            f"{engine_value!r} but AEAT-printed fixture shows {extracted_value!r}.\n"
            f"  diff: {engine_value - extracted_value!r}\n"
            f"  binding_values supplied: {binding_values}\n"
            f"  relation_values supplied: {relation_values}"
        )
