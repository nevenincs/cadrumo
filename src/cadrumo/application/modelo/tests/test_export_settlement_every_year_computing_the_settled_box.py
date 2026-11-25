"""Every supported Modelo 100 ejercicio that computes RESINGDEV settles from it, through the real export.

The two newest dictionaries both state "Resultado a ingresar o a devolver
(casilla [0670] o casilla [0695])" for RESINGDEV: the remainder 0695 once the spouse
compensation suspends part of an amount to pay (0693), otherwise the result
0670; a waived refund (0694) leaves it without a value. The years come from
what each revision computes, never from a list here. Each draft is calculated
by the real builder over the published revision and the record is written by
the XSD-checked XML export; each expected amount is read from the draft's own
boxes.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest
from defusedxml import ElementTree as DefusedElementTree

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.modelo import Modelo
from ....core.payment_instalment_election import PaymentInstalmentElection
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.payment_instalment_split import first_instalment_share
from ....domain.calculations.registry.result_casillas import derive_result_disposition
from ....domain.calculations.registry.tests.authored_editions import (
    newest_authored_editions,
    supported_authored_exercises,
)
from ....domain.deadlines.models import RefundAccount
from ....domain.filing.protocols import ModeloInputValue
from ....domain.filing.schema import ModeloDraft
from ....domain.modelos.errors import ModeloExportError
from ....domain.submission.models import ModeloDraftStatus
from ...filing.draft_construction import build_draft
from ...filing.export import export_draft
from ...filing.runtime import ModeloOperatorProfile, RegistrySchemaAccessor, build_runtime_schema_provider
from ...filing.tests.export_support import filer_with_nothing_else, m151_producer_snapshot
from ..export_settlement import SettlementRefusal, declared_settlement, settlement_dictionary_values
from ..settlement_casilla import declaration_settlement_casilla_id

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_SALARY = "0003"
_RESULT: CasillaId = validated_casilla_id("0670")
_SUSPENDED = "0693"
_WAIVED = "0694"
_REMAINDER: CasillaId = validated_casilla_id("0695")
_SETTLED: CasillaId = validated_casilla_id("RESINGDEV")
_WITHHELD = "renta-retencion-soportada-trabajo"
_REFUND_IBAN = "ES9121000418450200051332"


def _provider(operation: PinnedAuthorityOperation, year: int) -> RegistrySchemaAccessor:
    return build_runtime_schema_provider(
        filing_year=year, period=Period.from_year_and_code(year, "0A"), modelos=("100",), operation=operation
    )


def _years_computing_the_settled_box(operation: PinnedAuthorityOperation) -> list[int]:
    return [
        year
        for year in supported_authored_exercises("100")
        if declaration_settlement_casilla_id("100", _provider(operation, year).get_snapshot("100").revision) == _SETTLED
    ]


def _draft(provider: RegistrySchemaAccessor, year: int, inputs: Mapping[str, ModeloInputValue]) -> ModeloDraft:
    stated = filer_with_nothing_else(provider)
    stated |= {_SALARY: Decimal("30000.00"), **inputs}
    amounts = {key: value for key, value in stated.items() if isinstance(value, Decimal)}
    bound = resolve_available_bound_inputs_by_casilla_id(provider.get_snapshot("100").revision, amounts)
    return build_draft(
        modelo="100",
        period=Period.from_year_and_code(year, "0A"),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="DECLARANTE PRUEBA"),
        inputs={**bound, **stated},
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _values(draft: ModeloDraft) -> dict[CasillaId, object]:
    return {value.casilla_id: value.value for value in draft.values}


def _money(draft: ModeloDraft, casilla_id: CasillaId) -> Decimal:
    value = _values(draft)[casilla_id]
    assert isinstance(value, Decimal)
    return value


def _compose(
    operation: PinnedAuthorityOperation,
    provider: RegistrySchemaAccessor,
    year: int,
    draft: ModeloDraft,
    instalment: PaymentInstalmentElection = PaymentInstalmentElection.SINGLE,
) -> dict[str, object]:
    period = Period.from_year_and_code(year, "0A")
    disposition = derive_result_disposition("100", {_RESULT: _money(draft, _RESULT)}, period=period)
    return settlement_dictionary_values(
        disposition=disposition,
        settlement=declared_settlement(
            "100", provider.get_snapshot("100").revision, _values(draft), disposition=disposition
        ),
        instalment=instalment,
        first_instalment_share=first_instalment_share("100", period_day=period.end_date, authority=operation),
        charge_account=None,
        refund_account=RefundAccount(iban=_REFUND_IBAN),
    )


def _exported_settlement(
    provider: RegistrySchemaAccessor, draft: ModeloDraft, settlement: Mapping[str, object], path: Path
) -> dict[str, str]:
    export_draft(
        draft,
        output_path=path,
        producer_snapshot=m151_producer_snapshot().model_copy(update={"modelo": Modelo("100")}),
        dictionary_values=settlement,
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity=None,
        schema_provider=provider,
    )
    root = DefusedElementTree.fromstring(path.read_bytes())
    (block,) = [element for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "DatosIngresoDevolucion"]
    return {
        element.tag.rsplit("}", 1)[-1]: element.text
        for element in block.iter()
        if len(element) == 0 and element.text is not None
    }


def test_the_two_newest_revisions_settle_from_their_computed_box(operation: PinnedAuthorityOperation) -> None:
    """Guards the years below from running over nothing, and pins the two newest authored dictionaries among them."""
    years = _years_computing_the_settled_box(operation)

    assert set(newest_authored_editions("100", 2)) <= set(years)


def test_a_plain_amount_to_pay_is_paid_from_the_settled_box(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    for year in _years_computing_the_settled_box(operation):
        provider = _provider(operation, year)
        draft = _draft(provider, year, {})
        result = _money(draft, _RESULT)
        assert result > 0 and _money(draft, _SETTLED) == result, year

        rows = _exported_settlement(
            provider, draft, _compose(operation, provider, year, draft), tmp_path / f"{year}.xml"
        )

        assert rows == {"TIPODECLARACION": "I", "ING_IMPORTE": f"{result:.2f}"}, year


def test_a_suspended_part_leaves_the_remainder_0695_to_pay_and_to_split(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    for year in _years_computing_the_settled_box(operation):
        provider = _provider(operation, year)
        draft = _draft(provider, year, {_SUSPENDED: Decimal("200.00")})
        result, remainder = _money(draft, _RESULT), _money(draft, _REMAINDER)
        assert remainder == result - Decimal("200.00") > 0 and _money(draft, _SETTLED) == remainder, year

        at_once = _exported_settlement(
            provider, draft, _compose(operation, provider, year, draft), tmp_path / f"once-{year}.xml"
        )
        split = _exported_settlement(
            provider,
            draft,
            _compose(operation, provider, year, draft, PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_PAID),
            tmp_path / f"split-{year}.xml",
        )

        assert at_once == {"TIPODECLARACION": "I", "ING_IMPORTE": f"{remainder:.2f}"}, year
        first = Decimal(split["ING_IMPORTE_PF1"])
        assert first + Decimal(split["ING_IMPORTE_PF2"]) == remainder, year
        assert abs(first - remainder * Decimal("0.60")) < Decimal("0.01"), year


def test_a_refund_is_paid_out_from_the_settled_box(operation: PinnedAuthorityOperation, tmp_path: Path) -> None:
    for year in _years_computing_the_settled_box(operation):
        provider = _provider(operation, year)
        draft = _draft(provider, year, {_WITHHELD: Decimal("20000.00")})
        result = _money(draft, _RESULT)
        assert result < 0 and _money(draft, _SETTLED) == result, year

        rows = _exported_settlement(
            provider, draft, _compose(operation, provider, year, draft), tmp_path / f"{year}.xml"
        )

        assert rows == {
            "TIPODECLARACION": "D",
            "DEV_IMPORTE": f"{-result:.2f}",
            "DEV_CUENTACORRIENTE": _REFUND_IBAN,
        }, year


def test_a_waived_refund_leaves_the_settled_box_without_a_value_and_refuses_the_settlement(
    operation: PinnedAuthorityOperation,
) -> None:
    for year in _years_computing_the_settled_box(operation):
        provider = _provider(operation, year)
        draft = _draft(provider, year, {_WITHHELD: Decimal("20000.00"), _WAIVED: Decimal("100.00")})
        assert _money(draft, _RESULT) < 0 and _values(draft).get(_SETTLED) is None, year

        settled = declared_settlement("100", provider.get_snapshot("100").revision, _values(draft), disposition=None)
        with pytest.raises(ModeloExportError) as refused:
            _compose(operation, provider, year, draft)

        assert settled.refusal is SettlementRefusal.RESULT_UNKNOWN, year
        assert refused.value.context == {"cause": "result_unknown", "result_disposition": "D"}, year


def test_a_result_to_pay_wholly_suspended_is_refused_as_unsupported(operation: PinnedAuthorityOperation) -> None:
    for year in _years_computing_the_settled_box(operation):
        provider = _provider(operation, year)
        payable = _money(_draft(provider, year, {}), _RESULT)
        draft = _draft(provider, year, {_SUSPENDED: payable})
        assert _money(draft, _SETTLED) == 0, year

        with pytest.raises(ModeloExportError) as refused:
            _compose(operation, provider, year, draft)

        assert refused.value.context == {"cause": "settlement_unsupported", "result_disposition": "I"}, year
