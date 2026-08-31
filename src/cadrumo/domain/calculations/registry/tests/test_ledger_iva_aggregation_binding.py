"""Core ledger IVA aggregation binding tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from .....core.aggregation import BindingAggregationOp, BindingSourceKind
from ....iva import (
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaExemptionArticle,
    IvaFlowDirection,
    IvaLedgerObservationRole,
    IvaRateKind,
)
from ..errors import RegistryValidationError
from ..ledger_bindings import (
    IvaLedgerObservation,
    _IvaLedgerSelector,
    resolve_ledger_iva_aggregation_binding_values,
    unsupported_ledger_iva_observations,
    validate_ledger_iva_aggregation_binding_definition,
)
from ..schema import DataBindingDefinition, ModeloRevision
from ..schema_references import PeriodSelector
from ._ledger_iva_aggregation_support import (
    _M303_AUTOREPERCUTIDO_INTERIOR_DEDUCIBLE_CASILLA,
    _M303_AUTOREPERCUTIDO_INTERIOR_DEVENGADO_CASILLA,
    _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    _M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
    _M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
    _binding,
    _calculate_303_from_observations,
    _observation,
    _revision_with_bindings,
    _with_aggregation,
    _with_selector,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_validate_accepts_canonical_iva_repercutido_binding() -> None:
    binding = _binding()
    assert binding.id == "modelo-303-iva-repercutido-general-cuota"
    assert binding.selector, "binding must declare a selector for validation to be meaningful"
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
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_iva_aggregation_binding_definition(_with_selector(_binding(), **selector_updates))


def test_validate_rejects_non_sum_aggregation() -> None:
    with pytest.raises(RegistryValidationError, match="aggregation op 'sum'"):
        validate_ledger_iva_aggregation_binding_definition(_with_aggregation(_binding(), BindingAggregationOp.COPY))


def test_validate_rejects_wrong_source_kind() -> None:
    binding = _binding().model_copy(update={"source": "manual_input"})
    with pytest.raises(RegistryValidationError, match="not a ledger_iva_aggregation"):
        validate_ledger_iva_aggregation_binding_definition(binding)


def _article_filter_binding(**selector_updates: object) -> DataBindingDefinition:
    selector: dict[str, object] = {
        "categories": (IvaCategory.DOMESTIC_EXEMPT,),
        "exemption_articles": (IvaExemptionArticle.ART_20_UNO_14,),
        "rate_kinds": (IvaRateKind.EXEMPT,),
        "flow_direction": IvaFlowDirection.REPERCUTIDO,
        "fact": "base_amount_sum",
        "observation_roles": (IvaLedgerObservationRole.SETTLEMENT,),
        "cash_accounting_treatments": (
            IvaCashAccountingTreatment.NONE,
            IvaCashAccountingTreatment.TAXPAYER_REGIME,
            IvaCashAccountingTreatment.SUPPLIER_REGIME,
        ),
    }
    selector.update(selector_updates)
    return DataBindingDefinition(
        id="test-art-20-base",
        source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        selector=_IvaLedgerSelector.model_validate(selector),
        legal_refs=("ley-37-1992:art-20",),
        source_refs=("test-source",),
    )


def _minimal_revision_with_bindings(*bindings: DataBindingDefinition) -> ModeloRevision:
    return ModeloRevision(
        id="test-revision",
        localization_key="test.schema.revision.test-revision.label",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(year_from=2026, periods=("2T",)),
        legal_refs=("ley-37-1992:art-20",),
        source_refs=("test-source",),
        bindings=bindings,
    )


_MALFORMED_EXEMPTION_ARTICLE_SELECTOR_CASES = (
    pytest.param({"exemption_articles": ()}, id="empty-exemption-articles"),
    pytest.param({"exemption_articles": ("bogus",)}, id="unknown-exemption-article"),
    pytest.param(
        {
            "categories": (IvaCategory.DOMESTIC_GENERAL,),
            "exemption_articles": (IvaExemptionArticle.ART_20_UNO_14,),
        },
        id="exemption-article-without-domestic-exempt-category",
    ),
)


@pytest.mark.parametrize("selector_updates", _MALFORMED_EXEMPTION_ARTICLE_SELECTOR_CASES)
def test_validate_rejects_malformed_exemption_article_selector_without_registry_resources(
    selector_updates: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="exemption_articles"):
        _article_filter_binding(**selector_updates)


_SINGLE_BINDING_SELECTOR_CASES = (
    pytest.param(
        "modelo-303-iva-repercutido-general-cuota",
        (
            _observation(applied_rate=Decimal("0.21"), flow=IvaFlowDirection.REPERCUTIDO, iva=Decimal("210")),
            _observation(
                applied_rate=Decimal("0.21"),
                flow=IvaFlowDirection.SOPORTADO,
                iva=Decimal("105"),
                deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
                deduction_authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
            ),
            _observation(
                applied_rate=Decimal("0.21"),
                flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
                iva=Decimal("90"),
                deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
                deduction_authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
            ),
        ),
        Decimal("210"),
        id="repercutido",
    ),
    pytest.param(
        "modelo-303-iva-soportado-interiores-cuota",
        (
            _observation(applied_rate=Decimal("0.21"), flow=IvaFlowDirection.REPERCUTIDO, iva=Decimal("210")),
            _observation(
                applied_rate=Decimal("0.21"),
                flow=IvaFlowDirection.SOPORTADO,
                iva=Decimal("105"),
                deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
                deduction_authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
            ),
        ),
        Decimal("105"),
        id="soportado",
    ),
    pytest.param(
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota",
        (
            _observation(
                applied_rate=Decimal("0.21"),
                category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
                flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
                iva=Decimal("42"),
                deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
                deduction_authority=IvaDeductionEvidenceAuthority.INTRA_EU_SELF_ASSESSMENT,
            ),
            _observation(
                applied_rate=Decimal("0.21"),
                category=IvaCategory.DOMESTIC_GENERAL,
                flow=IvaFlowDirection.SOPORTADO,
                iva=Decimal("99"),
                deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
                deduction_authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
            ),
        ),
        Decimal("42"),
        id="autorepercutido-intracomunitaria",
    ),
)


@pytest.mark.parametrize(("binding_id", "observations", "expected_amount"), _SINGLE_BINDING_SELECTOR_CASES)
def test_resolve_filters_by_binding_selector(
    binding_id: str,
    observations: tuple[IvaLedgerObservation, ...],
    expected_amount: Decimal,
) -> None:
    revision = _revision_with_bindings(_binding(binding_id))
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {binding_id: expected_amount}


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
    revision = _revision_with_bindings(
        _binding("modelo-303-iva-autorepercutido-interior-devengado-cuota"),
        _binding("modelo-303-iva-autorepercutido-interior-deducible-cuota"),
    )
    observations = [
        _observation(
            applied_rate=Decimal("0.21"),
            ledger_id="domestic-rc",
            category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
            flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            iva=Decimal("42.00"),
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
            deduction_authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
        ),
        # A stray SOPORTADO reverse-charge row must not be selected by the
        # inversion_sujeto_pasivo-flow bindings.
        _observation(
            applied_rate=Decimal("0.21"),
            ledger_id="stray-soportado",
            category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("99.00"),
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
            deduction_authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
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


def test_resolve_intracomunitaria_binding_consumes_inversion_sujeto_pasivo_flow() -> None:
    """The intracomunitaria binding resolves the ISP-flow observation.

    Pre-flow-fix the application classifier left intra-community-acquisition
    reverse-charge observations on a direction-only ``SOPORTADO`` flow, so this
    ``inversion_sujeto_pasivo``-flow binding was effectively unreachable from the
    ledger path. With the classifier now routing reverse-charge categories to
    ``INVERSION_SUJETO_PASIVO``, the binding consumes the observation; a
    separately grounded domestic ``SOPORTADO`` row must NOT match.
    """
    revision = _revision_with_bindings(_binding("modelo-303-iva-autorepercutido-intracomunitaria-cuota"))
    observations = [
        _observation(
            applied_rate=Decimal("0.21"),
            ledger_id="ica-isp",
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            iva=Decimal("63.00"),
            deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
            deduction_authority=IvaDeductionEvidenceAuthority.INTRA_EU_SELF_ASSESSMENT,
        ),
        _observation(
            applied_rate=Decimal("0.21"),
            ledger_id="ica-soportado",
            category=IvaCategory.DOMESTIC_GENERAL,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("77.00"),
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
            deduction_authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("63.00")}


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
    domestic_only = _calculate_303_from_observations(
        filing_year=2025,
        period="1T",
        observations=(
            _observation(
                applied_rate=Decimal("0.21"), ledger_id="sale", txn_date=date(2025, 2, 15), iva=Decimal("21.00")
            ),
        ),
    )
    with_reverse_charge = _calculate_303_from_observations(
        filing_year=2025,
        period="1T",
        observations=(
            _observation(
                applied_rate=Decimal("0.21"), ledger_id="sale", txn_date=date(2025, 2, 15), iva=Decimal("21.00")
            ),
            _observation(
                applied_rate=Decimal("0.21"),
                ledger_id="domestic-rc",
                txn_date=date(2025, 3, 1),
                category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
                flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
                iva=reverse_charge_cuota,
                deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
                deduction_authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
            ),
        ),
    )
    # Box 13 (devengado) and box 37 (deducible) both echo the self-assessed cuota
    # the observation carried — the binding copies the ledger fact verbatim.
    assert with_reverse_charge.values[_M303_AUTOREPERCUTIDO_INTERIOR_DEVENGADO_CASILLA] == reverse_charge_cuota
    assert with_reverse_charge.values[_M303_AUTOREPERCUTIDO_INTERIOR_DEDUCIBLE_CASILLA] == reverse_charge_cuota
    # The reverse-charge nets to zero: both totals rose by exactly the
    # self-assessed cuota, so the resultado is unchanged versus the
    # domestic-only filing. Each delta is computed by comparison, not by
    # summing literals (aeat-quality-gates).
    assert (
        with_reverse_charge.values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA]
        - domestic_only.values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA]
        == reverse_charge_cuota
    )
    assert (
        with_reverse_charge.values[_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA]
        - domestic_only.values[_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA]
        == reverse_charge_cuota
    )
    assert (
        with_reverse_charge.values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
        == domestic_only.values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
    )


def test_resolve_filters_by_category_set() -> None:
    """The selector's categories tuple is interpreted as a SET match —
    observations whose category is in the tuple count, others don't."""
    observations = [
        _observation(
            applied_rate=Decimal("0.21"),
            category=IvaCategory.DOMESTIC_GENERAL,
            rate_kind=IvaRateKind.GENERAL,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("210"),
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
            deduction_authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
        ),
        _observation(
            applied_rate=Decimal("0.10"),
            category=IvaCategory.DOMESTIC_REDUCED,
            rate_kind=IvaRateKind.REDUCED,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("100"),
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
            deduction_authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
        ),
        _observation(
            applied_rate=Decimal("0.21"),
            category=IvaCategory.RECARGO_EQUIVALENCIA,
            rate_kind=IvaRateKind.GENERAL,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("999"),
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(
        _revision_with_bindings(
            _binding(
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


def test_resolve_supports_base_amount_sum_fact() -> None:
    revision = _revision_with_bindings(_with_selector(_binding(), fact="base_amount_sum"))
    observations = [
        _observation(applied_rate=Decimal("0.21"), base=Decimal("1000"), iva=Decimal("210")),
        _observation(applied_rate=Decimal("0.21"), base=Decimal("500"), iva=Decimal("105")),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-repercutido-general-cuota": Decimal("1500")}


def test_resolve_filters_by_exemption_article_when_selector_declares_article() -> None:
    binding = _article_filter_binding()
    observations = (
        _observation(
            ledger_id="art-20-14",
            category=IvaCategory.DOMESTIC_EXEMPT,
            exemption_article=IvaExemptionArticle.ART_20_UNO_14,
            rate_kind=IvaRateKind.EXEMPT,
            base=Decimal("400.00"),
            iva=Decimal("0"),
        ),
        _observation(
            ledger_id="art-20-8",
            category=IvaCategory.DOMESTIC_EXEMPT,
            exemption_article=IvaExemptionArticle.ART_20_UNO_8,
            rate_kind=IvaRateKind.EXEMPT,
            base=Decimal("700.00"),
            iva=Decimal("0"),
        ),
        _observation(
            ledger_id="unknown-article",
            category=IvaCategory.DOMESTIC_EXEMPT,
            rate_kind=IvaRateKind.EXEMPT,
            base=Decimal("900.00"),
            iva=Decimal("0"),
        ),
    )

    result = resolve_ledger_iva_aggregation_binding_values(_minimal_revision_with_bindings(binding), observations)

    assert result == {"test-art-20-base": Decimal("400.00")}


def test_resolve_without_exemption_article_filter_keeps_broad_domestic_exempt_match() -> None:
    binding = _article_filter_binding(exemption_articles=None)
    observations = (
        _observation(
            ledger_id="art-20-14",
            category=IvaCategory.DOMESTIC_EXEMPT,
            exemption_article=IvaExemptionArticle.ART_20_UNO_14,
            rate_kind=IvaRateKind.EXEMPT,
            base=Decimal("400.00"),
            iva=Decimal("0"),
        ),
        _observation(
            ledger_id="art-20-8",
            category=IvaCategory.DOMESTIC_EXEMPT,
            exemption_article=IvaExemptionArticle.ART_20_UNO_8,
            rate_kind=IvaRateKind.EXEMPT,
            base=Decimal("700.00"),
            iva=Decimal("0"),
        ),
        _observation(
            ledger_id="unknown-article",
            category=IvaCategory.DOMESTIC_EXEMPT,
            rate_kind=IvaRateKind.EXEMPT,
            base=Decimal("900.00"),
            iva=Decimal("0"),
        ),
    )

    result = resolve_ledger_iva_aggregation_binding_values(_minimal_revision_with_bindings(binding), observations)

    assert result == {"test-art-20-base": Decimal("2000.00")}


def test_resolve_returns_zero_when_no_observation_matches() -> None:
    revision = _revision_with_bindings(_binding())
    observations = [
        _observation(applied_rate=Decimal("0.21"), category=IvaCategory.RECARGO_EQUIVALENCIA, iva=Decimal("999"))
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-repercutido-general-cuota": Decimal("0")}


def test_unsupported_ledger_iva_observations_identifies_unbound_regimes() -> None:
    revision = _revision_with_bindings(_binding())
    supported = _observation(applied_rate=Decimal("0.21"), ledger_id="ordinary-output")
    unsupported = _observation(
        applied_rate=Decimal("0.21"),
        ledger_id="recargo-row",
        category=IvaCategory.RECARGO_EQUIVALENCIA,
        flow=IvaFlowDirection.SOPORTADO,
        iva=Decimal("5.20"),
    )

    assert unsupported_ledger_iva_observations(revision, (supported, unsupported)) == (unsupported,)


def test_unsupported_excludes_cuota_less_by_law_categories() -> None:
    """#64 refinement: cuota-less-by-law categories must not be flagged as unsupported.

    An ``INTRA_COMMUNITY_SUPPLY`` repercutido observation (entrega
    intracomunitaria exenta, Ley 37/1992 art. 25) bears zero M303 cuota and
    correctly matches no cuota binding; it must be excluded from the unsupported
    set, whereas a ``DOMESTIC_REVERSE_CHARGE`` observation that genuinely bears a
    cuota but is routed by no binding yet must still be flagged.
    """
    revision = _revision_with_bindings(_binding())
    exempt_supply = _observation(
        applied_rate=Decimal("0.21"),
        ledger_id="intra-community-supply",
        category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        flow=IvaFlowDirection.REPERCUTIDO,
        iva=Decimal("0"),
    )
    reverse_charge = _observation(
        applied_rate=Decimal("0.21"),
        ledger_id="domestic-reverse-charge",
        category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
        flow=IvaFlowDirection.SOPORTADO,
        iva=Decimal("42.00"),
        deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
        deduction_authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
    )

    assert unsupported_ledger_iva_observations(revision, (exempt_supply, reverse_charge)) == (reverse_charge,)


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
    revision = _revision_with_bindings(_binding())
    zero_amount_reverse_charge = _observation(
        applied_rate=Decimal("0.21"),
        ledger_id="domestic-reverse-charge-zero",
        category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
        flow=IvaFlowDirection.SOPORTADO,
        base=Decimal("0"),
        iva=Decimal("0"),
        recargo=Decimal("0"),
        deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
        deduction_authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
    )

    assert unsupported_ledger_iva_observations(revision, (zero_amount_reverse_charge,)) == (zero_amount_reverse_charge,)


def test_resolve_handles_multiple_bindings_independently() -> None:
    revision = _revision_with_bindings(
        _binding("modelo-303-iva-repercutido-general-cuota"),
        _binding("modelo-303-iva-soportado-interiores-cuota"),
    )
    observations = [
        _observation(applied_rate=Decimal("0.21"), flow=IvaFlowDirection.REPERCUTIDO, iva=Decimal("210")),
        _observation(
            applied_rate=Decimal("0.21"),
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("63"),
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
            deduction_authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {
        "modelo-303-iva-repercutido-general-cuota": Decimal("210"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("63"),
    }
