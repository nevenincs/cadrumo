"""Tests for the standardized CRUD verb contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..crud_contract import (
    CANONICAL_CRUD_VERBS,
    BucketEventSuffix,
    CrudContractCatalogue,
    CrudVerb,
    KeyValueVerb,
    LifecycleStateVerb,
    MutatingNounGroupContract,
    NounGroupExceptionKind,
    OrthogonalAxis,
    event_suffix_for,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class TestCanonicalShape:
    def test_canonical_crud_verbs_are_locked_five(self) -> None:
        assert frozenset(CrudVerb) == CANONICAL_CRUD_VERBS
        assert {v.value for v in CANONICAL_CRUD_VERBS} == {"add", "remove", "update", "view", "list"}

    def test_event_suffix_for_mutating_crud_verbs(self) -> None:
        assert event_suffix_for(CrudVerb.ADD) is BucketEventSuffix.CREATED
        assert event_suffix_for(CrudVerb.REMOVE) is BucketEventSuffix.REMOVED
        assert event_suffix_for(CrudVerb.UPDATE) is BucketEventSuffix.UPDATED

    def test_event_suffix_for_read_verbs_is_none(self) -> None:
        assert event_suffix_for(CrudVerb.VIEW) is None
        assert event_suffix_for(CrudVerb.LIST) is None


class TestStrictCrudContract:
    def test_strict_crud_default_registers_all_five_verbs(self) -> None:
        contract = MutatingNounGroupContract(
            noun="purchase_invoice_evidence",
            cli_path="aeat app ledger evidence",
        )
        assert contract.exception is NounGroupExceptionKind.STRICT_CRUD
        assert contract.crud_verbs == CANONICAL_CRUD_VERBS
        assert contract.declares_crud() is True
        assert contract.all_verb_names() == {"add", "remove", "update", "view", "list"}

    def test_strict_crud_rejects_partial_verb_set(self) -> None:
        with pytest.raises(ValidationError, match="exactly the canonical five verbs"):
            MutatingNounGroupContract(
                noun="purchase_invoice_evidence",
                cli_path="aeat app ledger evidence",
                crud_verbs=frozenset({CrudVerb.ADD, CrudVerb.LIST}),
            )

    def test_strict_crud_rejects_key_value_verbs(self) -> None:
        with pytest.raises(ValidationError, match="must not register key-value verbs"):
            MutatingNounGroupContract(
                noun="purchase_invoice_evidence",
                cli_path="aeat app ledger evidence",
                key_value_verbs=frozenset({KeyValueVerb.SET}),
            )

    def test_strict_crud_allows_orthogonal_axes(self) -> None:
        contract = MutatingNounGroupContract(
            noun="ledger_transaction",
            cli_path="aeat app ledger",
            orthogonal_axes=frozenset(
                {
                    OrthogonalAxis.CLASSIFY,
                    OrthogonalAxis.ALLOCATE,
                    OrthogonalAxis.ATTACH,
                    OrthogonalAxis.LINK,
                    OrthogonalAxis.CHECK,
                    OrthogonalAxis.PREFLIGHT,
                },
            ),
            lifecycle_state_verbs=frozenset(
                {
                    LifecycleStateVerb.ARCHIVE,
                    LifecycleStateVerb.STASH,
                    LifecycleStateVerb.RESET,
                },
            ),
        )
        verbs = contract.all_verb_names()
        assert "add" in verbs
        assert "classify" in verbs
        assert "archive" in verbs


class TestKeyValueException:
    def test_key_value_exception_accepts_set_get_unset(self) -> None:
        contract = MutatingNounGroupContract(
            noun="usage_ratio",
            cli_path="aeat app ledger ratios",
            exception=NounGroupExceptionKind.KEY_VALUE_AS_RECORD,
            crud_verbs=frozenset(),
            key_value_verbs=frozenset({KeyValueVerb.SET, KeyValueVerb.GET, KeyValueVerb.UNSET, KeyValueVerb.LIST}),
        )
        assert contract.declares_crud() is False
        assert "set" in contract.all_verb_names()
        assert "get" in contract.all_verb_names()

    def test_key_value_exception_requires_at_least_one_key_verb(self) -> None:
        with pytest.raises(ValidationError, match="must register at least one"):
            MutatingNounGroupContract(
                noun="usage_ratio",
                cli_path="aeat app ledger ratios",
                exception=NounGroupExceptionKind.KEY_VALUE_AS_RECORD,
                crud_verbs=frozenset(),
            )

    def test_key_value_exception_rejects_partial_crud(self) -> None:
        with pytest.raises(ValidationError, match="partial CRUD registration is rejected"):
            MutatingNounGroupContract(
                noun="profile",
                cli_path="aeat config profile",
                exception=NounGroupExceptionKind.KEY_VALUE_AS_RECORD,
                crud_verbs=frozenset({CrudVerb.ADD, CrudVerb.LIST}),
                key_value_verbs=frozenset({KeyValueVerb.SET}),
            )


class TestLifecycleOnlyException:
    def test_lifecycle_only_rejects_crud_verbs(self) -> None:
        with pytest.raises(ValidationError, match="must not register CRUD verbs"):
            MutatingNounGroupContract(
                noun="bucket_lifecycle",
                cli_path="aeat config bucket",
                exception=NounGroupExceptionKind.LIFECYCLE_OPERATIONS_ONLY,
                lifecycle_state_verbs=frozenset({LifecycleStateVerb.ARCHIVE}),
            )

    def test_lifecycle_only_requires_at_least_one_lifecycle_verb(self) -> None:
        with pytest.raises(ValidationError, match="must register at least one lifecycle-state"):
            MutatingNounGroupContract(
                noun="bucket_lifecycle",
                cli_path="aeat config bucket",
                exception=NounGroupExceptionKind.LIFECYCLE_OPERATIONS_ONLY,
                crud_verbs=frozenset(),
            )


class TestNounValidation:
    def test_noun_must_be_lowercase(self) -> None:
        with pytest.raises(ValidationError, match="lowercase canonical form"):
            MutatingNounGroupContract(noun="PayableInvoice", cli_path="aeat app ledger payable-invoice")

    def test_noun_must_be_stripped(self) -> None:
        with pytest.raises(ValidationError, match="whitespace"):
            MutatingNounGroupContract(noun=" payable_invoice ", cli_path="aeat app ledger payable-invoice")


class TestCatalogue:
    def test_empty_catalogue_is_valid(self) -> None:
        catalogue = CrudContractCatalogue()
        assert catalogue.entries == ()
        assert catalogue.find("aeat app ledger") is None

    def test_catalogue_lookups_by_cli_path(self) -> None:
        evidence = MutatingNounGroupContract(
            noun="purchase_invoice_evidence",
            cli_path="aeat app ledger evidence",
        )
        payable = MutatingNounGroupContract(
            noun="payable_invoice",
            cli_path="aeat app ledger payable-invoice",
        )
        catalogue = CrudContractCatalogue(entries=(evidence, payable))
        assert catalogue.find("aeat app ledger evidence") is evidence
        assert catalogue.find("aeat app ledger payable-invoice") is payable
        assert catalogue.find("aeat config profile") is None

    def test_catalogue_rejects_duplicate_cli_paths(self) -> None:
        a = MutatingNounGroupContract(
            noun="purchase_invoice_evidence",
            cli_path="aeat app ledger evidence",
        )
        b = MutatingNounGroupContract(
            noun="purchase_invoice_evidence",
            cli_path="aeat app ledger evidence",
        )
        with pytest.raises(ValidationError, match="duplicate noun-group contract"):
            CrudContractCatalogue(entries=(a, b))


class TestImmutability:
    def test_contract_is_frozen(self) -> None:
        contract = MutatingNounGroupContract(
            noun="payable_invoice",
            cli_path="aeat app ledger payable-invoice",
        )
        with pytest.raises(ValidationError):
            setattr(contract, "noun", "other")  # noqa: B010 - frozen-model refusal is the assertion
