"""Cross-cutting authority enrollment tests for governed facts."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest

from ..._validate import RegistryValidator
from ...authority import collect_registry_identity_fingerprints, reset_registry_caches
from ...errors import RegistryValidationError
from ...schema import RegistryCatalogues
from ...schema_references import LegalReference, SourceReference
from .. import providers as provider_module
from ..providers import (
    FACT_PROVIDER_REGISTRATIONS,
    compile_registered_fact_providers,
    validate_fact_provider_directory_ownership,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _write_fact(path: Path) -> None:
    path.write_text(
        '''[fact]
fact_id = "test.limit"
family = "scalar"

[[fact.variants]]
variant_id = "test.limit.2025"
date_axis = "filing_period"
valid_from = 2025-01-01
legal_refs = ["missing-law"]
source_refs = ["missing-source"]
review_status = "pending_review"
ownership = "authored"

[[fact.variants.source_citations]]
source_ref = "missing-source"
required_text = ["limit"]

[fact.variants.payload]
kind = "scalar"
value = "10"
unit = "EUR"
''',
        encoding="utf-8",
    )


def test_fact_content_participates_in_authority_identity(tmp_path: Path) -> None:
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    path = facts_dir / "0001-test-limit.toml"
    _write_fact(path)
    before = collect_registry_identity_fingerprints(tmp_path)
    stat = path.stat()

    text = path.read_text(encoding="utf-8").replace('value = "10"', 'value = "20"')
    path.write_text(text, encoding="utf-8")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    after = collect_registry_identity_fingerprints(tmp_path)
    assert before != after


def test_fact_catalogue_identity_prevents_reusing_a_green_validation_memo(tmp_path: Path) -> None:
    shared_legal: dict[str, LegalReference] = {}
    shared_sources: dict[str, SourceReference] = {}
    RegistryValidator(RegistryCatalogues(legal=shared_legal, sources=shared_sources)).validate_registry(())
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    _write_fact(facts_dir / "0001-test-limit.toml")
    changed_catalogues = RegistryCatalogues(
        legal=shared_legal,
        sources=shared_sources,
        facts=compile_registered_fact_providers(tmp_path),
    )

    with pytest.raises(RegistryValidationError, match=r"unknown legal id.*missing-law"):
        RegistryValidator(changed_catalogues).validate_registry(())


def test_nested_governed_directory_requires_an_exact_provider_owner(tmp_path: Path) -> None:
    (tmp_path / "facts" / "unregistered").mkdir(parents=True)

    with pytest.raises(RegistryValidationError, match="has no registered provider"):
        validate_fact_provider_directory_ownership(tmp_path)


def test_authority_reset_invokes_every_registered_provider_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    resets: list[str] = []
    registration = replace(FACT_PROVIDER_REGISTRATIONS[0], reset=lambda: resets.append("authored-facts"))
    monkeypatch.setattr(provider_module, "FACT_PROVIDER_REGISTRATIONS", (registration,))

    reset_registry_caches()

    assert resets == ["authored-facts"]
