"""A revision that computes no settled box pays or refunds its result only while nothing is suspended.

The dictionary of every ejercicio states "Resultado a ingresar o a devolver
(casilla [0670] o casilla [0695])": the remainder 0695 once the spouse
compensation suspends part of an amount to pay (0693), otherwise the result
0670. A revision that computes no box of that role has no remainder, so its
settlement reads the result while the suspended part is nothing and refuses a
positive part as unsupported rather than pay the result in the remainder's
place. Every supported ejercicio of the shipped registry now computes the
settled box, so that settlement is no longer reachable from a published
revision; it stays the rule for a revision that computes none. Each such
revision here is the published one of a supported ejercicio with its computed
settled box made a manual one, which is exactly the shape the rule reads. The
years come from the registry's support envelope, never from a list here. Each
expected amount is read from the calculated draft's own boxes.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.payment_instalment_election import PaymentInstalmentElection
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.payment_instalment_split import first_instalment_share
from ....domain.calculations.registry.result_casillas import derive_result_disposition
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.tests.authored_editions import supported_authored_exercises
from ....domain.deadlines.models import RefundAccount
from ....domain.filing.protocols import ModeloInputValue
from ....domain.filing.schema import ModeloDraft
from ....domain.modelos.errors import ModeloExportError
from ....domain.submission.models import ModeloDraftStatus
from ...filing.draft_construction import build_draft
from ...filing.runtime import ModeloOperatorProfile, RegistrySchemaAccessor, build_runtime_schema_provider
from ...filing.tests.export_support import filer_with_nothing_else
from ..export_settlement import SettlementRefusal, declared_settlement, settlement_dictionary_values
from ..settlement_casilla import (
    declaration_settlement_casilla_id,
    declaration_settlement_remainder_casilla_ids,
    settlement_casilla_role,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_SALARY = "0003"
_RESULT: CasillaId = validated_casilla_id("0670")
_SUSPENDED: CasillaId = validated_casilla_id("0693")
_WAIVED: CasillaId = validated_casilla_id("0694")
_WITHHELD = "renta-retencion-soportada-trabajo"
_REFUND_IBAN = "ES9121000418450200051332"


def _without_the_settled_box(revision: ModeloRevision) -> ModeloRevision:
    """The revision with every computed box of the settlement role made a manual one, so it computes none."""
    role = settlement_casilla_role("100")
    assert role is not None
    return revision.model_copy(
        update={
            "casillas": tuple(
                casilla.model_copy(update={"input_kind": InputKind.MANUAL})
                if casilla.semantic_role == role and casilla.input_kind is InputKind.COMPUTED
                else casilla
                for casilla in revision.casillas
            )
        }
    )


def _years_settled_from_the_result(operation: PinnedAuthorityOperation) -> list[int]:
    """The supported ejercicios, each read with its settled box removed so it settles from its result."""
    years = list(supported_authored_exercises("100"))
    assert years
    return years


def _settling_from_the_result(operation: PinnedAuthorityOperation, year: int) -> ModeloRevision:
    return _without_the_settled_box(_provider(operation, year).get_snapshot("100").revision)


def _provider(operation: PinnedAuthorityOperation, year: int) -> RegistrySchemaAccessor:
    return build_runtime_schema_provider(
        filing_year=year, period=Period.from_year_and_code(year, "0A"), modelos=("100",), operation=operation
    )


def _result_is_calculated(provider: RegistrySchemaAccessor) -> bool:
    revision = provider.get_snapshot("100").revision
    return next(c for c in revision.casillas if c.id == _RESULT).input_kind is InputKind.COMPUTED


def _draft(provider: RegistrySchemaAccessor, year: int, inputs: Mapping[str, ModeloInputValue]) -> ModeloDraft:
    period = Period.from_year_and_code(year, "0A")
    stated = filer_with_nothing_else(provider)
    stated |= {_SALARY: Decimal("30000.00"), **inputs}
    amounts = {key: value for key, value in stated.items() if isinstance(value, Decimal)}
    bound = resolve_available_bound_inputs_by_casilla_id(provider.get_snapshot("100").revision, amounts)
    return build_draft(
        modelo="100",
        period=period,
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
    revision: ModeloRevision,
    year: int,
    draft: ModeloDraft,
    instalment: PaymentInstalmentElection = PaymentInstalmentElection.SINGLE,
) -> dict[str, object]:
    """Compose the settlement rows from the draft as the export does: disposition from 0670, amount per the revision."""
    period = Period.from_year_and_code(year, "0A")
    disposition = derive_result_disposition("100", {_RESULT: _money(draft, _RESULT)}, period=period)
    return settlement_dictionary_values(
        disposition=disposition,
        settlement=declared_settlement("100", revision, _values(draft), disposition=disposition),
        instalment=instalment,
        first_instalment_share=first_instalment_share("100", period_day=period.end_date, authority=operation),
        charge_account=None,
        refund_account=RefundAccount(iban=_REFUND_IBAN),
    )


def test_every_supported_year_computes_the_settled_box_so_only_a_revision_without_it_settles_from_the_result(
    operation: PinnedAuthorityOperation,
) -> None:
    """The published revisions all compute RESINGDEV; the revision without it has the result as its settled box."""
    years = _years_settled_from_the_result(operation)

    for year in years:
        published = _provider(operation, year).get_snapshot("100").revision
        assert declaration_settlement_remainder_casilla_ids("100", published) == (), year
        assert declaration_settlement_casilla_id("100", published) != _RESULT, year

        revision = _settling_from_the_result(operation, year)
        assert declaration_settlement_casilla_id("100", revision) == _RESULT, year
        assert declaration_settlement_remainder_casilla_ids("100", revision) == (_SUSPENDED, _WAIVED), year


def test_a_plain_amount_to_pay_is_paid_and_split_from_the_result(operation: PinnedAuthorityOperation) -> None:
    for year in _years_settled_from_the_result(operation):
        provider = _provider(operation, year)
        inputs: dict[str, ModeloInputValue] = (
            {} if _result_is_calculated(provider) else {str(_RESULT): Decimal("900.00")}
        )
        draft = _draft(provider, year, inputs)
        result = _money(draft, _RESULT)
        assert result > 0 and _values(draft)[_SUSPENDED] is None, year

        at_once = _compose(operation, _settling_from_the_result(operation, year), year, draft)
        split = _compose(
            operation,
            _settling_from_the_result(operation, year),
            year,
            draft,
            PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_PAID,
        )

        assert at_once == {"TIPODECLARACION": "I", "ING_IMPORTE": result, "ING_CUENTACORRIENTE": None}, year
        first, second = split["ING_IMPORTE_PF1"], split["ING_IMPORTE_PF2"]
        assert isinstance(first, Decimal) and isinstance(second, Decimal)
        assert first + second == result and abs(first - result * Decimal("0.60")) < Decimal("0.01"), year


def test_a_suspended_part_is_refused_because_the_remainder_is_not_computed(
    operation: PinnedAuthorityOperation,
) -> None:
    for year in _years_settled_from_the_result(operation):
        provider = _provider(operation, year)
        inputs: dict[str, ModeloInputValue] = {_SUSPENDED: Decimal("200.00")}
        if not _result_is_calculated(provider):
            inputs[str(_RESULT)] = Decimal("900.00")
        draft = _draft(provider, year, inputs)
        settling = _settling_from_the_result(operation, year)
        assert _money(draft, _SUSPENDED) == Decimal("200.00") and _money(draft, _RESULT) > 0, year

        settled = declared_settlement("100", settling, _values(draft), disposition=None)
        with pytest.raises(ModeloExportError) as refused:
            _compose(operation, _settling_from_the_result(operation, year), year, draft)

        assert settled.refusal is SettlementRefusal.SETTLEMENT_UNSUPPORTED, year
        assert refused.value.context == {"cause": "settlement_unsupported", "result_disposition": "I"}, year
        assert refused.value.translated_message == "application.modelo.errors.export_settlement_unsupported", year


def test_a_waived_refund_is_refused_because_the_remainder_is_not_computed(
    operation: PinnedAuthorityOperation,
) -> None:
    """Art. 97.6 a) LIRPF: a refund the filer waives in part is not paid out whole from the result."""
    for year in _years_settled_from_the_result(operation):
        provider = _provider(operation, year)
        inputs: dict[str, ModeloInputValue] = {_WAIVED: Decimal("400.00")}
        if _result_is_calculated(provider):
            inputs[_WITHHELD] = Decimal("20000.00")
        else:
            inputs[str(_RESULT)] = Decimal("-1000.00")
        draft = _draft(provider, year, inputs)
        settling = _settling_from_the_result(operation, year)
        assert _money(draft, _WAIVED) == Decimal("400.00") and _money(draft, _RESULT) < 0, year

        settled = declared_settlement("100", settling, _values(draft), disposition=None)
        with pytest.raises(ModeloExportError) as refused:
            _compose(operation, _settling_from_the_result(operation, year), year, draft)

        assert settled.refusal is SettlementRefusal.SETTLEMENT_UNSUPPORTED, year
        assert refused.value.context == {"cause": "settlement_unsupported", "result_disposition": "D"}, year
        assert refused.value.translated_message == "application.modelo.errors.export_settlement_unsupported", year


def test_a_waived_part_left_blank_is_nothing_as_the_calculation_reads_it(
    operation: PinnedAuthorityOperation,
) -> None:
    for year in _years_settled_from_the_result(operation):
        revision = _settling_from_the_result(operation, year)
        values: dict[CasillaId, object] = {_RESULT: Decimal("-310.40"), _WAIVED: None}

        settled = declared_settlement("100", revision, values, disposition=None)
        never_keyed = declared_settlement("100", revision, {_RESULT: Decimal("-310.40")}, disposition=None)

        assert settled.amount == Decimal("-310.40") and settled.refusal is None, year
        assert never_keyed == settled, year


def test_a_suspended_part_left_blank_is_nothing_as_the_calculation_reads_it(
    operation: PinnedAuthorityOperation,
) -> None:
    for year in _years_settled_from_the_result(operation):
        revision = _settling_from_the_result(operation, year)
        values: dict[CasillaId, object] = {_RESULT: Decimal("900.00"), _SUSPENDED: None}

        settled = declared_settlement("100", revision, values, disposition=None)
        never_keyed = declared_settlement("100", revision, {_RESULT: Decimal("900.00")}, disposition=None)

        assert settled.amount == Decimal("900.00") and settled.refusal is None, year
        assert never_keyed == settled, year


def test_a_refund_is_paid_out_from_the_result(operation: PinnedAuthorityOperation) -> None:
    for year in _years_settled_from_the_result(operation):
        provider = _provider(operation, year)
        inputs: dict[str, ModeloInputValue] = (
            {_WITHHELD: Decimal("20000.00")} if _result_is_calculated(provider) else {str(_RESULT): Decimal("-310.40")}
        )
        draft = _draft(provider, year, inputs)
        result = _money(draft, _RESULT)
        assert result < 0, year

        rows = _compose(operation, _settling_from_the_result(operation, year), year, draft)

        assert rows == {
            "TIPODECLARACION": "D",
            "DEV_IMPORTE": -result,
            "DEV_CUENTACORRIENTE": _REFUND_IBAN,
        }, year
