"""Behavioral publication guarantees for the development authority publisher."""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    read_authority_artifact,
    write_authority_artifact,
)
from cadrumo.domain.calculations.registry.errors import RegistryError, RegistryValidationError
from cadrumo.domain.calculations.registry.runtime_catalogues import (
    ApoderamientoScopeRecord,
    CountryVocabularyRecord,
    PublishedIvaPlaceOfSupplyRule,
    PublishedIvaRegulation,
    PublishedRecargoBand,
    RuntimeRegistryCatalogues,
    SpanishPostalTerritory,
    TerritoryCarveOut,
)

from ..compiler import fact_providers
from ..conformance.loader_directory_mode_support import (
    write_extracted_corpus_sidecar,
    write_fragmented_revision,
)
from ..pipeline.authority_publication import (
    AuthorityArtifactCurrencyStatus,
    authority_artifact_currency,
    publish_validated_authority_candidate,
    validate_authority_candidate,
)
from ..pipeline.cli import publish_authority_candidate_workflow
from ._referential_integrity_support import (
    minimal_catalogues,
    minimal_modelo,
    minimal_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CATALOGUE = (
    """\
[supported_filing_years]
floor = 2025
horizon = 2025

[sociedades_annual_manual_coverage]
"""
    + (
        'dispositions = [{ year = 2025, status = "unpublished", official_locator = "https://example.com/manuals", observed_at = 2026-09-10, acquisition_condition_key = "application.registry.manuals.coverage.recheck" }]\n'  # noqa: E501
    )
    + """

[legal."test-ley-001:art-1"]
evidence_tier = "legal_authority"
authority = "boe"
kind = "ley"
corpus_ref = "corpus/test/test-ley-001.html#a1"
document_id = "BOE-T-001"
article = "1"
permalink = "https://example.com/test"
effective_from = 2025-01-01
review_status = "pending_review"
required_text = ["test provision text"]

[sources."test-source-001"]
evidence_tier = "layout_authority"
authority = "aeat"
kind = "record_design"
corpus_path = "corpus/aeat_official/disenos_registro/modelo_999/files/test-source-001.pdf"
sha256 = "44f8354494a5ba03ba1792a8d3e9c534c47a9181980fde7a3f44b06ef2ae7c7f"
bytes = 1000
retrieved_at = 2025-01-01
source_url = "https://example.com/test-source"
review_status = "pending_review"

[sources."test-source-002"]
evidence_tier = "official_source_guidance"
authority = "aeat"
kind = "instructions"
corpus_path = "corpus/test/test-source-002.pdf"
sha256 = "44f8354494a5ba03ba1792a8d3e9c534c47a9181980fde7a3f44b06ef2ae7c7f"
bytes = 1000
retrieved_at = 2025-01-01
source_url = "https://example.com/test-source-002"
review_status = "pending_review"
"""
)

_RECORD_DESIGN_MANIFEST = """\
{
  "source": "Test AEAT record-design publisher",
  "retrieved_at": "2025-01-01",
  "artefacts": [
    {
      "stored_path": "files/test-source-001.pdf",
      "sha256": "44f8354494a5ba03ba1792a8d3e9c534c47a9181980fde7a3f44b06ef2ae7c7f",
      "bytes": 1000,
      "url": "https://example.com/test-source"
    }
  ]
}
"""

_MANIFEST = """\
[modelo]
id = "999"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]
"""

_REVISION = """\
[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
authority_grade = "applicability"
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]
orden_aplicabilidad = ["test-ley-001:art-1"]

[[revisions."2025".application_links]]
id = "test-filing-link"
surface = "filing"
consumer = "test"
requires_snapshot = true
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-002"]

[[revisions."2025".casillas]]
id = "01"
number = "01"
section = ["test"]
data_type = "integer"
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]

[[revisions."2025".workbook_parity_refs]]
id = "test-workbook-001"
workbook_source = "test-source-001"
fixture_id = "test-fixture-001"
formula_coverage = "record_design_layout"
runner_required = false
tolerance = "0.00"
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]
"""


def _previous_publication() -> AuthorityArtifact:
    """Return a complete typed authority representing an already published release."""
    legal_id = "ley-35-2006:art-1"
    runtime = RuntimeRegistryCatalogues(
        iva_regulations={
            "fixture-exempt": PublishedIvaRegulation(
                category="fixture-exempt",
                requires_reverse_charge=False,
                requires_supplier_iva_id=False,
                manual_references=(),
                citations=(),
                notes="No legal treatment is asserted.",
                legal_basis_exempt=True,
            )
        },
        iva_place_of_supply={
            "fixture-exempt": PublishedIvaPlaceOfSupplyRule(
                rule_id="fixture-exempt", notes="No placement is asserted.", legal_basis_exempt=True
            )
        },
        countries={"ES": CountryVocabularyRecord(code="ES", alpha3="ESP", names=("Espana",))},
        spanish_postal_territories={
            "28": SpanishPostalTerritory(
                postal_prefixes=("28",), scope="peninsula_baleares", name="Madrid", legal_refs=(legal_id,)
            )
        },
        territory_carve_outs={
            "ES": TerritoryCarveOut(code="ES", name="Espana", establishes_nothing=True, legal_refs=(legal_id,))
        },
        recargo_bands={
            "all": PublishedRecargoBand(
                id="all", min_completed_months=0, surcharge_pct=Decimal("1"), legal_ref=legal_id
            )
        },
        apoderamientos_version="fixture-v1",
        apoderamientos_scopes={
            "GENERAL": ApoderamientoScopeRecord(
                code="GENERAL", name_es="General", name_en="General", name_ca="General", name_hu="Altalanos"
            )
        },
    ).require_complete()
    return AuthorityArtifact(
        modelos=(minimal_modelo(minimal_revision()),),
        catalogues=minimal_catalogues().model_copy(update={"runtime": runtime}),
        identity_digest="e4c712d347701b34615314b6e3f8fdfd75ca5ee3eabe9c1c651668549fb7f66f",
    )


@pytest.fixture
def isolated_provider_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the test candidate's real compiler path independent of unrelated provider corpora."""
    monkeypatch.setattr(fact_providers, "FACT_PROVIDER_REGISTRATIONS", ())


def _stage_valid_candidate(root: Path) -> None:
    """Materialize a minimal but real compiler candidate, including its evidence."""
    registry_root = root / "registry" / "aeat"
    legal_dir = registry_root / "legal"
    revision_dir = registry_root / "modelos" / "999" / "revisions" / "2025"
    revision_dir.mkdir(parents=True)
    legal_dir.mkdir()
    corpus_dir = root / "corpus" / "test"
    corpus_dir.mkdir(parents=True)
    record_design_dir = root / "corpus" / "aeat_official" / "disenos_registro" / "modelo_999"
    (record_design_dir / "files").mkdir(parents=True)
    (record_design_dir / "files" / "test-source-001.pdf").write_bytes(b"x" * 1000)
    (record_design_dir / "manifest.json").write_text(_RECORD_DESIGN_MANIFEST, encoding="utf-8", newline="\n")
    (corpus_dir / "test-source-002.pdf").write_bytes(b"x" * 1000)
    legal_corpus = corpus_dir / "test-ley-001.html"
    legal_corpus.write_text("<html>test provision text</html>", encoding="utf-8")
    write_extracted_corpus_sidecar(legal_corpus, anchor="a1", text="test provision text")
    (legal_dir / "catalogue.toml").write_text(_CATALOGUE, encoding="utf-8")
    iva_dir = registry_root / "iva"
    iva_dir.mkdir()
    (iva_dir / "catalogues.toml").write_text(
        '[[regulations]]\ncategory = "fixture-exempt"\nrequires_reverse_charge = false\n'
        "requires_supplier_iva_id = false\nmanual_references = []\ncitations = []\n"
        'notes = "No legal treatment is asserted."\nlegal_basis_exempt = true\n',
        encoding="utf-8",
    )
    (iva_dir / "place_of_supply.toml").write_text(
        '[[place_of_supply_rules]]\nrule_id = "fixture-exempt"\nnotes = "No placement is asserted."\n'
        "legal_basis_exempt = true\n",
        encoding="utf-8",
    )
    (iva_dir / "country_names.toml").write_text(
        '[[country]]\ncode = "ES"\nalpha3 = "ESP"\nnames = ["Espana"]\n', encoding="utf-8"
    )
    (iva_dir / "territories.toml").write_text(
        '[[territory]]\npostal_prefixes = ["28"]\nscope = "peninsula_baleares"\nname = "Madrid"\n'
        'legal_refs = ["test-ley-001:art-1"]\n',
        encoding="utf-8",
    )
    (iva_dir / "territory_carve_outs.toml").write_text(
        '[[carve_out]]\ncode = "ES"\nname = "Espana"\nestablishes_nothing = true\n'
        'legal_refs = ["test-ley-001:art-1"]\n',
        encoding="utf-8",
    )
    (legal_dir / "ley-58-2003-recargo-bands.toml").write_text(
        '[[band]]\nid = "all"\nmin_completed_months = 0\nsurcharge_pct = "1"\nlegal_ref = "test-ley-001:art-1"\n',
        encoding="utf-8",
    )
    apoderamientos_dir = registry_root / "apoderamientos"
    apoderamientos_dir.mkdir()
    (apoderamientos_dir / "scopes.toml").write_text(
        'catalogue_version = "fixture-v1"\n[[scopes]]\ncode = "GENERAL"\nname_es = "General"\n'
        'name_en = "General"\nname_ca = "General"\nname_hu = "Altalanos"\nmodelo_codes = []\n',
        encoding="utf-8",
    )
    (registry_root / "modelos" / "999" / "manifest.toml").write_text(_MANIFEST, encoding="utf-8")
    write_fragmented_revision(revision_dir, _REVISION)


def test_staged_candidate_publishes_and_the_reader_consumes_it_as_current(
    tmp_path: Path, isolated_provider_registration: None
) -> None:
    """The pipeline workflow compiles a real candidate that the currency gate then accepts."""
    candidate_root = tmp_path / "candidate"
    _stage_valid_candidate(candidate_root)
    artifact_path = tmp_path / "published" / "authority.json"

    published = publish_authority_candidate_workflow(
        registry_root=candidate_root / "registry" / "aeat",
        source_root=candidate_root,
        artifact_path=artifact_path,
    )

    consumed = read_authority_artifact(artifact_path)
    currency = authority_artifact_currency(
        artifact_path,
        registry_root=candidate_root / "registry" / "aeat",
        source_root=candidate_root,
    )

    assert consumed == published
    assert consumed.modelos[0].id == "999"
    assert currency.status is AuthorityArtifactCurrencyStatus.CURRENT
    assert currency.recorded_identity_digest == published.identity_digest


def test_published_legal_evidence_answers_citation_queries_after_its_source_is_gone(
    tmp_path: Path, isolated_provider_registration: None
) -> None:
    """A published artifact carries the validated anchor needed by a runtime citation."""
    candidate_root = tmp_path / "candidate"
    _stage_valid_candidate(candidate_root)
    artifact_path = tmp_path / "published" / "authority.json"

    publish_authority_candidate_workflow(
        registry_root=candidate_root / "registry" / "aeat",
        source_root=candidate_root,
        artifact_path=artifact_path,
    )
    legal_source = candidate_root / "corpus" / "test" / "test-ley-001.html.extracted.json"
    legal_source.unlink()

    consumed = read_authority_artifact(artifact_path)

    assert consumed.evidence.quotation_is_grounded("test-ley-001:art-1", "test provision text")


def test_defective_candidate_refuses_before_replacing_the_previous_artifact(tmp_path: Path) -> None:
    """A real compiler refusal leaves the prior published artifact byte-for-byte intact."""
    artifact_path = tmp_path / "authority.json"
    write_authority_artifact(
        artifact_path,
        _previous_publication(),
    )
    previous_bytes = artifact_path.read_bytes()

    with pytest.raises(RegistryError):
        publish_authority_candidate_workflow(
            registry_root=tmp_path / "defective-registry",
            source_root=tmp_path / "defective-sources",
            artifact_path=artifact_path,
        )

    assert artifact_path.read_bytes() == previous_bytes


def test_provider_enrollment_requires_the_convenio_fact_before_publication(tmp_path: Path) -> None:
    """An enrolled provider set cannot silently publish without the treaty fact."""
    candidate_root = tmp_path / "candidate"
    _stage_valid_candidate(candidate_root)
    artifact_path = tmp_path / "authority.json"
    write_authority_artifact(artifact_path, _previous_publication())
    previous_bytes = artifact_path.read_bytes()

    with pytest.raises(RegistryValidationError, match=r"governed fact 'irnr\.convenio\.override' is not registered"):
        publish_authority_candidate_workflow(
            registry_root=candidate_root / "registry" / "aeat",
            source_root=candidate_root,
            artifact_path=artifact_path,
        )

    assert artifact_path.read_bytes() == previous_bytes


def test_divergent_record_design_manifest_identity_refuses_and_preserves_the_previous_artifact(
    tmp_path: Path, isolated_provider_registration: None
) -> None:
    """The publish workflow refuses a registry source that no longer binds its manifest artifact."""
    candidate_root = tmp_path / "candidate"
    _stage_valid_candidate(candidate_root)
    artifact_path = tmp_path / "authority.json"
    write_authority_artifact(
        artifact_path,
        _previous_publication(),
    )
    previous_bytes = artifact_path.read_bytes()
    manifest_path = candidate_root / "corpus" / "aeat_official" / "disenos_registro" / "modelo_999" / "manifest.json"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            "44f8354494a5ba03ba1792a8d3e9c534c47a9181980fde7a3f44b06ef2ae7c7f", "0" * 64
        ),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(RegistryError, match="does not exactly bind an official artifact catalog identity"):
        publish_authority_candidate_workflow(
            registry_root=candidate_root / "registry" / "aeat",
            source_root=candidate_root,
            artifact_path=artifact_path,
        )

    assert artifact_path.read_bytes() == previous_bytes


def test_equal_length_timestamp_restored_source_replacement_refuses_and_preserves_the_previous_artifact(
    tmp_path: Path, isolated_provider_registration: None
) -> None:
    """A content replacement cannot hide behind a matching evidence stat fingerprint."""
    candidate_root = tmp_path / "candidate"
    _stage_valid_candidate(candidate_root)
    artifact_path = tmp_path / "authority.json"
    write_authority_artifact(
        artifact_path,
        _previous_publication(),
    )
    previous_bytes = artifact_path.read_bytes()
    candidate = validate_authority_candidate(
        registry_root=candidate_root / "registry" / "aeat",
        source_root=candidate_root,
    )
    source = (
        candidate_root
        / "corpus"
        / "aeat_official"
        / "disenos_registro"
        / "modelo_999"
        / "files"
        / "test-source-001.pdf"
    )
    source_stat = source.stat()
    source.write_bytes(b"y" * source_stat.st_size)
    os.utime(source, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))

    with pytest.raises(RegistryValidationError):
        publish_validated_authority_candidate(
            candidate,
            artifact_path=artifact_path,
        )

    assert artifact_path.read_bytes() == previous_bytes


def test_candidate_change_after_validation_refuses_and_preserves_the_previous_artifact(
    tmp_path: Path, isolated_provider_registration: None
) -> None:
    """A registry edit cannot replace an artifact compiled from an earlier candidate receipt."""
    candidate_root = tmp_path / "candidate"
    _stage_valid_candidate(candidate_root)
    artifact_path = tmp_path / "authority.json"
    write_authority_artifact(
        artifact_path,
        _previous_publication(),
    )
    previous_bytes = artifact_path.read_bytes()
    candidate = validate_authority_candidate(
        registry_root=candidate_root / "registry" / "aeat",
        source_root=candidate_root,
    )
    revision = candidate_root / "registry" / "aeat" / "modelos" / "999" / "revisions" / "2025" / "revision.toml"
    revision.write_text(revision.read_text(encoding="utf-8") + "# publication race\n", encoding="utf-8")

    with pytest.raises(RegistryValidationError):
        publish_validated_authority_candidate(
            candidate,
            artifact_path=artifact_path,
        )

    assert artifact_path.read_bytes() == previous_bytes
