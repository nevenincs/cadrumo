"""The own-account operation: request shape per action, masked results and action semantics.

The register logic itself is the real domain document; only its encrypted store is
replaced by an in-memory holder that applies changes exactly as the guarded store
does (load, apply, keep the result). The encrypted store and the supervised
execution are proven in the persistence roundtrip and executor conformance tests.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pydantic
import pytest

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import LedgerDatePartition, Transaction, TransactionCatalogue
from ....domain.transactions.own_accounts import (
    OwnAccountHolding,
    OwnAccountRegister,
    OwnAccountRegisterValidationError,
    OwnAccountRole,
)
from ....domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..own_account_operation import (
    LedgerOwnAccountRequest,
    LedgerOwnAccountResult,
    apply_own_account_request,
    build_ledger_own_account_definition,
    build_ledger_own_account_registration,
)
from ..own_account_ports import OwnAccountRepositoryProtocol
from ..transaction_repository import bind_transaction_catalogue_repository_factory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("7a1c0e52-3b64-4d85-9e96-0acc00000a01")
_ES_IBAN = "ES9121000418450200051332"
_ES_IBAN_2 = "ES7921000813610123456789"


class _Register:
    """In-memory holder with the guarded store's load/apply/keep contract."""

    def __init__(self) -> None:
        self.document = OwnAccountRegister()

    def load(self) -> OwnAccountRegister:
        return self.document

    def mutate(self, change: Callable[[OwnAccountRegister], OwnAccountRegister]) -> OwnAccountRegister:
        self.document = change(self.document)
        return self.document


class _Catalogue:
    def __init__(self, catalogue: TransactionCatalogue) -> None:
        self._catalogue = catalogue

    @property
    def bucket_id(self) -> str:
        return str(_PROFILE)

    def exists(self) -> bool:
        return True

    def load(self) -> TransactionCatalogue:
        return self._catalogue

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        raise AssertionError(f"own-account removal reads the whole catalogue, not {start}..{end}")

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        raise AssertionError(f"own-account removal reads the whole catalogue, not {list(transaction_ids)}")

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        raise AssertionError(f"own-account removal reads the whole catalogue, not {start}..{end}")

    def save(self, catalogue: TransactionCatalogue) -> None:
        raise AssertionError(f"own-account actions never write the catalogue ({len(catalogue.transactions)} rows)")


@contextmanager
def _transactions(*transactions: Transaction) -> Iterator[None]:
    catalogue = TransactionCatalogue.from_transactions(transactions)

    def factory(*, bucket_id: str) -> TransactionCatalogueRepositoryProtocol:
        assert bucket_id == str(_PROFILE)
        return _Catalogue(catalogue)

    with bind_transaction_catalogue_repository_factory(factory):
        yield


def _request(action: str, **fields: object) -> LedgerOwnAccountRequest:
    return LedgerOwnAccountRequest.model_validate({"profile_id": _PROFILE, "action": action, **fields})


def _apply(register: _Register, action: str, **fields: object) -> LedgerOwnAccountResult:
    with _transactions():
        return apply_own_account_request(_request(action, **fields), bucket_id=str(_PROFILE), repository=register)


def _add(register: _Register, iban: str = _ES_IBAN, label: str = "synthetic account") -> LedgerOwnAccountResult:
    return _apply(register, "add", label=label, holding=OwnAccountHolding.TITULAR, iban=iban)


def _unused_repository(*, bucket_id: str) -> OwnAccountRepositoryProtocol:
    raise AssertionError(f"unexpected repository access for {bucket_id}")


def test_the_public_schemas_bind_and_round_trip() -> None:
    definition = build_ledger_own_account_definition(_unused_repository)
    registration = build_ledger_own_account_registration(definition)
    assert registration.contract.definition_id == definition.definition_id == "ledger.own_account"

    request = _request("add", label="synthetic", holding=OwnAccountHolding.TITULAR, iban=_ES_IBAN)
    assert LedgerOwnAccountRequest.model_validate_json(request.model_dump_json()) == request
    result = _add(_Register())
    assert LedgerOwnAccountResult.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize(
    ("action", "fields", "reason"),
    [
        ("add", {"label": "x", "holding": OwnAccountHolding.TITULAR}, "label, holding and IBAN"),
        ("show", {}, "requires account id"),
        ("list", {"own_account_id": "acc-01"}, "takes no account id"),
        ("close", {"own_account_id": "acc-01"}, "closed_on"),
        ("update", {"own_account_id": "acc-01"}, "at least one detail"),
        ("designate", {"own_account_id": "acc-01"}, "role and modelo"),
        ("show", {"own_account_id": "acc-01", "iban": _ES_IBAN}, "takes no account details"),
        ("undesignate", {"role": OwnAccountRole.CHARGE, "own_account_id": "acc-01"}, "takes no account id"),
    ],
)
def test_each_action_admits_only_its_own_fields(action: str, fields: dict[str, object], reason: str) -> None:
    with pytest.raises(pydantic.ValidationError, match=reason) as caught:
        _request(action, **fields)

    assert _ES_IBAN not in str(caught.value)


def test_add_assigns_the_next_id_and_publishes_only_the_mask() -> None:
    register = _Register()

    result = _add(register)

    assert result.changed is True
    assert result.own_account_id == "acc-01"
    (account,) = result.accounts
    assert account.masked_iban == "ES ···· 1332"
    assert account.sepa_marca == "1"
    serialized = result.model_dump_json()
    assert _ES_IBAN not in serialized
    assert _ES_IBAN[4:-4] not in serialized
    assert register.document.account("acc-01").iban == _ES_IBAN


def test_invalid_details_refuse_with_the_registered_error_and_no_account_material() -> None:
    register = _Register()

    with pytest.raises(OwnAccountRegisterValidationError, match="mod-97") as caught:
        _add(register, iban="ES9121000418450200051333")

    assert "0418450200051333" not in str(caught.value)
    assert register.document == OwnAccountRegister()


def test_list_and_show_read_without_changing_anything() -> None:
    register = _Register()
    _add(register)
    _add(register, iban=_ES_IBAN_2, label="second")
    before = register.document

    listed = _apply(register, "list")
    shown = _apply(register, "show", own_account_id="acc-02")

    assert [account.own_account_id for account in listed.accounts] == ["acc-01", "acc-02"]
    assert [account.label for account in shown.accounts] == ["second"]
    assert listed.changed is shown.changed is False
    assert register.document is before


def test_update_replaces_only_the_named_details() -> None:
    register = _Register()
    _add(register)

    result = _apply(register, "update", own_account_id="acc-01", label="renamed", opened_on=date(2020, 2, 1))

    stored = register.document.account("acc-01")
    assert result.changed is True
    assert (stored.label, stored.iban, stored.opened_on) == ("renamed", _ES_IBAN, date(2020, 2, 1))


def test_an_unchanged_update_reports_no_change() -> None:
    register = _Register()
    _add(register)

    result = _apply(register, "update", own_account_id="acc-01", label="synthetic account")

    assert result.changed is False


def test_close_then_designations_and_their_removal() -> None:
    register = _Register()
    _add(register)
    _add(register, iban=_ES_IBAN_2, label="second")

    _apply(register, "designate", own_account_id="acc-01", role=OwnAccountRole.CHARGE)
    scoped = _apply(register, "designate", own_account_id="acc-02", role=OwnAccountRole.REFUND, modelo="303")
    closed = _apply(register, "close", own_account_id="acc-02", closed_on=date(2026, 6, 30))

    assert [(item.role, item.modelo) for item in scoped.designations] == [(OwnAccountRole.REFUND, "303")]
    assert closed.accounts[0].closed_on == date(2026, 6, 30)
    assert len(register.document.designations) == 2

    with pytest.raises(OwnAccountRegisterValidationError, match="redesignate before removing"):
        _apply(register, "remove", own_account_id="acc-01")
    _apply(register, "undesignate", role=OwnAccountRole.CHARGE)
    removed = _apply(register, "remove", own_account_id="acc-01")

    assert removed.changed is True
    assert removed.accounts == ()
    assert [account.own_account_id for account in register.document.accounts] == ["acc-02"]


def test_an_unknown_account_is_refused() -> None:
    with pytest.raises(OwnAccountRegisterValidationError, match="acc-04"):
        _apply(_Register(), "show", own_account_id="acc-04")


def test_an_account_referenced_by_transactions_is_refused_removal() -> None:
    register = _Register()
    _add(register)
    booked = date(2026, 1, 5)
    with bundled_indexed_authority().operation():
        referencing = Transaction.model_validate(
            {
                "raw": RawTransaction(
                    provider_transaction_id="own-account-reference",
                    booked_date=booked,
                    value_date=booked,
                    amount=Decimal("10.00"),
                    currency="EUR",
                    counterparty="Synthetic Supplier SL",
                    description="synthetic movement",
                    provenance=RawProvenance(
                        source_path=Path(__file__),
                        source_sha256="c" * 64,
                        source_row_index=1,
                        source_format=SourceFormat.CSV,
                        ingested_at=datetime(2026, 1, 6, 9, 0, tzinfo=UTC),
                        provider_name="synthetic provider",
                    ),
                    raw_fields={},
                ),
                "direction": TransactionDirection.OUTGOING,
                "business_classification": BusinessClassification.BUSINESS,
                "source_jurisdiction": "ES",
                "group_label": None,
                "own_account_id": "acc-01",
            },
        )
        with _transactions(referencing), pytest.raises(OwnAccountRegisterValidationError, match="close it instead"):
            apply_own_account_request(
                _request("remove", own_account_id="acc-01"),
                bucket_id=str(_PROFILE),
                repository=register,
            )

    assert [account.own_account_id for account in register.document.accounts] == ["acc-01"]
