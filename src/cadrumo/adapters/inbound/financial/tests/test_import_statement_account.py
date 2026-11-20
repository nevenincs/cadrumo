"""The ledger import operation reads the account a statement names and can register it.

Every case runs the registered executor over the real providers and the real
own-account register logic; only the encrypted stores are in-memory holders.
The IBANs are synthetic.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from .....application.ledger.actions_import import LedgerProviderID
from .....application.ledger.import_operation import (
    LEDGER_IMPORT_OPERATION_DEFINITION_ID,
    LedgerImportAccountRegistration,
    LedgerImportExecutionResult,
    LedgerImportExecutor,
    LedgerImportOperationPorts,
    LedgerImportRequest,
    LedgerImportResultProjection,
    project_ledger_import_result,
)
from .....application.ledger.tests.action_port_fakes import InMemoryEventRepository
from .....application.ledger.tests.in_memory_transaction_repository import InMemoryTransactionRepository
from .....application.operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from .....application.tests.operation_host_fakes import (
    IrreversibleSectionGrant,
    RecordingEvents,
    RecordingOperands,
    executor_context,
)
from .....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .....core.optional_extras import OFX_EXTRA
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....domain.currency.service import CurrencyNormalizationService
from .....domain.transactions.models import TransactionCatalogue
from .....domain.transactions.own_accounts import (
    OwnAccountHolding,
    OwnAccountRegister,
    OwnBankAccountDetails,
)
from .....tests.inventory import FIXTURES_DIR
from .....tests.optional_extra_absence import optional_extra_absent
from ..ledger_import import build_ledger_import_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_inbound_adapter]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_BBVA = FIXTURES_DIR / "financial" / "tabular-dialects" / "bank_bbva_2026Q1.csv"
_INVOICE_PDF = Path(__file__).parents[4] / "application/ledger/tests/_evidence_corpus/zugferd_en16931_invoice.pdf"
_IBAN_BBVA = "ES9121000418450200051332"
_IBAN_OTHER = "ES7921000813610123456789"
_MASK = "ES " + "·" * 4 + " 1332"
_NO_ACCOUNT_CSV = "Fecha,Concepto,Importe\n08/01/2026,Pago tarjeta,-10.00\n09/01/2026,Transferencia recibida,25.00\n"
_OFX = (
    "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:USASCII\nCHARSET:1252\n"
    "COMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n\n"
    "<OFX><BANKMSGSRSV1><STMTTRNRS><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS>"
    f"<STMTRS><CURDEF>EUR<BANKACCTFROM><BANKID>0001<ACCTID>{_IBAN_BBVA}<ACCTTYPE>CHECKING</BANKACCTFROM>"
    "<BANKTRANLIST><DTSTART>20260401<DTEND>20260430"
    "<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260415<TRNAMT>121.00<FITID>ofx-001<NAME>Client SL</STMTTRN>"
    "</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n"
)
_REGISTRATION = LedgerImportAccountRegistration(label="Cuenta BBVA", holding=OwnAccountHolding.TITULAR)


@pytest.fixture
def operation(monkeypatch: pytest.MonkeyPatch) -> Iterator[PinnedAuthorityOperation]:
    """Run an import inside one pinned authority operation for the one active profile."""
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    with bundled_indexed_authority().operation() as operation:
        yield operation


class _Register:
    """In-memory own-account register with the guarded store's load/apply/keep contract."""

    def __init__(self, *ibans: str) -> None:
        self.document = OwnAccountRegister()
        for index, iban in enumerate(ibans, start=1):
            self.document = self.document.with_new_account(
                OwnBankAccountDetails(label=f"Account {index}", holding=OwnAccountHolding.TITULAR, iban=iban),
            )

    def load(self) -> OwnAccountRegister:
        return self.document

    def mutate(self, change: Callable[[OwnAccountRegister], OwnAccountRegister]) -> OwnAccountRegister:
        self.document = change(self.document)
        return self.document


class _Profile:
    """The in-memory stores of one profile, kept across several imports."""

    def __init__(self, register: _Register) -> None:
        self.register = register
        self.transactions = InMemoryTransactionRepository(
            bucket_id=str(_PROFILE), catalogue=TransactionCatalogue(), permit_secure_object_writes=True
        )
        self.events = InMemoryEventRepository()


def _import(
    profile: _Profile,
    operation: PinnedAuthorityOperation,
    path: Path,
    *,
    provider: LedgerProviderID = LedgerProviderID.CSV,
    effects: list[OperationEffect] | None = None,
    **options: object,
) -> LedgerImportResultProjection:
    """Run one import to its settled projection, as the operation host would."""
    stored = RecordingOperands("secure-result-reference")
    recorded = RecordingEvents()

    def ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerImportOperationPorts:
        assert bucket_id == str(_PROFILE)
        return LedgerImportOperationPorts(
            import_ports=build_ledger_import_ports(),
            transaction_repository=profile.transactions,
            bucket_event_repository=profile.events,
            currency_normalizer=CurrencyNormalizationService(),
            operation=operation,
            own_accounts=profile.register,
        )

    context = executor_context(
        LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        profile_id=str(_PROFILE),
        operation=operation,
        cancellation=IrreversibleSectionGrant(),
        events=recorded,
        operands=stored,
    )
    request = OperationRequest(
        definition_id=LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerImportRequest.model_validate(
            {"profile_id": _PROFILE, "files": (path,), "provider": provider, **options}
        ),
    )
    asyncio.run(LedgerImportExecutor(ports).execute(request, context))
    execution = stored.stored[0]
    assert isinstance(execution, LedgerImportExecutionResult)
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=LEDGER_IMPORT_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=recorded.effects[-1],
        settled_at=datetime(2026, 11, 19, 12, 0, tzinfo=UTC),
        result_ref="secure-result-reference",
    )
    if effects is not None:
        effects.extend(recorded.effects)
    return project_ledger_import_result(execution, receipt)


def _stored_account_ids(profile: _Profile) -> list[str | None]:
    return sorted(
        (transaction.own_account_id for transaction in profile.transactions.load().transactions.values()),
        key=str,
    )


def test_a_preview_names_the_account_by_mask_and_offers_to_register_it(operation: PinnedAuthorityOperation) -> None:
    profile = _Profile(_Register())

    preview = _import(profile, operation, _BBVA, dry_run=True)

    assert [item.model_dump() for item in preview.statement_accounts] == [
        {"file_index": 0, "masked_iban": _MASK, "own_account_id": None, "registrable": True},
    ]
    assert _IBAN_BBVA not in preview.model_dump_json()
    assert preview.settled_effect is OperationEffect.NONE
    assert profile.register.load().accounts == ()


def test_a_preview_names_the_registered_account_the_statement_names(operation: PinnedAuthorityOperation) -> None:
    profile = _Profile(_Register(_IBAN_OTHER, _IBAN_BBVA))

    preview = _import(profile, operation, _BBVA, dry_run=True)

    assert [(item.masked_iban, item.own_account_id, item.registrable) for item in preview.statement_accounts] == [
        (_MASK, "acc-02", False),
    ]


def test_the_registered_account_a_statement_names_receives_its_rows_without_a_choice(
    operation: PinnedAuthorityOperation,
) -> None:
    profile = _Profile(_Register(_IBAN_OTHER, _IBAN_BBVA))

    result = _import(profile, operation, _BBVA)

    assert result.imported == 12
    assert result.registered_own_account_id is None
    assert set(_stored_account_ids(profile)) == {"acc-02"}


def test_choosing_another_registered_account_refuses_the_file_and_writes_nothing(
    operation: PinnedAuthorityOperation,
) -> None:
    profile = _Profile(_Register(_IBAN_OTHER, _IBAN_BBVA))
    effects: list[OperationEffect] = []

    result = _import(profile, operation, _BBVA, own_account_id="acc-01", effects=effects)

    assert [(item.file_name, item.reason_code) for item in result.refused_files] == [
        (_BBVA.name, "own_account_mismatch"),
    ]
    assert result.imported == 0
    assert effects == [OperationEffect.NONE]
    assert profile.transactions.load().transactions == {}


def test_a_statement_that_names_no_account_takes_the_chosen_one(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    path = tmp_path / "no-account.csv"
    path.write_text(_NO_ACCOUNT_CSV, encoding="utf-8")
    profile = _Profile(_Register(_IBAN_BBVA))

    preview = _import(profile, operation, path, dry_run=True)
    result = _import(profile, operation, path, own_account_id="acc-01")

    assert preview.statement_accounts == ()
    assert result.imported == 2
    assert set(_stored_account_ids(profile)) == {"acc-01"}


def test_registering_the_statement_account_adds_one_masked_account_and_binds_every_row(
    operation: PinnedAuthorityOperation,
) -> None:
    profile = _Profile(_Register())
    effects: list[OperationEffect] = []

    result = _import(profile, operation, _BBVA, register_statement_account=_REGISTRATION, effects=effects)

    (account,) = profile.register.load().accounts
    assert (account.label, account.holding, account.iban, account.masked_iban) == (
        "Cuenta BBVA",
        OwnAccountHolding.TITULAR,
        _IBAN_BBVA,
        _MASK,
    )
    assert result.registered_own_account_id == account.own_account_id == "acc-01"
    assert [(item.own_account_id, item.registrable) for item in result.statement_accounts] == [("acc-01", False)]
    assert result.imported == 12
    assert set(_stored_account_ids(profile)) == {"acc-01"}
    assert effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert result.settled_effect is OperationEffect.UPDATED
    assert _IBAN_BBVA not in result.model_dump_json()


def test_a_second_identical_registering_import_adds_no_second_account(operation: PinnedAuthorityOperation) -> None:
    profile = _Profile(_Register())
    _import(profile, operation, _BBVA, register_statement_account=_REGISTRATION)

    again = _import(profile, operation, _BBVA, register_statement_account=_REGISTRATION)

    assert len(profile.register.load().accounts) == 1
    assert again.registered_own_account_id is None
    assert again.imported == 0
    assert again.skipped == 12
    assert again.settled_effect is OperationEffect.NONE


def test_registering_the_account_of_a_file_whose_rows_are_all_stored_is_still_an_update(
    operation: PinnedAuthorityOperation,
) -> None:
    """The register changed even though no row did, so the receipt must say UPDATED."""
    profile = _Profile(_Register())
    _import(profile, operation, _BBVA)
    effects: list[OperationEffect] = []

    result = _import(profile, operation, _BBVA, register_statement_account=_REGISTRATION, effects=effects)

    assert result.registered_own_account_id == "acc-01"
    assert effects[-1] is OperationEffect.UPDATED
    assert result.settled_effect is OperationEffect.UPDATED


def test_a_file_changed_since_its_preview_registers_nothing(operation: PinnedAuthorityOperation) -> None:
    profile = _Profile(_Register())
    effects: list[OperationEffect] = []

    result = _import(
        profile,
        operation,
        _BBVA,
        register_statement_account=_REGISTRATION,
        expected_source_sha256=("0" * 64,),
        effects=effects,
    )

    assert [item.reason_code for item in result.refused_files] == ["source_changed"]
    assert profile.register.load().accounts == ()
    assert profile.transactions.load().transactions == {}
    assert effects == [OperationEffect.NONE]


def test_a_statement_that_names_no_valid_account_cannot_register_one(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    path = tmp_path / "no-account.csv"
    path.write_text(_NO_ACCOUNT_CSV, encoding="utf-8")
    profile = _Profile(_Register())

    result = _import(profile, operation, path, register_statement_account=_REGISTRATION)

    assert [item.reason_code for item in result.refused_files] == ["statement_account_missing"]
    assert profile.register.load().accounts == ()
    assert profile.transactions.load().transactions == {}


def test_an_invoice_pdf_read_as_a_bank_statement_is_a_per_file_refusal(operation: PinnedAuthorityOperation) -> None:
    """Detection over a non-statement PDF ends as a refusal of that file, not a failed operation."""
    for provider in (LedgerProviderID.AUTO, LedgerProviderID.CSV):
        profile = _Profile(_Register())

        result = _import(profile, operation, _INVOICE_PDF, provider=provider)

        assert [(item.file_name, item.reason_code) for item in result.refused_files] == [
            (_INVOICE_PDF.name, "transaction_validation"),
        ], provider
        assert result.imported == 0


def test_an_ofx_statement_without_its_extra_is_a_per_file_refusal(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    path = tmp_path / "statement.ofx"
    path.write_text(_OFX, encoding="ascii")
    profile = _Profile(_Register())

    with optional_extra_absent(OFX_EXTRA):
        result = _import(profile, operation, path, provider=LedgerProviderID.OFX)

    assert [(item.file_name, item.reason_code) for item in result.refused_files] == [
        ("statement.ofx", "format_not_installed"),
    ]
    assert result.imported == 0


@pytest.mark.parametrize(
    "options",
    [
        {"dry_run": True},
        {"own_account_id": "acc-01"},
    ],
    ids=["dry-run", "chosen-account"],
)
def test_registering_the_statement_account_is_refused_with_a_preview_or_a_chosen_account(
    options: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        LedgerImportRequest.model_validate(
            {
                "profile_id": _PROFILE,
                "files": (_BBVA,),
                "provider": LedgerProviderID.CSV,
                "register_statement_account": _REGISTRATION,
                **options,
            }
        )


def test_registering_the_statement_account_takes_exactly_one_file(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        LedgerImportRequest(
            profile_id=_PROFILE,
            files=(_BBVA, tmp_path / "other.csv"),
            provider=LedgerProviderID.CSV,
            register_statement_account=_REGISTRATION,
        )


def test_a_registration_label_is_bounded_like_an_own_account_label() -> None:
    with pytest.raises(ValidationError):
        LedgerImportAccountRegistration(label="", holding=OwnAccountHolding.TITULAR)
    with pytest.raises(ValidationError):
        LedgerImportAccountRegistration(label="x" * 129, holding=OwnAccountHolding.TITULAR)


def test_a_folder_is_not_one_statement_to_register_an_account_from(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    for name in ("a.csv", "b.csv"):
        (tmp_path / name).write_text(_BBVA.read_text(encoding="utf-8"), encoding="utf-8")
    profile = _Profile(_Register())

    result = _import(profile, operation, tmp_path, register_statement_account=_REGISTRATION)

    assert sorted(item.file_name for item in result.refused_files) == ["a.csv", "b.csv"]
    assert profile.register.load().accounts == ()
