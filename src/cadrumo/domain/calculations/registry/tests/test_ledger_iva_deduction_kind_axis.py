"""A deducible binding can split one quantity by the row's fact-0085 deduction kind.

Modelo 303 asks for the cuota soportada on bienes corrientes and on bienes de
inversión in different boxes ([28]/[29] against [30]/[31]), and the two rows
share category, rate and flow. The ``deduction_fact_kinds`` selector axis is
what tells them apart, so these tests hold it to three things: it refuses a
declaration that could never be honoured, it admits only the kinds it names,
and the published 303 and 390 revisions split each deducible quantity into
kind sets that never both claim one row.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingAggregation, BindingAggregationOp
from .....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....iva.deduction_facts import IvaDeductionClassificationProvenance
from ....iva.flow import IvaFlowDirection
from ....iva.schema import (
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaLedgerObservationRole,
    IvaRateKind,
)
from ..binding_value_contract import BindingDataType, BindingValueChannel, BindingValueContract
from ..ledger_iva_bindings import IvaLedgerObservation, LedgerIvaProvider, resolve_ledger_iva_aggregation_binding_values
from ..ledger_iva_screen_bindings import deducible_deduction_kind_overlaps, invoice_ledger_screen_binding_ids
from ..schema import BindingDefinition, ModeloRevision
from ..schema_references import PeriodSelector
from .authored_editions import authored_revisions, filing_grade_exercises, filing_year_envelope
from .published_authority import published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_MONEY_VALUE = BindingValueContract(data_type=BindingDataType.MONEY, channel=BindingValueChannel.DECIMAL)

_YEAR = filing_year_envelope().horizon
_REVISION_ID = str(authored_revisions("303")[-1].id)


def _quarterly_coordinates(modelo_id: str) -> tuple[tuple[int, str], ...]:
    """Return one quarterly coordinate per authored design of every supported exercise.

    An exercise a modelo splits between two designs yields one coordinate for each
    design, so both of them are held to the same contract.
    """
    return tuple(
        (year, quarterly[0])
        for year in filing_year_envelope().years
        for revision in authored_revisions(modelo_id)
        if revision.valid_from.year <= year <= (revision.valid_to.year if revision.valid_to else year)
        if (quarterly := [p for p in revision.period_selector.periods_for_year(year) if p.endswith("T")])
    )


# Every filing coordinate the published registry answers for 303 and 390 across the supported span.
_M303_COORDINATES = _quarterly_coordinates("303")
_M390_YEARS = filing_grade_exercises("390")


def _soportado_selector(**axes: object) -> dict[str, object]:
    selector: dict[str, object] = {
        "categories": (IvaCategory("domestic_general"),),
        "rate_kinds": (IvaRateKind("general"),),
        "flow_direction": IvaFlowDirection.from_registry("soportado"),
        "fact": "iva_amount_sum",
        "observation_roles": (IvaLedgerObservationRole.SETTLEMENT,),
        "cash_accounting_treatments": (IvaCashAccountingTreatment("none"),),
    }
    selector.update(axes)
    return selector


def _binding(binding_id: str, kinds: tuple[str, ...] | None) -> BindingDefinition:
    axes: dict[str, object] = {} if kinds is None else {"deduction_fact_kinds": kinds}
    return BindingDefinition(
        id=binding_id,
        provider=LedgerIvaProvider.model_validate(_soportado_selector(**axes)),
        value=_MONEY_VALUE,
        aggregation=BindingAggregation(op=BindingAggregationOp.SUM),
        legal_refs=("ley-37-1992:art-92",),
        source_refs=(f"aeat-dr-303-{_YEAR}",),
    )


def _revision(*bindings: BindingDefinition) -> ModeloRevision:
    return ModeloRevision(
        id=_REVISION_ID,
        localization_key=f"test.schema.revision.{_REVISION_ID}.label",
        valid_from=date(_YEAR, 1, 1),
        period_selector=PeriodSelector(year_from=_YEAR, periods=("1T",)),
        legal_refs=("ley-37-1992:art-92",),
        source_refs=(f"aeat-dr-303-{_YEAR}",),
        bindings=bindings,
    )


def _purchase(ledger_id: str, *, kind: str, cuota: str, asset_id: str | None = None) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=date(_YEAR, 2, 10),
        category=IvaCategory("domestic_general"),
        rate_kind=IvaRateKind("general"),
        flow_direction=IvaFlowDirection.from_registry("soportado"),
        base_amount=(Decimal(cuota) / Decimal("0.21")).quantize(Decimal("0.01")),
        iva_amount=Decimal(cuota),
        deduction_fact_kind=IvaDeductionFactKind.from_registry(kind),
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
            source_locator=f"invoice:{ledger_id}",
            evidence_digest="a" * 64,
        ),
        investment_asset_id=asset_id,
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def test_a_kind_specific_binding_sums_only_the_rows_of_the_kinds_it_names() -> None:
    """The corriente row and the bien de inversión row reach one binding each."""
    revision = _revision(
        _binding("corrientes", ("domestic_current", "rectification")),
        _binding("bienes-inversion", ("domestic_investment",)),
        _binding("sin-distincion", None),
    )
    rows = (
        _purchase("corriente", kind="domestic_current", cuota="42.00"),
        _purchase("ordenador", kind="domestic_investment", cuota="840.00", asset_id="BI-1"),
    )

    values = resolve_ledger_iva_aggregation_binding_values(revision, rows)

    assert values["corrientes"] == Decimal("42.00")
    assert values["bienes-inversion"] == Decimal("840.00")
    # A binding that declares no kind keeps its earlier meaning: every row.
    assert values["sin-distincion"] == Decimal("882.00")


def test_an_undeclared_deduction_kind_is_refused() -> None:
    """The axis projects through fact 0085; a token it does not declare fails closed."""
    with pytest.raises(ValidationError, match="not declared by fact"):
        LedgerIvaProvider.model_validate(_soportado_selector(deduction_fact_kinds=("bien_de_inversion",)))


def test_a_repeated_deduction_kind_is_refused() -> None:
    with pytest.raises(ValidationError, match="deduction_fact_kinds entries must be unique"):
        LedgerIvaProvider.model_validate(
            _soportado_selector(deduction_fact_kinds=("domestic_investment", "domestic_investment")),
        )


def test_a_deduction_kind_on_a_flow_that_bears_no_deduction_is_refused() -> None:
    """Only a deducible row carries a kind, so the axis on an output flow could never match."""
    with pytest.raises(ValidationError, match="requires a deducible flow_direction"):
        LedgerIvaProvider.model_validate(
            _soportado_selector(
                flow_direction=IvaFlowDirection.from_registry("repercutido"),
                deduction_fact_kinds=("domestic_investment",),
            ),
        )


@pytest.mark.parametrize(("filing_year", "period"), _M303_COORDINATES)
def test_modelo_303_splits_every_deducible_quantity_without_overlap(filing_year: int, period: str) -> None:
    revision = published_snapshot("303", filing_year=filing_year, period=period).revision

    assert deducible_deduction_kind_overlaps(revision) == ()


@pytest.mark.parametrize("filing_year", _M390_YEARS)
def test_modelo_390_splits_every_deducible_quantity_without_overlap(filing_year: int) -> None:
    revision = published_snapshot("390", filing_year=filing_year, period="0A").revision

    assert deducible_deduction_kind_overlaps(revision) == ()


@pytest.mark.parametrize(("filing_year", "period"), _M303_COORDINATES)
def test_the_invoice_screen_compares_the_bienes_de_inversion_cuota_too(filing_year: int, period: str) -> None:
    """Splitting the domestic input slot must not take the investment cuota off the screen."""
    screened = invoice_ledger_screen_binding_ids(
        published_snapshot("303", filing_year=filing_year, period=period).revision,
        modelo="303",
    )

    assert "modelo-303-iva-soportado-interiores-cuota" in screened
    assert "modelo-303-iva-soportado-interiores-bienes-inversion-cuota" in screened
