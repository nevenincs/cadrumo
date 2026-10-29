"""The invoice repository's authenticated read, against the real encrypted store.

:meth:`InvoiceCatalogueRepository.load_authenticated` returns what full
validation returns, invoice for invoice, while skipping one re-derivation the
store's authentication proves: the stored invoice id. These tests hold it to
that, show every write path still reading through full validation, show the
schema and ownership gates still refusing before anything is trusted, and pin
the trusted entry point to that one method.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any, Final

import pytest
from pydantic import ValidationError

from .....domain.invoices.catalogue import InvoiceCatalogue
from .....domain.invoices.models import Invoice
from .....domain.invoices.tests.invoice_catalogue_seed import SeedCase, fields_set, seed_payload, seed_payloads
from .....tests.inventory import production_python_files, repo_relative
from ...storage.errors import EnvelopeVersionError
from ...storage.secure_object_namespaces import INVOICE_CATALOGUE_NAMESPACE
from ...storage.tests.secure_sql import (
    TestRuntimeProfile,
    isolated_runtime_profile,
    mutate_encrypted_secure_object_json,
)
from ..invoices import InvoiceCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_DERIVED_ID_REFUSAL: Final = "invoice_id must match the stable hash derived from identity fields"


def _catalogue(payloads: list[dict[str, object]], *, bucket_id: str | None = None) -> InvoiceCatalogue:
    invoices = [Invoice.model_validate_json(json.dumps(payload)) for payload in payloads]
    if bucket_id is not None:
        invoices = [invoice.model_copy(update={"bucket_id": bucket_id}) for invoice in invoices]
    return InvoiceCatalogue(invoices={invoice.invoice_id: invoice for invoice in invoices})


def _mutate_stored(profile: TestRuntimeProfile, mutate: Callable[[dict[str, Any]], None]) -> None:
    from sqlalchemy import select

    from ...storage.sql.orm import SecureObjectRow

    mutate_encrypted_secure_object_json(
        profile.repository._engine,
        row_statement=select(SecureObjectRow).where(SecureObjectRow.namespace == INVOICE_CATALOGUE_NAMESPACE.namespace),
        mutate=mutate,
    )


def test_an_authenticated_read_returns_what_full_validation_returns(
    tmp_path: Path, authority_operation: object
) -> None:
    """Values, JSON, set fields and order agree with ``load`` for every stored invoice."""
    del authority_operation
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = InvoiceCatalogueRepository()
        repo.save(_catalogue(seed_payloads(), bucket_id=profile.bucket_id))

        full = repo.load()
        trusted = repo.load_authenticated()

        assert trusted.invoice_ids() == tuple(full.invoices)
        for invoice_id in trusted.invoice_ids():
            read = trusted.require(invoice_id)
            assert read == full.invoices[invoice_id]
            assert read.model_dump_json() == full.invoices[invoice_id].model_dump_json()
            assert fields_set(read) == fields_set(full.invoices[invoice_id])
        assert trusted.values() == tuple(full.values())


def test_an_absent_catalogue_reads_empty(tmp_path: Path) -> None:
    """No stored row is an empty catalogue, as ``load`` reports it."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        trusted = InvoiceCatalogueRepository().load_authenticated()

        assert len(trusted) == 0
        assert trusted.invoice_ids() == ()


def test_every_write_path_reads_the_stored_catalogue_through_full_validation(
    tmp_path: Path, authority_operation: object
) -> None:
    """A stored id no longer derived from its fields refuses ``load``, ``load_revisioned`` and ``mutate``.

    Only the read-only authenticated read accepts it. Routing any write path
    through the trusted decode makes one of these refusals disappear.
    """
    del authority_operation
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = InvoiceCatalogueRepository()
        original = _catalogue([seed_payload(SeedCase(1, date(2025, 7, 7), ("RATE_21",)))])
        repo.save(original)
        (invoice_id,) = original.invoices

        def renumber(envelope: dict[str, Any]) -> None:
            envelope["payload"]["invoices"][invoice_id]["invoice_number"] = "PASS-9999"

        _mutate_stored(profile, renumber)

        assert repo.load_authenticated().require(invoice_id).invoice_number == "PASS-9999"
        with pytest.raises(ValidationError, match=_DERIVED_ID_REFUSAL):
            repo.load()
        with pytest.raises(ValidationError, match=_DERIVED_ID_REFUSAL):
            repo.load_revisioned()
        with pytest.raises(ValidationError, match=_DERIVED_ID_REFUSAL):
            repo.mutate(lambda catalogue: catalogue)


def test_a_rate_not_in_force_still_refuses_the_invoice_an_authenticated_read_returns(
    tmp_path: Path, authority_operation: object
) -> None:
    """Dated registry rules stay on the authenticated read; only the returned invoice is checked."""
    del authority_operation
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = InvoiceCatalogueRepository()
        stale = seed_payload(SeedCase(1, date(2024, 11, 15), ("RATE_2",)))
        fine = seed_payload(SeedCase(2, date(2025, 7, 7), ("RATE_21",)))
        catalogue = _catalogue([stale, fine])
        repo.save(catalogue)
        stale_id, fine_id = catalogue.invoices

        def move_out_of_window(envelope: dict[str, Any]) -> None:
            envelope["payload"]["invoices"][stale_id]["issued_at"] = "2025-02-03"

        _mutate_stored(profile, move_out_of_window)
        trusted = repo.load_authenticated()

        assert trusted.require(fine_id).invoice_id == fine_id
        with pytest.raises(ValidationError, match="line rate RATE_2 was not in force on 2025-02-03"):
            trusted.require(stale_id)
        with pytest.raises(ValidationError, match="line rate RATE_2 was not in force on 2025-02-03"):
            trusted.values()


def test_an_inner_schema_stamp_other_than_current_is_refused_before_anything_is_trusted(
    tmp_path: Path, authority_operation: object
) -> None:
    """A catalogue not written under the current schema is never handed to the trusted decode."""
    del authority_operation
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = InvoiceCatalogueRepository()
        original = _catalogue([seed_payload(SeedCase(1, date(2025, 7, 7), ("RATE_21",)))])
        repo.save(original)
        (invoice_id,) = original.invoices

        def restamp_and_renumber(envelope: dict[str, Any]) -> None:
            envelope["schema_version"] = INVOICE_CATALOGUE_NAMESPACE.schema_version + 1
            envelope["payload"]["invoices"][invoice_id]["invoice_number"] = "PASS-9999"

        _mutate_stored(profile, restamp_and_renumber)

        with pytest.raises(EnvelopeVersionError):
            repo.load_authenticated()


def test_a_foreign_record_refuses_the_read_though_no_read_returns_it(
    tmp_path: Path, authority_operation: object
) -> None:
    """The ownership guard reads every stored record's bucket, validated or not."""
    from .....domain.invoices.errors import InvoicePersistenceError

    del authority_operation
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = InvoiceCatalogueRepository()
        catalogue = _catalogue(
            [
                seed_payload(SeedCase(1, date(2025, 7, 7), ("RATE_21",))),
                seed_payload(SeedCase(2, date(2025, 7, 7), ("RATE_21",))),
            ],
            bucket_id=profile.bucket_id,
        )
        repo.save(catalogue)
        _first, second = catalogue.invoices

        def attribute_elsewhere(envelope: dict[str, Any]) -> None:
            envelope["payload"]["invoices"][second]["bucket_id"] = "00000000-0000-4000-8000-0000000000ff"

        _mutate_stored(profile, attribute_elsewhere)

        with pytest.raises(InvoicePersistenceError, match="carries invoices attributed to"):
            repo.load_authenticated()


_ENTRY_POINT: Final = "decode_authenticated_invoice_catalogue"
_REPOSITORY_MODULE: Final = "src/cadrumo/adapters/persistence/profile/invoices.py"
_REPOSITORY_METHOD: Final = "load_authenticated"


def _entry_point_references(source: str) -> list[str]:
    """Return the enclosing function of every reference to the trusted entry point."""
    tree = ast.parse(source)
    found: list[str] = []

    def visit(node: ast.AST, enclosing: str) -> None:
        for child in ast.iter_child_nodes(node):
            scope = child.name if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) else enclosing
            named = (
                (isinstance(child, ast.Name) and child.id == _ENTRY_POINT)
                or (isinstance(child, ast.Attribute) and child.attr == _ENTRY_POINT)
                or (isinstance(child, ast.alias) and child.name == _ENTRY_POINT)
            )
            if named:
                found.append(enclosing)
            visit(child, scope)

    visit(tree, "<module>")
    return found


def test_the_reference_scan_sees_aliased_and_attribute_references() -> None:
    """Positive control: an aliased import and an attribute call in a write path are both found."""
    source = (
        "from cadrumo.domain.invoices.catalogue import decode_authenticated_invoice_catalogue as decode\n"
        "from cadrumo.domain.invoices import catalogue\n"
        "def mutate(records):\n"
        "    return catalogue.decode_authenticated_invoice_catalogue(records)\n"
    )
    assert _entry_point_references(source) == ["<module>", "mutate"]


def test_only_the_repository_authenticated_read_reaches_the_trusted_entry_point() -> None:
    """No production module but the repository names the entry point, and only inside ``load_authenticated``."""
    callers: dict[str, list[str]] = {}
    for path in production_python_files():
        references = _entry_point_references(path.read_text(encoding="utf-8"))
        if references:
            callers[repo_relative(path)] = references

    assert set(callers) == {_REPOSITORY_MODULE}
    assert set(callers[_REPOSITORY_MODULE]) == {"<module>", _REPOSITORY_METHOD}
    assert callers[_REPOSITORY_MODULE].count("<module>") == 1
