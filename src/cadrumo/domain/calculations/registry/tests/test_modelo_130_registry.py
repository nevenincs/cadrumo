"""Modelo 130 registry behaviour for direct-estimation instalment filings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.bindings_previous_filing import resolve_previous_filing_binding_values
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.validate import RegistryValidator

from .....core import CasillaId, normalise_corpus_text, validated_casilla_id
from .....core.resources import bundled_path
from .....tests.registry_observations import registry_grounded_modelo_observation
from ..authority import bundled_authority
from ..binding_selector_utils import selector_as_dict
from ..bindings import RegistryModeloObservation
from ..temporal import select_revision
from ._registry_schema_support import _committed_modelo, _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ModeloFixture = tuple[ModeloDefinition, RegistryCatalogues]


_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02")
_M130_PAGOS_PREVIOS_CASILLA: CasillaId = validated_casilla_id("05")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06")
_M130_PAGO_FRACCIONADO_CASILLA: CasillaId = validated_casilla_id("07")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10")
_M130_DIFERENCIA_PREVIA_CASILLA: CasillaId = validated_casilla_id("14")
_M130_CARRY_FORWARD_CASILLA: CasillaId = validated_casilla_id("15")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16")
_M130_DIFERENCIA_CASILLA: CasillaId = validated_casilla_id("17")
_M130_PRIOR_RETURN_CASILLA: CasillaId = validated_casilla_id("18")
_M130_SALDO_NEGATIVO_CASILLA: CasillaId = validated_casilla_id("saldo-negativo-fin-periodo")
_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: CasillaId = validated_casilla_id("0224")
_M100_RENDIMIENTO_SOURCE_1479_CASILLA: CasillaId = validated_casilla_id("1479")
_M100_RENDIMIENTO_SOURCE_1553_CASILLA: CasillaId = validated_casilla_id("1553")
_M100_RENDIMIENTO_SOURCE_1577_CASILLA: CasillaId = validated_casilla_id("1577")
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
    "workflow",
}
_M130_EXTRACTION_PROFILE_TARGET_LEGAL_REFS = frozenset(
    {
        "ley-35-2006:art-27",
        "ley-35-2006:art-28",
        "ley-35-2006:art-30",
        "ley-35-2006:art-99",
        "orden-eha-672-2007:art-1",
        "rd-439-2007:art-110",
        "rd-439-2007:art-95",
    }
)
_M130_SUPPORTED_DEADLINES = {
    2022: (
        ("2022-04-20", "2022-04-15"),
        ("2022-07-20", "2022-07-15"),
        ("2022-10-20", "2022-10-15"),
        ("2023-01-30", "2023-01-25"),
    ),
    2023: (
        ("2023-04-20", "2023-04-15"),
        ("2023-07-20", "2023-07-15"),
        ("2023-10-20", "2023-10-15"),
        ("2024-01-30", "2024-01-25"),
    ),
    2024: (
        ("2024-04-22", "2024-04-17"),
        ("2024-07-22", "2024-07-17"),
        ("2024-10-21", "2024-10-16"),
        ("2025-01-30", "2025-01-27"),
    ),
    2025: (
        ("2025-04-21", "2025-04-15"),
        ("2025-07-21", "2025-07-16"),
        ("2025-10-20", "2025-10-15"),
        ("2026-01-30", "2026-01-27"),
    ),
    2026: (
        ("2026-04-20", "2026-04-15"),
        ("2026-07-20", "2026-07-15"),
        ("2026-10-20", "2026-10-15"),
        ("2027-01-30", None),
    ),
}


@pytest.fixture(scope="module")
def modelo_130_registry():
    return _committed_modelo("130")


def _snapshot_130(_modelo_130_registry: _ModeloFixture, *, period: str = "1T", filing_year: int = 2026):
    return _committed_snapshot("130", filing_year, period)


def test_modelo_130_supported_year_deadline_census_dates_sources_and_ownership(
    modelo_130_registry: _ModeloFixture,
) -> None:
    modelo, catalogues = modelo_130_registry
    revision = modelo.revisions["2019-y-siguientes"]
    windows = {(window.filing_year, window.period.registry_token): window for window in revision.deadline_windows}

    assert len(revision.deadline_windows) == len(windows) == 20
    assert set(revision.constructs[0].deadline_windows) == {window.id for window in revision.deadline_windows}
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    calendar_refs = {f"aeat-calendario-contribuyente-{year}" for year in range(2022, 2027)}
    assert calendar_refs <= set(revision.source_refs)
    assert calendar_refs <= set(revision.constructs[0].source_refs)
    for source_ref in calendar_refs:
        source = catalogues.sources[source_ref]
        assert (source.authority, source.evidence_tier) == ("aeat", "official_source_guidance")
        assert (bundled_path() / source.corpus_path).is_file()

    for filing_year, expected_deadlines in _M130_SUPPORTED_DEADLINES.items():
        expected_periods = {"1T", "2T", "3T", "4T"}
        assert {period for year, period in windows if year == filing_year} == expected_periods
        projected = bundled_authority().deadline_windows(filing_year, modelos=("130",))
        assert len(projected) == 4
        assert {window.period.registry_token for _, _, window in projected} == expected_periods

        for quarter, (close_text, cutoff_text) in enumerate(expected_deadlines, start=1):
            period = f"{quarter}T"
            window = windows[(filing_year, period)]
            assert select_revision(modelo, filing_year=filing_year, period=period) is revision
            assert window.id == f"modelo-130-{filing_year}-{period.lower()}"
            assert window.filing_year == window.period.filing_year == filing_year
            assert window.opens_on == date(window.closes_on.year, window.closes_on.month, 1)
            assert window.closes_on == date.fromisoformat(close_text)
            assert window.payment_cutoff_on == (None if cutoff_text is None else date.fromisoformat(cutoff_text))
            expected_sources = {"aeat-modelo-130-instructions"}
            if window.closes_on.year <= 2026:
                expected_sources.add(f"aeat-calendario-contribuyente-{window.closes_on.year}")
            assert set(window.source_refs) == expected_sources

    assert windows[(2026, "4T")].payment_cutoff_on is None


def test_modelo_130_extraction_profile_legal_refs_match_target_casillas(
    modelo_130_registry: _ModeloFixture,
) -> None:
    modelo, _catalogues = modelo_130_registry
    revision = modelo.revisions["2019-y-siguientes"]
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
    profile = next(item for item in revision.extraction_profiles if item.id == "modelo-130-declaracion-pdf")
    target_refs = frozenset(
        legal_ref for target in profile.target_casillas for legal_ref in casillas_by_id[target.casilla_id].legal_refs
    )

    assert target_refs == _M130_EXTRACTION_PROFILE_TARGET_LEGAL_REFS
    assert set(profile.legal_refs) == _M130_EXTRACTION_PROFILE_TARGET_LEGAL_REFS


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
    assert art_110.notes is not None
    assert "apartado 110.5 vigente" in art_110.notes

    revision = modelo.revisions["2019-y-siguientes"]
    carry_binding = next(
        binding for binding in revision.bindings if binding.id == "modelo-130-resultados-negativos-anteriores"
    )
    carry_casilla = next(casilla for casilla in revision.casillas if casilla.id == _M130_CARRY_FORWARD_CASILLA)
    instruction_source = catalogues.sources["aeat-modelo-130-instructions"]

    assert carry_binding.source == "previous_filing"
    assert selector_as_dict(carry_binding) == {
        "source_modelo": "130",
        "source_casilla_id": _M130_SALDO_NEGATIVO_CASILLA,
        "source_period_offset_from_target": -1,
        "max_year_delta": 0,
    }
    assert carry_binding.source_refs == ("aeat-modelo-130-instructions",)
    assert carry_binding.source_citations
    assert carry_casilla.input_kind is InputKind.COMPUTED
    assert carry_casilla.formula == "modelo-130-resultados-negativos-anteriores-cap"
    assert carry_casilla.binding is None
    assert carry_casilla.constraints is not None
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


def test_modelo_130_art109_profile_advisory_is_not_a_casilla_17_formula_branch(
    modelo_130_registry: _ModeloFixture,
) -> None:
    modelo, _catalogues = modelo_130_registry
    revision = modelo.revisions["2019-y-siguientes"]
    formula = next(item for item in revision.formulas if item.id == "modelo-130-diferencia")
    predicate = next(
        item
        for item in revision.verification_predicates
        if item.predicate_id == "modelo-130-art109-exencion-alta-retencion"
    )

    assert "rd-439-2007:art-109" not in formula.legal_refs
    assert "rd-439-2007:art-110-3-b" not in formula.legal_refs
    expression = formula.expression
    assert expression.op == "subtract"
    assert len(expression.args) == 2
    assert expression.args[0].op == "subtract"
    assert tuple(arg.casilla_id for arg in expression.args[0].args) == ("14", "15")
    assert expression.args[1].casilla_id == "16"
    assert predicate.expression == 'profile_flag_enabled("art109_activity_income_withholding_ge_70pct")'
    assert predicate.legal_refs == ("rd-439-2007:art-109",)


def test_modelo_130_validated_snapshot_owns_workflow_surfaces(modelo_130_registry: _ModeloFixture) -> None:
    snapshot = _snapshot_130(modelo_130_registry)

    construct = snapshot.revision.constructs[0]
    linked_by_surface = {
        link.surface: link for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert set(linked_by_surface) >= _REQUIRED_SURFACES
    assert all(link.requires_snapshot for link in linked_by_surface.values())


def test_validator_rejects_missing_relationless_direct_settlement_classification(
    modelo_130_registry: _ModeloFixture,
) -> None:
    """The direct same-modelo carries cannot lose their declared settlement treatment."""
    modelo, catalogues = modelo_130_registry
    revision = modelo.revisions["2019-y-siguientes"]
    classification = next(item for item in revision.dependency_classifications if item.source_modelo == "130")
    construct = next(item for item in revision.constructs if classification.id in item.dependency_classifications)
    mutated_construct = construct.model_copy(
        update={
            "dependency_classifications": tuple(
                item for item in construct.dependency_classifications if item != classification.id
            ),
        },
    )
    mutated_revision = revision.model_copy(
        update={
            "dependency_classifications": tuple(
                item for item in revision.dependency_classifications if item.id != classification.id
            ),
            "constructs": tuple(item if item.id != construct.id else mutated_construct for item in revision.constructs),
        },
    )
    mutated_modelo = modelo.model_copy(
        update={"revisions": {**modelo.revisions, revision.id: mutated_revision}},
    )

    with pytest.raises(
        RegistryValidationError,
        match=r"previous_filing source modelo '130' has no dependency classification",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


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


def test_modelo_130_first_period_carry_forward_defaults_to_zero_for_capped_formula(
    modelo_130_registry: _ModeloFixture,
) -> None:
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
    assert casilla_15.formula_id == "modelo-130-resultados-negativos-anteriores-cap"
    assert "modelo-130-resultados-negativos-anteriores" in casilla_15.operand_refs
    assert casilla_15.absent_by_design is False

    # Casilla 05 (pagos fraccionados anteriores) is now a bound carry; at 1T the
    # expanding span has no prior same-ejercicio quarter, so it resolves to a
    # clean zero through the same absent-by-design path as casilla 15.
    casilla_05 = next(obs for obs in result.observations if obs.casilla_id == _M130_PAGOS_PREVIOS_CASILLA)
    assert casilla_05.value == Decimal("0")
    assert casilla_05.absent_by_design is True


def test_modelo_130_capped_carry_forward_casilla_input_is_rejected(
    modelo_130_registry: _ModeloFixture,
) -> None:
    with pytest.raises(
        RegistryValidationError,
        match="computed registry casillas cannot be supplied as inputs",
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
    with pytest.raises(
        RegistryValidationError,
        match="observation-backed bound casilla projection is inconsistent",
    ):
        calculate_registry_snapshot(
            _snapshot_130(modelo_130_registry, period="2T"),
            inputs={
                _M130_INGRESOS_CASILLA: Decimal("10000"),
                _M130_GASTOS_CASILLA: Decimal("4000"),
                _M130_RETENCIONES_CASILLA: Decimal("100"),
                _M130_AGRARIAN_VOLUME_CASILLA: Decimal("2000"),
                _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("10"),
                _M130_PAGOS_PREVIOS_CASILLA: Decimal("500"),  # claims 500
                _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
                _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
            },
            date_context={"filing_period": date(2026, 7, 20)},
            binding_values={
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
                "modelo-130-pagos-fraccionados-anteriores": Decimal("300"),  # claims 300 — diverges
                "modelo-130-resultados-negativos-anteriores": Decimal("0"),
            },
        )


def test_modelo_130_carry_forward_caps_prior_negative_seed_at_positive_c14(
    modelo_130_registry: _ModeloFixture,
) -> None:
    snapshot_2t = _snapshot_130(modelo_130_registry, period="2T")
    first_period_observation = registry_grounded_modelo_observation(
        modelo="130",
        filing_year=2026,
        period="1T",
        casilla_values={
            _M130_PAGO_FRACCIONADO_CASILLA: Decimal("38.00"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_SALDO_NEGATIVO_CASILLA: Decimal("62.00"),
        },
    )
    prior_year_income_observation = registry_grounded_modelo_observation(
        modelo="100",
        filing_year=2025,
        period="0A",
        casilla_values={
            _M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: Decimal("20000.00"),
            _M100_RENDIMIENTO_SOURCE_1479_CASILLA: Decimal("0"),
            _M100_RENDIMIENTO_SOURCE_1553_CASILLA: Decimal("0"),
            _M100_RENDIMIENTO_SOURCE_1577_CASILLA: Decimal("0"),
        },
    )
    resolved_bindings = resolve_previous_filing_binding_values(
        snapshot_2t.revision,
        (first_period_observation, prior_year_income_observation),
        filing_year=2026,
        period="2T",
    )

    assert resolved_bindings["modelo-130-resultados-negativos-anteriores"] == Decimal("62.00")
    assert resolved_bindings["modelo-130-pagos-fraccionados-anteriores"] == Decimal("38.00")

    result = calculate_registry_snapshot(
        snapshot_2t,
        inputs={
            _M130_INGRESOS_CASILLA: Decimal("377"),
            _M130_GASTOS_CASILLA: Decimal("0"),
            _M130_RETENCIONES_CASILLA: Decimal("0"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
        },
        date_context={"filing_period": date(2026, 7, 20)},
        binding_values=resolved_bindings,
    )

    assert result.values[_M130_DIFERENCIA_PREVIA_CASILLA] == Decimal("37.40")
    assert result.values[_M130_CARRY_FORWARD_CASILLA] == Decimal("37.40")
    assert result.values[_M130_DIFERENCIA_CASILLA] == Decimal("0.00")


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
# Modelo 130 casilla 17 official form formula
# ---------------------------------------------------------------------------


def test_modelo_130_high_casilla_06_amount_does_not_zero_casilla_17(
    modelo_130_registry: _ModeloFixture,
) -> None:
    """Casilla 06 is retenciones amount, so c06/c01 does not create an Art. 109 zero branch.

    A positive apartado-II lane keeps the official casilla 17 result non-zero,
    making the retired branch observable.
    """
    result = calculate_registry_snapshot(
        _snapshot_130(modelo_130_registry),
        inputs={
            _M130_INGRESOS_CASILLA: Decimal("15000"),
            _M130_GASTOS_CASILLA: Decimal("5000"),
            _M130_RETENCIONES_CASILLA: Decimal("10500"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("1000000"),
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

    expected = casilla_14.value - casilla_15.value - casilla_16.value
    assert expected != Decimal("0")
    assert casilla_17.value == expected


def test_modelo_130_casilla_17_uses_standard_subtraction_for_low_retention_amount(
    modelo_130_registry: _ModeloFixture,
) -> None:
    """Casilla 17 equals the standard subtraction when the retained amount is small too.

    Oracle values: ingresos (c01) = 50000, gastos (c02) = 10000,
    rendimiento neto (c03) = 40000, retenciones (c06) = 1000.
    Formula chain: c04=8000, c05=0, c07=7000, c12=7000, c13=0, c14=7000,
    c15=0, c16=0 -> c17 = 7000.
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
            _M130_RETENCIONES_CASILLA: Decimal("1000"),
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
    # Standard formula must yield a positive payment when income > costs and
    # retenciones are small.
    assert casilla_17.value != Decimal("0"), "casilla 17 must not be zero when income=50000 and retenciones=1000"


# ---------------------------------------------------------------------------
# Retención article distinction (Art. 101.5 vs the misattributed "Art. 101.6
# sport/art"). Two grounded guards: (1) M130 has no retención-rate
# computation home, so no activity-article branch belongs in it; (2) the
# sport/artistic professional rate is the REDUCED 7% of art. 95.1.d RIRPF, not a
# distinct 15% "Art. 101.6" case.
# ---------------------------------------------------------------------------


def test_modelo_130_retencion_casilla_is_reported_amount_not_a_rate_computation(
    modelo_130_registry: _ModeloFixture,
) -> None:
    """M130 carries no retención-rate computation, so no Art. 101.5/101.6 branch.

    The retención RATE on professional activities is set by the PAYER under
    art. 95 RIRPF (developing art. 101.5 LIRPF) and reported on Modelo 111;
    Modelo 130 never computes it. In M130 the suffered retención enters as a
    manually-reported amount (casilla 06) subtracted by the official form
    arithmetic. There is therefore no place in M130 to branch
    a retención treatment on the activity article, so the "Art. 101.6
    sport/art" axis has no M130 calculation home: art. 95 RIRPF grounds the
    reported amount's provenance, not a rate the form derives.
    """
    modelo, _catalogues = modelo_130_registry
    revision = modelo.revisions["2019-y-siguientes"]
    retenciones = next(casilla for casilla in revision.casillas if casilla.id == _M130_RETENCIONES_CASILLA)

    assert retenciones.input_kind is InputKind.MANUAL
    assert retenciones.binding is None
    assert retenciones.formula is None
    # The retención provision (art. 95 RIRPF) grounds the reported amount's
    # provenance; it is not a rate the form computes.
    assert "rd-439-2007:art-95" in retenciones.legal_refs


def test_art_95_rirpf_grounds_sport_and_artistic_activity_at_reduced_7pct(
    modelo_130_registry: _ModeloFixture,
) -> None:
    """Issue #549 grounding: sport/artistic professional activity is the REDUCED
    7% retención of art. 95.1.d RIRPF, not a distinct 15% "Art. 101.6" case.

    The round-22 testimonial asserted an "Art. 101.6 LIRPF (deportivo/artístico)"
    at 15% distinct from the general professional 15% of art. 101.5. Grounded
    against the bundled consolidated RIRPF, that premise is wrong: art. 95.1
    RIRPF sets the general professional rate at 15% and a REDUCED 7% rate for
    contributors in the artistic/sport IAE groups (sección segunda grupos
    851-869 and sección tercera agrupaciones 01/02/03/05 — cine, danza, música,
    espectáculos). There is no 15% sport/art carve-out to model.

    Expected wording is derived from the bundled authoritative consolidated
    RIRPF (rd-439-2007 art. 95), not hand-restated: the test would fail if a
    future change encoded the testimonial's wrong 15% sport/art rate.
    """
    _modelo, catalogues = modelo_130_registry
    art_95 = catalogues.legal["rd-439-2007:art-95"]

    assert art_95.article == "95"
    # The registry declares both the general 15% and the reduced 7% rate; the
    # legal evidence gate cross-checks these phrases against the corpus at build.
    joined_required = "\n".join(art_95.required_text)
    assert "15 por ciento sobre los ingresos íntegros" in joined_required
    assert "7 por ciento" in joined_required

    # Cross-check against the bundled authoritative corpus: the reduced 7% rate
    # is the one that enumerates the artistic/sport IAE groups, and the artistic
    # groups appear only after (within) the 7% clause — never under a 15% rate.
    corpus_path = art_95.corpus_ref.split("#", 1)[0]
    corpus_text = (bundled_path() / f"{corpus_path}.extracted.md").read_text("utf-8")
    normalised = normalise_corpus_text(corpus_text)

    seven_pct_index = normalised.find(normalise_corpus_text("7 por ciento"))
    fifteen_pct_index = normalised.find(normalise_corpus_text("15 por ciento"))
    seccion_tercera_index = normalised.find(normalise_corpus_text("sección tercera"))
    grupo_851_index = normalised.find(normalise_corpus_text("851"))

    # The corpus states the general professional 15% rate first, then the
    # reduced 7% rate, whose clause enumerates the artistic/sport IAE groups.
    assert fifteen_pct_index != -1
    assert seven_pct_index != -1
    assert fifteen_pct_index < seven_pct_index
    assert seccion_tercera_index > seven_pct_index
    assert grupo_851_index > seven_pct_index
