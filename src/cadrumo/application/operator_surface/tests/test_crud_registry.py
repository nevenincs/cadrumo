"""Tests for the builtin noun-group catalogue."""

from __future__ import annotations

import pytest

from ..crud_contract import (
    CANONICAL_CRUD_VERBS,
    NounGroupExceptionKind,
)
from ..crud_registry import (
    APODERADO,
    BUILTIN_CRUD_CATALOGUE,
    EVIDENCE,
    INVENTORY,
    INVOICE,
    STORAGE,
    USAGE_RATIOS,
    get_builtin_catalogue,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class TestCatalogueShape:
    def test_catalogue_lists_every_registered_noun_group(self) -> None:
        assert BUILTIN_CRUD_CATALOGUE.entries == (
            EVIDENCE,
            INVOICE,
            USAGE_RATIOS,
            INVENTORY,
            APODERADO,
            STORAGE,
        )

    def test_old_split_invoice_contracts_are_gone(self) -> None:
        # The payable / collectible split collapsed into one INVOICE contract.
        from .. import crud_registry as registry

        assert not hasattr(registry, "PAYABLE_INVOICE")
        assert not hasattr(registry, "COLLECTIBLE_INVOICE")
        nouns = {entry.noun for entry in BUILTIN_CRUD_CATALOGUE.entries}
        assert "payable_invoice" not in nouns
        assert "collectible_invoice" not in nouns
        assert "invoice" in nouns

    def test_get_builtin_catalogue_returns_same_instance(self) -> None:
        assert get_builtin_catalogue() is BUILTIN_CRUD_CATALOGUE


class TestCanonicalCrudEntries:
    def test_evidence_declares_strict_crud(self) -> None:
        assert EVIDENCE.exception is NounGroupExceptionKind.STRICT_CRUD
        assert EVIDENCE.crud_verbs == CANONICAL_CRUD_VERBS

    def test_invoice_declares_strict_crud_with_link_axis(self) -> None:
        assert INVOICE.exception is NounGroupExceptionKind.STRICT_CRUD
        assert INVOICE.crud_verbs == CANONICAL_CRUD_VERBS
        assert INVOICE.noun == "invoice"
        verbs = INVOICE.all_verb_names()
        assert "link" in verbs


class TestKeyValueExceptionEntry:
    def test_usage_ratios_declares_key_value_exception(self) -> None:
        assert USAGE_RATIOS.exception is NounGroupExceptionKind.KEY_VALUE_AS_RECORD
        assert USAGE_RATIOS.crud_verbs == frozenset()
        verbs = USAGE_RATIOS.all_verb_names()
        assert "set" in verbs
        assert "get" in verbs
        assert "unset" in verbs
        assert "list" in verbs


class TestLifecycleOnlyEntries:
    def test_inventory_declares_lifecycle_only(self) -> None:
        assert INVENTORY.exception is NounGroupExceptionKind.LIFECYCLE_OPERATIONS_ONLY
        assert INVENTORY.crud_verbs == frozenset()
        assert len(INVENTORY.lifecycle_state_verbs) >= 1

    def test_apoderado_declares_lifecycle_only(self) -> None:
        assert APODERADO.exception is NounGroupExceptionKind.LIFECYCLE_OPERATIONS_ONLY
        assert APODERADO.crud_verbs == frozenset()

    def test_storage_declares_lifecycle_only(self) -> None:
        # A storage category is declared by the core taxonomy, so it can be
        # emptied but never added, removed, or edited field-by-field.
        assert STORAGE.exception is NounGroupExceptionKind.LIFECYCLE_OPERATIONS_ONLY
        assert STORAGE.crud_verbs == frozenset()
        assert STORAGE.noun == "storage_area"


class TestCatalogueUniquePaths:
    def test_every_cli_path_is_unique(self) -> None:
        paths = [entry.cli_path for entry in BUILTIN_CRUD_CATALOGUE.entries]
        assert len(paths) == len(set(paths))

    def test_every_noun_is_unique(self) -> None:
        nouns = [entry.noun for entry in BUILTIN_CRUD_CATALOGUE.entries]
        assert len(nouns) == len(set(nouns))


class TestCatalogueLookup:
    def test_find_resolves_known_paths(self) -> None:
        assert BUILTIN_CRUD_CATALOGUE.find("aeat app ledger evidence") is EVIDENCE
        assert BUILTIN_CRUD_CATALOGUE.find("aeat config auth apoderado") is APODERADO

    def test_find_returns_none_on_unknown_path(self) -> None:
        assert BUILTIN_CRUD_CATALOGUE.find("aeat app foo bar") is None


class TestRequiredAuditClosure:
    """Every mutating noun-group exposed by the operator surface has a
    corresponding catalogue entry."""

    def test_invoice_noun_group_is_represented(self) -> None:
        assert BUILTIN_CRUD_CATALOGUE.find("aeat app ledger invoice") is INVOICE
        assert BUILTIN_CRUD_CATALOGUE.find("aeat app ledger payable-invoice") is None
        assert BUILTIN_CRUD_CATALOGUE.find("aeat app ledger collectible-invoice") is None

    def test_apoderado_subgroup_is_represented(self) -> None:
        assert BUILTIN_CRUD_CATALOGUE.find("aeat config auth apoderado") is not None

    def test_inventory_noun_group_is_represented(self) -> None:
        assert BUILTIN_CRUD_CATALOGUE.find("aeat app ledger inventory") is not None

    def test_storage_noun_group_is_represented(self) -> None:
        assert BUILTIN_CRUD_CATALOGUE.find("aeat config storage") is not None

    def test_ratios_key_value_exception_is_represented(self) -> None:
        entry = BUILTIN_CRUD_CATALOGUE.find("aeat app ledger ratios")
        assert entry is not None
        assert entry.exception is NounGroupExceptionKind.KEY_VALUE_AS_RECORD
