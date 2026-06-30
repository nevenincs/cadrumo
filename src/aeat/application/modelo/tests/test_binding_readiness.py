"""Real-behaviour coverage for binding-readiness fallbacks."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from ....core import Period
from ....domain.calculations.registry import (
    AmbiguousRevisionSelectionError,
    RegistryValidationError,
    ValidatedRegistryAuthority,
)
from .._binding_readiness import _annual_period_for_year, profile_resolvable_binding_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MINIMAL_CATALOGUE_TOML = """\
[legal."test-ley-001:art-1"]
evidence_tier = "legal_authority"
authority = "boe"
kind = "ley"
corpus_ref = "corpus/test/test-ley-001.html#a1"
document_id = "BOE-T-001"
article = "1"
permalink = "https://example.com/test"
effective_from = 2025-01-01
review_status = "reviewed"

[sources."test-source-001"]
evidence_tier = "layout_authority"
authority = "aeat"
kind = "record_design"
corpus_path = "corpus/test/test-source-001.pdf"
sha256 = "44f8354494a5ba03ba1792a8d3e9c534c47a9181980fde7a3f44b06ef2ae7c7f"
bytes = 1000
retrieved_at = 2025-01-01
source_url = "https://example.com/test-source"
review_status = "reviewed"
"""

_MINIMAL_MANIFEST_TOML = """\
[modelo]
id = "999"
title = "Binding readiness ambiguity test modelo"
official_name = "Binding readiness ambiguity test modelo"
tax_domain = "iva"
cadence = "quarterly"
jurisdiction = "ES-AEAT"
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]
"""

_MINIMAL_REVISION_TOML_TEMPLATE = """\
[revisions."{revision_id}"]
label = "{label}"
valid_from = 2025-01-01
period_selector = {{ years = [2025], periods = ["{period}"] }}
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]
orden_aplicabilidad = ["test-ley-001:art-1"]

[[revisions."{revision_id}".application_links]]
id = "test-filing-link"
surface = "filing"
consumer = "cli.app"
requires_snapshot = true
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]

[[revisions."{revision_id}".casillas]]
id = "01"
number = "01"
label = "Test casilla"
section = ["test"]
data_type = "integer"
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]

[[revisions."{revision_id}".workbook_parity_refs]]
id = "test-workbook-001"
workbook_source = "test-source-001"
fixture_id = "test-fixture-001"
formula_coverage = "record_design_layout"
runner_required = false
tolerance = "0.00"
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]
"""


def _write_year_ambiguous_registry(tmp_path: Path) -> Path:
    registry_root = tmp_path / "registry" / "aeat"
    legal_dir = registry_root / "legal"
    modelos_dir = registry_root / "modelos" / "999"
    legal_dir.mkdir(parents=True)
    modelos_dir.mkdir(parents=True)
    corpus_file = tmp_path / "corpus" / "test" / "test-source-001.pdf"
    corpus_file.parent.mkdir(parents=True)
    corpus_file.write_bytes(b"x" * 1000)

    (legal_dir / "catalogue.toml").write_text(_MINIMAL_CATALOGUE_TOML, encoding="utf-8")
    (modelos_dir / "manifest.toml").write_text(_MINIMAL_MANIFEST_TOML, encoding="utf-8")

    for revision_id, label, period in (
        ("2025-1t", "2025 first quarter", "1T"),
        ("2025-2t", "2025 second quarter", "2T"),
    ):
        revision_dir = modelos_dir / "revisions" / revision_id
        revision_dir.mkdir(parents=True)
        (revision_dir / "revision.toml").write_text(
            _MINIMAL_REVISION_TOML_TEMPLATE.format(revision_id=revision_id, label=label, period=period),
            encoding="utf-8",
        )

    return registry_root


def test_unresolvable_registry_scope_is_logged_as_conservative_unresolved(caplog: pytest.LogCaptureFixture) -> None:
    """Invalid registry scopes return no resolved bindings and emit debug diagnostics."""
    caplog.set_level(logging.DEBUG, logger="aeat.application.modelo._binding_readiness")

    resolved = profile_resolvable_binding_ids(
        modelo="not-a-modelo",
        bucket_id="operator",
        filing_year=2026,
        period=None,
    )

    assert resolved == frozenset()
    assert any(
        "binding-readiness: annual period unavailable" in record.message
        and "treating profile bindings as unresolved" in record.message
        for record in caplog.records
    )


def test_unresolvable_typed_period_scope_is_logged_as_conservative_unresolved(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit Period scopes use the typed registry token at the snapshot boundary."""
    caplog.set_level(logging.DEBUG, logger="aeat.application.modelo._binding_readiness")

    resolved = profile_resolvable_binding_ids(
        modelo="not-a-modelo",
        bucket_id="operator",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
    )

    assert resolved == frozenset()
    assert any(
        "binding-readiness: registry snapshot unavailable" in record.message and "period=1T" in record.message
        for record in caplog.records
    )


def test_typed_period_scope_must_match_filing_year() -> None:
    """The helper refuses contradictory typed coordinates before querying the registry."""

    with pytest.raises(RegistryValidationError, match="does not match filing year"):
        profile_resolvable_binding_ids(
            modelo="303",
            bucket_id="operator",
            filing_year=2025,
            period=Period.from_year_and_code(2026, "1T"),
        )


def test_year_only_binding_readiness_refuses_multiple_covering_revisions(tmp_path: Path) -> None:
    """A year-only readiness query must not silently select one period-specific revision."""

    registry_root = _write_year_ambiguous_registry(tmp_path)
    authority = ValidatedRegistryAuthority.load(registry_root, source_root=tmp_path)

    with pytest.raises(AmbiguousRevisionSelectionError) as exc_info:
        _annual_period_for_year(authority, modelo="999", filing_year=2025)

    assert exc_info.value.modelo_id == "999"
    assert exc_info.value.candidate_ids == ("2025-1t", "2025-2t")
