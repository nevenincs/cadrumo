"""Real-behaviour coverage for binding-readiness fallbacks."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import pytest

from ....core import Period, RegistryAuthorityGrade
from ....domain.calculations.registry.authority import ValidatedRegistryAuthority
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.queries import RegistryQueryService
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
review_status = "agent_reviewed"
reviewed_at = 2025-01-01
reviewed_by = "registry-test"
required_text = ["test provision text"]

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

[sources."test-source-002"]
evidence_tier = "official_source_guidance"
authority = "aeat"
kind = "instructions"
corpus_path = "corpus/test/test-source-002.pdf"
sha256 = "44f8354494a5ba03ba1792a8d3e9c534c47a9181980fde7a3f44b06ef2ae7c7f"
bytes = 1000
retrieved_at = 2025-01-01
source_url = "https://example.com/test-source-002"
review_status = "reviewed"
"""

_MINIMAL_MANIFEST_TOML = """\
[modelo]
id = "999"
tax_domain = "iva"
cadence = "quarterly"
jurisdiction = "ES-AEAT"
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]
"""

# Scalar revision metadata only; per-section array-of-tables live in fragment
# subdirectories (the loader rejects inline sections in revision.toml). The
# label is derived from the shared locale catalogue, not stored on the
# revision, so it carries no TOML field here.
_MINIMAL_REVISION_TOML_TEMPLATE = """\
[revisions."{revision_id}"]
valid_from = {valid_from}
{valid_to_line}
period_selector = {{ years = [2025], periods = ["{period}"] }}
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]
orden_aplicabilidad = ["test-ley-001:art-1"]
# Declared by INTENT, as the validator requires, not read off the fragments
# below: this synthetic revision exists only to make two revisions cover one
# year so a year-only readiness query meets an ambiguous boundary. It is
# never asked to compute an amount or back a filing draft.
authority_grade = "applicability"
"""

_APPLICATION_LINKS_FRAGMENT_TEMPLATE = """\
[[revisions."{revision_id}".application_links]]
id = "test-filing-link"
surface = "filing"
consumer = "cli.app"
requires_snapshot = true
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-002"]
"""

_CASILLAS_FRAGMENT_TEMPLATE = """\
[[revisions."{revision_id}".casillas]]
id = "01"
number = "01"
section = ["test"]
data_type = "integer"
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]
"""

_WORKBOOK_PARITY_FRAGMENT_TEMPLATE = """\
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


def _write_year_ambiguous_registry(
    tmp_path: Path,
    *,
    revisions: tuple[tuple[str, str, str, str | None], ...] = (
        ("2025-1t", "1T", "2025-01-01", None),
        ("2025-2t", "2T", "2025-01-01", None),
    ),
) -> Path:
    registry_root = tmp_path / "registry" / "aeat"
    legal_dir = registry_root / "legal"
    modelos_dir = registry_root / "modelos" / "999"
    legal_dir.mkdir(parents=True)
    modelos_dir.mkdir(parents=True)
    # The loader requires one registry-wide supported-filing-years declaration.
    # This fixture's revisions select 2025 and the readiness call asks about
    # 2026, so both are admitted here; without the file the tree refuses to load
    # before any readiness behaviour is reached.
    (legal_dir / "supported-filing-years.toml").write_text(
        "[supported_filing_years]\nyears = [2025, 2026]\n",
        encoding="utf-8",
    )
    corpus_file = tmp_path / "corpus" / "test" / "test-source-001.pdf"
    corpus_file.parent.mkdir(parents=True)
    corpus_file.write_bytes(b"x" * 1000)
    (corpus_file.parent / "test-source-002.pdf").write_bytes(b"x" * 1000)
    (corpus_file.parent / "test-ley-001.html").write_text("<html>test provision text</html>", encoding="utf-8")
    # The registry loader requires a companion ``.extracted.json`` sidecar
    # alongside every legal-reference corpus file (see
    # ``domain.calculations.registry._legal._legal_corpus_text``); a single
    # unit whose text carries the catalogue's declared ``required_text``
    # satisfies both the existence check and the anchor resolution.
    (corpus_file.parent / "test-ley-001.html.extracted.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source_kind": "normatives_html",
                "status": "ok",
                "source_relpath": "corpus/test/test-ley-001.html",
                "source_sha256": "0" * 64,
                "preprocessor_id": "test-fixture",
                "preprocessor_version": "1.0",
                "units": [
                    {
                        "text": "test provision text",
                        "title": "Article 1",
                        "section": "Article 1",
                        "anchor": "a1",
                    },
                ],
            },
        ),
        encoding="utf-8",
    )

    (legal_dir / "catalogue.toml").write_text(_MINIMAL_CATALOGUE_TOML, encoding="utf-8")
    (modelos_dir / "manifest.toml").write_text(_MINIMAL_MANIFEST_TOML, encoding="utf-8")

    for revision_id, period, valid_from, valid_to in revisions:
        revision_dir = modelos_dir / "revisions" / revision_id
        revision_dir.mkdir(parents=True)
        (revision_dir / "revision.toml").write_text(
            _MINIMAL_REVISION_TOML_TEMPLATE.format(
                revision_id=revision_id,
                period=period,
                valid_from=valid_from,
                valid_to_line="" if valid_to is None else f"valid_to = {valid_to}",
            ),
            encoding="utf-8",
        )
        for section, template in (
            ("application_links", _APPLICATION_LINKS_FRAGMENT_TEMPLATE),
            ("casillas", _CASILLAS_FRAGMENT_TEMPLATE),
            ("workbook_parity_refs", _WORKBOOK_PARITY_FRAGMENT_TEMPLATE),
        ):
            section_dir = revision_dir / section
            section_dir.mkdir()
            (section_dir / f"0001-{section.replace('_', '-')}.toml").write_text(
                template.format(revision_id=revision_id),
                encoding="utf-8",
            )

    return registry_root


def test_unresolvable_registry_scope_is_logged_as_conservative_unresolved(caplog: pytest.LogCaptureFixture) -> None:
    """Invalid registry scopes return no resolved bindings and emit debug diagnostics."""
    caplog.set_level(logging.DEBUG, logger="cadrumo.application.modelo._binding_readiness")

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
    caplog.set_level(logging.DEBUG, logger="cadrumo.application.modelo._binding_readiness")

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

    with pytest.raises(RegistryValidationError):
        profile_resolvable_binding_ids(
            modelo="303",
            bucket_id="operator",
            filing_year=2025,
            period=Period.from_year_and_code(2026, "1T"),
        )


def test_year_only_binding_readiness_refuses_multiple_covering_revisions(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A year-only readiness query must not silently select one period-specific revision.

    ``_annual_period_for_year`` is a read-only discovery helper whose contract
    is "None means undetermined"; it CATCHES the selector's
    ``AmbiguousRevisionSelectionError`` rather than propagating it, so a
    mid-year AEAT design boundary degrades to unresolved bindings instead of
    turning a readiness query into an operator-facing error.
    """
    caplog.set_level(logging.DEBUG, logger="cadrumo.application.modelo._binding_readiness")

    registry_root = _write_year_ambiguous_registry(tmp_path)
    authority = ValidatedRegistryAuthority.load(registry_root, source_root=tmp_path)

    assert _annual_period_for_year(authority, modelo="999", filing_year=2025) is None
    assert any(
        "binding-readiness: filing_year=2025 for modelo=999 is covered by revisions 2025-1t, 2025-2t" in record.message
        for record in caplog.records
    )


def test_year_only_report_and_readiness_share_effective_revision_selection(tmp_path: Path) -> None:
    """Same-year revisions select the effective window before readiness materialises its snapshot."""
    registry_root = _write_year_ambiguous_registry(
        tmp_path,
        revisions=(
            ("2025-early", "1T", "2025-01-01", "2025-06-30"),
            ("2025-late", "2T", "2025-07-01", None),
        ),
    )
    authority = ValidatedRegistryAuthority.load(registry_root, source_root=tmp_path)
    service = RegistryQueryService(authority)

    early_as_of = date(2025, 3, 31)
    late_as_of = date(2025, 9, 30)
    early_report = service.bindings_for_year("999", filing_year=2025, as_of=early_as_of)
    late_report = service.bindings_for_year("999", filing_year=2025, as_of=late_as_of)

    assert (early_report.revision, early_report.period) == ("2025-early", "1T")
    assert (late_report.revision, late_report.period) == ("2025-late", "2T")
    assert _annual_period_for_year(authority, modelo="999", filing_year=2025, as_of=early_as_of) == early_report.period
    assert _annual_period_for_year(authority, modelo="999", filing_year=2025, as_of=late_as_of) == late_report.period
    # These assertions are about which revision SELECTION lands on, so they ask
    # for the applicability rung the fixture declares. ``snapshot`` defaults to
    # ``FILING``, which this synthetic revision truthfully cannot satisfy -- and
    # raising its declared grade to silence that would be picking the rung to
    # match a caller instead of the revision's intent, which is exactly what the
    # grade validator refuses.
    assert (
        authority.snapshot(
            "999",
            filing_year=2025,
            period=early_report.period or "",
            on=early_as_of,
            revision_id=early_report.revision,
            grade=RegistryAuthorityGrade.APPLICABILITY,
        ).revision.id
        == early_report.revision
    )
    assert (
        authority.snapshot(
            "999",
            filing_year=2025,
            period=late_report.period or "",
            on=late_as_of,
            revision_id=late_report.revision,
            grade=RegistryAuthorityGrade.APPLICABILITY,
        ).revision.id
        == late_report.revision
    )
