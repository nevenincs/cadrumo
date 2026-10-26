"""Encrypted roundtrip and guarded mutation of the own bank account register.

Persists :class:`OwnAccountRegister` under ``cadrumo.ledger.own_accounts`` at
``SensitivityClass.FINANCIAL``.

Anti-tautology: the fixture fills every optional field (a non-SEPA account with its
BIC and full bank block, dates, a non-EUR currency, both designation scopes). A
probe rewrites a persisted label and checks the reload differs, and another
deletes a required field and checks the load refuses rather than re-defaulting.
The plaintext probe scans every byte the profile wrote to disk for the account
numbers, the BIC and the operator mask.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pydantic
import pytest
from sqlalchemy import select

from .....core.modelo import Modelo
from .....domain.transactions.own_accounts import (
    OwnAccountDesignation,
    OwnAccountHolding,
    OwnAccountRegister,
    OwnAccountRegisterValidationError,
    OwnAccountRole,
    OwnBankAccountDetails,
)
from ...storage.secure_object_namespaces import LEDGER_OWN_ACCOUNTS_NAMESPACE
from ...storage.sql.engine import get_engine
from ...storage.sql.orm import SecureObjectRow
from ...storage.tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ..own_accounts import OwnAccountRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_ES_IBAN = "ES9121000418450200051332"
_TR_IBAN = "TR330006100519786457841326"
_TR_BIC = "TCZATRIS"


def _spanish_account() -> OwnBankAccountDetails:
    return OwnBankAccountDetails(
        label="synthetic main account",
        holding=OwnAccountHolding.TITULAR,
        iban=_ES_IBAN,
        opened_on=date(2020, 1, 15),
    )


def _foreign_account() -> OwnBankAccountDetails:
    return OwnBankAccountDetails(
        label="synthetic lira account",
        holding=OwnAccountHolding.COTITULAR,
        iban=_TR_IBAN,
        swift_bic=_TR_BIC,
        bank_name="Synthetic Bank",
        bank_address="1 Example Street",
        bank_city="Ankara",
        bank_country_code="TR",
        currency="TRY",
        opened_on=date(2021, 3, 1),
        closed_on=date(2026, 6, 30),
    )


def _designations() -> tuple[OwnAccountDesignation, ...]:
    return (
        OwnAccountDesignation(role=OwnAccountRole.CHARGE, own_account_id="acc-01"),
        OwnAccountDesignation(role=OwnAccountRole.REFUND, modelo=Modelo("303"), own_account_id="acc-02"),
    )


def _populate(repository: OwnAccountRepository) -> OwnAccountRegister:
    repository.mutate(lambda current: current.with_new_account(_spanish_account()))
    repository.mutate(lambda current: current.with_new_account(_foreign_account()))
    current = repository.load()
    for designation in _designations():
        current = repository.mutate(lambda register, designation=designation: register.with_designation(designation))
    return current


def _register_row():
    return select(SecureObjectRow).where(
        SecureObjectRow.namespace == LEDGER_OWN_ACCOUNTS_NAMESPACE.namespace,
        SecureObjectRow.object_key == LEDGER_OWN_ACCOUNTS_NAMESPACE.require_default_object_key(),
    )


def test_an_absent_register_loads_empty(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="0b6d2a3e-4f51-4c62-8d73-0acc00000001"):
        assert OwnAccountRepository().load() == OwnAccountRegister()


def test_the_register_survives_encrypted_storage_field_for_field(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="1c7e3b4f-5062-4d73-9e84-0acc00000002"):
        written = _populate(OwnAccountRepository())

        loaded = OwnAccountRepository().load()

        assert loaded == written
        assert [account.own_account_id for account in loaded.accounts] == ["acc-01", "acc-02"]
        assert loaded.account("acc-02").bank_city == "Ankara"
        assert loaded.account("acc-02").closed_on == date(2026, 6, 30)
        assert loaded.designations == _designations()
        assert loaded.last_ordinal == 2


def test_no_account_material_reaches_disk_or_the_object_key(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="2d8f4c50-6173-4e84-8f95-0acc00000003") as profile:
        written = _populate(OwnAccountRepository())
        masks = [account.masked_iban for account in written.accounts]

        with get_engine(profile.settings).connect() as connection:
            rows = connection.execute(
                select(SecureObjectRow.object_key).where(
                    SecureObjectRow.namespace == LEDGER_OWN_ACCOUNTS_NAMESPACE.namespace,
                ),
            ).all()
        # One singleton row whose stored key is the keyed digest of "default".
        assert len(rows) == 1

        on_disk = b"".join(path.read_bytes() for path in profile.storage_root.rglob("*") if path.is_file())
        assert on_disk, "the probe must read the bytes the profile wrote"
        for secret in (_ES_IBAN, _TR_IBAN, _TR_BIC, "05100519786457841326", "Synthetic Bank", *masks):
            assert secret.encode("utf-8") not in on_disk
            assert secret.encode("utf-16-le") not in on_disk


def test_a_refused_change_writes_nothing(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="3e905d61-7284-4f95-9fa6-0acc00000004"):
        repository = OwnAccountRepository()
        repository.mutate(lambda current: current.with_new_account(_spanish_account()))
        before = repository.load()

        with pytest.raises(ValueError, match="same account number twice"):
            repository.mutate(lambda current: current.with_new_account(_spanish_account()))
        with pytest.raises(ValueError, match="unregistered accounts"):
            repository.mutate(
                lambda current: current.with_designation(
                    OwnAccountDesignation(role=OwnAccountRole.REFUND, own_account_id="acc-09"),
                ),
            )
        with pytest.raises(OwnAccountRegisterValidationError, match="already closed"):
            repository.mutate(
                lambda current: current.with_closed_account("acc-01", date(2026, 1, 1)).with_closed_account(
                    "acc-01",
                    date(2026, 1, 2),
                ),
            )

        assert repository.load() == before


def test_an_interleaved_addition_is_kept_and_ids_stay_distinct(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="4fa16e72-8395-40a6-8ab7-0acc00000005"):
        interloper_written = False

        def add_while_another_lands(current: OwnAccountRegister) -> OwnAccountRegister:
            # The interloping write lands after this attempt's read and before its
            # write, the window two concurrent callers race in; the guard must
            # re-apply this change to the interloper's document.
            nonlocal interloper_written
            if not interloper_written:
                interloper_written = True
                OwnAccountRepository().mutate(lambda other: other.with_new_account(_foreign_account()))
            return current.with_new_account(_spanish_account())

        OwnAccountRepository().mutate(add_while_another_lands)

        loaded = OwnAccountRepository().load()
        assert [(account.own_account_id, account.iban) for account in loaded.accounts] == [
            ("acc-01", _TR_IBAN),
            ("acc-02", _ES_IBAN),
        ]


def test_a_rewritten_label_surfaces_on_reload(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="50b27f83-94a6-41b7-9bc8-0acc00000006") as profile:
        repository = OwnAccountRepository()
        written = _populate(repository)

        def mutate(document):
            assert document["accounts"][0]["label"] == "synthetic main account"
            document["accounts"][0]["label"] = "rewritten"

        mutate_encrypted_secure_object_json(get_engine(profile.settings), row_statement=_register_row(), mutate=mutate)

        reloaded = repository.load()
        assert reloaded != written
        assert reloaded.account("acc-01").label == "rewritten"


def test_a_deleted_required_field_refuses_the_load(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="61c38094-a5b7-42c8-8cd9-0acc00000007") as profile:
        repository = OwnAccountRepository()
        _populate(repository)

        def mutate(document):
            del document["accounts"][0]["holding"]

        mutate_encrypted_secure_object_json(get_engine(profile.settings), row_statement=_register_row(), mutate=mutate)

        with pytest.raises(pydantic.ValidationError, match="holding"):
            repository.load()
