"""Modelo 130 registry behaviour for direct-estimation instalment filings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.resources import bundled_path

from . import (
    RegistryValidationError,
    build_snapshot,
    calculate_registry_snapshot,
    load_registry_tree,
)
from ._bindings import (
    CasillaObservation,
    RegistryModeloObservation,
    resolve_previous_filing_binding_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
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


def _snapshot_130(modelo_130_registry, *, period: str = "1T", filing_year: int = 2026):
    modelo, catalogues = modelo_130_registry
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period=period,
    )


def test_modelo_130_validated_snapshot_owns_workflow_surfaces(modelo_130_registry) -> None:
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


def test_modelo_130_requires_external_previous_year_income_binding_for_minoracion(modelo_130_registry) -> None:
    with pytest.raises(RegistryValidationError, match="previous_year_economic_activity_net_income"):
        calculate_registry_snapshot(
            _snapshot_130(modelo_130_registry),
            inputs={"01": Decimal("12000.00"), "02": Decimal("4000.00")},
            date_context={"filing_period": date(2026, 4, 20)},
            binding_values={"modelo-130-resultados-negativos-anteriores": Decimal("0")},
        )


def test_modelo_130_first_period_carry_forward_is_absent_by_design(modelo_130_registry) -> None:
    """At 1T the prior-quarter carry-forward selector has no anchor.

    The Modelo 130 `modelo-130-resultados-negativos-anteriores`
    binding declares `source_period_offset_from_target = -1` and
    `max_year_delta = 0` to model AEAT's RD 439/2007 art. 110.5
    same-ejercicio rule: 1T pulls from a hypothetical "0T" which
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
            "01": Decimal("10000"),
            "02": Decimal("4000"),
            "05": Decimal("250"),
            "06": Decimal("100"),
            "08": Decimal("2000"),
            "10": Decimal("10"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        date_context={"filing_period": date(2026, 4, 20)},
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
        },
    )

    casilla_15 = next(obs for obs in result.observations if obs.casilla_id == "15")
    assert casilla_15.value == Decimal("0")
    assert casilla_15.absent_by_design is True


def test_modelo_130_second_period_carry_forward_picks_up_first_period_saldo(modelo_130_registry) -> None:
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

    first_period_observation = RegistryModeloObservation(
        modelo="130",
        filing_year=2026,
        period="1T",
        observations=(
            CasillaObservation(casilla_id="saldo-negativo-fin-periodo", value=saldo_seed),
        ),
    )
    # The M100 income-reduction binding also resolves through the
    # previous-filing pipeline. Supply a zeroed 2025 0A observation
    # so the resolver completes; the test asserts the M130
    # carry-forward path independently.
    prior_year_income_observation = RegistryModeloObservation(
        modelo="100",
        filing_year=2025,
        period="0A",
        observations=tuple(
            CasillaObservation(casilla_id=cid, value=Decimal("0"))
            for cid in ("0224", "1479", "1553", "1577")
        ),
    )

    resolved_bindings = resolve_previous_filing_binding_values(
        snapshot_2t.revision,
        (first_period_observation, prior_year_income_observation),
        filing_year=2026,
        period="2T",
    )

    assert resolved_bindings["modelo-130-resultados-negativos-anteriores"] == saldo_seed

    result = calculate_registry_snapshot(
        snapshot_2t,
        inputs={
            "01": Decimal("16000"),
            "02": Decimal("6000"),
            "05": Decimal("500"),
            "06": Decimal("250"),
            "08": Decimal("3000"),
            "10": Decimal("20"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        date_context={"filing_period": date(2026, 7, 20)},
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            **resolved_bindings,
        },
    )

    casilla_15 = next(obs for obs in result.observations if obs.casilla_id == "15")
    assert casilla_15.value == saldo_seed
    assert casilla_15.absent_by_design is False

    # Casilla 17 (diferencia) is `(C14 - C15) - C16`; the carry-forward
    # subtracts the seed from the gross diferencia. Structural assert:
    # C17 is strictly less than (C14 - C16) by the seed amount.
    casilla_14 = next(obs for obs in result.observations if obs.casilla_id == "14")
    casilla_16 = next(obs for obs in result.observations if obs.casilla_id == "16")
    casilla_17 = next(obs for obs in result.observations if obs.casilla_id == "17")
    assert casilla_17.value == casilla_14.value - saldo_seed - casilla_16.value


def test_modelo_130_previous_filing_bound_casilla_input_is_silently_ignored(modelo_130_registry) -> None:
    """Inputs targeting a previous-filing bound casilla are ignored.

    The narrowed P03 runtime contract: bound casillas whose binding
    source is `previous_filing` resolve EXCLUSIVELY through
    `binding_values` or the absent-by-design path. The inputs
    mapping path that historically allowed silent zero-fill is
    closed for this binding source. Passing
    `inputs={"15": Decimal("100")}` for the 1T snapshot (where the
    M130 carry-forward selector returns no anchor) yields
    C15 = Decimal("0") with `absent_by_design = True` — the input
    value is silently discarded, not honoured.

    The original ADR Decision Z2 mandated a hard rejection
    (`RegistryValidationError` on any bound-casilla input). The
    narrower contract was adopted during P03 implementation
    because the production `resolve_bound_casilla_inputs` helper
    legitimately projects binding values into the inputs mapping
    as a runtime convenience, and non-numeric bound casillas (NIF,
    text) historically use the inputs fallback. The strict-
    rejection follow-up is tracked at plan step P06.S21.
    """

    result = calculate_registry_snapshot(
        _snapshot_130(modelo_130_registry),
        inputs={
            "01": Decimal("10000"),
            "02": Decimal("4000"),
            "05": Decimal("250"),
            "06": Decimal("100"),
            "08": Decimal("2000"),
            "10": Decimal("10"),
            "15": Decimal("100"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        date_context={"filing_period": date(2026, 4, 20)},
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
        },
    )

    casilla_15 = next(obs for obs in result.observations if obs.casilla_id == "15")
    assert casilla_15.value == Decimal("0")
    assert casilla_15.absent_by_design is True
