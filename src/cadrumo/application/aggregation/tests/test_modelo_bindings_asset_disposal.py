"""A baja on the forms: figures in the boxes each edition binds, excess in Modelo 130 casilla 01, nothing in casilla 02.

Hand-worked from the 12,000.00 mobiliario element at a 10% linear coefficient that the source
mesh tests use, whose table minimum is 5% (one over the 20-year maximum period).  Modelo 100
and Modelo 130 are read through their real resolvers and the published 2025 revisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.actividad_asset_disposal_bindings import (
    ActivityAssetDisposalRoute,
    activity_asset_disposal_route_casillas,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.invoices.catalogue import InvoiceCatalogue
from cadrumo.domain.modelos.calculation_revision_sources import ActivityAssetConsumption, CalculationNoteSentence
from cadrumo.domain.renta.actividad_asset.disposal import (
    ActivityAssetDisposal,
    ActivityAssetDisposalCalculation,
    ActivityAssetDisposalReason,
    PriorFreeDepreciationRegime,
)
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetIncompleteError
from cadrumo.domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue

from ...actividad_asset.history import ActivityAssetHistory
from ...modelo.calculation_notes import GATE_REFUSED_REASONS
from ...modelo.tests.source_diagnostics_support import apply_expected_missing_binding_diagnostics
from ..activity_asset_disposal_projection import (
    ActivityAssetDisposalRow,
    calculate_asset_disposal,
    disposal_row_source_identities,
)
from ..modelo_bindings import LedgerRentaIncomeAggregationSourceResolver
from ..modelo_bindings_actividad_assets import (
    ActivityAssetDisposalExcess,
    activity_asset_disposal_excess_m131_findings,
)
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .renta_income_aggregation_support import _catalogue_read_ports
from .test_modelo_source_mesh_ledger import (
    BUCKET_ID,
    InMemoryTransactionCatalogueRepository,
    StaticActivityAssetHistoryRepository,
    _acquisition_row,
    _register_claim,
    _revision,
    reasons,
    register_asset,
    resolve_m100,
    resolve_m130,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_TRANSACTION = "c" * 64
_M130 = "2019-y-siguientes"
_INCOME_BINDING = "modelo-130-actividad-economica-ingresos-cumulative"


def disposed_asset_history(
    *,
    reason: ActivityAssetDisposalReason = ActivityAssetDisposalReason.SALE,
    proceeds: str = "12000.00",
    costs: str = "0.00",
    on: date = date(2025, 6, 30),
    regime: PriorFreeDepreciationRegime | None = None,
    in_service: date = date(2025, 1, 1),
    prior_claim: str | None = None,
    transaction_id: str = _TRANSACTION,
) -> ActivityAssetHistory:
    asset = register_asset("furniture", transaction_id=transaction_id, in_service=in_service)
    claims = () if prior_claim is None else (_register_claim(asset, amount=Decimal(prior_claim), tax_year=2024),)
    history = ActivityAssetHistory(revisions=(asset,), claims=claims)
    baja = ActivityAssetDisposal(
        disposal_date=on,
        reason=reason,
        proceeds=Decimal(proceeds),
        transmission_costs=Decimal(costs),
        prior_free_depreciation_regime=regime,
    )
    return history.apply_correction(asset.with_disposal(baja), ())


def _excess_history(transaction_id: str = _TRANSACTION) -> ActivityAssetHistory:
    """5,000.00 charged in 2024 against table maxima of 1,200.00 and 12,000 x 10% x 181 / 365 = 595.07."""
    return disposed_asset_history(
        regime=PriorFreeDepreciationRegime.TRLIS_DT_37,
        in_service=date(2024, 1, 1),
        prior_claim="5000.00",
        transaction_id=transaction_id,
    )


def _income(
    history: ActivityAssetHistory,
    period: str,
    *,
    rows: tuple[Transaction, ...] = (),
) -> CalculationSourceResolution:
    repository = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    repository.save(TransactionCatalogue.from_transactions(rows))
    return LedgerRentaIncomeAggregationSourceResolver(
        ports=_catalogue_read_ports(invoices=InvoiceCatalogue(), transactions=TransactionCatalogue()),
        activity_asset_history_repository=StaticActivityAssetHistoryRepository(history),
        transaction_repository=repository,
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="130",
            filing_year=2025,
            period=Period.from_year_and_code(2025, period),
            revision=_revision("130", _M130),
        ),
    )


def _income_box(resolution: CalculationSourceResolution) -> Decimal:
    return next(value for binding, value in resolution.binding_values.items() if str(binding) == _INCOME_BINDING)


def _findings(resolution: CalculationSourceResolution) -> list[str]:
    return [item.message for item in resolution.diagnostics if item.reason == "activity_asset_disposal_finding"]


def _blocks(resolution: CalculationSourceResolution) -> set[str]:
    return set(reasons(resolution)) & GATE_REFUSED_REASONS


def _boxes(resolution: CalculationSourceResolution) -> dict[str, Decimal]:
    """Return the nonzero disposal figures by the box each binding's id ends in."""
    return {
        str(binding).rsplit("-", 1)[-1]: value
        for binding, value in resolution.binding_values.items()
        if str(binding).startswith("renta-activity-asset-disposal-") and value != Decimal("0")
    }


def test_a_sale_gain_enters_its_box_and_states_clave_5_on_the_row() -> None:
    resolution = resolve_m100(disposed_asset_history())

    # No claim: reduction is the minimum 12,000 x 5% x 181 / 365 = 297.53, all of it gain.
    assert _boxes(resolution) == {"1654": Decimal("297.53")}
    assert _blocks(resolution) == set()
    assert {str(binding): value for binding, value in resolution.enum_binding_values.items()} == {
        "renta-activity-asset-disposal-element-type-1626": "5",
    }
    assert not any("clave" in note for note in _findings(resolution))


def test_the_stated_clave_is_not_reported_as_a_missing_box() -> None:
    resolution = resolve_m100(disposed_asset_history())

    checked = apply_expected_missing_binding_diagnostics(_revision("100", "2025"), resolution)

    assert "unresolved_binding" not in reasons(checked)
    assert not {str(binding) for binding in checked.unresolved_binding_ids} & {
        "renta-activity-asset-disposal-element-type-1626"
    }


def test_a_year_with_no_element_row_states_no_clave_and_owes_none() -> None:
    resolution = resolve_m100(ActivityAssetHistory())

    assert not resolution.enum_binding_values
    assert "unresolved_binding" not in reasons(resolution)
    assert "renta-activity-asset-disposal-element-type-1626" in {
        str(binding) for binding in resolution.inapplicable_binding_ids
    }


def test_a_sale_loss_enters_the_loss_box_as_a_magnitude() -> None:
    # 10,000.00 less the net value 11,702.47.
    assert _boxes(resolve_m100(disposed_asset_history(proceeds="10000.00"))) == {"1639": Decimal("1702.47")}


def test_a_theft_with_compensation_goes_to_the_no_transmission_box() -> None:
    resolution = resolve_m100(disposed_asset_history(reason=ActivityAssetDisposalReason.THEFT, proceeds="12000.00"))

    assert _boxes(resolution) == {"0304": Decimal("297.53")}


def test_a_withdrawal_reaches_no_box() -> None:
    resolution = resolve_m100(disposed_asset_history(reason=ActivityAssetDisposalReason.WITHDRAWAL, proceeds="0.00"))

    assert _boxes(resolution) == {}
    assert _blocks(resolution) == set()


def test_each_supported_edition_binds_every_route() -> None:
    expected = {
        ActivityAssetDisposalRoute.EXCESS_DIRECT_ESTIMATION: "0179",
        ActivityAssetDisposalRoute.EXCESS_OBJECTIVE_ESTIMATION: "1478",
        ActivityAssetDisposalRoute.TRANSMISSION_GAIN_ELEMENT: "1654",
        ActivityAssetDisposalRoute.TRANSMISSION_LOSS_ELEMENT: "1639",
        ActivityAssetDisposalRoute.TRANSMISSION_GAIN_PROPERTY: "1843",
        ActivityAssetDisposalRoute.TRANSMISSION_LOSS_PROPERTY: "1832",
        ActivityAssetDisposalRoute.NO_TRANSMISSION_GAIN: "0304",
        ActivityAssetDisposalRoute.NO_TRANSMISSION_LOSS: "0305",
        ActivityAssetDisposalRoute.TRANSMISSION_ELEMENT_TYPE: "1626",
    }
    for year in ("2022", "2023", "2024", "2025"):
        revision = _revision("100", year)
        assert dict(activity_asset_disposal_route_casillas(revision)) == expected
        casilla = next(item for item in revision.casillas if item.id == "1626")
        assert casilla.input_kind == "bound"
        assert casilla.binding == "renta-activity-asset-disposal-element-type-1626"


def test_the_calculation_consumes_the_baja_revision() -> None:
    history = disposed_asset_history()
    expected = f"activity-asset-disposal:{history.revisions[-1].revision_id}"

    assert expected in {item.source_ref for item in resolve_m100(history).provenance}
    assert expected in {item.source_ref for item in resolve_m130(history, "2T").provenance}
    assert expected not in {item.source_ref for item in resolve_m130(history, "1T").provenance}


def test_a_later_year_has_no_zero_row_from_a_baja_claim() -> None:
    asset = register_asset("furniture", transaction_id=_TRANSACTION)
    baja = ActivityAssetDisposal(
        disposal_date=date(2024, 12, 31),
        reason=ActivityAssetDisposalReason.WITHDRAWAL,
        proceeds=Decimal("0.00"),
        transmission_costs=Decimal("0.00"),
    )
    earlier = register_asset("furniture", transaction_id=_TRANSACTION, in_service=date(2024, 1, 1))
    del asset
    history = ActivityAssetHistory(revisions=(earlier,)).apply_correction(earlier.with_disposal(baja), ())

    resolution = resolve_m100(history)

    assert not [item for item in resolution.provenance if item.source_ref.startswith("activity-asset-claim:")]
    assert _blocks(resolution) == set()


@pytest.mark.parametrize(("period", "expected"), [("1T", "0"), ("2T", "3204.93"), ("3T", "3204.93")])
def test_the_excess_enters_casilla_01_from_the_quarter_of_the_transmission(period: str, expected: str) -> None:
    # 5,000.00 less 1,200.00 and 595.07.
    assert _income_box(_income(_excess_history(), period)) == Decimal(expected)


def test_the_excess_enters_box_0179_of_modelo_100_and_stays_out_of_casilla_02() -> None:
    history = _excess_history()

    assert _boxes(resolve_m100(history))["0179"] == Decimal("3204.93")
    assert Decimal("3204.93") not in resolve_m130(history, "2T").binding_values.values()


def test_no_attestation_means_no_excess() -> None:
    history = disposed_asset_history(in_service=date(2024, 1, 1), prior_claim="5000.00")

    assert _income_box(_income(history, "2T")) == Decimal("0")


def test_an_agrarian_excess_is_a_finding_and_reaches_no_box() -> None:
    row = _acquisition_row("farm-machine", activity="B01")
    history = _excess_history(transaction_id=row.transaction_id)
    instalment = resolve_m130(history, "2T", rows=(row,))

    assert _income_box(_income(history, "2T", rows=(row,))) == Decimal("0")
    assert any("agrarian" in note for note in _findings(instalment))
    # The acquisition row itself is an unclassified expense, which the ledger reports separately.
    assert _blocks(instalment) == {"source_domain_not_ready"}


def test_modelo_131_says_the_excess_is_not_routed() -> None:
    revision = _excess_history().revisions[-1]

    (finding,) = activity_asset_disposal_excess_m131_findings(
        (ActivityAssetDisposalExcess(revision=revision, target_casilla_id="01", amount=Decimal("3204.93")),),
        resolver_id="resolver",
    )

    assert finding.reason == "activity_asset_disposal_finding"
    assert "3204.93" in finding.message


def test_modelo_131_says_an_excess_it_could_not_work_out_as_modelos_100_and_130_do() -> None:
    revision = _excess_history().revisions[-1]
    unworked = ActivityAssetDisposalExcess(
        revision=revision,
        target_casilla_id="01",
        error=ActividadAssetIncompleteError(translated_message="ledger.actividad_asset.errors.opening_history_missing"),
    )

    (finding,) = activity_asset_disposal_excess_m131_findings((unworked,), resolver_id="resolver")

    assert finding.reason == "activity_asset_disposal_finding"
    assert finding.source_ref == f"activity-asset:{revision.asset_id}"
    assert "could not be worked out" in finding.message
    assert "0.00" not in finding.message
    assert finding.reason not in GATE_REFUSED_REASONS


def _consumption(resolution: CalculationSourceResolution) -> ActivityAssetConsumption:
    return ActivityAssetConsumption.from_source_refs(row.source_ref for row in resolution.provenance)


def test_a_claim_of_an_earlier_year_moves_the_baja_and_the_calculation_records_that() -> None:
    """12,000.00 from 2024 at 10 %, minimum 5 %, sold on 30 June 2025 for 12,000.00.

    With no claim the minimum runs 12,000.00 x 5 % x (1 + 181 / 365) = 897.53, so the gain is
    12,000.00 - (12,000.00 - 897.53) = 897.53. With a 2024 claim of 1,200.00 the deduction exceeds
    the minimum and the gain is 1,200.00. The revision and the 2025 claims are the same in both.
    """
    unclaimed = disposed_asset_history(in_service=date(2024, 1, 1))
    claimed = disposed_asset_history(in_service=date(2024, 1, 1), prior_claim="1200.00")

    before, after = resolve_m100(unclaimed), resolve_m100(claimed)

    assert _boxes(before)["1654"] == Decimal("897.53")
    assert _boxes(after)["1654"] == Decimal("1200.00")
    recorded, current = _consumption(before), _consumption(after)
    assert recorded.claim_ids == current.claim_ids == ()
    assert recorded.disposal_revision_ids == current.disposal_revision_ids
    assert recorded.disposal_digests != current.disposal_digests
    assert current.disposals_changed_from(recorded) == 1
    assert current.disposals_changed_from(current) == 0


def test_the_digest_stands_while_nothing_behind_the_baja_moved() -> None:
    history = disposed_asset_history(in_service=date(2024, 1, 1))

    assert _consumption(resolve_m100(history)) == _consumption(resolve_m100(history))


def test_a_modelo_130_excess_records_the_figures_it_rests_on() -> None:
    """A 2024 claim of 4,000.00 gives 4,000.00 - 1,795.07 = 2,204.93 of excess; 5,000.00 gives 3,204.93."""

    def history(prior_claim: str) -> ActivityAssetHistory:
        return disposed_asset_history(
            regime=PriorFreeDepreciationRegime.TRLIS_DT_37,
            in_service=date(2024, 1, 1),
            prior_claim=prior_claim,
        )

    recorded = _consumption(resolve_m130(history("4000.00"), "4T"))
    current = _consumption(resolve_m130(history("5000.00"), "4T"))

    assert recorded.disposal_revision_ids == current.disposal_revision_ids
    assert current.disposals_changed_from(recorded) == 1
    assert _income_box(_income(history("4000.00"), "4T")) == Decimal("2204.93")
    assert _income_box(_income(history("5000.00"), "4T")) == Decimal("3204.93")


def _two_sales(*, second_proceeds: str) -> ActivityAssetHistory:
    first = register_asset("first", transaction_id="c" * 64)
    second = register_asset("second", transaction_id="d" * 64)

    def sold(asset: ActivityAssetRevision, proceeds: str) -> ActivityAssetRevision:
        return asset.with_disposal(
            ActivityAssetDisposal(
                disposal_date=date(2025, 6, 30),
                reason=ActivityAssetDisposalReason.SALE,
                proceeds=Decimal(proceeds),
                transmission_costs=Decimal("0.00"),
            ),
        )

    return (
        ActivityAssetHistory(revisions=(first, second))
        .apply_correction(sold(first, "12000.00"), ())
        .apply_correction(sold(second, second_proceeds), ())
    )


def _row_values(resolution: CalculationSourceResolution, box: str) -> dict[int, object]:
    return {index: value for (binding, index), value in resolution.row_binding_values.items() if binding.endswith(box)}


def _shared_row_notes(resolution: CalculationSourceResolution) -> list[str]:
    return [
        item.fact.element_refs[0]
        for item in resolution.diagnostics
        if item.fact is not None and item.fact.sentence is CalculationNoteSentence.DISPOSAL_SHARED_ROW
    ]


def test_a_gain_and_a_loss_each_take_a_row_of_their_own() -> None:
    # Net value 12,000 - 297.53 = 11,702.47: 12,000 gains 297.53 and 10,000 loses 1,702.47.
    resolution = resolve_m100(_two_sales(second_proceeds="10000.00"))

    assert _boxes(resolution) == {"1654": Decimal("297.53"), "1639": Decimal("1702.47")}
    assert _row_values(resolution, "1654") == {1: Decimal("297.53")}
    assert _row_values(resolution, "1639") == {2: Decimal("1702.47")}
    assert _row_values(resolution, "1633") == {1: Decimal("12000.00"), 2: Decimal("10000.00")}
    assert _row_values(resolution, "1637") == {1: Decimal("11702.47"), 2: Decimal("11702.47")}
    assert _row_values(resolution, "1631")[1] == "2025-06-30"
    assert set(_row_values(resolution, "1626")) == {1, 2}
    assert set(resolution.row_source_identities) == set(resolution.row_binding_values)
    assert _shared_row_notes(resolution) == []
    assert _blocks(resolution) == set()


def test_two_gains_keep_their_sum_for_the_forms_total_and_each_has_its_row() -> None:
    resolution = resolve_m100(_two_sales(second_proceeds="12000.00"))

    assert _boxes(resolution) == {"1654": Decimal("595.06")}
    assert _row_values(resolution, "1654") == {1: Decimal("297.53"), 2: Decimal("297.53")}
    assert _shared_row_notes(resolution) == []


def test_one_sale_has_its_row() -> None:
    resolution = resolve_m100(disposed_asset_history())
    assert _row_values(resolution, "1633")
    assert _shared_row_notes(resolution) == []


def test_the_row_states_the_value_of_transmission_net_of_costs() -> None:
    # 12,000 less 100 of costs is 11,900; the net value is 11,702.47, so the gain is 197.53.
    resolution = resolve_m100(disposed_asset_history(costs="100.00"))

    assert _row_values(resolution, "1633") == {1: Decimal("11900.00")}
    assert _row_values(resolution, "1637") == {1: Decimal("11702.47")}
    assert _row_values(resolution, "1654") == {1: Decimal("197.53")}
    assert _boxes(resolution)["1654"] == Decimal("197.53")


@dataclass(frozen=True, slots=True)
class _SameSale(ActivityAssetDisposalRow):
    """A row whose identity holds still, so its fingerprint can move only with what it states."""

    @property
    def source_identity(self) -> str:
        return "same-sale"


def _fingerprint(revision: ActivityAssetRevision, calculation: ActivityAssetDisposalCalculation) -> str:
    row = _SameSale(
        revision=revision,
        route=ActivityAssetDisposalRoute.TRANSMISSION_GAIN_ELEMENT,
        amount=Decimal("1.00"),
        calculation=calculation,
    )
    key = ("any-binding", 1)
    return disposal_row_source_identities({key: row.source_identity}, (row,))[key].fingerprint


def test_the_row_fingerprint_moves_with_the_costs_and_the_date_of_the_sale(
    operation: PinnedAuthorityOperation,
) -> None:
    history = disposed_asset_history()
    revision = history.revisions[-1]
    calculation = calculate_asset_disposal(revision, history, operation=operation)
    baseline = _fingerprint(revision, calculation)
    disposal = revision.disposal
    assert disposal is not None

    assert baseline != _fingerprint(revision, calculation.model_copy(update={"transmission_costs": Decimal("1.00")}))
    assert baseline != _fingerprint(
        revision.model_copy(update={"disposal": disposal.model_copy(update={"disposal_date": date(2025, 7, 1)})}),
        calculation,
    )
    assert baseline == _fingerprint(revision, calculation)
