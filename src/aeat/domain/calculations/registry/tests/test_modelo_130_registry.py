"""Modelo 130 registry behaviour for direct-estimation instalment filings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import bundled_path
from .....tests.registry_observations import registry_grounded_modelo_observation
from .. import (
    CasillaId,
    ModeloDefinition,
    RegistryCatalogues,
    RegistryValidationError,
    build_snapshot,
    calculate_registry_snapshot,
    load_registry_tree,
    resolve_previous_filing_binding_values,
    validated_casilla_id,
)
from .._bindings import RegistryModeloObservation
from .._text import normalise_corpus_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ModeloFixture = tuple[ModeloDefinition, RegistryCatalogues]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"Modelo 130 registry fixture casilla key {value!r} is not a CasillaId") from exc


_M130_INGRESOS_CASILLA: CasillaId = _casilla_id("01")
_M130_GASTOS_CASILLA: CasillaId = _casilla_id("02")
_M130_PAGOS_PREVIOS_CASILLA: CasillaId = _casilla_id("05")
_M130_RETENCIONES_CASILLA: CasillaId = _casilla_id("06")
_M130_PAGO_FRACCIONADO_CASILLA: CasillaId = _casilla_id("07")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = _casilla_id("08")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = _casilla_id("10")
_M130_DIFERENCIA_PREVIA_CASILLA: CasillaId = _casilla_id("14")
_M130_CARRY_FORWARD_CASILLA: CasillaId = _casilla_id("15")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = _casilla_id("16")
_M130_DIFERENCIA_CASILLA: CasillaId = _casilla_id("17")
_M130_PRIOR_RETURN_CASILLA: CasillaId = _casilla_id("18")
_M130_SALDO_NEGATIVO_CASILLA: CasillaId = _casilla_id("saldo-negativo-fin-periodo")
_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: CasillaId = _casilla_id("0224")
_M100_RENDIMIENTO_SOURCE_1479_CASILLA: CasillaId = _casilla_id("1479")
_M100_RENDIMIENTO_SOURCE_1553_CASILLA: CasillaId = _casilla_id("1553")
_M100_RENDIMIENTO_SOURCE_1577_CASILLA: CasillaId = _casilla_id("1577")
_M100_RENDIMIENTO_SOURCE_CASILLAS = (
    _M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA,
    _M100_RENDIMIENTO_SOURCE_1479_CASILLA,
    _M100_RENDIMIENTO_SOURCE_1553_CASILLA,
    _M100_RENDIMIENTO_SOURCE_1577_CASILLA,
)
_REQUIRED_SURFACES = {
    "approval",
    "calculation",
    "deadline",
    "export",
    "extractor",
    "filing",
    "portal",
    "reconciliation",
    "review",
    "verification",
    "workflow",
}


def _load_modelo(modelo_id: str):
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == modelo_id)
    return modelo, catalogues


@pytest.fixture(scope="module")
def modelo_130_registry():
    return _load_modelo("130")


def _snapshot_130(modelo_130_registry: _ModeloFixture, *, period: str = "1T", filing_year: int = 2026):
    modelo, catalogues = modelo_130_registry
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period=period,
    )


def test_modelo_130_casilla_15_grounding_uses_aeat_instruction_citation(
    modelo_130_registry: _ModeloFixture,
) -> None:
    modelo, catalogues = modelo_130_registry

    art_110 = catalogues.legal["rd-439-2007:art-110"]
    art_110_required_text = normalise_corpus_text("\n".join(art_110.required_text))

    assert art_110.article == "110"
    assert "rd-439-2007:art-110-5" not in catalogues.legal
    assert "20 por ciento del rendimiento neto" in art_110.required_text
    assert "trimestres anteriores del mismo año" in art_110.required_text
    assert "resultados negativos" not in art_110_required_text
    assert "casilla 15" not in art_110_required_text
    assert "apartado 110.5 vigente" in art_110.notes

    revision = modelo.revisions["2019-y-siguientes"]
    carry_binding = next(
        binding for binding in revision.bindings if binding.id == "modelo-130-resultados-negativos-anteriores"
    )
    carry_casilla = next(casilla for casilla in revision.casillas if casilla.id == _M130_CARRY_FORWARD_CASILLA)
    instruction_source = catalogues.sources["aeat-modelo-130-instructions"]

    assert carry_binding.source == "previous_filing"
    assert carry_binding.selector == {
        "source_modelo": "130",
        "source_casilla_id": "saldo-negativo-fin-periodo",
        "source_period_offset_from_target": -1,
        "max_year_delta": 0,
    }
    assert carry_binding.source_refs == ("aeat-modelo-130-instructions",)
    assert carry_binding.source_citations
    assert carry_casilla.constraints.source_refs == ("aeat-modelo-130-instructions",)
    assert instruction_source.evidence_tier == "official_source_guidance"
    assert instruction_source.kind == "instructions"

    citation = carry_binding.source_citations[0]
    assert citation.source_ref == "aeat-modelo-130-instructions"
    assert "importe (sin signo) de los resultados negativos" in citation.required_text
    assert "en ningún caso podrá figurar en la casilla 15 un importe superior" in citation.required_text

    instruction_text = normalise_corpus_text((bundled_path() / instruction_source.corpus_path).read_text("utf-8"))
    for required_text in citation.required_text:
        assert normalise_corpus_text(required_text) in instruction_text


def test_modelo_130_validated_snapshot_owns_workflow_surfaces(modelo_130_registry: _ModeloFixture) -> None:
    modelo, catalogues = modelo_130_registry
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
    )

    construct = snapshot.revision.constructs[0]
    linked_by_surface = {
        link.surface: link for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert set(linked_by_surface) >= _REQUIRED_SURFACES
    assert all(link.requires_snapshot for link in linked_by_surface.values())


def test_modelo_130_requires_external_previous_year_income_binding_for_minoracion(
    modelo_130_registry: _ModeloFixture,
) -> None:
    with pytest.raises(RegistryValidationError, match="previous_year_economic_activity_net_income"):
        calculate_registry_snapshot(
            _snapshot_130(modelo_130_registry),
            inputs={_M130_INGRESOS_CASILLA: Decimal("12000.00"), _M130_GASTOS_CASILLA: Decimal("4000.00")},
            date_context={"filing_period": date(2026, 4, 20)},
            binding_values={"modelo-130-resultados-negativos-anteriores": Decimal("0")},
        )


def test_modelo_130_first_period_carry_forward_is_absent_by_design(modelo_130_registry: _ModeloFixture) -> None:
    """At 1T the prior-quarter carry-forward selector has no anchor.

    The Modelo 130 `modelo-130-resultados-negativos-anteriores`
    binding declares `source_period_offset_from_target = -1` and
    `max_year_delta = 0` to model AEAT's same-ejercicio instruction
    rule under the RD 439/2007 art. 110 pago-fraccionado framework:
    1T pulls from a hypothetical "0T" which
    does not exist within the same ejercicio, so the binding
    produces no anchor and casilla 15 materialises Decimal(0)
    through the absent-by-design constructor path. The
    `CasillaObservation` for C15 must carry
    `absent_by_design = True` so downstream audit surfaces can
    distinguish this structural zero from a value-bearing
    observation.

    Real-behaviour test: no mocks, no fakes. The 1T snapshot is
    built from the committed registry; the calculator runs
    end-to-end with no previous-filing observations supplied.
    """

    result = calculate_registry_snapshot(
        _snapshot_130(modelo_130_registry),
        inputs={
            _M130_INGRESOS_CASILLA: Decimal("10000"),
            _M130_GASTOS_CASILLA: Decimal("4000"),
            _M130_RETENCIONES_CASILLA: Decimal("100"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("2000"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("10"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
        },
        date_context={"filing_period": date(2026, 4, 20)},
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
        },
    )

    casilla_15 = next(obs for obs in result.observations if obs.casilla_id == _M130_CARRY_FORWARD_CASILLA)
    assert casilla_15.value == Decimal("0")
    assert casilla_15.absent_by_design is True

    # Casilla 05 (pagos fraccionados anteriores) is now a bound carry; at 1T the
    # expanding span has no prior same-ejercicio quarter, so it resolves to a
    # clean zero through the same absent-by-design path as casilla 15.
    casilla_05 = next(obs for obs in result.observations if obs.casilla_id == _M130_PAGOS_PREVIOS_CASILLA)
    assert casilla_05.value == Decimal("0")
    assert casilla_05.absent_by_design is True


def test_modelo_130_previous_filing_bound_casilla_input_without_binding_value_is_rejected(
    modelo_130_registry: _ModeloFixture,
) -> None:
    """Strict-rejection recovered via consistency hardening.

    The original design mandated `RegistryValidationError` when any
    bound-casilla input was supplied. The P03 narrowing accepted
    the production `resolve_bound_inputs_by_casilla_id` projection
    pattern (inputs mirrors binding_values for runtime ergonomics).
    The narrowing left a hole: a test fixture could lie by passing
    a previous_filing bound casilla via inputs ONLY, with no
    binding_values entry. The silent-zero hazard re-emerges in
    disguise.

    The consistency hardening closes the hole: previous_filing bound
    casillas in inputs MUST be accompanied by the matching
    binding_values[binding_id] entry. This test pins the strict-
    rejection contract for the smuggle-via-inputs-only pattern.
    """

    with pytest.raises(
        RegistryValidationError,
        match="previous-filing bound registry casillas cannot be supplied via inputs",
    ):
        calculate_registry_snapshot(
            _snapshot_130(modelo_130_registry),
            inputs={
                _M130_INGRESOS_CASILLA: Decimal("10000"),
                _M130_GASTOS_CASILLA: Decimal("4000"),
                _M130_RETENCIONES_CASILLA: Decimal("100"),
                _M130_AGRARIAN_VOLUME_CASILLA: Decimal("2000"),
                _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("10"),
                _M130_CARRY_FORWARD_CASILLA: Decimal("999"),  # smuggled — no matching binding_value
                _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
                _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
            },
            date_context={"filing_period": date(2026, 4, 20)},
            binding_values={
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
                # modelo-130-resultados-negativos-anteriores deliberately omitted
            },
        )


@pytest.mark.parametrize(
    ("target_period", "prior_period", "filing_date_month"),
    [("3T", "2T", 10), ("4T", "3T", 1)],
)
def test_modelo_130_third_and_fourth_quarter_carry_forward_picks_up_prior_quarter_saldo(
    modelo_130_registry: _ModeloFixture,
    target_period: str,
    prior_period: str,
    filing_date_month: int,
) -> None:
    """Extend regression coverage to 3T and 4T quarters.

    The companion case covers 2T-resolves-from-1T. Structurally the cap rule is
    identical for 3T→2T and 4T→3T, but the parametrised coverage
    locks the full quarterly chain so a future cap regression that
    only affects 3T or 4T cannot land silently.

    No tautological assertion: expected C15 is the prior period's
    saldo seed by binding contract (op=copy aggregation), not a
    re-derivation of any formula under test.
    """

    snapshot = _snapshot_130(modelo_130_registry, period=target_period)
    saldo_seed = Decimal("750.00")
    filing_year = 2026

    # The casilla-05 expanding-span carry now requires casilla 07 and casilla 16
    # observations on EVERY same-ejercicio quarter strictly preceding the target.
    # Seed each prior quarter with a chosen 07/16 pair (the prior quarter that
    # carries the saldo seed also carries its casilla 07 and 16). All prior 07
    # are positive here, so casilla 05 = Σ 07_q − Σ 16_q over the prior quarters.
    _PRIOR_07 = {"1T": Decimal("300.00"), "2T": Decimal("400.00"), "3T": Decimal("500.00")}
    _PRIOR_16 = {"1T": Decimal("20.00"), "2T": Decimal("30.00"), "3T": Decimal("40.00")}
    prior_quarters = {"3T": ("1T", "2T"), "4T": ("1T", "2T", "3T")}[target_period]

    def _prior_obs(period: str) -> RegistryModeloObservation:
        casilla_values = {
            _M130_PAGO_FRACCIONADO_CASILLA: _PRIOR_07[period],
            _M130_HOME_DEDUCTION_CASILLA: _PRIOR_16[period],
        }
        if period == prior_period:
            casilla_values[_M130_SALDO_NEGATIVO_CASILLA] = saldo_seed
        return registry_grounded_modelo_observation(
            modelo="130",
            filing_year=filing_year,
            period=period,
            casilla_values=casilla_values,
        )

    prior_observations = tuple(_prior_obs(period) for period in prior_quarters)
    prior_year_income_observation = registry_grounded_modelo_observation(
        modelo="100",
        filing_year=filing_year - 1,
        period="0A",
        casilla_values={cid: Decimal("0") for cid in _M100_RENDIMIENTO_SOURCE_CASILLAS},
    )

    resolved_bindings = resolve_previous_filing_binding_values(
        snapshot.revision,
        (*prior_observations, prior_year_income_observation),
        filing_year=filing_year,
        period=target_period,
    )

    assert resolved_bindings["modelo-130-resultados-negativos-anteriores"] == saldo_seed
    # casilla 05 = Σ max(0, 07_q) − Σ 16_q computed independently from the seeded
    # prior-quarter inputs (a different code path than the span binding).
    expected_casilla_05 = sum(
        (max(Decimal("0"), _PRIOR_07[q]) for q in prior_quarters),
        Decimal("0"),
    ) - sum((_PRIOR_16[q] for q in prior_quarters), Decimal("0"))
    assert resolved_bindings["modelo-130-pagos-fraccionados-anteriores"] == expected_casilla_05

    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            _M130_INGRESOS_CASILLA: Decimal("20000"),
            _M130_GASTOS_CASILLA: Decimal("8000"),
            _M130_RETENCIONES_CASILLA: Decimal("200"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("4000"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("20"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
        },
        date_context={
            "filing_period": date(
                filing_year if target_period != "4T" else filing_year + 1,
                filing_date_month,
                20,
            ),
        },
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            **resolved_bindings,
        },
    )

    casilla_15 = next(obs for obs in result.observations if obs.casilla_id == _M130_CARRY_FORWARD_CASILLA)
    assert casilla_15.value == saldo_seed
    assert casilla_15.absent_by_design is False
    casilla_05 = next(obs for obs in result.observations if obs.casilla_id == _M130_PAGOS_PREVIOS_CASILLA)
    assert casilla_05.value == expected_casilla_05
    assert casilla_05.absent_by_design is False


def test_modelo_130_previous_filing_bound_inputs_must_match_binding_values(modelo_130_registry: _ModeloFixture) -> None:
    """Inputs and binding_values must agree on bound carry-forward values.

    The consistency hardening introduced the smuggle-rejection (input present, binding
    value absent). This test pins the consistency-check that
    adds: when BOTH maps declare the same bound casilla but with
    DIFFERENT values, the runtime must reject the inconsistency
    rather than silently pick the binding_values entry. The source-
    of-truth contract is preserved while the divergence is surfaced.
    """

    with pytest.raises(
        RegistryValidationError,
        match="previous-filing bound casilla projection is inconsistent",
    ):
        calculate_registry_snapshot(
            _snapshot_130(modelo_130_registry, period="2T"),
            inputs={
                _M130_INGRESOS_CASILLA: Decimal("10000"),
                _M130_GASTOS_CASILLA: Decimal("4000"),
                _M130_RETENCIONES_CASILLA: Decimal("100"),
                _M130_AGRARIAN_VOLUME_CASILLA: Decimal("2000"),
                _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("10"),
                _M130_CARRY_FORWARD_CASILLA: Decimal("500"),  # claims 500
                _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
                _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
            },
            date_context={"filing_period": date(2026, 7, 20)},
            binding_values={
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
                "modelo-130-resultados-negativos-anteriores": Decimal("300"),  # claims 300 — diverges
            },
        )


def test_modelo_130_second_period_carry_forward_picks_up_first_period_saldo(
    modelo_130_registry: _ModeloFixture,
) -> None:
    """2T pulls the prior quarter's saldo-negativo-fin-periodo seed into C15.

    End-to-end real-behaviour test: build a 1T observation
    carrying `saldo-negativo-fin-periodo = 500` (the persisted seed
    produced when a 1T filing's casilla 17 ran negative), resolve
    the previous-filing bindings for a 2T snapshot through
    `resolve_previous_filing_binding_values`, pass the resolved
    map into `calculate_registry_snapshot`, and assert C15 in the
    2T calculation equals the 1T seed. C17 in 2T must then reflect
    the subtraction.

    The expected C15 value (Decimal('500')) is the 1T seed by
    construction, not a re-derivation of the formula under test —
    the binding's aggregation is `op = "copy"`, so C15 is required
    to equal the seed verbatim. No tautological assertion.
    """

    snapshot_2t = _snapshot_130(modelo_130_registry, period="2T")
    saldo_seed = Decimal("500.00")

    # The 1T filing carries casilla 07 and 16 (now read by the casilla-05
    # expanding-span carry) alongside the saldo seed.
    prior_07 = Decimal("450.00")
    prior_16 = Decimal("25.00")
    first_period_observation = registry_grounded_modelo_observation(
        modelo="130",
        filing_year=2026,
        period="1T",
        casilla_values={
            _M130_PAGO_FRACCIONADO_CASILLA: prior_07,
            _M130_HOME_DEDUCTION_CASILLA: prior_16,
            _M130_SALDO_NEGATIVO_CASILLA: saldo_seed,
        },
    )
    # The M100 income-reduction binding also resolves through the
    # previous-filing pipeline. Supply a zeroed 2025 0A observation
    # so the resolver completes; the test asserts the M130
    # carry-forward path independently.
    prior_year_income_observation = registry_grounded_modelo_observation(
        modelo="100",
        filing_year=2025,
        period="0A",
        casilla_values={cid: Decimal("0") for cid in _M100_RENDIMIENTO_SOURCE_CASILLAS},
    )

    resolved_bindings = resolve_previous_filing_binding_values(
        snapshot_2t.revision,
        (first_period_observation, prior_year_income_observation),
        filing_year=2026,
        period="2T",
    )

    assert resolved_bindings["modelo-130-resultados-negativos-anteriores"] == saldo_seed
    # 2T casilla 05 = max(0, 07_1T) − 16_1T over the single prior quarter.
    expected_casilla_05 = max(Decimal("0"), prior_07) - prior_16
    assert resolved_bindings["modelo-130-pagos-fraccionados-anteriores"] == expected_casilla_05

    result = calculate_registry_snapshot(
        snapshot_2t,
        inputs={
            _M130_INGRESOS_CASILLA: Decimal("16000"),
            _M130_GASTOS_CASILLA: Decimal("6000"),
            _M130_RETENCIONES_CASILLA: Decimal("250"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("3000"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("20"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
        },
        date_context={"filing_period": date(2026, 7, 20)},
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            **resolved_bindings,
        },
    )

    casilla_15 = next(obs for obs in result.observations if obs.casilla_id == _M130_CARRY_FORWARD_CASILLA)
    assert casilla_15.value == saldo_seed
    assert casilla_15.absent_by_design is False
    casilla_05 = next(obs for obs in result.observations if obs.casilla_id == _M130_PAGOS_PREVIOS_CASILLA)
    assert casilla_05.value == expected_casilla_05
    assert casilla_05.absent_by_design is False

    # Casilla 17 (diferencia) is `(C14 - C15) - C16`; the carry-forward
    # subtracts the seed from the gross diferencia. Structural assert:
    # C17 is strictly less than (C14 - C16) by the seed amount.
    casilla_14 = next(obs for obs in result.observations if obs.casilla_id == _M130_DIFERENCIA_PREVIA_CASILLA)
    casilla_16 = next(obs for obs in result.observations if obs.casilla_id == _M130_HOME_DEDUCTION_CASILLA)
    casilla_17 = next(obs for obs in result.observations if obs.casilla_id == _M130_DIFERENCIA_CASILLA)
    assert casilla_17.value == casilla_14.value - saldo_seed - casilla_16.value


# Note: the "silently_ignored" test that previously lived here
# (pinned the amendment's narrowed contract) was superseded by
# The strict-rejection contract is now restored for the
# smuggle-via-inputs-only pattern. The new
# test_modelo_130_previous_filing_bound_casilla_input_without_binding_value_is_rejected
# above is the harder gate.


# ---------------------------------------------------------------------------
# Art. 110.3.b RIRPF: high-retention exemption formula (casilla 17)
# ---------------------------------------------------------------------------


def test_modelo_130_art110_3b_casilla_17_is_zero_when_retention_ratio_meets_threshold(
    modelo_130_registry: _ModeloFixture,
) -> None:
    """Art. 110.3.b RIRPF: casilla 17 = 0 when retenciones/rendimientos >= 70%.

    Oracle values: rendimientos íntegros (c01) = 15000, retenciones (c06) = 10500.
    Ratio = 10500 / 15000 = 0.70 — exactly at the Art. 110.3.b threshold.
    The formula for casilla 17 (modelo-130-diferencia) must produce Decimal(0)
    because the autónomo is exempt from the quarterly payment.

    Expected value derivation: Art. 110.3.b RD 439/2007 mandates zero payment
    when the accumulated retention ratio >= 70% of gross income. This is not
    derived from the formula under test; it is derived from the regulatory rule.
    """
    result = calculate_registry_snapshot(
        _snapshot_130(modelo_130_registry),
        inputs={
            _M130_INGRESOS_CASILLA: Decimal("15000"),
            _M130_GASTOS_CASILLA: Decimal("5000"),
            _M130_RETENCIONES_CASILLA: Decimal("10500"),  # 10500/15000 = exactly 70%
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
        },
        date_context={"filing_period": date(2026, 4, 20)},
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
    )

    casilla_17 = next(obs for obs in result.observations if obs.casilla_id == _M130_DIFERENCIA_CASILLA)
    assert casilla_17.value == Decimal("0"), (
        f"Art. 110.3.b: casilla 17 must be zero when retention ratio >= 70%; got {casilla_17.value}"
    )


def test_modelo_130_art110_3b_casilla_17_computes_normally_when_retention_ratio_below_threshold(
    modelo_130_registry: _ModeloFixture,
) -> None:
    """Anti-tautology: casilla 17 equals the standard subtraction when retenciones/rendimientos < 70%.

    Oracle values: ingresos (c01) = 50000, gastos (c02) = 10000,
    rendimiento neto (c03) = 40000, retenciones (c06) = 1000.
    Ratio = 1000 / 50000 = 0.02 (2%) — well below the 70% threshold.
    Formula chain: c04=8000, c05=0, c07=7000, c12=7000, c13=0, c14=7000,
    c15=0, c16=0 → c17 = 7000 (standard subtraction, NOT the exemption zero).

    The ratio is deliberately far from 70% so this test is sensitive to any
    accidental triggering of the exemption branch. A regression that applied
    the exemption at 2% retention would produce c17=0, failing the assertion.

    Expected value derivation: standard M130 formula chain — not the Art. 110.3.b
    exemption rule under test. This is the anti-tautology proof that the formula
    branch condition is real and the exemption only fires at >= 70%.
    """
    result = calculate_registry_snapshot(
        _snapshot_130(modelo_130_registry),
        inputs={
            _M130_INGRESOS_CASILLA: Decimal("50000"),
            _M130_GASTOS_CASILLA: Decimal("10000"),
            # c03 (rendimiento neto) is computed via the
            # ``modelo-130-rendimiento-neto`` formula (c01 − c02);
            # supplying it as input would trip the computed-casilla gate.
            # c05 (pagos fraccionados anteriores) is a bound carry; at 1T the
            # expanding span is empty so it resolves to 0 absent-by-design.
            _M130_RETENCIONES_CASILLA: Decimal("1000"),  # 1000/50000 = 2% — well below threshold; c04=8000 > c06
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
        },
        date_context={"filing_period": date(2026, 4, 20)},
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
    )

    casilla_17 = next(obs for obs in result.observations if obs.casilla_id == _M130_DIFERENCIA_CASILLA)
    casilla_14 = next(obs for obs in result.observations if obs.casilla_id == _M130_DIFERENCIA_PREVIA_CASILLA)
    casilla_15 = next(obs for obs in result.observations if obs.casilla_id == _M130_CARRY_FORWARD_CASILLA)
    casilla_16 = next(obs for obs in result.observations if obs.casilla_id == _M130_HOME_DEDUCTION_CASILLA)

    # The standard subtraction formula: (c14 - c15) - c16
    expected = casilla_14.value - casilla_15.value - casilla_16.value
    assert casilla_17.value == expected, (
        f"Below-threshold case: casilla 17 must equal (c14-c15)-c16 = {expected}; got {casilla_17.value}"
    )
    # Anti-tautology: standard formula must yield a positive payment when income > costs
    # and retenciones are small. If c17 = 0 here, the exemption branch fired incorrectly.
    assert casilla_17.value != Decimal("0"), (
        "Below-threshold case: casilla 17 must not be zero when income=50000 and retenciones=1000 (2% ratio)"
    )
