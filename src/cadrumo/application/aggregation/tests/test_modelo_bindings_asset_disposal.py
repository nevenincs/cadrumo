"""A baja on the forms: figures in the boxes each edition binds, excess in Modelo 130 casilla 01, nothing in casilla 02.

Hand-worked from the 12,000.00 mobiliario element at a 10% linear coefficient that the source
mesh tests use, whose table minimum is 5% (one over the 20-year maximum period).  Modelo 100
and Modelo 130 are read through their real resolvers and the published 2025 revisions.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.actividad_asset_disposal_bindings import (
    ActivityAssetDisposalRoute,
    activity_asset_disposal_route_casillas,
)
from cadrumo.domain.invoices.catalogue import InvoiceCatalogue
from cadrumo.domain.renta.actividad_asset.disposal import (
    ActivityAssetDisposal,
    ActivityAssetDisposalReason,
    PriorFreeDepreciationRegime,
)
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue

from ...actividad_asset.history import ActivityAssetHistory
from ...modelo.calculation_notes import GATE_REFUSED_REASONS
from ..modelo_bindings import LedgerRentaIncomeAggregationSourceResolver
from ..modelo_bindings_actividad_assets import (
    ActivityAssetDisposalExcess,
    activity_asset_disposal_excess_m131_findings,
)
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .renta_income_aggregation_support import _catalogue_read_ports
from .test_modelo_source_mesh_ledger import (
    _BUCKET_ID,
    InMemoryTransactionCatalogueRepository,
    _acquisition_row,
    _reasons,
    _register_claim,
    _revision,
    _StaticActivityAssetHistoryRepository,
    register_asset,
    resolve_m100,
    resolve_m130,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_TRANSACTION = "c" * 64
_M130 = "2019-y-siguientes"
_INCOME_BINDING = "modelo-130-actividad-economica-ingresos-cumulative"


def _disposed(
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
    return _disposed(
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
    repository = InMemoryTransactionCatalogueRepository(bucket_id=_BUCKET_ID)
    repository.save(TransactionCatalogue.from_transactions(rows))
    return LedgerRentaIncomeAggregationSourceResolver(
        ports=_catalogue_read_ports(invoices=InvoiceCatalogue(), transactions=TransactionCatalogue()),
        activity_asset_history_repository=_StaticActivityAssetHistoryRepository(history),
        transaction_repository=repository,
    ).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
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
    return set(_reasons(resolution)) & GATE_REFUSED_REASONS


def _boxes(resolution: CalculationSourceResolution) -> dict[str, Decimal]:
    """Return the nonzero disposal figures by the box each binding's id ends in."""
    return {
        str(binding).rsplit("-", 1)[-1]: value
        for binding, value in resolution.binding_values.items()
        if str(binding).startswith("renta-activity-asset-disposal-") and value != Decimal("0")
    }


def test_a_sale_gain_enters_its_box_and_names_clave_5_on_the_row() -> None:
    resolution = resolve_m100(_disposed())

    # No claim: reduction is the minimum 12,000 x 5% x 181 / 365 = 297.53, all of it gain.
    assert _boxes(resolution) == {"1654": Decimal("297.53")}
    assert _blocks(resolution) == set()
    assert any("clave 5 in box 1626" in note for note in _findings(resolution))


def test_a_sale_loss_enters_the_loss_box_as_a_magnitude() -> None:
    # 10,000.00 less the net value 11,702.47.
    assert _boxes(resolve_m100(_disposed(proceeds="10000.00"))) == {"1639": Decimal("1702.47")}


def test_a_theft_with_compensation_goes_to_the_no_transmission_box() -> None:
    resolution = resolve_m100(_disposed(reason=ActivityAssetDisposalReason.THEFT, proceeds="12000.00"))

    assert _boxes(resolution) == {"0304": Decimal("297.53")}


def test_a_withdrawal_reaches_no_box() -> None:
    resolution = resolve_m100(_disposed(reason=ActivityAssetDisposalReason.WITHDRAWAL, proceeds="0.00"))

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
    }
    for year in ("2022", "2023", "2024", "2025"):
        assert dict(activity_asset_disposal_route_casillas(_revision("100", year))) == expected


def test_the_calculation_consumes_the_baja_revision() -> None:
    history = _disposed()
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
    history = _disposed(in_service=date(2024, 1, 1), prior_claim="5000.00")

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
        (ActivityAssetDisposalExcess(revision=revision, amount=Decimal("3204.93")),),
        resolver_id="resolver",
    )

    assert finding.reason == "activity_asset_disposal_finding"
    assert "3204.93" in finding.message
