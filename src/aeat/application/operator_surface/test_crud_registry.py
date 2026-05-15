"""Tests for the builtin noun-group catalogue."""

from __future__ import annotations

import pytest

from aeat.application.operator_surface._crud_contract import (
    CANONICAL_CRUD_VERBS,
    NounGroupExceptionKind,
)
from aeat.application.operator_surface._crud_registry import (
    APODERADO,
    BUILTIN_CRUD_CATALOGUE,
    COLLECTIBLE_INVOICE,
    EVIDENCE,
    INVENTORY,
    PAYABLE_INVOICE,
    USAGE_RATIOS,
    get_builtin_catalogue,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


class TestCatalogueShape:
    def test_catalogue_lists_every_registered_noun_group(self) -> None:
        assert BUILTIN_CRUD_CATALOGUE.entries == (
            EVIDENCE,
            PAYABLE_INVOICE,
            COLLECTIBLE_INVOICE,
            USAGE_RATIOS,
            INVENTORY,
            APODERADO,
        )

    def test_get_builtin_catalogue_returns_same_instance(self) -> None:
        assert get_builtin_catalogue() is BUILTIN_CRUD_CATALOGUE


class TestCanonicalCrudEntries:
    def test_evidence_declares_strict_crud(self) -> None:
        assert EVIDENCE.exception is NounGroupExceptionKind.STRICT_CRUD
        assert EVIDENCE.crud_verbs == CANONICAL_CRUD_VERBS

    def test_payable_invoice_declares_strict_crud_with_link_axis(self) -> None:
        assert PAYABLE_INVOICE.exception is NounGroupExceptionKind.STRICT_CRUD
        assert PAYABLE_INVOICE.crud_verbs == CANONICAL_CRUD_VERBS
        verbs = PAYABLE_INVOICE.all_verb_names()
        assert "link" in verbs

    def test_collectible_invoice_declares_strict_crud_with_link_axis(self) -> None:
        assert COLLECTIBLE_INVOICE.exception is NounGroupExceptionKind.STRICT_CRUD
        verbs = COLLECTIBLE_INVOICE.all_verb_names()
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

    def test_invoice_decoupling_is_represented(self) -> None:
        assert BUILTIN_CRUD_CATALOGUE.find("aeat app ledger payable-invoice") is not None
        assert BUILTIN_CRUD_CATALOGUE.find("aeat app ledger collectible-invoice") is not None

    def test_apoderado_subgroup_is_represented(self) -> None:
        assert BUILTIN_CRUD_CATALOGUE.find("aeat config auth apoderado") is not None

    def test_inventory_noun_group_is_represented(self) -> None:
        assert BUILTIN_CRUD_CATALOGUE.find("aeat app ledger inventory") is not None

    def test_ratios_key_value_exception_is_represented(self) -> None:
        entry = BUILTIN_CRUD_CATALOGUE.find("aeat app ledger ratios")
        assert entry is not None
        assert entry.exception is NounGroupExceptionKind.KEY_VALUE_AS_RECORD
