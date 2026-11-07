"""Core ledger IVA aggregation binding tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

import pytest
from _pytest.mark import ParameterSet
from pydantic import ValidationError

from cadrumo.core.aggregation import BindingAggregationOp
from cadrumo.domain.calculations.registry.binding_value_contract import (
    BindingDataType,
    BindingValueChannel,
    BindingValueContract,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.ledger_iva_bindings import (
    IvaLedgerObservation,
    LedgerIvaProvider,
    resolve_ledger_iva_aggregation_binding_values,
    unsupported_ledger_iva_observations,
    validate_ledger_iva_aggregation_binding,
    validate_ledger_iva_aggregation_binding_definition,
)
from cadrumo.domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.iva.schema import IvaLedgerObservationRole
from dev.registry.compiler.authority import compiled_bundled_authority

from .ledger_iva_aggregation_support import (
    M303_AUTOREPERCUTIDO_INTERIOR_DEDUCIBLE_CASILLA,
    M303_AUTOREPERCUTIDO_INTERIOR_DEVENGADO_CASILLA,
    M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
    M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
    calculate_303_from_observations,
    cash_treatment,
    deduction_authority,
    deduction_kind,
    exemption,
    ledger_iva_aggregation_binding,
    ledger_iva_aggregation_category,
    ledger_iva_aggregation_flow,
    ledger_iva_aggregation_observation,
    ledger_iva_aggregation_rate_kind,
    revision_with_bindings,
    with_aggregation,
    with_selector,
)

_MONEY_VALUE = BindingValueContract(data_type=BindingDataType.MONEY, channel=BindingValueChannel.DECIMAL)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = filing_year_envelope().horizon


def test_validate_accepts_canonical_iva_repercutido_binding() -> None:
    binding = ledger_iva_aggregation_binding()
    assert binding.id == "modelo-303-iva-repercutido-general-cuota"
    assert binding.provider, "binding must declare a selector for validation to be meaningful"
    with validating_governed_facts(compiled_bundled_authority()):
        result = validate_ledger_iva_aggregation_binding_definition(binding)
    assert result is None


_MALFORMED_SELECTOR_CASES = (
    pytest.param({"categories": ("bogus",)}, id="unknown-category"),
    pytest.param({"rate_kinds": ("medium",)}, id="unknown-rate-kind"),
    pytest.param({"flow_direction": "unknown"}, id="unknown-flow-direction"),
    pytest.param({"categories": ()}, id="empty-categories"),
    pytest.param({"rate_kinds": ()}, id="empty-rate-kinds"),
    pytest.param({"fact": "bogus"}, id="unknown-fact"),
)


@pytest.mark.parametrize("selector_updates", _MALFORMED_SELECTOR_CASES)
def test_validate_rejects_malformed_selector(selector_updates: dict[str, object]) -> None:
    binding = with_selector(ledger_iva_aggregation_binding(), **selector_updates)
    with validating_governed_facts(compiled_bundled_authority()):
        failures = validate_ledger_iva_aggregation_binding(binding)
    assert failures, "the registry build gate must reject a malformed typed provider member"


def test_validate_rejects_non_sum_aggregation() -> None:
    with (
        validating_governed_facts(compiled_bundled_authority()),
        pytest.raises(
            RegistryValidationError,
            match="aggregation op 'sum'",
        ),
    ):
        validate_ledger_iva_aggregation_binding_definition(
            with_aggregation(ledger_iva_aggregation_binding(), BindingAggregationOp.COPY)
        )


def test_validate_rejects_wrong_source_kind() -> None:
    binding = with_selector(ledger_iva_aggregation_binding(), kind="manual_input")
    with pytest.raises(RegistryValidationError, match="not a ledger_iva_aggregation"):
        validate_ledger_iva_aggregation_binding_definition(binding)


def _article_filter_binding(**selector_updates: object) -> BindingDefinition:
    selector: dict[str, object] = {
        "categories": (ledger_iva_aggregation_category("domestic_exempt"),),
        "exemption_articles": (exemption("art_20_uno_14"),),
        "rate_kinds": (ledger_iva_aggregation_rate_kind("exempt"),),
        "flow_direction": ledger_iva_aggregation_flow("repercutido"),
        "fact": "base_amount_sum",
        "observation_roles": (IvaLedgerObservationRole.SETTLEMENT,),
        "cash_accounting_treatments": (
            cash_treatment("none"),
            cash_treatment("supplier_regime"),
        ),
    }
    selector.update(selector_updates)
    with validating_governed_facts(compiled_bundled_authority()):
        return BindingDefinition(
            id="test-art-20-base",
            provider=LedgerIvaProvider.model_validate(selector),
            value=_MONEY_VALUE,
            legal_refs=("ley-37-1992:art-20",),
            source_refs=("test-source",),
        )


def _minimal_revision_with_bindings(*bindings: BindingDefinition) -> ModeloRevision:
    return ModeloRevision(
        id="test-revision",
        localization_key="test.schema.revision.test-revision.label",
        valid_from=date(_YEAR, 1, 1),
        period_selector=PeriodSelector(year_from=_YEAR, periods=("2T",)),
        legal_refs=("ley-37-1992:art-20",),
        source_refs=("test-source",),
        bindings=bindings,
    )


def _malformed_exemption_article_selector_cases() -> tuple[ParameterSet, ...]:
    """Build governed selector cases only when this proof executes."""
    with validating_governed_facts(compiled_bundled_authority()):
        return (
            pytest.param({"exemption_articles": ()}, id="empty-exemption-articles"),
            pytest.param({"exemption_articles": ("bogus",)}, id="unknown-exemption-article"),
            pytest.param(
                {
                    "categories": (ledger_iva_aggregation_category("domestic_general"),),
                    "exemption_articles": (exemption("art_20_uno_14"),),
                },
                id="exemption-article-without-domestic-exempt-category",
            ),
        )


@pytest.mark.usefixtures("governed_fact_scope")
def test_validate_rejects_malformed_exemption_article_selector_without_registry_resources() -> None:
    for case in _malformed_exemption_article_selector_cases():
        with pytest.raises(ValidationError, match="exemption_articles"):
            _article_filter_binding(**cast("dict[str, object]", case.values[0]))


def _single_binding_selector_cases() -> tuple[ParameterSet, ...]:
    """Build governed observation cases only when their resolver proof executes."""
    with validating_governed_facts(compiled_bundled_authority()):
        return (
            pytest.param(
                "modelo-303-iva-repercutido-general-cuota",
                (
                    ledger_iva_aggregation_observation(
                        applied_rate=Decimal("0.21"),
                        flow=ledger_iva_aggregation_flow("repercutido"),
                        iva=Decimal("210"),
                    ),
                    ledger_iva_aggregation_observation(
                        applied_rate=Decimal("0.21"),
                        flow=ledger_iva_aggregation_flow("soportado"),
                        iva=Decimal("105"),
                        deduction_fact_kind=deduction_kind("domestic_current"),
                        deduction_authority=deduction_authority("invoice_evidence"),
                    ),
                    ledger_iva_aggregation_observation(
                        applied_rate=Decimal("0.21"),
                        flow=ledger_iva_aggregation_flow("inversion_sujeto_pasivo"),
                        iva=Decimal("90"),
                        deduction_fact_kind=deduction_kind("domestic_current"),
                        deduction_authority=deduction_authority("invoice_evidence"),
                    ),
                ),
                Decimal("210"),
                id="repercutido",
            ),
            pytest.param(
                "modelo-303-iva-soportado-interiores-cuota",
                (
                    ledger_iva_aggregation_observation(
                        applied_rate=Decimal("0.21"),
                        flow=ledger_iva_aggregation_flow("repercutido"),
                        iva=Decimal("210"),
                    ),
                    ledger_iva_aggregation_observation(
                        applied_rate=Decimal("0.21"),
                        flow=ledger_iva_aggregation_flow("soportado"),
                        iva=Decimal("105"),
                        deduction_fact_kind=deduction_kind("domestic_current"),
                        deduction_authority=deduction_authority("invoice_evidence"),
                    ),
                ),
                Decimal("105"),
                id="soportado",
            ),
            pytest.param(
                "modelo-303-iva-autorepercutido-intracomunitaria-cuota",
                (
                    ledger_iva_aggregation_observation(
                        applied_rate=Decimal("0.21"),
                        category=ledger_iva_aggregation_category("intra_community_acquisition_reverse_charge"),
                        flow=ledger_iva_aggregation_flow("inversion_sujeto_pasivo"),
                        iva=Decimal("42"),
                        deduction_fact_kind=deduction_kind("intra_eu_current"),
                        deduction_authority=deduction_authority("intra_eu_self_assessment"),
                    ),
                    ledger_iva_aggregation_observation(
                        applied_rate=Decimal("0.21"),
                        category=ledger_iva_aggregation_category("domestic_general"),
                        flow=ledger_iva_aggregation_flow("soportado"),
                        iva=Decimal("99"),
                        deduction_fact_kind=deduction_kind("domestic_current"),
                        deduction_authority=deduction_authority("invoice_evidence"),
                    ),
                ),
                Decimal("42"),
                id="autorepercutido-intracomunitaria",
            ),
        )


def test_resolve_filters_by_binding_selector() -> None:
    failures: list[str] = []
    for case in _single_binding_selector_cases():
        binding_id, observations, expected_amount = cast(
            "tuple[str, tuple[IvaLedgerObservation, ...], Decimal]", case.values
        )
        try:
            revision = revision_with_bindings(ledger_iva_aggregation_binding(binding_id))
            result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
        except Exception as error:
            failures.append(f"{case.id}: {type(error).__name__}: {error}")
            continue
        if result != {binding_id: expected_amount}:
            failures.append(f"{case.id}: expected {expected_amount!r}, got {result!r}")
    assert not failures, "\n".join(failures)


@pytest.mark.usefixtures("governed_fact_scope")
def test_resolve_routes_domestic_reverse_charge_to_devengado_and_deducible_net_zero() -> None:
    """Domestic inversión del sujeto pasivo (LIVA art. 84.Uno.2) books both sides.

    A ``DOMESTIC_REVERSE_CHARGE`` observation on the ``INVERSION_SUJETO_PASIVO``
    flow (as the application classifier now emits via
    ``derive_flow_for_classification``) is consumed by BOTH new bindings:
    ``modelo-303-iva-autorepercutido-interior-devengado-cuota`` (official box 13)
    and ``modelo-303-iva-autorepercutido-interior-deducible-cuota`` (official box
    37). Each resolves the same self-assessed cuota, so the pair nets to zero in
    the resultado. The ``SOPORTADO`` reverse-charge observation must NOT leak in
    (it is a different flow and the application gate would never emit it).
    """
    revision = revision_with_bindings(
        ledger_iva_aggregation_binding("modelo-303-iva-autorepercutido-interior-devengado-cuota"),
        ledger_iva_aggregation_binding("modelo-303-iva-autorepercutido-interior-deducible-cuota"),
    )
    observations = [
        ledger_iva_aggregation_observation(
            applied_rate=Decimal("0.21"),
            ledger_id="domestic-rc",
            category=ledger_iva_aggregation_category("domestic_reverse_charge"),
            flow=ledger_iva_aggregation_flow("inversion_sujeto_pasivo"),
            iva=Decimal("42.00"),
            deduction_fact_kind=deduction_kind("domestic_current"),
            deduction_authority=deduction_authority("invoice_evidence"),
        ),
        # A stray SOPORTADO reverse-charge row must not be selected by the
        # inversion_sujeto_pasivo-flow bindings.
        ledger_iva_aggregation_observation(
            applied_rate=Decimal("0.21"),
            ledger_id="stray-soportado",
            category=ledger_iva_aggregation_category("domestic_reverse_charge"),
            flow=ledger_iva_aggregation_flow("soportado"),
            iva=Decimal("99.00"),
            deduction_fact_kind=deduction_kind("domestic_current"),
            deduction_authority=deduction_authority("invoice_evidence"),
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {
        "modelo-303-iva-autorepercutido-interior-devengado-cuota": Decimal("42.00"),
        "modelo-303-iva-autorepercutido-interior-deducible-cuota": Decimal("42.00"),
    }
    devengado = result["modelo-303-iva-autorepercutido-interior-devengado-cuota"]
    deducible = result["modelo-303-iva-autorepercutido-interior-deducible-cuota"]
    assert devengado - deducible == Decimal("0")


@pytest.mark.usefixtures("governed_fact_scope")
def test_resolve_intracomunitaria_binding_consumes_inversion_sujeto_pasivo_flow() -> None:
    """The intracomunitaria binding resolves the ISP-flow observation.

    Pre-flow-fix the application classifier left intra-community-acquisition
    reverse-charge observations on a direction-only ``SOPORTADO`` flow, so this
    ``inversion_sujeto_pasivo``-flow binding was effectively unreachable from the
    ledger path. With the classifier now routing reverse-charge categories to
    ``INVERSION_SUJETO_PASIVO``, the binding consumes the observation; a
    separately grounded domestic ``SOPORTADO`` row must NOT match.
    """
    revision = revision_with_bindings(
        ledger_iva_aggregation_binding("modelo-303-iva-autorepercutido-intracomunitaria-cuota")
    )
    observations = [
        ledger_iva_aggregation_observation(
            applied_rate=Decimal("0.21"),
            ledger_id="ica-isp",
            category=ledger_iva_aggregation_category("intra_community_acquisition_reverse_charge"),
            flow=ledger_iva_aggregation_flow("inversion_sujeto_pasivo"),
            iva=Decimal("63.00"),
            deduction_fact_kind=deduction_kind("intra_eu_current"),
            deduction_authority=deduction_authority("intra_eu_self_assessment"),
        ),
        ledger_iva_aggregation_observation(
            applied_rate=Decimal("0.21"),
            ledger_id="ica-soportado",
            category=ledger_iva_aggregation_category("domestic_general"),
            flow=ledger_iva_aggregation_flow("soportado"),
            iva=Decimal("77.00"),
            deduction_fact_kind=deduction_kind("domestic_current"),
            deduction_authority=deduction_authority("invoice_evidence"),
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("63.00")}


@pytest.mark.usefixtures("governed_fact_scope")
def test_calculate_303_domestic_reverse_charge_books_boxes_13_and_37_with_zero_net_impact() -> None:
    """End-to-end: a reverse-charge ISP observation books box 13 + 37 and nets to zero.

    Calculates the M303 snapshot from a domestic sale plus a domestic
    reverse-charge ISP observation whose self-assessed cuota the autorepercutido
    interior bindings echo verbatim. Box 13 (devengado) and box 37 (deducible)
    must each equal the observation's own ``iva_amount`` (the binding copies the
    ledger fact; no hand-computed aggregate is asserted). Because the same cuota
    lands on BOTH the cuota-devengada-total and the cuota-deducible-total (LIVA
    art. 84.Uno.2 + art. 92 deduction), the reverse-charge contribution to the
    resultado is exactly zero — the resultado and both totals' *deltas* versus the
    domestic-only filing are derived by comparison, never by literal addition.
    """
    reverse_charge_cuota = Decimal("63.00")
    domestic_only = calculate_303_from_observations(
        filing_year=_YEAR,
        period="1T",
        observations=(
            ledger_iva_aggregation_observation(
                applied_rate=Decimal("0.21"), ledger_id="sale", txn_date=date(_YEAR, 2, 15), iva=Decimal("21.00")
            ),
        ),
    )
    with_reverse_charge = calculate_303_from_observations(
        filing_year=_YEAR,
        period="1T",
        observations=(
            ledger_iva_aggregation_observation(
                applied_rate=Decimal("0.21"), ledger_id="sale", txn_date=date(_YEAR, 2, 15), iva=Decimal("21.00")
            ),
            ledger_iva_aggregation_observation(
                applied_rate=Decimal("0.21"),
                ledger_id="domestic-rc",
                txn_date=date(_YEAR, 3, 1),
                category=ledger_iva_aggregation_category("domestic_reverse_charge"),
                flow=ledger_iva_aggregation_flow("inversion_sujeto_pasivo"),
                iva=reverse_charge_cuota,
                deduction_fact_kind=deduction_kind("domestic_current"),
                deduction_authority=deduction_authority("invoice_evidence"),
            ),
        ),
    )
    # Box 13 (devengado) and box 37 (deducible) both echo the self-assessed cuota
    # the observation carried — the binding copies the ledger fact verbatim.
    assert with_reverse_charge.values[M303_AUTOREPERCUTIDO_INTERIOR_DEVENGADO_CASILLA] == reverse_charge_cuota
    assert with_reverse_charge.values[M303_AUTOREPERCUTIDO_INTERIOR_DEDUCIBLE_CASILLA] == reverse_charge_cuota
    # The reverse-charge nets to zero: both totals rose by exactly the
    # self-assessed cuota, so the resultado is unchanged versus the
    # domestic-only filing. Each delta is computed by comparison, not by
    # summing literals (aeat-quality-gates).
    assert (
        with_reverse_charge.values[M303_CUOTA_DEVENGADA_TOTAL_CASILLA]
        - domestic_only.values[M303_CUOTA_DEVENGADA_TOTAL_CASILLA]
        == reverse_charge_cuota
    )
    assert (
        with_reverse_charge.values[M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA]
        - domestic_only.values[M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA]
        == reverse_charge_cuota
    )
    assert (
        with_reverse_charge.values[M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
        == domestic_only.values[M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
    )


@pytest.mark.usefixtures("governed_fact_scope")
def test_resolve_filters_by_category_set() -> None:
    """The selector's categories tuple is interpreted as a SET match —
    observations whose category is in the tuple count, others don't."""
    observations = [
        ledger_iva_aggregation_observation(
            applied_rate=Decimal("0.21"),
            category=ledger_iva_aggregation_category("domestic_general"),
            rate_kind=ledger_iva_aggregation_rate_kind("general"),
            flow=ledger_iva_aggregation_flow("soportado"),
            iva=Decimal("210"),
            deduction_fact_kind=deduction_kind("domestic_current"),
            deduction_authority=deduction_authority("invoice_evidence"),
        ),
        ledger_iva_aggregation_observation(
            applied_rate=Decimal("0.10"),
            category=ledger_iva_aggregation_category("domestic_reduced"),
            rate_kind=ledger_iva_aggregation_rate_kind("reduced"),
            flow=ledger_iva_aggregation_flow("soportado"),
            iva=Decimal("100"),
            deduction_fact_kind=deduction_kind("domestic_current"),
            deduction_authority=deduction_authority("invoice_evidence"),
        ),
        ledger_iva_aggregation_observation(
            applied_rate=Decimal("0.21"),
            category=ledger_iva_aggregation_category("recargo_equivalencia"),
            rate_kind=ledger_iva_aggregation_rate_kind("general"),
            flow=ledger_iva_aggregation_flow("soportado"),
            iva=Decimal("999"),
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(
        revision_with_bindings(
            ledger_iva_aggregation_binding(
                "modelo-303-iva-soportado-interiores-cuota",
            ),
        ),
        observations,
    )
    # Filter contract verification: the binding's category set excludes
    # RECARGO_EQUIVALENCIA. The aggregator must (1) NOT leak the 999
    # EUR recargo observation into the result and (2) include both
    # DOMESTIC_GENERAL and DOMESTIC_REDUCED observations. This
    # bounds the result between the largest single matching observation
    # and the upper bound that would include the excluded category.
    cuota = result["modelo-303-iva-soportado-interiores-cuota"]
    # Upper bound: the recargo's 999 EUR observation must not leak in.
    assert cuota < Decimal("999"), f"recargo observation leaked into result; got {cuota}"
    # Lower bound: both matching observations must contribute; the
    # result must exceed the largest single matching observation.
    assert cuota > Decimal("210"), f"only one matching observation aggregated; got {cuota}"


@pytest.mark.usefixtures("governed_fact_scope")
def test_resolve_supports_base_amount_sum_fact() -> None:
    revision = revision_with_bindings(with_selector(ledger_iva_aggregation_binding(), fact="base_amount_sum"))
    observations = [
        ledger_iva_aggregation_observation(applied_rate=Decimal("0.21"), base=Decimal("1000"), iva=Decimal("210")),
        ledger_iva_aggregation_observation(applied_rate=Decimal("0.21"), base=Decimal("500"), iva=Decimal("105")),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-repercutido-general-cuota": Decimal("1500")}


def _domestic_exempt_article_observations() -> tuple[IvaLedgerObservation, ...]:
    return (
        ledger_iva_aggregation_observation(
            ledger_id="art-20-14",
            category=ledger_iva_aggregation_category("domestic_exempt"),
            exemption_article=exemption("art_20_uno_14"),
            rate_kind=ledger_iva_aggregation_rate_kind("exempt"),
            base=Decimal("400.00"),
            iva=Decimal("0"),
        ),
        ledger_iva_aggregation_observation(
            ledger_id="art-20-8",
            category=ledger_iva_aggregation_category("domestic_exempt"),
            exemption_article=exemption("art_20_uno_8"),
            rate_kind=ledger_iva_aggregation_rate_kind("exempt"),
            base=Decimal("700.00"),
            iva=Decimal("0"),
        ),
        ledger_iva_aggregation_observation(
            ledger_id="unknown-article",
            category=ledger_iva_aggregation_category("domestic_exempt"),
            rate_kind=ledger_iva_aggregation_rate_kind("exempt"),
            base=Decimal("900.00"),
            iva=Decimal("0"),
        ),
    )


@pytest.mark.usefixtures("governed_fact_scope")
def test_resolve_filters_by_exemption_article_when_selector_declares_article() -> None:
    binding = _article_filter_binding()
    observations = _domestic_exempt_article_observations()

    result = resolve_ledger_iva_aggregation_binding_values(_minimal_revision_with_bindings(binding), observations)

    assert result == {"test-art-20-base": Decimal("400.00")}


@pytest.mark.usefixtures("governed_fact_scope")
def test_resolve_without_exemption_article_filter_keeps_broad_domestic_exempt_match() -> None:
    binding = _article_filter_binding(exemption_articles=None)
    observations = _domestic_exempt_article_observations()

    result = resolve_ledger_iva_aggregation_binding_values(_minimal_revision_with_bindings(binding), observations)

    assert result == {"test-art-20-base": Decimal("2000.00")}


@pytest.mark.usefixtures("governed_fact_scope")
def test_resolve_returns_zero_when_no_observation_matches() -> None:
    revision = revision_with_bindings(ledger_iva_aggregation_binding())
    observations = [
        ledger_iva_aggregation_observation(
            applied_rate=Decimal("0.21"),
            category=ledger_iva_aggregation_category("recargo_equivalencia"),
            iva=Decimal("999"),
        )
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-repercutido-general-cuota": Decimal("0")}


@pytest.mark.usefixtures("governed_fact_scope")
def test_unsupported_ledger_iva_observations_identifies_unbound_regimes() -> None:
    revision = revision_with_bindings(ledger_iva_aggregation_binding())
    supported = ledger_iva_aggregation_observation(applied_rate=Decimal("0.21"), ledger_id="ordinary-output")
    unsupported = ledger_iva_aggregation_observation(
        applied_rate=Decimal("0.21"),
        ledger_id="recargo-row",
        category=ledger_iva_aggregation_category("recargo_equivalencia"),
        flow=ledger_iva_aggregation_flow("soportado"),
        iva=Decimal("5.20"),
    )

    assert unsupported_ledger_iva_observations(revision, (supported, unsupported)) == (unsupported,)


@pytest.mark.usefixtures("governed_fact_scope")
def test_unsupported_excludes_cuota_less_by_law_categories() -> None:
    """#64 refinement: cuota-less-by-law categories must not be flagged as unsupported.

    An ``INTRA_COMMUNITY_SUPPLY`` repercutido observation (entrega
    intracomunitaria exenta, Ley 37/1992 art. 25) bears zero M303 cuota and
    correctly matches no cuota binding; it must be excluded from the unsupported
    set, whereas a ``DOMESTIC_REVERSE_CHARGE`` observation that genuinely bears a
    cuota but is routed by no binding yet must still be flagged.
    """
    revision = revision_with_bindings(ledger_iva_aggregation_binding())
    exempt_supply = ledger_iva_aggregation_observation(
        applied_rate=Decimal("0.21"),
        ledger_id="intra-community-supply",
        category=ledger_iva_aggregation_category("intra_community_supply"),
        flow=ledger_iva_aggregation_flow("repercutido"),
        iva=Decimal("0"),
    )
    reverse_charge = ledger_iva_aggregation_observation(
        applied_rate=Decimal("0.21"),
        ledger_id="domestic-reverse-charge",
        category=ledger_iva_aggregation_category("domestic_reverse_charge"),
        flow=ledger_iva_aggregation_flow("soportado"),
        iva=Decimal("42.00"),
        deduction_fact_kind=deduction_kind("domestic_current"),
        deduction_authority=deduction_authority("invoice_evidence"),
    )

    assert unsupported_ledger_iva_observations(revision, (exempt_supply, reverse_charge)) == (reverse_charge,)


@pytest.mark.usefixtures("governed_fact_scope")
def test_unsupported_flags_zero_amount_observation_unlike_every_other_ledger_family() -> None:
    """IVA's fail-closed screen has NO zero-amount false-fire guard, unlike its six siblings.

    Every other ``unsupported_ledger_*`` function excludes a matched-nothing
    observation once its declarable amount is zero. IVA is the sole
    documented exception (F15): a ``DOMESTIC_REVERSE_CHARGE`` observation
    genuinely bears a cuota by law and is not in
    ``CUOTA_LESS_M303_IVA_CATEGORIES``, so it must be flagged as unsupported
    even when this particular row's base/iva/recargo all happen to be zero
    — the guard other families have does not exist here, on purpose, and
    must not be added to "match" them (doing so would silently suppress a
    real routing gap on a future non-zero row of the same unrouted
    category).
    """
    revision = revision_with_bindings(ledger_iva_aggregation_binding())
    zero_amount_reverse_charge = ledger_iva_aggregation_observation(
        applied_rate=Decimal("0.21"),
        ledger_id="domestic-reverse-charge-zero",
        category=ledger_iva_aggregation_category("domestic_reverse_charge"),
        flow=ledger_iva_aggregation_flow("soportado"),
        base=Decimal("0"),
        iva=Decimal("0"),
        recargo=Decimal("0"),
        deduction_fact_kind=deduction_kind("domestic_current"),
        deduction_authority=deduction_authority("invoice_evidence"),
    )

    assert unsupported_ledger_iva_observations(revision, (zero_amount_reverse_charge,)) == (zero_amount_reverse_charge,)


@pytest.mark.usefixtures("governed_fact_scope")
def test_resolve_handles_multiple_bindings_independently() -> None:
    revision = revision_with_bindings(
        ledger_iva_aggregation_binding("modelo-303-iva-repercutido-general-cuota"),
        ledger_iva_aggregation_binding("modelo-303-iva-soportado-interiores-cuota"),
    )
    observations = [
        ledger_iva_aggregation_observation(
            applied_rate=Decimal("0.21"), flow=ledger_iva_aggregation_flow("repercutido"), iva=Decimal("210")
        ),
        ledger_iva_aggregation_observation(
            applied_rate=Decimal("0.21"),
            flow=ledger_iva_aggregation_flow("soportado"),
            iva=Decimal("63"),
            deduction_fact_kind=deduction_kind("domestic_current"),
            deduction_authority=deduction_authority("invoice_evidence"),
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {
        "modelo-303-iva-repercutido-general-cuota": Decimal("210"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("63"),
    }
