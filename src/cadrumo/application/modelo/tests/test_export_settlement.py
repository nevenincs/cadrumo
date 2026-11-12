"""The settlement rows of a Modelo 100 record are the ones its official 2025 dictionary declares.

Each composition is checked against the published dictionary of the 2025
revision: every row it writes is a field that dictionary declares under
``DatosIngresoDevolucion``, and the rows of one block never mix with
another's. Amounts are worked by hand; account numbers are synthetic.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.errors.error_codes import resolve_error_message
from ....core.payment_instalment_election import PaymentInstalmentElection
from ....core.resources.bundled_data import resolve_corpus_binary
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.export_xml_dictionary import xml_dictionary_entries
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition, revision_covering
from ....domain.calculations.registry.tests.published_authority import published_revision, published_source_reference
from ....domain.deadlines.models import ChargeAccount, RefundAccount
from ....domain.modelos.errors import ModeloExportError
from ..action_errors import (
    ModeloChargeAccountMissingError,
    ModeloInstalmentElectionRefusedError,
    ModeloRefundAccountMissingError,
)
from ..export_settlement import DeclaredSettlement, SettlementRefusal, settlement_dictionary_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_SPANISH_IBAN = "ES9121000418450200051332"
_GERMAN_IBAN = "DE89370400440532013000"
_CHARGE = ChargeAccount(iban=_SPANISH_IBAN)
_SIXTY = Decimal("0.60")


def _settled(amount: str) -> DeclaredSettlement:
    return DeclaredSettlement(amount=Decimal(amount), refusal=None)


def _settlement_paths() -> dict[str, str]:
    """The newest authored dictionary's settlement rows, by field id, with the record path each is written at."""
    revision = published_revision("100", str(revision_covering("100", newest_authored_edition("100")).id))
    layout = revision.export_layouts[0]
    assert layout.dictionary_source_ref is not None
    source = published_source_reference(str(layout.dictionary_source_ref))
    path = resolve_corpus_binary(*source.corpus_path.split("/"))
    assert path is not None
    entries = xml_dictionary_entries(
        layout,
        sources={str(source.id): source},
        source_payloads={str(source.id): path.read_bytes()},
        casillas=revision.casillas,
    )
    return {entry.field_id: entry.path for entry in entries if "/DatosIngresoDevolucion/" in entry.path}


def _blocks(values: dict[str, object]) -> set[str]:
    """The settlement blocks the populated rows are written in."""
    paths = _settlement_paths()
    assert set(values) <= set(paths), set(values) - set(paths)
    return {
        paths[field].split("/DatosIngresoDevolucion/", 1)[1].rsplit("/", 1)[0]
        for field, value in values.items()
        if value is not None and field != "TIPODECLARACION"
    }


def test_a_result_paid_at_once_states_its_amount_and_no_account() -> None:
    values = settlement_dictionary_values(
        disposition=ResultDisposition.INGRESO,
        settlement=_settled("1234.56"),
        first_instalment_share=_SIXTY,
        instalment=PaymentInstalmentElection.SINGLE,
        charge_account=None,
        refund_account=None,
    )

    assert values == {"TIPODECLARACION": "I", "ING_IMPORTE": Decimal("1234.56"), "ING_CUENTACORRIENTE": None}
    assert _blocks(values) == {"AINGRESAR/PAGONOFRACC"}


def test_a_direct_debit_states_the_charge_account() -> None:
    values = settlement_dictionary_values(
        disposition=ResultDisposition.DOMICILIACION,
        settlement=_settled("1234.56"),
        first_instalment_share=_SIXTY,
        instalment=PaymentInstalmentElection.SINGLE,
        charge_account=_CHARGE,
        refund_account=None,
    )

    assert values["TIPODECLARACION"] == "U" and values["ING_CUENTACORRIENTE"] == _SPANISH_IBAN


@pytest.mark.parametrize(
    ("disposition", "instalment", "first_account", "second_account", "second_debited"),
    [
        (
            ResultDisposition.INGRESO,
            PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_PAID,
            None,
            None,
            False,
        ),
        (
            ResultDisposition.INGRESO,
            PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_DEBITED,
            None,
            _SPANISH_IBAN,
            True,
        ),
        (
            ResultDisposition.DOMICILIACION,
            PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_DEBITED,
            _SPANISH_IBAN,
            _SPANISH_IBAN,
            True,
        ),
        (
            ResultDisposition.DOMICILIACION,
            PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_PAID,
            _SPANISH_IBAN,
            None,
            False,
        ),
    ],
)
def test_two_instalments_split_sixty_forty_in_the_fractioned_block(
    disposition: ResultDisposition,
    instalment: PaymentInstalmentElection,
    first_account: str | None,
    second_account: str | None,
    second_debited: bool,
) -> None:
    # 60 per cent of 1.000,01 is 600,006: 600,01 on filing and the remaining 400,00.
    values = settlement_dictionary_values(
        disposition=disposition,
        settlement=_settled("1000.01"),
        first_instalment_share=_SIXTY,
        instalment=instalment,
        charge_account=_CHARGE,
        refund_account=None,
    )

    assert values == {
        "TIPODECLARACION": disposition.value,
        "ING_IMPORTE_PF1": Decimal("600.01"),
        "ING_IMPORTE_PF2": Decimal("400.00"),
        "ING_DOMICILIA_PF2": second_debited,
        "ING_CUENTACORRIENTE_PF1": first_account,
        "ING_CUENTACORRIENTE_PF2": second_account,
    }
    assert _blocks(values) == {"AINGRESAR/PAGOFRACC"}


def test_a_debited_instalment_without_a_charge_account_is_refused() -> None:
    with pytest.raises(ModeloChargeAccountMissingError) as refused:
        settlement_dictionary_values(
            disposition=ResultDisposition.INGRESO,
            settlement=_settled("100.00"),
            first_instalment_share=_SIXTY,
            instalment=PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_DEBITED,
            charge_account=None,
            refund_account=None,
        )

    assert refused.value.context == {"account_role": "charge", "result_disposition": "I"}


def test_a_refund_states_its_positive_amount_into_a_spanish_account() -> None:
    values = settlement_dictionary_values(
        disposition=ResultDisposition.DEVOLUCION,
        settlement=_settled("-310.40"),
        first_instalment_share=_SIXTY,
        instalment=PaymentInstalmentElection.SINGLE,
        charge_account=None,
        refund_account=RefundAccount(iban=_SPANISH_IBAN),
    )

    assert values == {"TIPODECLARACION": "D", "DEV_IMPORTE": Decimal("310.40"), "DEV_CUENTACORRIENTE": _SPANISH_IBAN}
    assert _blocks(values) == {"ADEVOLVER"}


def test_a_refund_abroad_in_the_sepa_zone_states_the_account_and_its_bic() -> None:
    values = settlement_dictionary_values(
        disposition=ResultDisposition.DEVOLUCION,
        settlement=_settled("-310.40"),
        first_instalment_share=_SIXTY,
        instalment=PaymentInstalmentElection.SINGLE,
        charge_account=None,
        refund_account=RefundAccount(iban=_GERMAN_IBAN, swift_bic="COBADEFFXXX"),
    )

    assert values == {
        "TIPODECLARACION": "D",
        "DEV_IMPORTE": Decimal("310.40"),
        "DEV_CUENTACORRIENTESEPA": _GERMAN_IBAN,
        "DEV_SWIFT": "COBADEFFXXX",
    }
    assert _blocks(values) == {"ADEVOLVER", "ADEVOLVER/DEVSEPA"}


def test_a_nil_result_states_its_disposition_alone_and_an_absent_one_writes_nothing() -> None:
    nil = settlement_dictionary_values(
        disposition=ResultDisposition.NEGATIVA,
        settlement=_settled("0.00"),
        first_instalment_share=_SIXTY,
        instalment=PaymentInstalmentElection.SINGLE,
        charge_account=None,
        refund_account=None,
    )
    absent = settlement_dictionary_values(
        disposition=None,
        settlement=DeclaredSettlement(amount=None, refusal=SettlementRefusal.RESULT_UNKNOWN),
        instalment=PaymentInstalmentElection.SINGLE,
        first_instalment_share=_SIXTY,
        charge_account=None,
        refund_account=None,
    )

    assert nil == {"TIPODECLARACION": "N"} and set(nil) <= set(_settlement_paths())
    assert absent == {}


def test_a_refund_without_an_account_or_an_amount_is_refused() -> None:
    with pytest.raises(ModeloRefundAccountMissingError) as no_account:
        settlement_dictionary_values(
            disposition=ResultDisposition.DEVOLUCION,
            settlement=_settled("-1.00"),
            first_instalment_share=_SIXTY,
            instalment=PaymentInstalmentElection.SINGLE,
            charge_account=None,
            refund_account=None,
        )
    with pytest.raises(ModeloExportError) as no_amount:
        settlement_dictionary_values(
            disposition=ResultDisposition.INGRESO,
            settlement=DeclaredSettlement(amount=None, refusal=SettlementRefusal.RESULT_UNKNOWN),
            instalment=PaymentInstalmentElection.SINGLE,
            first_instalment_share=_SIXTY,
            charge_account=None,
            refund_account=None,
        )
    with pytest.raises(ModeloExportError) as unsupported:
        settlement_dictionary_values(
            disposition=ResultDisposition.INGRESO,
            settlement=DeclaredSettlement(amount=None, refusal=SettlementRefusal.SETTLEMENT_UNSUPPORTED),
            instalment=PaymentInstalmentElection.SINGLE,
            first_instalment_share=_SIXTY,
            charge_account=None,
            refund_account=None,
        )

    assert no_account.value.context == {"account_role": "refund", "result_disposition": "D"}
    assert no_amount.value.context == {"cause": "result_unknown", "result_disposition": "I"}
    assert unsupported.value.context == {"cause": "settlement_unsupported", "result_disposition": "I"}
    assert no_amount.value.translated_message == "application.modelo.errors.export_settlement_unknown"
    assert unsupported.value.translated_message == "application.modelo.errors.export_settlement_unsupported"


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
@pytest.mark.parametrize("refusal", list(SettlementRefusal))
def test_a_settlement_refusal_reads_in_every_language_and_is_no_write_failure(
    refusal: SettlementRefusal, locale: str
) -> None:
    with pytest.raises(ModeloExportError) as refused:
        settlement_dictionary_values(
            disposition=ResultDisposition.INGRESO,
            settlement=DeclaredSettlement(amount=None, refusal=refusal),
            instalment=PaymentInstalmentElection.SINGLE,
            first_instalment_share=_SIXTY,
            charge_account=None,
            refund_account=None,
        )

    generic = ModeloExportError(
        translated_message="application.modelo.errors.export_draft_write_failed",
        context={"calculation_revision_id": "revision-1"},
    )
    message = resolve_error_message(refused.value, locale=locale)
    assert message != resolve_error_message(generic, locale=locale)
    assert "application.modelo.errors" not in message and "%{" not in message


def test_a_split_the_modelo_does_not_declare_is_refused() -> None:
    with pytest.raises(ModeloInstalmentElectionRefusedError) as refused:
        settlement_dictionary_values(
            disposition=ResultDisposition.INGRESO,
            settlement=_settled("100.00"),
            instalment=PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_PAID,
            first_instalment_share=None,
            charge_account=None,
            refund_account=None,
        )

    assert refused.value.context == {"reason": "not_declared", "result_disposition": "I"}


def test_an_amount_whose_second_instalment_would_be_nothing_is_paid_at_once_never_split() -> None:
    """60 per cent of 0,01 is 0,006: the first instalment takes the cent and the second would be 0,00."""
    with pytest.raises(ModeloInstalmentElectionRefusedError) as refused:
        settlement_dictionary_values(
            disposition=ResultDisposition.INGRESO,
            settlement=_settled("0.01"),
            instalment=PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_PAID,
            first_instalment_share=_SIXTY,
            charge_account=None,
            refund_account=None,
        )
    at_once = settlement_dictionary_values(
        disposition=ResultDisposition.INGRESO,
        settlement=_settled("0.01"),
        instalment=PaymentInstalmentElection.SINGLE,
        first_instalment_share=_SIXTY,
        charge_account=None,
        refund_account=None,
    )
    least = settlement_dictionary_values(
        disposition=ResultDisposition.INGRESO,
        settlement=_settled("0.02"),
        instalment=PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_PAID,
        first_instalment_share=_SIXTY,
        charge_account=None,
        refund_account=None,
    )

    assert refused.value.context == {"reason": "second_instalment_nothing", "result_disposition": "I"}
    assert at_once == {"TIPODECLARACION": "I", "ING_IMPORTE": Decimal("0.01"), "ING_CUENTACORRIENTE": None}
    assert least["ING_IMPORTE_PF1"] == Decimal("0.01") and least["ING_IMPORTE_PF2"] == Decimal("0.01")
