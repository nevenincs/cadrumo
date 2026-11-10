"""A 2025 Modelo 100 pays or refunds the box it settles, through the real calculation and the XSD-checked export.

The draft is calculated by the real builder over the published 2025 revision,
the settlement is composed from it as the export composes it, and the record
is written by the real XML export, which refuses any value the official XSD
does not admit. The settled box is RESINGDEV (0700), "Resultado a ingresar o a
devolver (casilla [0670] o casilla [0695])": the result 0670, or the remainder
0695 once the spouse compensation suspends part of an amount to pay (0693).
Each expected amount is read from the calculated draft's own boxes, never from
the code under test.
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
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition
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

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_YEAR = newest_authored_edition("100")
_PERIOD = Period.from_year_and_code(_YEAR, "0A")
_SALARY = "0003"
_RESULT: CasillaId = validated_casilla_id("0670")
_SUSPENDED = "0693"
_WAIVED = "0694"
_REMAINDER: CasillaId = validated_casilla_id("0695")
_SETTLED: CasillaId = validated_casilla_id("0700")
_WITHHELD = "renta-retencion-soportada-trabajo"
_REFUND_IBAN = "ES9121000418450200051332"


def _provider(operation: PinnedAuthorityOperation) -> RegistrySchemaAccessor:
    return build_runtime_schema_provider(filing_year=_YEAR, period=_PERIOD, modelos=("100",), operation=operation)


def _draft(provider: RegistrySchemaAccessor, inputs: Mapping[str, ModeloInputValue]) -> ModeloDraft:
    stated = filer_with_nothing_else(provider)
    stated |= {_SALARY: Decimal("30000.00"), **inputs}
    amounts = {key: value for key, value in stated.items() if isinstance(value, Decimal)}
    bound = resolve_available_bound_inputs_by_casilla_id(provider.get_snapshot("100").revision, amounts)
    return build_draft(
        modelo="100",
        period=_PERIOD,
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
    draft: ModeloDraft,
    instalment: PaymentInstalmentElection = PaymentInstalmentElection.SINGLE,
) -> dict[str, object]:
    """Compose the settlement rows from the draft as the export does: disposition from 0670, amount from 0700."""
    values = _values(draft)
    disposition = derive_result_disposition("100", {_RESULT: _money(draft, _RESULT)}, period=_PERIOD)
    return settlement_dictionary_values(
        disposition=disposition,
        settlement=declared_settlement("100", provider.get_snapshot("100").revision, values, disposition=disposition),
        instalment=instalment,
        first_instalment_share=first_instalment_share("100", period_day=_PERIOD.end_date, authority=operation),
        charge_account=None,
        refund_account=RefundAccount(iban=_REFUND_IBAN),
    )


def _exported_settlement(
    provider: RegistrySchemaAccessor, draft: ModeloDraft, settlement: Mapping[str, object], path: Path
) -> dict[str, str]:
    """Write the record through the XSD-checked export and read back its ``DatosIngresoDevolucion`` rows."""
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


def test_a_plain_amount_to_pay_is_paid_from_the_settled_box(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    provider = _provider(operation)
    draft = _draft(provider, {})
    result = _money(draft, _RESULT)
    assert result > 0 and _money(draft, _SETTLED) == result

    rows = _exported_settlement(provider, draft, _compose(operation, provider, draft), tmp_path / "plain.xml")

    assert rows == {"TIPODECLARACION": "I", "ING_IMPORTE": f"{result:.2f}"}


def test_a_suspended_part_leaves_the_remainder_0695_to_pay_and_to_split(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    """With 200,00 suspended against the spouse's refund the record pays 0695, never the result 0670."""
    provider = _provider(operation)
    draft = _draft(provider, {_SUSPENDED: Decimal("200.00")})
    result, remainder = _money(draft, _RESULT), _money(draft, _REMAINDER)
    assert remainder == result - Decimal("200.00") > 0 and _money(draft, _SETTLED) == remainder

    at_once = _exported_settlement(provider, draft, _compose(operation, provider, draft), tmp_path / "once.xml")
    split = _exported_settlement(
        provider,
        draft,
        _compose(operation, provider, draft, PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_PAID),
        tmp_path / "split.xml",
    )

    assert at_once == {"TIPODECLARACION": "I", "ING_IMPORTE": f"{remainder:.2f}"}
    first = Decimal(split["ING_IMPORTE_PF1"])
    assert split["TIPODECLARACION"] == "I" and "ING_IMPORTE" not in split
    assert first + Decimal(split["ING_IMPORTE_PF2"]) == remainder
    assert abs(first - remainder * Decimal("0.60")) < Decimal("0.01")


def test_a_refund_is_paid_out_from_the_settled_box(operation: PinnedAuthorityOperation, tmp_path: Path) -> None:
    provider = _provider(operation)
    draft = _draft(provider, {_WITHHELD: Decimal("20000.00")})
    result = _money(draft, _RESULT)
    assert result < 0 and _money(draft, _SETTLED) == result

    rows = _exported_settlement(provider, draft, _compose(operation, provider, draft), tmp_path / "refund.xml")

    assert rows == {"TIPODECLARACION": "D", "DEV_IMPORTE": f"{-result:.2f}", "DEV_CUENTACORRIENTE": _REFUND_IBAN}


def test_an_unresolved_settled_box_refuses_the_settlement_and_never_reads_the_result(
    operation: PinnedAuthorityOperation,
) -> None:
    """A waived refund leaves 0700 without a value; the refund of 0670 is not composed in its place."""
    provider = _provider(operation)
    draft = _draft(provider, {_WITHHELD: Decimal("20000.00"), _WAIVED: Decimal("100.00")})
    assert _money(draft, _RESULT) < 0 and _values(draft).get(_SETTLED) is None

    settled = declared_settlement("100", provider.get_snapshot("100").revision, _values(draft), disposition=None)
    with pytest.raises(ModeloExportError) as refused:
        _compose(operation, provider, draft)

    assert settled.refusal is SettlementRefusal.RESULT_UNKNOWN
    assert refused.value.context == {"cause": "result_unknown", "result_disposition": "D"}
    assert refused.value.translated_message == "application.modelo.errors.export_settlement_unknown"


def test_a_result_to_pay_wholly_suspended_is_refused_as_unsupported(operation: PinnedAuthorityOperation) -> None:
    """The design gives no settlement block for a result to pay of which nothing remains to pay."""
    provider = _provider(operation)
    payable = _money(_draft(provider, {}), _RESULT)
    draft = _draft(provider, {_SUSPENDED: payable})
    assert _money(draft, _SETTLED) == 0

    with pytest.raises(ModeloExportError) as refused:
        _compose(operation, provider, draft)

    assert refused.value.context == {"cause": "settlement_unsupported", "result_disposition": "I"}
    assert refused.value.translated_message == "application.modelo.errors.export_settlement_unsupported"
