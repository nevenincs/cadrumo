"""M111 verification-chain tests over declaracion PDF fixtures.

Modelo 111 carries NO rate, bracket or coefficient. Its whole computation is
two definitional rules the órden states in prose:

    casilla 28 = 03 + 06 + 09 + 12 + 15 + 18 + 21 + 24 + 27
    casilla 30 = 28 - 29

For a rule of that shape the grounding artefact is the órden's stated
aggregation, not a numeric worked example: what must be proven is that the
engine sums exactly the epígrafes AEAT names. Numbers are probes for that, not
facts in their own right. Both rules are declared in the M111 registry revision
with ``source_citations`` quoting the instrucciones ("suma de las retenciones e
ingresos a cuenta", "por todos los conceptos"), so the citation lives in the
registry and this module exercises it.

That splits the coverage in two, matching what each fixture class can support:

* :func:`test_verification_chain_m111_parses_each_committed_render` reads the
  committed renders. They are ``role = "parser_anchor"`` specimens, so parse
  fidelity is exactly what they are evidence of.
* :func:`test_verification_chain_m111_aggregates_the_epigrafes_the_orden_names`
  drives the arithmetic with distinct probe amounts of its own. A parser_anchor
  render cannot supply them: it prints five casillas out of the nine the sum
  needs, whatever its amounts are.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from .....core.casilla_id import validated_casilla_id
from .....tests import FIXTURES_DIR
from ._verification_chain_support import (
    _COMPUTED_CASILLAS_M111,
    CasillaId,
    _calculate_engine_values_from_inputs,
    _decimal_inputs_from_extracted_values,
    _parse_extracted_declaracion_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_M111_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id("28")
_M111_PAGOS_ANTERIORES_CASILLA: CasillaId = validated_casilla_id("29")
_M111_RESULTADO_CASILLA: CasillaId = validated_casilla_id("30")

#: The nine epígrafe totals the órden names as the operands of casilla 28.
#:
#: Order matters only for readability; the aggregation is a sum. The list is the
#: registry formula ``modelo-111-total-retenciones-ingresos``'s declared operand
#: set, and this test exists to prove the engine sums exactly these.
_M111_RETENCIONES_TOTAL_LEAVES: tuple[CasillaId, ...] = (
    validated_casilla_id("03"),
    validated_casilla_id("06"),
    validated_casilla_id("09"),
    validated_casilla_id("12"),
    validated_casilla_id("15"),
    validated_casilla_id("18"),
    validated_casilla_id("21"),
    validated_casilla_id("24"),
    validated_casilla_id("27"),
)

#: One distinct probe per epígrafe, plus a distinct prior-autoliquidación amount.
#:
#: PROBES, NOT AN ORACLE. These amounts are chosen here and assert no tax fact;
#: no filing and no tax outcome is claimed. They are pairwise distinct and
#: non-round so the assertion can tell a genuine nine-operand sum apart from a
#: max, a first- or last-element pick, a partial sum over a subset, or a
#: hardcoded constant. Identical amounts cannot distinguish any of those, which
#: is why the committed renders — every amount redacted to ``1000.00`` — cannot
#: carry this assertion however authentic the document they came from.
_M111_EPIGRAFE_PROBES: dict[CasillaId, Decimal] = {
    validated_casilla_id("03"): Decimal("111.11"),
    validated_casilla_id("06"): Decimal("222.22"),
    validated_casilla_id("09"): Decimal("333.33"),
    validated_casilla_id("12"): Decimal("444.44"),
    validated_casilla_id("15"): Decimal("555.55"),
    validated_casilla_id("18"): Decimal("666.66"),
    validated_casilla_id("21"): Decimal("777.77"),
    validated_casilla_id("24"): Decimal("888.88"),
    validated_casilla_id("27"): Decimal("999.99"),
}
_M111_PAGOS_ANTERIORES_PROBE = Decimal("1234.56")

_M111_QUARTER_CASES = (
    # (pdf_stem, year, period, the casilla set this render prints)
    ("2024-1T", 2024, "1T", frozenset(validated_casilla_id(_v) for _v in ("07", "08", "09", "28", "30"))),
    ("2024-2T", 2024, "2T", frozenset(validated_casilla_id(_v) for _v in ("07", "08", "09", "28", "30"))),
    ("2024-3T", 2024, "3T", frozenset(validated_casilla_id(_v) for _v in ("07", "08", "09", "28", "30"))),
    # The 4T render prints casilla 30 alone. Pinning that explicitly is what
    # makes this case assert something: before the set was pinned, 4T supplied
    # no inputs, executed no assertion, and still reported success.
    ("2024-4T", 2024, "4T", frozenset(validated_casilla_id(_v) for _v in ("30",))),
)


@pytest.mark.parametrize("pdf_stem,year,period,expected_extracted_casillas", _M111_QUARTER_CASES)
def test_verification_chain_m111_parses_each_committed_render(
    pdf_stem: str,
    year: int,
    period: str,
    expected_extracted_casillas: frozenset[CasillaId],
) -> None:
    """Each committed M111 render parses to exactly the casilla set it declares.

    This is a PARSE-FIDELITY test over ``role = "parser_anchor"`` fixtures, and
    that is the whole of its claim. The specimens WERE real AEAT renders; they
    were withdrawn for carrying name-shaped strings the redaction pipeline never
    wrote, and what stands in their place reproduces their printed layout. Their
    numbers are probes chosen by the fixture generator, so no arithmetic is
    asserted against them here -- the aggregation test below drives that from
    its own probes instead. The role is checked rather than assumed, so a
    fixture re-stamped as a formula specimen cannot silently land in a
    parse-fidelity test.

    Pinning the casilla set per render is what gives the 4T case content: it
    prints casilla 30 alone, and an earlier version of this test guarded its
    every assertion on leaf inputs 4T does not have, so the case passed while
    verifying nothing.
    """
    sidecar_path = FIXTURES_DIR / "justificantes" / "111" / f"{pdf_stem}.json"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar.get("role") == "parser_anchor", (
        f"{sidecar_path.name} declares role {sidecar.get('role')!r}; this test reads it as a "
        f"parse-fidelity anchor and asserts no arithmetic over its redacted amounts."
    )

    extracted = _parse_extracted_declaracion_values(modelo="111", fixture_stem=pdf_stem, year=year, period=period)

    assert frozenset(extracted) == expected_extracted_casillas, (
        f"PARSER-GAP [{pdf_stem}]: extracted casilla set drifted.\n"
        f"  expected: {sorted(expected_extracted_casillas)}\n"
        f"  got:      {sorted(extracted)}"
    )

    # The parsed casilla ids must be ones the engine accepts as inputs: this is
    # the parse -> engine seam, and it is verified without asserting anything
    # about the placeholder amounts that flow through it.
    inputs = _decimal_inputs_from_extracted_values(extracted, excluding=_COMPUTED_CASILLAS_M111)
    engine_values = _calculate_engine_values_from_inputs(
        modelo="111",
        year=year,
        period=period,
        label=pdf_stem,
        inputs=inputs,
    )
    for computed_id in (_M111_RETENCIONES_TOTAL_CASILLA, _M111_RESULTADO_CASILLA):
        assert isinstance(engine_values.get(computed_id), Decimal), (
            f"FORMULA-MISMATCH [{pdf_stem}]: casilla {computed_id!r} absent or non-Decimal in the "
            f"engine result, so the parsed inputs did not reach the formula DAG.\n"
            f"  inputs: {sorted(inputs)}"
        )


def test_verification_chain_m111_aggregates_the_epigrafes_the_orden_names() -> None:
    """Casilla 28 sums exactly the nine epígrafes, and casilla 30 subtracts 29.

    GROUNDING: the órden's stated aggregation rule, not a numeric example.
    Modelo 111 has no rate or bracket, so there is nothing a worked example
    could ground that the rule does not already fix. AEAT states casilla 28 as
    "la suma de las retenciones e ingresos a cuenta que, por todos los
    conceptos, se hayan hecho constar en los epígrafes anteriores", and the M111
    registry revision declares that formula with a ``source_citations`` entry
    requiring exactly that wording. What must be proven is that the engine sums
    those nine epígrafes and no others.

    The probe amounts are pairwise distinct (see ``_M111_EPIGRAFE_PROBES``), so
    this fails if the engine picks one operand, sums a subset, or returns a
    constant. Asserting against the arithmetic sum of the probes is not
    tautological: the sum is computed here from the operand list the ÓRDEN
    names, while the engine computes from the operand list the REGISTRY
    declares. A registry formula that dropped casilla 24, or added a casilla the
    órden does not list, diverges and fails.
    """
    engine_values = _calculate_engine_values_from_inputs(
        modelo="111",
        year=2024,
        period="1T",
        label="M111/probe/aggregation",
        inputs={**_M111_EPIGRAFE_PROBES, _M111_PAGOS_ANTERIORES_CASILLA: _M111_PAGOS_ANTERIORES_PROBE},
    )

    expected_28 = sum(_M111_EPIGRAFE_PROBES[leaf] for leaf in _M111_RETENCIONES_TOTAL_LEAVES)
    engine_28 = engine_values.get(_M111_RETENCIONES_TOTAL_CASILLA)
    assert engine_28 == expected_28, (
        f"AGGREGATION-MISMATCH: casilla 28 must be the sum of the nine epígrafes the órden "
        f"names {[str(leaf) for leaf in _M111_RETENCIONES_TOTAL_LEAVES]}.\n"
        f"  engine:   {engine_28!r}\n"
        f"  expected: {expected_28!r}\n"
        f"  probes:   { {str(k): str(v) for k, v in _M111_EPIGRAFE_PROBES.items()} }"
    )

    expected_30 = expected_28 - _M111_PAGOS_ANTERIORES_PROBE
    engine_30 = engine_values.get(_M111_RESULTADO_CASILLA)
    assert engine_30 == expected_30, (
        f"AGGREGATION-MISMATCH: casilla 30 must be casilla 28 minus casilla 29.\n"
        f"  engine:   {engine_30!r}\n"
        f"  expected: {expected_30!r} (= {expected_28!r} - {_M111_PAGOS_ANTERIORES_PROBE!r})"
    )


def test_verification_chain_m111_epigrafe_probe_values_are_pairwise_distinct() -> None:
    """The probes must stay distinct, or the aggregation assertion loses its power.

    This is the guard on the guard. The M111 aggregation test can only tell a
    sum from a max or a first-element pick because its nine probe amounts
    differ; a well-meaning edit that made them uniform would leave that test
    green while silently gutting it — which is precisely the failure this
    module was rewritten to remove.
    """
    probes = list(_M111_EPIGRAFE_PROBES.values())
    assert len(set(probes)) == len(probes), f"epígrafe probes must be pairwise distinct, got {probes!r}"
    assert set(_M111_EPIGRAFE_PROBES) == set(_M111_RETENCIONES_TOTAL_LEAVES), (
        "every epígrafe the órden names must carry a probe, and no others: "
        f"probes={sorted(_M111_EPIGRAFE_PROBES)} leaves={sorted(_M111_RETENCIONES_TOTAL_LEAVES)}"
    )
