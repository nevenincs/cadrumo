"""Tests for registry source and legal catalogue verification."""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.record_design_epoch import RECORD_DESIGN_EPOCH_RE
from .....core.external_constants import PDF_EXTENSION, XLS_EXTENSION, XLSM_EXTENSION, XLSX_EXTENSION
from .....core.resources import bundled_path
from .....tests import REPO_ROOT
from .....tests.aeat_literal_fixtures import RECORD_DESIGN_ROUTE_BASE_FIXTURE
from .._snapshot_internals import check_snapshot_filing_review_tier
from .._validate import RegistryValidator
from ..authority import ValidatedRegistryAuthority, bundled_authority
from ..corpus_catalogue import resolve_record_design_binary, verify_source_catalogue, verify_source_file
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
from ._catalogue_verification_support import _catalogues, _registry_tree
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


def test_committed_registry_tree_has_coherent_shared_catalogues() -> None:
    modelos, catalogues = _registry_tree()

    assert len(modelos) >= 5, "committed registry must declare several modelos"
    assert len(catalogues.legal) > 0, "shared legal catalogue must be non-empty"
    assert len(catalogues.sources) > 0, "shared sources catalogue must be non-empty"
    verify_legal_catalogue_grounding(catalogues.legal, source_root=bundled_path())
    verify_source_catalogue(REPO_ROOT, catalogues.sources)
    validator = RegistryValidator(catalogues, source_root=bundled_path())
    validator.validate_registry(modelos)


#: The deliberately year-vintaged excerpts a corpus forbidden-text clause must
#: never treat as a defect: each carries at least one phrase unique to its own
#: historical redaction, which is what pins its intended vintage. See the
#: grounding reference's "vintaged excerpts behave CORRECTLY" finding.
_DELIBERATELY_VINTAGED_EXCERPT_IDS = (
    "ley-35-2006:art-23-2021",
    "ley-35-2006:art-52-2015",
    "ley-35-2006:art-52-2021",
    "ley-35-2006:art-66-2021",
    "ley-35-2006:art-68-2018",
)


def test_forbidden_text_clause_is_additive_over_the_full_committed_legal_catalogue() -> None:
    """The new optional forbidden-text clause must not disturb any existing entry.

    A refusal firing on a synthetic fixture proves the clause CAN catch a
    repealed phrase; it proves nothing about whether the clause over-reaches on
    the real catalogue. This is the control that decides closure: every entry
    in the committed catalogue still loads and validates unchanged now that the
    schema carries the new clause. The deliberately year-vintaged excerpts are
    named explicitly because they legitimately contain text current law does
    not, and none of them is given a forbidden_text clause by this change.
    """
    _modelos, catalogues = _registry_tree()

    assert len(catalogues.legal) > 0, "control is meaningless against an empty catalogue"
    for vintaged_id in _DELIBERATELY_VINTAGED_EXCERPT_IDS:
        assert vintaged_id in catalogues.legal, f"{vintaged_id!r} must remain in the committed legal catalogue"
        assert catalogues.legal[vintaged_id].forbidden_text == (), (
            f"{vintaged_id!r} is a deliberately historical excerpt; this control authors no forbidden_text for it"
        )

    verify_legal_catalogue_grounding(catalogues.legal, source_root=bundled_path())


def test_no_legal_reference_grounds_a_normatives_citation_in_a_derived_artefact() -> None:
    """A ``corpus_ref`` under ``corpus/normatives/`` must name the source, not a build product.

    ``7cdae88dc1`` reverted 22 refs that pointed ``corpus_ref`` at a
    ``*.html.extracted.md`` sidecar -- a workaround for the anchor-resolution
    regression ``daa9876ed3`` fixed properly -- back onto their source
    ``*.html`` documents, because no code path resolves or expects a
    ``corpus_ref`` naming ``.extracted.md``: the resolver always derives its
    own ``<corpus_ref path>.extracted.json`` sidecar from the named ``.html``
    source. This gate keeps that reversion from silently drifting back.

    ``corpus/manuals/**/*.pdf.extracted.md`` refs are the deliberate
    exception, carved out by name rather than caught by this pattern: a PDF
    manual excerpt has no ``.html`` counterpart to point at, so its
    ``corpus_ref`` legitimately names the extracted markdown directly (see
    ``irpf-autonomica-madrid.toml``, 3 refs, committed long before the 22-ref
    regression this gate targets). A naive "no path ends in ``.extracted.md``"
    rule would red on those three legitimate refs; this one matches only the
    ``normatives``-rooted, ``.html.extracted.md``-suffixed shape the
    regression actually took.
    """
    _modelos, catalogues = _registry_tree()

    offending = sorted(
        f"{ref_id} -> {reference.corpus_ref!r}"
        for ref_id, reference in catalogues.legal.items()
        if reference.corpus_ref is not None
        and reference.corpus_ref.partition("#")[0].startswith("corpus/normatives/")
        and reference.corpus_ref.partition("#")[0].endswith(".html.extracted.md")
    )

    assert offending == [], (
        "legal reference(s) ground a citation in a derived .extracted.md artefact "
        f"instead of the .html source it was built from: {offending}"
    )


def test_the_derived_artefact_gate_still_admits_the_pdf_manual_exception() -> None:
    """The gate above must not have been satisfied by accidentally excluding the exception too.

    Proves the negative test isn't vacuous: the three legitimate
    ``corpus/manuals/**/*.pdf.extracted.md`` refs still exist in the committed
    catalogue and are exactly the ones the gate's ``corpus/normatives/`` scope
    exempts, not references that happen not to exist at all.
    """
    _modelos, catalogues = _registry_tree()

    manual_extracted_md_refs = [
        ref_id
        for ref_id, reference in catalogues.legal.items()
        if reference.corpus_ref is not None
        and reference.corpus_ref.partition("#")[0].startswith("corpus/manuals/")
        and reference.corpus_ref.partition("#")[0].endswith(".pdf.extracted.md")
    ]

    assert len(manual_extracted_md_refs) >= 3, (
        f"expected the committed Madrid autonomic-deduction manual refs to still be present, "
        f"found {manual_extracted_md_refs}"
    )


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
                'review_status = "reviewed"',
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
                'review_status = "reviewed"',
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


def test_committed_aeat_record_design_sources_match_corpus_manifests() -> None:
    catalogues = _catalogues()
    checked: list[str] = []

    for source in catalogues.sources.values():
        path = Path(source.corpus_path)
        parts = path.parts
        if len(parts) < 5 or parts[:3] != ("corpus", "aeat_official", "disenos_registro"):
            continue
        # corpus_path is stored relative to the bundled corpus root
        # (src/cadrumo/_data/), so resolve via bundled_path rather than
        # REPO_ROOT to find the on-disk manifest.
        modelo_dir = bundled_path(*parts[:4])
        manifest_path = modelo_dir / "manifest.json"
        assert manifest_path.is_file(), f"{source.id} missing corpus manifest {manifest_path}"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        stored_path = Path(*parts[4:]).as_posix()
        artefact = next(
            (item for item in manifest["artefacts"] if item["stored_path"] == stored_path),
            None,
        )

        assert artefact is not None, f"{source.id} missing manifest artefact for {stored_path}"
        assert source.sha256 == artefact["sha256"], source.id
        assert source.bytes == artefact["bytes"], source.id
        assert source.source_url == artefact["url"], source.id
        checked.append(source.id)

    assert checked


#: The SAME extension set the schema's own ``kind == "record_design"`` validator
#: accepts (``_schema_references.py``), reused rather than redeclared. A source
#: NOT kind-``record_design`` whose bundled file carries one of these binary
#: extensions AND lives under the AEAT ``disenos_registro/`` tree is exactly the
#: shape the schema's forward check cannot see: nothing constrains what a
#: ``form_spec`` (or other) kind may point at, so a real Diseño de Registro
#: binary can sit mislabelled indefinitely with no gate noticing.
_BINARY_RECORD_DESIGN_EXTENSIONS = (PDF_EXTENSION, XLS_EXTENSION, XLSX_EXTENSION, XLSM_EXTENSION)


def test_no_non_record_design_source_points_at_a_binary_design_under_disenos_registro() -> None:
    """A ``form_spec`` (or other) kind may not point at a real AEAT design binary.

    Deliberately extension-scoped, not path-scoped: a bare "non-record_design
    under disenos_registro/" rule would ALSO flag the 12 ``dictionary`` and 6
    ``xsd`` companion files Modelo 100 correctly declares under its own kind --
    those are a real, distinct evidence type living beside the design, not a
    misclassified design. The binary-extension discriminator is what keeps this
    check anchored on the PROPERTY (this file IS a design workbook by its own
    extension) rather than a hand-list of which paths are exempt today, which
    would go stale silently after the next rename or reclassification.

    KNOWN BLIND SPOT, found and confirmed by inspection while building this
    check, not by this check itself: Modelo 123 declares two ``form_spec``
    sources whose ``corpus_path`` ends in ``.txt``
    (``aeat-dr-123-2024-v20-form-text``, ``aeat-dr-123-2019-2023-v13-form-text``).
    Reading the bundled files confirms they are row-by-row plain-text
    TRANSCRIPTIONS of the exact same posición/longitud/tipo/descripción Diseño
    de Registro content a bundled binary would carry -- genuine record-design
    evidence, not a landing page or procedure note -- but their ``source_url``
    already names the real ``.xls`` AEAT publishes. A binary-extension
    discriminator cannot see this: ``.txt`` is not a design extension, and the
    schema's own ``record_design`` kind validator would refuse a ``.txt``
    corpus_path if this were reclassified as-is (only .pdf/.xls/.xlsx/.xlsm are
    accepted). Closing this specific gap means re-bundling the real ``.xls``
    binary AEAT already publishes at the recorded ``source_url``, not widening
    the schema to accept a derived transcription -- the same "never ground on a
    derived artefact" posture this registry already takes for
    ``.html.extracted.md`` normatives citations. Reported here rather than
    silently passed: this test's own binary-extension scope cannot catch it,
    so it must not be allowed to look covered.
    """
    catalogues = _catalogues()
    offending: list[str] = []
    for source in catalogues.sources.values():
        if source.kind == "record_design":
            continue
        path = Path(source.corpus_path)
        if "disenos_registro" not in path.parts:
            continue
        suffix = source.corpus_path.rsplit(".", 1)
        extension = "." + suffix[1].lower() if len(suffix) == 2 else ""
        if extension in _BINARY_RECORD_DESIGN_EXTENSIONS:
            offending.append(
                f"{source.id!r} declares kind={source.kind!r} but its corpus_path "
                f"{source.corpus_path!r} is a {extension} binary under disenos_registro/ -- "
                "reclassify as kind='record_design' with a record_design_epoch, or confirm "
                "by content that it is genuinely NOT the AEAT design (e.g. a companion "
                "dictionary/xsd correctly modelled under its own kind, which never carries "
                "a design-binary extension)",
            )

    assert offending == [], (
        "non-record_design source(s) point at what their own extension declares is a "
        "binary AEAT design under disenos_registro/ -- the same misclassification tier5's "
        "M210/M280/M345 sweep found and corrected, reported here as a set so a NEW instance "
        "is caught rather than silently joining a stale allowlist:\n  " + "\n  ".join(sorted(offending))
    )


def _record_design_modelo(corpus_path: str) -> str | None:
    """Return the modelo a design's bundled corpus path sits under."""
    parts = Path(corpus_path).parts
    for part in parts:
        if part.startswith("modelo_"):
            return part.removeprefix("modelo_")
    return None


def test_every_record_design_source_declares_a_unique_well_formed_epoch() -> None:
    """A design binary no generator can select is an invisible under-declaration.

    ``resolve_record_design_binary`` refuses a ``record_design`` source that
    declares no ``record_design_epoch``, so the omission is not benign: it makes
    the bundled, hash-pinned, reviewed binary unreachable by the export-fragment
    generator. Nothing surfaced that until a generator was pointed at the modelo,
    which for an unauthored export layout is never -- so the sibling
    misclassification check above could demand "reclassify as kind='record_design'
    with a record_design_epoch" while 60 of the catalogue's 121 design sources
    carried no epoch at all.

    Epochs are also asserted UNIQUE per modelo, because the epoch is the key the
    generator's semantic-map and render-profile trees are addressed by
    (the authored registry mapping tree). Two designs for one modelo
    sharing an epoch cannot both be mapped, and AEAT does re-lay a form out
    mid-ejercicio -- which is exactly what the grammar's optional sub-year label
    ("2024-early", "2024-late") exists to distinguish.

    The pending set below is deliberately reason-bearing and fails when stale: an
    entry that acquires an epoch, or disappears, must leave this map rather than
    sit here looking cleared.
    """
    pending: dict[str, str] = {
        # Two same-ejercicio re-layout PAIRS. A bare year would collide, so each
        # pair needs the sub-year label ruling (which half is early/late, on
        # AEAT's own edition boundary) from the campaign that owns the M303
        # epoch vocabulary -- the same ruling that produced 2024-early/2024-late.
        "aeat-dr-303-2018": "same-ejercicio pair with aeat-dr-303-2018-salvo-ultimo-periodo",
        "aeat-dr-303-2018-salvo-ultimo-periodo": "same-ejercicio pair with aeat-dr-303-2018",
        "aeat-dr-303-2021-hasta-periodo-06": "same-ejercicio pair with aeat-dr-303-2021-desde-periodo-07",
        "aeat-dr-303-2021-desde-periodo-07": "same-ejercicio pair with aeat-dr-303-2021-hasta-periodo-06",
        # Mechanically derivable, but these sit in trees another campaign holds
        # open (the M303/M390 generator-authority work and the designless-modelo
        # adjudication). Declared here rather than swept, so the omission stays
        # visible and attributed instead of racing a peer's edit.
        "aeat-dr-303-2014": "held by the in-flight M303 generator-authority campaign",
        "aeat-dr-303-2015-2016": "held by the in-flight M303 generator-authority campaign",
        "aeat-dr-303-2017": "held by the in-flight M303 generator-authority campaign",
        "aeat-dr-303-2019-2020": "held by the in-flight M303 generator-authority campaign",
        "aeat-dr-390-2015": "held by the in-flight M390 generator-authority campaign",
        "aeat-dr-390-2016": "held by the in-flight M390 generator-authority campaign",
        # Every official manifest artefact is registered so the corpus and
        # catalogue agree, but this map does not invent selection windows. These source
        # titles describe versions/updates (or an ATF translation), not a
        # non-conflicting filing period relative to the actively selected
        # design. The source rows deliberately remain resolver-unreachable
        # until the temporal-design owner supplies that authority.
        "aeat-dr-036-v40": "AEAT's 2023 update to the 2021-y-siguientes design has no selection boundary",
        "aeat-dr-036-v35": "AEAT's 2021 update has no selection boundary against v40",
        "aeat-dr-202-2025-mar-update": "AEAT's March 2026 update has no selection boundary against the active 2025 design",
        "aeat-dr-202-2019-september-update": "AEAT's September 2019 update has no selection boundary against the active 2019 design",
        "aeat-dr-202-2012-v32": "the official version label does not establish a filing-period window",
        "aeat-dr-202-2013-v33": "the official version label does not establish the boundary before the 3P 2013 design",
        "aeat-dr-202-2010-v13": "the official version label does not establish a filing-period window",
        "aeat-dr-345-2023-archive": "the archive's 2023 design conflicts with the selected 2023 edition absent an effective boundary",
        "aeat-dr-349-2002": "the historical order title does not establish a bounded filing window",
        "aeat-dr-604-atf-spanish": "the Spanish ATF appendix is a translated logical design, not an independently dated epoch",
        "aeat-dr-604-atf-english": "the English ATF appendix is a translated logical design, not an independently dated epoch",
        # The modelo 184 ejercicio-2023 pair. Its revision cites BOTH the AEAT
        # diseno de registro and the BOE publication of the orden that
        # established it, so a bare "2023" would collide with the epoch
        # aeat-dr-184-2023-2024 already holds. Which of the two is the
        # selectable LAYOUT and which is merely the establishing instrument is
        # the temporal-design owner's ruling, not a sub-year label: they are the
        # same layout, not an AEAT mid-ejercicio re-lay.
        "boe-dr-184-2023-2024": "same-ejercicio pair with aeat-dr-184-2023-2024, which already holds epoch 2023",
        # The four older raw BOE ordenes for modelo 184. These carry NO epoch by
        # adjudication, not by omission: test_modelo_184_registry's
        # raw-BOE-design-eras regression asserts `record_design_epoch is None`
        # for exactly these four, on the ruling that a raw BOE design is
        # provenance and not a surrogate for a later AEAT map. Its parser
        # refusal is deliberate and load-bearing. Declaring an epoch here to
        # satisfy this gate contradicts that contract -- which is precisely what
        # happened before this entry existed.
        "boe-dr-184-2015": "raw BOE orden, adjudicated provenance rather than a mapped design",
        "boe-dr-184-2016-2018": "raw BOE orden, adjudicated provenance rather than a mapped design",
        "boe-dr-184-2019-2021": "raw BOE orden, adjudicated provenance rather than a mapped design",
        "boe-dr-184-2022": "raw BOE orden, adjudicated provenance rather than a mapped design",
        # Historical modelo 353 ordenes, registered so corpus and catalogue
        # agree. Neither declares applies_from/applies_to, and no modelo 353
        # revision cites either -- the modelo's revisions begin at 2021. There is
        # therefore no filing period to derive an epoch from, and inventing one
        # would assert a selection window nothing evidences.
        "aeat-dr-353-2007-orden": "the historical orden declares no filing window and no revision cites it",
        "aeat-dr-353-2008-orden": "the historical orden declares no filing window and no revision cites it",
    }

    modelos, catalogues = _registry_tree()
    designs = [source for source in catalogues.sources.values() if source.kind == "record_design"]
    assert designs, "the catalogue must declare record-design sources for this gate to mean anything"

    cited = {source_ref for modelo in modelos for source_ref in modelo.source_refs}
    cited |= {
        source_ref
        for modelo in modelos
        for revision in modelo.revisions.values()
        for source_ref in revision.source_refs
    }

    undeclared = {source.id for source in designs if source.record_design_epoch is None}

    malformed = sorted(
        f"{source.id!r} declares epoch {source.record_design_epoch!r}"
        for source in designs
        if source.record_design_epoch is not None and not RECORD_DESIGN_EPOCH_RE.fullmatch(source.record_design_epoch)
    )
    assert malformed == [], (
        "record-design epoch(s) do not match the shared epoch grammar (a four-digit ejercicio "
        "with an optional lower-case sub-year label):\n  " + "\n  ".join(malformed)
    )

    stale = sorted(source_id for source_id in pending if source_id not in undeclared)
    assert stale == [], (
        "pending record-design epoch entr(ies) are stale -- the source now declares an epoch, or no "
        "longer exists. Remove them from the pending map:\n  " + "\n  ".join(stale)
    )
    newly_undeclared = sorted(undeclared - set(pending))
    assert newly_undeclared == [], (
        "record-design source(s) declare no record_design_epoch, so resolve_record_design_binary "
        "refuses them and no export-fragment generator can reach their bundled binary. Declare the "
        "ejercicio the design governs:\n  " + "\n  ".join(newly_undeclared)
    )

    by_modelo_epoch: dict[tuple[str, str], list[str]] = {}
    for source in designs:
        if source.record_design_epoch is None:
            continue
        modelo = _record_design_modelo(source.corpus_path)
        if modelo is None:
            continue
        by_modelo_epoch.setdefault((modelo, source.record_design_epoch), []).append(source.id)
    collisions = sorted(
        f"modelo {modelo} epoch {epoch!r}: {', '.join(sorted(source_ids))}"
        for (modelo, epoch), source_ids in by_modelo_epoch.items()
        if len(source_ids) > 1
    )
    assert collisions == [], (
        "two record-design sources for one modelo share an epoch, so they address the same "
        "generator mapping directory and cannot both be authored. Distinguish them with the "
        "grammar's sub-year label:\n  " + "\n  ".join(collisions)
    )


def test_modelo_202_active_record_design_is_latest_manifested_revision() -> None:
    catalogues = _catalogues()
    source = catalogues.sources["aeat-dr-202-2025"]
    manifest_path = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_202", "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidates = [
        artefact
        for artefact in manifest["artefacts"]
        if artefact["original_filename"] == "DR202e25.xlsx" and "2025 y siguientes" in artefact["title"]
    ]
    latest = max(candidates, key=lambda artefact: artefact["retrieved_at"])

    assert source.corpus_path.endswith(latest["stored_path"])
    assert source.sha256 == latest["sha256"]
    assert source.bytes == latest["bytes"]
    assert source.source_url == latest["url"]


def test_modelo_100_record_design_sources_match_manifest() -> None:
    catalogues = _catalogues()
    manifest_path = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_100", "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources_by_path = {source.corpus_path: source for source in catalogues.sources.values()}
    checked: list[str] = []

    for artefact in manifest["artefacts"]:
        title = artefact["title"]
        if not (
            "Diccionario declaración individual" in title
            or "Diccionario declaración individual (toma de datos)" in title
            or "Esquema XSD Ejercicio" in title
        ):
            continue
        corpus_path = f"corpus/aeat_official/disenos_registro/modelo_100/{artefact['stored_path']}"
        source = sources_by_path.get(corpus_path)

        assert source is not None, f"Modelo 100 corpus artefact has no registry source: {corpus_path}"
        assert source.sha256 == artefact["sha256"]
        assert source.bytes == artefact["bytes"]
        assert source.source_url == artefact["url"]
        assert source.evidence_tier == "layout_authority"
        assert source.kind in {"dictionary", "xsd"}
        verify_source_file(REPO_ROOT, source)
        checked.append(source.id)

    assert len(checked) == 18


def _source_path(corpus_path: str) -> Path:
    return bundled_path(*corpus_path.split("/"))


def _record_design_label(corpus_path: str, casilla_id: str) -> str:
    marker = f"[{casilla_id}]"
    for line in _source_path(corpus_path).read_text(encoding="cp1252").splitlines():
        if marker not in line:
            continue
        label = line.split(marker, 1)[1].strip()
        assert label.startswith("[") and label.endswith("]"), line
        return label[1:-1]
    raise AssertionError(f"source {corpus_path} has no label for casilla {casilla_id}")


def _manual_extracted_text(corpus_path: str) -> str:
    extracted_path = Path(f"{_source_path(corpus_path)}.extracted.json")
    raw_payload = json.loads(extracted_path.read_text(encoding="utf-8"))
    assert isinstance(raw_payload, dict)
    raw_units = raw_payload.get("units")
    assert isinstance(raw_units, list)
    texts: list[str] = []
    for raw_unit in raw_units:
        assert isinstance(raw_unit, dict)
        text = raw_unit.get("text")
        assert isinstance(text, str)
        texts.append(text)
    return "\n".join(texts)


def test_modelo_100_2021_deportistas_0489_is_grounded_in_dictionary_and_manual() -> None:
    modelos, catalogues = _registry_tree()
    modelo = next(modelo for modelo in modelos if modelo.id == "100")
    revision = modelo.revisions["2021"]
    casilla = next(casilla for casilla in revision.casillas if casilla.id == "0489")
    dictionary = catalogues.sources["aeat-dr-100-2021-dictionary"]
    manual = catalogues.sources["aeat-renta-2021-manual-parte1"]

    assert dictionary.evidence_tier == "layout_authority"
    assert manual.evidence_tier == "official_source_guidance"
    assert casilla.label == _record_design_label(dictionary.corpus_path, "0489")
    assert "aeat-renta-2021-manual-parte1" in casilla.source_refs
    assert casilla.semantic_role == "irpf_red_deportistas_aportaciones_contribuciones"

    manual_text = " ".join(_manual_extracted_text(manual.corpus_path).split())
    assert "casillas [0488] y [0489]" in manual_text
    assert "aportaciones y contribuciones realizadas en 2021" in manual_text


def test_modelo_100_2021_forestal_0302_prefers_manual_year_over_dictionary_drift() -> None:
    modelos, catalogues = _registry_tree()
    modelo = next(modelo for modelo in modelos if modelo.id == "100")
    revision = modelo.revisions["2021"]
    casilla = next(casilla for casilla in revision.casillas if casilla.id == "0302")
    dictionary = catalogues.sources["aeat-dr-100-2021-dictionary"]
    manual = catalogues.sources["aeat-renta-2021-manual-parte1"]

    expected_label = (
        "Ganancias patrimoniales obtenidas por los vecinos en 2021 como consecuencia de "
        "aprovechamientos forestales en montes públicos"
    )

    assert _record_design_label(dictionary.corpus_path, "0302") == expected_label.replace("2021", "2020")
    assert casilla.label == expected_label
    assert "aeat-renta-2021-manual-parte1" in casilla.source_refs

    manual_text = " ".join(_manual_extracted_text(manual.corpus_path).split())
    assert expected_label in manual_text
    assert "Esta ganancia patrimonial ha estado sujeta en 2021 a la retención del 19 por 100" in manual_text


def test_renta_manual_sources_match_manifest() -> None:
    catalogues = _catalogues()
    sources_by_path = {source.corpus_path: source for source in catalogues.sources.values()}
    renta_root = bundled_path("corpus", "manuals", "renta")
    manifest_paths = sorted(
        renta_root.glob("*/*/manifest.json"),
        key=lambda path: path.relative_to(renta_root).as_posix(),
    )
    checked: list[str] = []

    assert manifest_paths
    for manifest_path in manifest_paths:
        root = manifest_path.parent
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        pdf_path = root / manifest["relative_pdf_path"]
        # corpus_path on registry sources is bundled-corpus-relative
        # (i.e. begins with ``corpus/...``), so relativise against the
        # bundle root rather than REPO_ROOT.
        corpus_path = pdf_path.relative_to(bundled_path()).as_posix()
        source = sources_by_path.get(corpus_path)

        assert manifest["synthetic"] is False, f"Renta manual manifest must cite a real PDF: {manifest_path}"
        assert pdf_path.is_file(), f"Renta manual manifest points at a missing PDF: {pdf_path}"
        assert source is not None, f"Renta manual corpus artefact has no registry source: {corpus_path}"
        assert source.sha256 == manifest["sha256"]
        assert source.bytes == manifest["content_length"]
        assert source.source_url == manifest["source_pdf_url"]
        assert source.evidence_tier == "official_source_guidance"
        assert source.kind == "manual_pdf"
        verify_source_file(REPO_ROOT, source)
        checked.append(source.id)

    assert checked == [
        "aeat-renta-2020-manual-parte1",
        "aeat-renta-2021-manual-parte1",
        "aeat-renta-2022-manual-parte1",
        "aeat-renta-2023-manual-parte1",
        "aeat-renta-2024-manual-parte1",
        "aeat-renta-2024-manual-deducciones-autonomicas",
        "aeat-renta-2025-manual-parte1",
        "aeat-renta-2025-manual-deducciones-autonomicas",
    ]


def test_renta_economic_activity_legal_basis_links_to_corpus() -> None:
    catalogues = _catalogues()

    assert {
        "ley-35-2006:art-27",
        "ley-35-2006:art-28",
        "ley-35-2006:art-30",
        "ley-35-2006:art-31",
        "ley-35-2006:art-32",
    }.issubset(catalogues.legal)
    verify_legal_catalogue_grounding(catalogues.legal, source_root=bundled_path())


def _assert_lirpf_reference_links_to_full_boe_corpus(
    ref_id: str,
    effective_from: date,
    required_text: tuple[str, ...],
):
    catalogues = _catalogues()
    reference = catalogues.legal[ref_id]
    article = ref_id.rsplit("-", 1)[-1]

    assert reference.corpus_ref == f"corpus/normatives/html/ley-35-2006.html#a{article}", ref_id
    assert reference.effective_from == effective_from, ref_id
    assert reference.required_text == required_text, ref_id
    verify_legal_catalogue_grounding({reference.id: reference}, source_root=bundled_path())
    return reference


def test_lirpf_work_and_capital_income_foundations_link_to_full_boe_corpus() -> None:
    cases = (
        (
            "ley-35-2006:art-17",
            date(2020, 2, 6),
            (
                "Rendimientos íntegros del trabajo.",
                "contraprestaciones o utilidades",
                "trabajo personal o de la relación laboral o estatutaria",
                "Las pensiones y haberes pasivos percibidos",
                "se calificarán como rendimientos de actividades económicas",
            ),
        ),
        (
            "ley-35-2006:art-18",
            date(2015, 1, 1),
            (
                "Porcentajes de reducción aplicables a determinados rendimientos del trabajo.",
                "El 30 por ciento de reducción",
                "período de generación superior a dos años",
                "300.000 euros anuales",
            ),
        ),
        (
            "ley-35-2006:art-19",
            date(2015, 1, 1),
            (
                "Rendimiento neto del trabajo.",
                "disminuir el rendimiento íntegro en el importe de los gastos deducibles",
                "cotizaciones a la Seguridad Social",
                "gastos de defensa jurídica",
                "2.000 euros anuales",
            ),
        ),
        (
            "ley-35-2006:art-20",
            date(2024, 1, 1),
            (
                "Reducción por obtención de rendimientos del trabajo.",
                "rendimientos netos del trabajo inferiores a 19.747,5 euros",
                "no tengan rentas, excluidas las exentas, distintas de las del trabajo superiores a 6.500 euros",
                "iguales o inferiores a 14.852 euros: 7.302 euros anuales",
                "multiplicar por 1,75 la diferencia",
                "multiplicar por 1,14 la diferencia",
                "el saldo resultante no podrá ser negativo",
            ),
        ),
        (
            "ley-35-2006:art-22",
            date(2007, 1, 1),
            (
                "Rendimientos íntegros del capital inmobiliario.",
                "bienes inmuebles rústicos y urbanos",
                "se deriven del arrendamiento",
                "importe que por todos los conceptos deba satisfacer",
            ),
        ),
        (
            "ley-35-2006:art-23",
            date(2024, 1, 1),
            (
                "Gastos deducibles y reducciones.",
                "gastos necesarios para la obtención de los rendimientos",
                "el 3 por ciento sobre el mayor",
                "el coste de adquisición satisfecho o el valor catastral",
                "En un 90 por ciento",
                "En un 70 por ciento",
                "En un 60 por ciento",
                "En un 50 por ciento",
            ),
        ),
        (
            "ley-35-2006:art-24",
            date(2007, 1, 1),
            (
                "Rendimiento en caso de parentesco.",
                "sea el cónyuge o un pariente",
                "hasta el tercer grado inclusive",
                "no podrá ser inferior al que resulte de las reglas del artículo 85",
            ),
        ),
        (
            "ley-35-2006:art-25",
            date(2015, 1, 1),
            (
                "Rendimientos íntegros del capital mobiliario.",
                "Rendimientos obtenidos por la participación en los fondos propios",
                "Los dividendos",
                "Rendimientos obtenidos por la cesión a terceros de capitales propios",
                "intereses y cualquier otra forma de retribución",
                "Otros rendimientos del capital mobiliario",
            ),
        ),
        (
            "ley-35-2006:art-26",
            date(2015, 1, 1),
            (
                "Gastos deducibles y reducciones.",
                "gastos de administración y depósito de valores negociables",
                "arrendamiento de bienes muebles, negocios o minas",
                "se reducirán en un 30 por ciento",
                "300.000 euros anuales",
            ),
        ),
    )
    for ref_id, effective_from, required_text in cases:
        reference = _assert_lirpf_reference_links_to_full_boe_corpus(ref_id, effective_from, required_text)
        if ref_id == "ley-35-2006:art-20":
            assert reference.notes is not None
            assert "effects from 2024-01-01" in reference.notes


def test_lirpf_economic_activity_chapter_links_to_full_boe_corpus() -> None:
    cases = (
        (
            "ley-35-2006:art-27",
            date(2015, 1, 1),
            (
                "Rendimientos íntegros de actividades económicas",
                "ordenación por cuenta propia de medios de producción",
                "arrendamiento de inmuebles se realiza como actividad económica",
            ),
        ),
        (
            "ley-35-2006:art-28",
            date(2007, 1, 1),
            (
                "Reglas generales de cálculo del rendimiento neto",
                "rendimiento neto de las actividades económicas",
                "según las normas del Impuesto sobre Sociedades",
                "ganancias o pérdidas patrimoniales derivadas de los elementos patrimoniales afectos",
            ),
        ),
        (
            "ley-35-2006:art-30",
            date(2018, 1, 1),
            (
                "Normas para la determinación del rendimiento neto en estimación directa",
                "método de estimación directa",
                "normal y la simplificada",
                "gastos de difícil justificación",
            ),
        ),
        (
            "ley-35-2006:art-31",
            date(2016, 1, 1),
            (
                "Normas para la determinación del rendimiento neto en estimación objetiva",
                "método de estimación objetiva",
                "salvo que renuncien a su aplicación",
                "signos, índices o módulos",
            ),
        ),
        (
            "ley-35-2006:art-32",
            date(2023, 1, 1),
            (
                "Reducciones.",
                "rendimientos netos con un período de generación superior a dos años",
                "el saldo resultante no podrá ser negativo",
                "inicien el ejercicio de una actividad económica",
                "no podrá superar el importe de 300.000 euros anuales",
            ),
        ),
    )
    for ref_id, effective_from, required_text in cases:
        _assert_lirpf_reference_links_to_full_boe_corpus(ref_id, effective_from, required_text)


def test_lirpf_capital_gains_foundation_links_to_full_boe_corpus() -> None:
    cases = (
        (
            "ley-35-2006:art-33",
            date(2015, 1, 1),
            (
                "Concepto.",
                "Son ganancias y pérdidas patrimoniales",
                "variaciones en el valor del patrimonio",
                "alteración en la composición",
                # Art. 33.5.f: a loss is not computable where homogeneous
                # securities were acquired inside the two-month window. It is
                # part of the same article and belongs in its anchor proof, so
                # the pin tracks the entry rather than the entry being trimmed
                # back to match a stale pin.
                "hubiera adquirido valores homogéneos dentro de los dos meses anteriores o posteriores",
            ),
        ),
        (
            "ley-35-2006:art-34",
            date(2007, 1, 1),
            (
                "Importe de las ganancias o pérdidas patrimoniales. Norma general",
                "diferencia entre los valores de adquisición y transmisión",
                "valor de mercado de los elementos patrimoniales",
                "mejoras en los elementos patrimoniales transmitidos",
            ),
        ),
        (
            "ley-35-2006:art-37",
            date(2015, 1, 1),
            (
                "Normas específicas de valoración",
                # LIRPF art. 37.1.a is "valores admitidos a negociación". The
                # "acciones" phrasing belongs to the Manual Práctico's worked
                # examples, not to the statute this reference cites.
                "valores admitidos a negociación",
                "valores no admitidos a negociación",
                "instituciones de inversión colectiva",
            ),
        ),
    )
    for ref_id, effective_from, required_text in cases:
        _assert_lirpf_reference_links_to_full_boe_corpus(ref_id, effective_from, required_text)


def test_lirpf_state_quota_chain_links_to_full_boe_corpus() -> None:
    cases = (
        (
            "ley-35-2006:art-62",
            date(2007, 1, 1),
            (
                "Cuota íntegra estatal.",
                "La cuota íntegra estatal será la suma",
                "artículos 63 y 66",
                "bases liquidables general y del ahorro",
            ),
        ),
        (
            "ley-35-2006:art-63",
            date(2021, 1, 1),
            (
                "Escala general del Impuesto.",
                "base liquidable general que exceda del importe del mínimo personal y familiar",
                "A la base liquidable general se le aplicarán los tipos",
                "se minorará en el importe derivado de aplicar",
                "tipo medio de gravamen general estatal",
            ),
        ),
        (
            "ley-35-2006:art-66",
            date(2024, 12, 22),
            (
                "Tipos de gravamen del ahorro.",
                "base liquidable del ahorro que exceda",
                "A la base liquidable del ahorro se le aplicarán los tipos",
                "se minorará en el importe derivado de aplicar",
                "contribuyentes que tuviesen su residencia habitual en el extranjero",
            ),
        ),
        (
            "ley-35-2006:art-67",
            date(2015, 1, 1),
            (
                "Cuota líquida estatal.",
                "La cuota líquida estatal del Impuesto será el resultado de disminuir la cuota íntegra estatal",
                "deducción por inversión en empresas de nueva o reciente creación",
                "50 por ciento del importe total de las deducciones",
                "no podrá ser negativo",
            ),
        ),
    )
    for ref_id, effective_from, required_text in cases:
        _assert_lirpf_reference_links_to_full_boe_corpus(ref_id, effective_from, required_text)


def test_lirpf_autonomic_quota_chain_links_to_full_boe_corpus() -> None:
    cases = (
        (
            "ley-35-2006:art-73",
            date(2007, 1, 1),
            (
                "Cuota íntegra autonómica.",
                "La cuota íntegra autonómica del Impuesto será la suma",
                "artículos 74 y 76",
                "base liquidable general y del ahorro",
            ),
        ),
        (
            "ley-35-2006:art-74",
            date(2011, 1, 12),
            (
                "Escala autonómica del Impuesto.",
                "base liquidable general que exceda del importe del mínimo personal y familiar",
                "escala autonómica del Impuesto",
                "aprobadas por la Comunidad Autónoma",
                "tipo medio de gravamen general autonómico",
            ),
        ),
        (
            "ley-35-2006:art-75",
            date(2025, 4, 3),
            (
                "Especialidades aplicables en los supuestos de anualidades por alimentos a favor de los hijos.",
                "satisfagan las anualidades por alimentos a sus hijos",
                "aplicarán la escala prevista",
                "mínimo personal y familiar",
                "incrementado en 1.980 euros anuales",
                "sin que pueda resultar negativa",
            ),
        ),
        (
            "ley-35-2006:art-76",
            date(2024, 12, 22),
            (
                "Tipo de gravamen del ahorro.",
                "base liquidable del ahorro que exceda",
                "A la base liquidable del ahorro se le aplicarán los tipos",
                "se minorará en el importe derivado de aplicar",
            ),
        ),
        (
            "ley-35-2006:art-77",
            date(2015, 1, 1),
            (
                "Cuota líquida autonómica.",
                "La cuota líquida autonómica será el resultado de disminuir",
                "50 por ciento del importe total de las deducciones",
                "deducciones establecidas por la Comunidad Autónoma",
                "no podrá ser negativo",
            ),
        ),
    )
    for ref_id, effective_from, required_text in cases:
        reference = _assert_lirpf_reference_links_to_full_boe_corpus(ref_id, effective_from, required_text)
        if ref_id == "ley-35-2006:art-75":
            assert reference.notes is not None
            assert "not the generic autonomic quota article" in reference.notes


def test_lirpf_minimum_and_broad_deduction_foundations_link_to_full_boe_corpus() -> None:
    cases = (
        (
            "ley-35-2006:art-56",
            date(2010, 1, 1),
            (
                "Mínimo personal y familiar.",
                "constituye la parte de la base liquidable",
                "necesidades básicas personales y familiares",
                "Cuando no exista base liquidable general",
                "artículos 57, 58, 59 y 60",
                "gravamen autonómico",
            ),
        ),
        (
            "ley-35-2006:art-68",
            date(2023, 1, 1),
            (
                "Deducciones.",
                "Deducción por inversión en empresas de nueva o reciente creación",
                "50 por ciento de las cantidades satisfechas",
                "La base máxima de deducción será de 100.000 euros anuales",
                "Deducciones en actividades económicas",
                "Deducciones por donativos y otras aportaciones",
                "Deducción por rentas obtenidas en Ceuta o Melilla",
                "actuaciones para la protección y difusión del Patrimonio Histórico Español",
            ),
        ),
    )
    for ref_id, effective_from, required_text in cases:
        _assert_lirpf_reference_links_to_full_boe_corpus(ref_id, effective_from, required_text)


def test_lirpf_family_joint_and_attribution_foundations_link_to_full_boe_corpus() -> None:
    cases = (
        (
            "ley-35-2006:art-82",
            date(2007, 1, 1),
            (
                "Tributación conjunta.",
                "modalidades de unidad familiar",
                "cónyuges no separados legalmente",
                "Los hijos menores",
                "Nadie podrá formar parte de dos unidades familiares",
                "31 de diciembre de cada año",
            ),
        ),
        (
            "ley-35-2006:art-83",
            date(2007, 1, 1),
            (
                "Opción por la tributación conjunta.",
                "podrán optar, en cualquier período impositivo",
                "no vinculará para períodos sucesivos",
                "deberá abarcar a la totalidad de los miembros",
                "Si uno de ellos presenta declaración individual",
            ),
        ),
        (
            "ley-35-2006:art-84",
            date(2010, 1, 1),
            (
                "Normas aplicables en la tributación conjunta.",
                "idéntica cuantía en la tributación conjunta",
                "se reducirá en 3.400 euros anuales",
                "se reducirá en 2.150 euros anuales",
                "No se aplicará esta reducción cuando el contribuyente conviva",
            ),
        ),
        (
            "ley-35-2006:art-86",
            date(2007, 1, 1),
            (
                "Régimen de atribución de rentas.",
                "se atribuirán a los socios, herederos, comuneros o partícipes",
                "sección 2.ª",
            ),
        ),
        (
            "ley-35-2006:art-87",
            date(2022, 10, 20),
            (
                "Entidades en régimen de atribución de rentas.",
                "artículo 8.3 de esta Ley",
                "entidades constituidas en el extranjero",
                "no estarán sujetas al Impuesto sobre Sociedades",
                "apartado 12 del artículo 15 bis",
            ),
        ),
        (
            "ley-35-2006:art-88",
            date(2007, 1, 1),
            (
                "Calificación de la renta atribuida.",
                "tendrán la naturaleza derivada de la actividad o fuente",
                "para cada uno de ellos",
            ),
        ),
        (
            "ley-35-2006:art-89",
            date(2007, 1, 1),
            (
                "Cálculo de la renta atribuible y pagos a cuenta.",
                "Para el cálculo de las rentas a atribuir",
                "se determinarán con arreglo a las normas de este Impuesto",
                "no serán aplicables las reducciones previstas en los artículos 23.2, 23.3, 26.2 y 32",
                "estarán sujetas a retención o ingreso a cuenta",
                "se atribuirán por partes iguales",
                "podrán practicar en su declaración las reducciones previstas",
            ),
        ),
    )
    for ref_id, effective_from, required_text in cases:
        reference = _assert_lirpf_reference_links_to_full_boe_corpus(ref_id, effective_from, required_text)
        if ref_id == "ley-35-2006:art-84":
            assert reference.notes is not None
            assert "in force from 2010-01-01" in reference.notes
        if ref_id == "ley-35-2006:art-87":
            assert reference.notes is not None
            assert "in force from 2022-10-20" in reference.notes
