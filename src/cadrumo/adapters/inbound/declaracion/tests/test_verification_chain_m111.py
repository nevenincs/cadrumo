"""M111 verification-chain tests over declaracion PDF fixtures."""

from __future__ import annotations

import pytest

from ._verification_chain_support import (
    _COMPUTED_CASILLAS_M111,
    CasillaId,
    _assert_engine_closure_matches_extracted_decimal,
    _calculate_engine_values_from_inputs,
    _casilla_id,
    _casilla_ids,
    _decimal_inputs_from_extracted_values,
    _parse_extracted_declaracion_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_M111_RETENCIONES_TOTAL_CASILLA: CasillaId = _casilla_id("28")
_M111_RESULTADO_CASILLA: CasillaId = _casilla_id("30")
_M111_RETENCIONES_TOTAL_LEAVES: frozenset[CasillaId] = _casilla_ids(
    "03",
    "06",
    "09",
    "12",
    "15",
    "18",
    "21",
    "24",
    "27",
)


_M111_QUARTER_CASES = (
    # (pdf_stem, year, period, casillas the render prints, casillas it can close)
    ("2024-1T", 2024, "1T", _casilla_ids("07", "08", "09", "28", "30"), _casilla_ids("28", "30")),
    ("2024-2T", 2024, "2T", _casilla_ids("07", "08", "09", "28", "30"), _casilla_ids("28", "30")),
    ("2024-3T", 2024, "3T", _casilla_ids("07", "08", "09", "28", "30"), _casilla_ids("28", "30")),
    # The 4T render prints casilla 30 alone — no retenciones leaf and no
    # casilla 28 — so nothing is closure-checkable from it. Declaring an empty
    # closure set makes that explicit: the case still asserts parse fidelity,
    # and the leaves-vs-closure invariant below fails if the render ever starts
    # or stops printing leaves without this table being updated to match.
    ("2024-4T", 2024, "4T", _casilla_ids("30"), frozenset()),
)


@pytest.mark.parametrize(
    "pdf_stem,year,period,expected_extracted_casillas,closure_casillas",
    _M111_QUARTER_CASES,
)
def test_verification_chain_m111_engine_recomputes_closure_casillas_28_and_30(
    pdf_stem: str,
    year: int,
    period: str,
    expected_extracted_casillas: frozenset[CasillaId],
    closure_casillas: frozenset[CasillaId],
) -> None:
    """Parse each M111 justificante render, then close 28/30 wherever leaves exist.

    WHAT THIS VERIFIES. Two things, both real:

    * Parse fidelity — each committed render yields exactly the casilla set it
      is declared to yield. The set is pinned per case, so a parser regression
      that drops or invents a casilla fails here rather than silently shrinking
      the closure check to nothing.
    * Engine closure — where the render prints a retenciones leaf, the engine
      recomputes casilla 28 (total retenciones, sum of the leaves) and casilla
      30 (resultado) and they agree with the render's own printed totals.

    WHAT THIS DOES NOT VERIFY: that any amount is what AEAT would compute. The
    111 fixtures are ``provenance = "real_corpus"``, ``role = "parser_anchor"``
    — real AEAT renders whose amounts the redaction pipeline replaced with the
    uniform placeholder ``1000.00``. Their layout and labels are authoritative;
    their numbers are not. Because engine and expected value are both derived
    from that same placeholder, the closure holds for any amount, and the 1T-3T
    sum degenerates to a single non-zero term. Calling this AEAT-grounded, as an
    earlier docstring did, was false.

    WHERE A REAL ORACLE PLUGS IN: an AEAT worked example for M111 belongs in
    ``corpus/manual_oracles/`` as ``modelo-111-<year>-<scenario>.json`` with
    ``expected_by_casilla_id``, and the casillas declared in the M111 revision's
    ``externally_grounded_casilla_ids``. ``test_external_oracle_grounding_enrolled.py``
    then binds it in both directions. No such oracle is bundled for M111 today.
    """
    extracted = _parse_extracted_declaracion_values(modelo="111", fixture_stem=pdf_stem, year=year, period=period)

    assert frozenset(extracted) == expected_extracted_casillas, (
        f"PARSER-GAP [{pdf_stem}]: extracted casilla set drifted.\n"
        f"  expected: {sorted(expected_extracted_casillas)}\n"
        f"  got:      {sorted(extracted)}"
    )

    inputs = _decimal_inputs_from_extracted_values(extracted, excluding=_COMPUTED_CASILLAS_M111)
    engine_values = _calculate_engine_values_from_inputs(
        modelo="111",
        year=year,
        period=period,
        label=pdf_stem,
        inputs=inputs,
    )

    # A case may only claim a closure it can actually compute: closing casilla
    # 28 requires at least one retenciones leaf, otherwise the "closure" would
    # compare a printed total against an empty sum and pass vacuously. Binding
    # the two together means a parser change that drops the leaves turns the
    # affected case red instead of silently reducing it to a no-op — which is
    # exactly how the 4T case used to pass while asserting nothing.
    has_leaf_inputs = bool(inputs.keys() & _M111_RETENCIONES_TOTAL_LEAVES)
    assert has_leaf_inputs == bool(closure_casillas), (
        f"PARSER-GAP [{pdf_stem}]: retenciones leaves present={has_leaf_inputs} but the case "
        f"declares closure casillas {sorted(closure_casillas)}. A render with no leaf cannot "
        f"close a total, and a render with leaves should be closing one."
    )
    assert closure_casillas <= frozenset(extracted), (
        f"PARSER-GAP [{pdf_stem}]: declared closure casillas {sorted(closure_casillas)} "
        f"are not all present in the extracted set {sorted(extracted)}."
    )

    for casilla_id in sorted(closure_casillas):
        _assert_engine_closure_matches_extracted_decimal(
            label=pdf_stem,
            engine_values=engine_values,
            extracted=extracted,
            casilla_id=casilla_id,
            inputs=inputs,
        )
