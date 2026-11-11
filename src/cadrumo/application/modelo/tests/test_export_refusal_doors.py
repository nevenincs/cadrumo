"""An export the filer's facts stop is a refusal with served words and, where one exists, a door.

The account, instalment and period causes were once reported as failures to
write the file. They are refusals: nothing is wrong with writing, and the
operator can put the cause right. Each carries a registered REFUSED code,
catalogue words that need no further context, and a verdict that names the
action which puts it right or says honestly that none does.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.errors.error_codes import (
    ErrorCategory,
    get_registered_error_code,
    resolve_error_message,
)
from ....core.i18n.render import lookup_translation
from ....core.operator_action_enums import ActionArgumentStatus, ActionConditionality, NoRecoveryOutcome
from ....core.payment_instalment_election import PaymentInstalmentElection
from ....core.period import Period
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.deadlines.models import ChargeAccount
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.errors import ModeloExportError
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...operations.error_detail import build_operation_error_detail
from ...operator_surface.action_targets import resolve_recorded_precondition_action
from ..action_errors import (
    ModeloChargeAccountMissingError,
    ModeloExportPeriodUnmappableError,
    ModeloInstalmentElectionRefusedError,
    ModeloRefundAccountMissingError,
)
from ..export_preparation import resolve_work_unit_period
from ..export_settlement import DeclaredSettlement, settlement_dictionary_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("en", "es", "ca", "hu")
_SIXTY = Decimal("0.60")


def _settle(
    disposition: ResultDisposition,
    amount: str,
    *,
    instalment: PaymentInstalmentElection = PaymentInstalmentElection.SINGLE,
    share: Decimal | None = _SIXTY,
    charge: ChargeAccount | None = None,
) -> dict[str, object]:
    return settlement_dictionary_values(
        disposition=disposition,
        settlement=DeclaredSettlement(amount=Decimal(amount), refusal=None),
        instalment=instalment,
        first_instalment_share=share,
        charge_account=charge,
        refund_account=None,
    )


def _assert_served_in_every_language(error: BaseException) -> None:
    for locale in _LOCALES:
        message = resolve_error_message(error, locale=locale)
        assert message
        assert "%{" not in message and "{" not in message
        assert "errors." not in message and "application.modelo" not in message


def _assert_registered_words_resolve(error: BaseException) -> None:
    registered = get_registered_error_code(error)
    for key in (registered.message_key, getattr(error, "translated_message", None)):
        if key is None:
            continue
        for locale in _LOCALES:
            words = lookup_translation(key, locale=locale)
            assert words is not None and words.strip(), (key, locale)


@pytest.mark.parametrize(
    ("disposition", "amount", "error_type", "code", "role"),
    [
        (
            ResultDisposition.DEVOLUCION,
            "-10.00",
            ModeloRefundAccountMissingError,
            "REFUSED_MODELO_REFUND_ACCOUNT_MISSING",
            "refund",
        ),
        (
            ResultDisposition.DOMICILIACION,
            "10.00",
            ModeloChargeAccountMissingError,
            "REFUSED_MODELO_CHARGE_ACCOUNT_MISSING",
            "charge",
        ),
    ],
)
def test_a_missing_account_is_a_refusal_whose_door_is_adding_an_account(
    disposition: ResultDisposition,
    amount: str,
    error_type: type[Exception],
    code: str,
    role: str,
) -> None:
    with pytest.raises(error_type) as refused:
        _settle(disposition, amount)
    error = refused.value

    registered = get_registered_error_code(error)
    assert registered.code == code
    assert registered.category is ErrorCategory.REFUSED
    _assert_registered_words_resolve(error)
    _assert_served_in_every_language(error)

    detail = build_operation_error_detail(error)
    assert detail is not None
    assert detail.error_code == code
    assert detail.refusal_words is not None
    assert "{" not in detail.refusal_words
    assert code not in detail.refusal_words
    verdict = detail.precondition_verdict()
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.ledger.account.add"
    assert verdict.no_recovery_outcome is None
    assert verdict.conditionality is ActionConditionality.REQUIRES_ARGUMENTS
    assert verdict.missing_argument_names == ("holding", "label")
    assert {item.status for item in verdict.argument_bindings} == {ActionArgumentStatus.MISSING}
    (evidence,) = verdict.evidence
    assert evidence.values["account_role"] == role
    assert detail.context_mapping()["account_role"] == role

    resolved = resolve_recorded_precondition_action(verdict)
    assert resolved.action is not None
    assert resolved.action.cli_path is not None
    assert resolved.action.cli_path[-4:] == ("app", "ledger", "account", "add")
    assert set(resolved.missing_argument_names) == {"holding", "label"}


def test_a_debited_second_instalment_without_a_charge_account_names_the_same_door() -> None:
    with pytest.raises(ModeloChargeAccountMissingError) as refused:
        _settle(
            ResultDisposition.INGRESO,
            "100.00",
            instalment=PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_DEBITED,
        )

    verdict = refused.value.terminal_precondition_verdict
    assert verdict is not None and verdict.action is not None
    assert verdict.action.action_id == "operator.ledger.account.add"


@pytest.mark.parametrize(
    ("amount", "share", "reason"),
    [("100.00", None, "not_declared"), ("0.01", _SIXTY, "second_instalment_nothing")],
)
def test_an_instalment_split_the_export_cannot_write_is_a_refusal_with_an_honest_no_door(
    amount: str, share: Decimal | None, reason: str
) -> None:
    with pytest.raises(ModeloInstalmentElectionRefusedError) as refused:
        _settle(
            ResultDisposition.INGRESO,
            amount,
            instalment=PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_PAID,
            share=share,
        )
    error = refused.value

    registered = get_registered_error_code(error)
    assert registered.code == "REFUSED_MODELO_INSTALMENT_ELECTION"
    assert registered.category is ErrorCategory.REFUSED
    _assert_registered_words_resolve(error)
    _assert_served_in_every_language(error)

    detail = build_operation_error_detail(error)
    assert detail is not None
    assert detail.refusal_words is not None
    assert "{" not in detail.refusal_words
    assert registered.code not in detail.refusal_words
    assert detail.context_mapping()["reason"] == reason
    verdict = detail.precondition_verdict()
    assert verdict is not None
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_period_that_is_not_of_the_filing_year_is_a_refusal_not_a_write_failure() -> None:
    year = filing_year_envelope().horizon
    period = Period.from_year_and_code(year, "0A")
    stamp = datetime(year, 1, 10, 10, 0, tzinfo=UTC)
    revision_id = "r" + "0" * 63
    unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id="bucket",
            modelo=ModeloCode("100"),
            filing_year=year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id="bucket",
        modelo=ModeloCode("100"),
        filing_year=year,
        period=period,
        revision_id=revision_id,
        name="declaration",
        created_at=stamp,
        updated_at=stamp,
    )
    # Construction refuses a year that disagrees with the period, so the drifted record is a copy.
    drifted = unit.model_copy(update={"filing_year": year - 1})

    with pytest.raises(ModeloExportPeriodUnmappableError) as refused:
        resolve_work_unit_period(drifted)
    error = refused.value

    registered = get_registered_error_code(error)
    assert registered.code == "REFUSED_MODELO_EXPORT_PERIOD_UNMAPPABLE"
    assert registered.category is ErrorCategory.REFUSED
    _assert_registered_words_resolve(error)
    _assert_served_in_every_language(error)

    detail = build_operation_error_detail(error)
    assert detail is not None
    assert detail.refusal_words is not None
    assert "{" not in detail.refusal_words
    assert unit.work_unit_id in detail.refusal_words
    verdict = detail.precondition_verdict()
    assert verdict is not None
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL


def test_a_genuine_write_failure_keeps_the_failure_code() -> None:
    error = ModeloExportError(
        translated_message="application.modelo.errors.export_draft_write_failed",
        context={"calculation_revision_id": "revision-1"},
    )

    registered = get_registered_error_code(error)
    assert registered.code == "FAIL_MODELO_EXPORT"
    assert registered.category is ErrorCategory.FAIL
