"""Calculate keeps succeeding, and says what the rate boxes did not account for.

The decision splits this condition across two gates: an advisory here, a refusal
at export. The advisory carries the whole load of making that split fair -- the
repair is a ledger edit, and an operator who first learns of the problem when
the export refuses has been told at the one moment they can do nothing about it.

So two properties are pinned here, in the order they can break silently:
the advisory names the amount and the tier the repair needs; and the coordinator
actually CALLS the collector and RETURNS rather than raising, so calculate still
succeeds while the advisory fires. The last hop -- diagnostic to typed envelope
notice -- is pinned in the CLI package that owns it, in
``entrypoints/cli/tests/test_source_advisory_notice_channel.py``.

What is NOT claimed: no registry revision in the tree declares a rate-specific
binding yet, so no fixture here drives real ledger rows through a real Modelo
390 split. The revision below is built to the shape the decision prescribes, and
the derivation that recognises that shape from a revision is pinned separately
in ``domain/calculations/registry/tests/test_rate_box_partition.py``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.schema import DataBindingDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ....core import CasillaId, Modelo, validated_casilla_id
from ....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
from ....domain.iva import IvaCategory, IvaFlowDirection, IvaRateKind
from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ...aggregation import CalculationSourceDiagnostic
from .._calculation_diagnostics import collect_bucket_aggregation_advisory_diagnostics
from .._rate_box_advisory import collect_rate_box_coverage_diagnostics

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "6b6b6b6b-6b6b-4b6b-8b6b-6b6b6b6b6b6b"
_FILING_YEAR = 2025
_ANNUAL_PERIOD = "0A"
_REASON = "rate_boxes_underaccount_total"

_LEGAL = ("ley-37-1992:art-91",)
_SOURCE = ("aeat-dr-390-2025",)

_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "iva.anual.repercutido.super-reducido",
    surface="test.rate_box.total",
)
_BOX_4PCT: CasillaId = validated_casilla_id("02", surface="test.rate_box.box")


_bucket = active_profile_isolated_backend_fixture(bucket_id=_BUCKET_ID, name="_bucket")


def _binding(binding_id: str, *, applied_rates: tuple[Decimal, ...] | None) -> DataBindingDefinition:
    selector: dict[str, object] = {
        "categories": (IvaCategory.DOMESTIC_SUPER_REDUCED,),
        "rate_kinds": (IvaRateKind.SUPER_REDUCED,),
        "flow_direction": IvaFlowDirection.REPERCUTIDO,
        "fact": "iva_amount_sum",
    }
    if applied_rates is not None:
        selector["applied_rates"] = applied_rates
    return DataBindingDefinition(
        id=binding_id,
        source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        selector=selector,
        aggregation=BindingAggregation(op=BindingAggregationOp.SUM),
        legal_refs=_LEGAL,
        source_refs=_SOURCE,
    )


def _casilla(casilla_id: CasillaId, *, number: str, binding: str, exports: bool) -> CasillaDefinition:
    return CasillaDefinition(
        id=casilla_id,
        number=number,
        localization_keys=(f"test.schema.casilla.{number}.label",),
        section=("iva", "anual"),
        input_kind="bound",
        binding=binding,
        export_refs=("modelo-390-page-02.field",) if exports else (),
        legal_refs=_LEGAL,
        source_refs=_SOURCE,
    )


def _split_revision() -> ModeloRevision:
    """A tier split into a rate-blind total layer and one rate-specific box."""
    return ModeloRevision(
        id="2010-y-siguientes",
        localization_key="test.schema.revision.2010-y-siguientes.label",
        valid_from=date(2024, 1, 1),
        period_selector=PeriodSelector(year_from=2024, periods=(_ANNUAL_PERIOD,)),
        legal_refs=_LEGAL,
        source_refs=_SOURCE,
        bindings=(
            _binding("m390-super-reducido-total", applied_rates=None),
            _binding("m390-super-reducido-4pct", applied_rates=(Decimal("0.04"),)),
        ),
        casillas=(
            _casilla(_TOTAL_CASILLA, number="9001", binding="m390-super-reducido-total", exports=False),
            _casilla(_BOX_4PCT, number="02", binding="m390-super-reducido-4pct", exports=True),
        ),
    )


def _coordinator_diagnostics(values: dict[CasillaId, Decimal]) -> tuple[CalculationSourceDiagnostic, ...]:
    """Every advisory the COORDINATOR raises, not the collector called directly."""
    return collect_bucket_aggregation_advisory_diagnostics(
        _split_revision(),
        values,
        modelo=Modelo.M390.value,
        period_token=_ANNUAL_PERIOD,
        filing_year=_FILING_YEAR,
        bucket_id=_BUCKET_ID,
    )


def test_the_advisory_names_the_unaccounted_amount_and_its_tier() -> None:
    """420.00 declared, 300.00 in the 4 % box: 120.00 carries no rate.

    The operator's repair is to record the rate on those ledger rows, so the
    amount and the tier are the two things the message must carry -- without
    them the advisory says only that something is wrong.
    """
    diagnostics = collect_rate_box_coverage_diagnostics(
        _split_revision(),
        {_TOTAL_CASILLA: Decimal("420.00"), _BOX_4PCT: Decimal("300.00")},
    )

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.reason == _REASON
    assert "120.00" in diagnostic.message
    assert IvaRateKind.SUPER_REDUCED.value in diagnostic.message
    assert diagnostic.remedy is not None


def test_a_breakdown_reaching_its_total_raises_nothing() -> None:
    """The negative control: an advisory that always fires teaches nothing."""
    diagnostics = collect_rate_box_coverage_diagnostics(
        _split_revision(),
        {_TOTAL_CASILLA: Decimal("420.00"), _BOX_4PCT: Decimal("420.00")},
    )

    assert diagnostics == ()


def test_the_coordinator_raises_the_advisory_and_returns() -> None:
    """The wiring and the non-blocking property, which break together.

    A collector that returns the right rows and is never called protects nobody,
    so nothing here calls the collector -- remove its line from the coordinator
    and this test goes red. And the coordinator RETURNING rather than raising is
    the whole basis of the split: refusing here would withhold the number the
    ledger repair depends on, and would make the export refusal unreachable,
    since nothing would get that far.
    """
    diagnostics = _coordinator_diagnostics({_TOTAL_CASILLA: Decimal("420.00"), _BOX_4PCT: Decimal("300.00")})

    assert _REASON in {diagnostic.reason for diagnostic in diagnostics}
