"""Registry coverage and period-matrix verification tests."""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.resources.bundled_data import bundled_path
from .....tests import REPO_ROOT
from .....tests.aeat_literal_fixtures import RECORD_DESIGN_ROUTE_BASE_FIXTURE
from .._snapshot_internals import check_snapshot_filing_review_tier
from ..authority import ValidatedRegistryAuthority, bundled_authority
from ..corpus_catalogue import resolve_record_design_binary, verify_source_file
from ..coverage import (
    EvidenceTierCoverageGate,
    _snapshot_filing_review_proof,
    audit_registry_model_law_coverage,
    build_model_law_coverage_ledger,
)
from ..errors import NoRevisionForPeriodError, RegistryValidationError
from ..legal import verify_legal_catalogue_grounding
from ..loader_fingerprints import clear_fingerprint_cache
from ..schema import filing_period_from_scope
from ..schema_references import SourceReference
from ..snapshot import build_snapshot
from ..temporal import coverage_assessment_horizon, revision_selection_coordinates, select_revision
from ._catalogue_verification_support import _registry_tree
from ._loader_directory_mode_support import write_extracted_corpus_sidecar, write_fragmented_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUPPORTED_RECORD_DESIGN_YEARS = range(2023, 2027)
_PUBLICATION_BOUND_RECORD_DESIGN_EXCEPTIONS = {
    ("184", "2025-y-siguientes", 2026): "aeat-dr-184-2025",
}
_M038_SOURCE_ERA_LEGAL_REFS = {
    "orden-hac-646-2024:art-1",
    "orden-hac-646-2024:df-unica",
}


def test_supported_period_matrix_has_applicable_record_design_sources() -> None:
    """Every selected period carries an official layout applicable at its end.

    Record-design applicability is evidence for a filing period, not a second
    revision selector.  In particular, Modelo 303's 2024 late design applies
    to 3T/09 onward while its revision intentionally shares the filing year
    with the early design.  The production selector must therefore resolve by
    period token alone; the canonical period end only verifies the selected
    design source, never chooses the revision.
    """
    modelos, catalogues = _registry_tree()
    missing: list[str] = []
    checked: set[tuple[str, str, int]] = set()
    required_modelos: set[str] = set()
    resolved_exceptions: set[tuple[str, str, int]] = set()

    for modelo in modelos:
        modelo_id = str(modelo.id)
        modelo_sources = [
            catalogues.sources[source_ref]
            for source_ref in modelo.source_refs
            if catalogues.sources[source_ref].kind == "record_design"
        ]
        if not modelo_sources:
            continue
        required_modelos.add(modelo_id)
        for revision in modelo.revisions.values():
            sources = [
                catalogues.sources[source_ref]
                for source_ref in revision.source_refs
                if catalogues.sources[source_ref].kind == "record_design"
            ]
            for year in _SUPPORTED_RECORD_DESIGN_YEARS:
                if not revision.period_selector.includes_year(year):
                    continue
                revision_id = str(revision.id)
                exception_key = (modelo_id, revision_id, year)
                period_start = max(date(year, 1, 1), revision.valid_from)
                period_end = min(date(year, 12, 31), revision.valid_to or date.max)
                if period_start > period_end:
                    continue

                checked.add(exception_key)
                for period in revision.period_selector.periods:
                    selected = select_revision(
                        modelo,
                        filing_year=year,
                        period=period,
                    )
                    assert selected.id == revision.id

                if not sources:
                    missing.append(f"modelo {modelo_id}, revision {revision.id}, no record-design source")
                    continue

                pending_source_ref = _PUBLICATION_BOUND_RECORD_DESIGN_EXCEPTIONS.get(exception_key)
                if pending_source_ref is not None:
                    assert modelo.cadence == "annual"
                    assert pending_source_ref in revision.source_refs
                    assert not any(
                        source.applies_from is not None and source.applies_from.year >= year for source in sources
                    ), f"remove stale record-design publication exception {exception_key}"
                    resolved_exceptions.add(exception_key)
                    continue

                for period in revision.period_selector.periods:
                    filing_period = filing_period_from_scope(year, period)
                    evidence_date = (
                        filing_period.end_date
                        if filing_period is not None and filing_period.has_date_span()
                        else period_end
                    )
                    if not _record_design_sources_cover(sources, evidence_date):
                        missing.append(
                            f"modelo {modelo_id}, revision {revision.id}, period {period}, "
                            f"uncovered {evidence_date.isoformat()}",
                        )

    assert required_modelos == {modelo_id for modelo_id, _, _ in checked}
    assert resolved_exceptions == set(_PUBLICATION_BOUND_RECORD_DESIGN_EXCEPTIONS)
    assert not missing, "supported record-design matrix gaps:\n" + "\n".join(missing)


def _record_design_sources_cover(sources: Sequence[SourceReference], evidence_date: date) -> bool:
    """Return whether a cited record-design source covers one period endpoint."""
    return any(
        (source.applies_from is None or source.applies_from <= evidence_date)
        and (source.applies_to is None or source.applies_to >= evidence_date)
        for source in sources
    )


def test_modelo_220_2025_scope_refuses_an_unevidenced_2026_successor() -> None:
    """The shared source-matrix predicate must bite if M220 is widened again."""
    modelos, catalogues = _registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "220")
    revision = modelo.revisions["2025"]

    assert (revision.valid_from, revision.valid_to) == (date(2025, 1, 1), date(2025, 12, 31))
    assert (revision.period_selector.year_from, revision.period_selector.year_to) == (2025, 2025)
    assert select_revision(modelo, filing_year=2025, period="0A").id == "2025"
    with pytest.raises(NoRevisionForPeriodError):
        select_revision(modelo, filing_year=2026, period="0A")

    widened_revision = revision.model_copy(
        update={"period_selector": revision.period_selector.model_copy(update={"year_to": 2026})},
    )
    widened_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, "2025": widened_revision}})
    sources = [
        catalogues.sources[source_ref]
        for source_ref in widened_revision.source_refs
        if catalogues.sources[source_ref].kind == "record_design"
    ]

    assert tuple(source.id for source in sources) == ("aeat-dr-220-2025",)
    assert sources[0].applies_to == date(2025, 12, 31)
    assert select_revision(widened_modelo, filing_year=2026, period="0A").id == "2025"
    assert not _record_design_sources_cover(sources, date(2026, 12, 31))


def test_modelo_038_refuses_unevidenced_history_and_keeps_historical_pdf_unselected() -> None:
    """M038's legal cutover and inspection receipt cannot select pre-June history."""
    modelos, catalogues = _registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "038")
    june_2024 = modelo.revisions["2024-desde-06"]
    current_source = catalogues.sources["aeat-dr-038-2024"]
    historical_source = catalogues.sources["aeat-dr-038-2012-inspection"]

    manifest_path = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_038", "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    (historical_artefact,) = [
        artefact for artefact in manifest["artefacts"] if artefact["sha256"] == historical_source.sha256
    ]
    assert {
        key: historical_artefact[key] for key in ("modelo", "title", "original_filename", "sha256", "bytes", "url")
    } == {
        "bytes": 79486,
        "modelo": "038",
        "original_filename": "dr038_2005.pdf",
        "sha256": "e9008d9c0c407c76143d6997f3a5fb52a2a482c40571f395da7dcf8a8fee3d9d",
        "title": "038 - Orden HAC/66/2002, de 15 de enero (actualizado a 18/01/2012)",
        "url": f"{RECORD_DESIGN_ROUTE_BASE_FIXTURE}/DR_01_99/archivos/dr038_2005.pdf",
    }

    amendment_refs = {ref_id: catalogues.legal[ref_id] for ref_id in _M038_SOURCE_ERA_LEGAL_REFS}
    verify_legal_catalogue_grounding(amendment_refs, source_root=bundled_path())
    assert amendment_refs["orden-hac-646-2024:art-1"].required_text == (
        "Se introduce un nuevo campo, «Identificador registral único de la sociedad (IRUS)»",
        "ocupará las posiciones 153-165 del registro de tipo 2",
        "166-250",
    )
    assert amendment_refs["orden-hac-646-2024:df-unica"].required_text == (
        "será aplicable, por primera vez, a la declaración informativa correspondiente al mes de junio de 2024",
        "se presentará durante el mes de julio de 2024",
    )
    for revision in modelo.revisions.values():
        assert set(revision.legal_refs) >= _M038_SOURCE_ERA_LEGAL_REFS
        assert len(revision.constructs) == 1
        assert set(revision.constructs[0].legal_refs) >= _M038_SOURCE_ERA_LEGAL_REFS

    assert historical_source.applies_from is None
    assert historical_source.applies_to is None
    assert historical_source.record_design_epoch == "2012"
    verify_source_file(REPO_ROOT, historical_source)
    assert historical_source.id not in modelo.source_refs
    assert all(historical_source.id not in revision.source_refs for revision in modelo.revisions.values())
    assert current_source.applies_from == date(2024, 6, 1)
    assert current_source.applies_to is None

    # The documented 2012 era identifies the binary, but does not invent an
    # unsupported filing window. Selection therefore still fails closed before
    # a parser can consume the hash-verified historical PDF.
    with pytest.raises(RegistryValidationError, match="does not declare applies_from"):
        resolve_record_design_binary(
            bundled_path(),
            catalogues.sources,
            source_ref="aeat-dr-038-2012-inspection",
            filing_year=2012,
            design_epoch="2012",
        )

    for filing_year, period in ((2012, "12"), (2023, "12"), (2024, "01"), (2024, "05")):
        with pytest.raises(NoRevisionForPeriodError):
            select_revision(modelo, filing_year=filing_year, period=period)
    assert select_revision(modelo, filing_year=2024, period="06").id == "2024-desde-06"
    assert select_revision(modelo, filing_year=2024, period="12").id == "2024-desde-06"
    assert select_revision(modelo, filing_year=2025, period="01").id == "2025-y-siguientes"
    assert select_revision(modelo, filing_year=2026, period="12").id == "2025-y-siguientes"

    # A future author could accidentally widen both coordinates. Selection then
    # succeeds, but the selected source still exposes the unsupported month.
    widened_selector = june_2024.period_selector.model_copy(
        update={"periods": ("05", *june_2024.period_selector.periods)}
    )
    widened_revision = june_2024.model_copy(
        update={"valid_from": date(2024, 1, 1), "period_selector": widened_selector}
    )
    widened_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, "2024-desde-06": widened_revision}})
    selected = select_revision(widened_modelo, filing_year=2024, period="05")
    sources = [
        catalogues.sources[source_ref]
        for source_ref in selected.source_refs
        if catalogues.sources[source_ref].kind == "record_design"
    ]

    assert selected.id == "2024-desde-06"
    assert tuple(source.id for source in sources) == ("aeat-dr-038-2024",)
    assert not _record_design_sources_cover(sources, date(2024, 5, 31))


def test_committed_registry_tree_has_required_model_law_coverage() -> None:
    authority = bundled_authority()
    audit = audit_registry_model_law_coverage(authority)

    modelo_038 = next(
        ledger
        for ledger in audit.ledgers
        if (ledger.modelo, ledger.revision, ledger.filing_year, ledger.period) == ("038", "2024-desde-06", 2024, "06")
    )
    assert modelo_038.revision == "2024-desde-06"
    assert modelo_038.authority_scope == "inspection_only"
    assert not modelo_038.filing_eligible
    gates = {gate.tier: gate for gate in modelo_038.gates}
    assert gates["legal_authority"].legal_refs == (
        "ley-58-2003:art-93",
        "orden-hac-646-2024:art-1",
        "orden-hac-646-2024:df-unica",
        "orden-hac-66-2002:art-1",
        "orden-hac-66-2002:art-6",
    )
    assert gates["official_source_guidance"].source_refs == ("enrolled-modelo-038-procedure",)
    assert gates["layout_authority"].source_refs == ("aeat-dr-038-2024",)
    assert gates["layout_authority"].workbook_refs == ("modelo-038-2024-static-layout",)

    # Keep the full selector-derived denominator and every mandatory tier
    # visible. M038's inspection projection is deliberately non-filing, but
    # its evidence still belongs in every claimed month through the current
    # registered horizon.
    assert audit.ok
    assert audit.required_gate_failures == ()
    assessment_horizon = coverage_assessment_horizon(authority.catalogues)
    expected_coordinates = {
        (modelo.id, revision.id, filing_year, period)
        for modelo in authority.modelos
        for revision in modelo.revisions.values()
        for filing_year, period in revision_selection_coordinates(
            revision,
            assessment_horizon=assessment_horizon,
        )
    }
    actual_coordinates = {
        (ledger.modelo, ledger.revision, ledger.filing_year, ledger.period) for ledger in audit.ledgers
    }
    assert actual_coordinates == expected_coordinates
    for ledger in audit.ledgers:
        gates = {gate.tier: gate for gate in ledger.gates}
        assert gates["legal_authority"].status == "satisfied", ledger
        assert gates["official_source_guidance"].status == "satisfied", ledger
        assert gates["layout_authority"].status == "satisfied", ledger


def _synthetic_reviewed_coverage_authority(tmp_path: Path) -> ValidatedRegistryAuthority:
    """Build the smallest validator-backed reviewed corpus with no layout evidence."""
    registry_root = tmp_path / "registry" / "aeat"
    legal_dir = registry_root / "legal"
    revision_dir = registry_root / "modelos" / "999" / "revisions" / "2025-2026"
    legal_dir.mkdir(parents=True)
    revision_dir.mkdir(parents=True)

    corpus_dir = tmp_path / "corpus" / "test"
    corpus_dir.mkdir(parents=True)
    legal_corpus = corpus_dir / "synthetic-orden.html"
    legal_corpus.write_text("<html>synthetic provision text</html>", encoding="utf-8")
    write_extracted_corpus_sidecar(legal_corpus, anchor="a1", text="synthetic provision text")
    guidance_bytes = b"synthetic official guidance"
    parity_bytes = b"synthetic executable parity"
    (corpus_dir / "synthetic-guidance.pdf").write_bytes(guidance_bytes)
    (corpus_dir / "synthetic-parity.pdf").write_bytes(parity_bytes)

    legal_dir.joinpath("catalogue.toml").write_text(
        "\n".join(
            (
                "[supported_filing_years]",
                "years = [2025, 2026]",
                "",
                '[legal."orden-test-0001:art-1"]',
                'evidence_tier = "legal_authority"',
                'authority = "boe"',
                'kind = "orden"',
                'corpus_ref = "corpus/test/synthetic-orden.html#a1"',
                'document_id = "BOE-A-2025-00001"',
                'article = "1"',
                'permalink = "https://example.com/synthetic-orden"',
                "effective_from = 2025-01-01",
                'review_status = "operator_reviewed"',
                "reviewed_at = 2026-08-25",
                'reviewed_by = "synthetic corpus reviewer"',
                'required_text = ["synthetic provision text"]',
                "",
                '[sources."test-source-guidance"]',
                'evidence_tier = "official_source_guidance"',
                'authority = "aeat"',
                'kind = "instructions"',
                'corpus_path = "corpus/test/synthetic-guidance.pdf"',
                f'sha256 = "{hashlib.sha256(guidance_bytes).hexdigest()}"',
                f"bytes = {len(guidance_bytes)}",
                "retrieved_at = 2026-08-25",
                'source_url = "https://example.com/synthetic-guidance"',
                'review_status = "pending_review"',
                "",
                '[sources."test-source-parity"]',
                'evidence_tier = "executable_parity_evidence"',
                'authority = "aeat"',
                'kind = "instructions"',
                'corpus_path = "corpus/test/synthetic-parity.pdf"',
                f'sha256 = "{hashlib.sha256(parity_bytes).hexdigest()}"',
                f"bytes = {len(parity_bytes)}",
                "retrieved_at = 2026-08-25",
                'source_url = "https://example.com/synthetic-parity"',
                'review_status = "pending_review"',
                "",
            ),
        ),
        encoding="utf-8",
    )
    registry_root.joinpath("modelos", "999", "manifest.toml").write_text(
        "\n".join(
            (
                "[modelo]",
                'id = "999"',
                'tax_domain = "iva"',
                'cadence = "annual"',
                'jurisdiction = "ES-AEAT"',
                'legal_refs = ["orden-test-0001:art-1"]',
                'source_refs = ["test-source-guidance"]',
                "",
            ),
        ),
        encoding="utf-8",
    )
    write_fragmented_revision(
        revision_dir,
        """\
[revisions."2025-2026"]
valid_from = 2025-01-01
period_selector = { years = [2025, 2026], periods = ["0A"] }
authority_grade = "applicability"
review_status = "agent_reviewed"
reviewed_by = "synthetic corpus reviewer"
reviewed_at = 2026-08-25
legal_refs = ["orden-test-0001:art-1"]
source_refs = ["test-source-guidance"]
orden_aplicabilidad = ["orden-test-0001:art-1"]

[[revisions."2025-2026".application_links]]
id = "synthetic-coverage-filing"
surface = "filing"
consumer = "synthetic.coverage"
requires_snapshot = true
legal_refs = ["orden-test-0001:art-1"]
source_refs = ["test-source-guidance"]

[[revisions."2025-2026".casillas]]
id = "01"
number = "01"
section = ["synthetic"]
data_type = "integer"
legal_refs = ["orden-test-0001:art-1"]
source_refs = ["test-source-guidance"]

[[revisions."2025-2026".workbook_parity_refs]]
id = "synthetic-coverage-parity"
workbook_source = "test-source-parity"
fixture_id = "synthetic-coverage-fixture"
formula_coverage = "formula_form"
runner_required = true
output_cells = { result = "Synthetic!A1" }
tolerance = "0.00"
legal_refs = ["orden-test-0001:art-1"]
source_refs = ["test-source-parity"]
""",
    )
    clear_fingerprint_cache()
    return ValidatedRegistryAuthority.load(registry_root, source_root=tmp_path)


def test_model_law_matrix_reports_a_non_vacuous_gap_from_a_synthetic_reviewed_corpus(tmp_path: Path) -> None:
    """A validator-backed reviewed corpus produces each derived missing-layout cell."""
    authority = _synthetic_reviewed_coverage_authority(tmp_path)
    modelo = authority.modelo("999")
    revision = modelo.revisions["2025-2026"]
    inspection = authority.inspect_revision("999", filing_year=2025, period="0A")
    assert {source.evidence_tier for source in inspection.sources.values()} == {
        "official_source_guidance",
        "executable_parity_evidence",
    }
    assert not any(source.evidence_tier == "layout_authority" for source in inspection.sources.values())

    audit = audit_registry_model_law_coverage(authority)
    expected_coordinates = set(
        revision_selection_coordinates(
            revision,
            assessment_horizon=coverage_assessment_horizon(authority.catalogues),
        ),
    )
    layout_gaps = [
        ledger
        for ledger in audit.ledgers
        if next(gate for gate in ledger.gates if gate.tier == "layout_authority").status == "gap"
    ]

    assert len(expected_coordinates) > 1
    ledgers = [ledger for ledger in audit.ledgers if ledger.revision == revision.id]
    assert {(ledger.filing_year, ledger.period) for ledger in ledgers} == expected_coordinates
    assert all(ledger.authority_scope == "inspection_only" for ledger in ledgers)
    assert {(ledger.filing_year, ledger.period) for ledger in layout_gaps} == expected_coordinates
    assert audit.required_gate_failures


def test_coverage_filing_review_proof_delegates_to_snapshot_owned_check(tmp_path: Path) -> None:
    """Coverage classification obtains review status from the snapshot boundary."""
    authority = _synthetic_reviewed_coverage_authority(tmp_path)
    modelo = authority.modelo("999")
    revision = modelo.revisions["2025-2026"]
    inspection = authority.inspect_revision(modelo.id, filing_year=2025, period="0A")

    snapshot_tier = check_snapshot_filing_review_tier(
        modelo,
        revision,
        authority.catalogues,
        set(inspection.legal_ref_ids),
    )
    proof = _snapshot_filing_review_proof(modelo, revision, authority, inspection)

    assert "check_snapshot_filing_review_tier(" in inspect.getsource(_snapshot_filing_review_proof)
    assert proof is not None
    assert proof.review_tier is snapshot_tier


def test_coverage_gate_rejects_satisfied_without_evidence_refs() -> None:
    with pytest.raises(ValidationError, match="cannot be satisfied without evidence refs"):
        EvidenceTierCoverageGate(
            tier="legal_authority",
            status="satisfied",
            detail="missing evidence",
        )


def test_public_model_law_ledger_keeps_unproven_snapshot_inspection_only() -> None:
    """A snapshot-shaped value cannot self-attest filing authority."""
    modelos, catalogues = _registry_tree()
    modelo = next(modelo for modelo in modelos if modelo.id == "182")
    # Build at the rung modelo 182 declares, not the FILING default. Demanding a
    # filing-grade build in order to prove the ledger reports NOT filing-eligible
    # is self-contradictory: the build refuses first, and the assertion below --
    # the actual subject -- never runs.
    revision = select_revision(modelo, filing_year=2025, period="0A")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
        grade=revision.effective_authority_grade,
    )

    ledger = build_model_law_coverage_ledger(snapshot)

    assert ledger.authority_scope == "inspection_only"
    assert not ledger.filing_eligible


def test_coverage_gate_rejects_gap_with_evidence_refs() -> None:
    with pytest.raises(ValidationError, match="coverage gap cannot carry evidence refs"):
        EvidenceTierCoverageGate(
            tier="legal_authority",
            status="gap",
            legal_refs=("ley-58-2003:art-119",),
            detail="inconsistent gap",
        )


def test_coverage_gate_rejects_blank_evidence_ref_ids() -> None:
    for field_update in (
        {"legal_refs": ("",)},
        {"source_refs": ("",)},
        {"workbook_refs": ("",)},
        {"cross_reference_refs": ("",)},
    ):
        with pytest.raises(ValidationError, match=next(iter(field_update))):
            EvidenceTierCoverageGate(
                tier="legal_authority",
                status="satisfied",
                detail="blank evidence id",
                **field_update,
            )
