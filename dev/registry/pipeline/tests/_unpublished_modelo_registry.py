"""A minimal isolated registry holding one fictional, never-published Modelo 999 revision.

The tree is compiled through the real development compiler, so a generated-tree
lifecycle invocation can be driven against a revision that genuinely exists,
has no committed export tree and declares no storage inheritance. Nothing here
reads from or writes to the bundled registry except to copy the shared runtime
inputs every compilation requires.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.toml import freeze_toml, parse_toml, render_toml
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.schema import SupportedFilingYearsCatalogue

from ...compiler.authority import compile_validated_authority, compiled_bundled_authority
from ...conformance.loader_directory_mode_support import write_extracted_corpus_sidecar, write_fragmented_revision

UNPUBLISHED_MODELO: Final = "999"
UNPUBLISHED_REVISION: Final = "unpublished-fixture"
#: A record-design source the planted revision declares and the catalogue carries.
DECLARED_RECORD_DESIGN_SOURCE: Final = "test-source-001"

#: The official guidance the filing application link cites.
_GUIDANCE_SOURCE: Final = "test-source-002"
_LEGAL_REF: Final = "test-ley-001:art-1"
_CORPUS_SHA256: Final = "44f8354494a5ba03ba1792a8d3e9c534c47a9181980fde7a3f44b06ef2ae7c7f"


@dataclass(frozen=True, slots=True)
class UnpublishedModeloRegistry:
    """The isolated registry's roots and the authority compiled from them."""

    source_root: Path
    registry_root: Path
    authority: ValidatedRegistryAuthority
    filing_year: int


def _support_declaration() -> str:
    return bundled_path("registry", "aeat", "legal", "supported-filing-years.toml").read_text(encoding="utf-8")


def _supported_years() -> tuple[int, ...]:
    catalogue = SupportedFilingYearsCatalogue.model_validate(
        parse_toml(_support_declaration())["supported_filing_years"]
    )
    return tuple(catalogue.years)


def _catalogue_toml() -> str:
    coverage = "".join(
        "\n[[sociedades_annual_manual_coverage.dispositions]]\n"
        f"year = {year}\n"
        'status = "unpublished"\n'
        'official_locator = "https://example.com/manuals"\n'
        "observed_at = 2026-09-10\n"
        'acquisition_condition_key = "application.registry.manuals.coverage.recheck_aeat_publication"\n'
        for year in _supported_years()
    )
    return (
        _support_declaration()
        + coverage
        + f"""
[legal."{_LEGAL_REF}"]
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

[sources."{DECLARED_RECORD_DESIGN_SOURCE}"]
evidence_tier = "layout_authority"
authority = "aeat"
kind = "record_design"
corpus_path = "corpus/test/{DECLARED_RECORD_DESIGN_SOURCE}.pdf"
sha256 = "{_CORPUS_SHA256}"
bytes = 1000
retrieved_at = 2025-01-01
source_url = "https://example.com/test-source"
review_status = "pending_review"

[sources."{_GUIDANCE_SOURCE}"]
evidence_tier = "official_source_guidance"
authority = "aeat"
kind = "instructions"
corpus_path = "corpus/test/{_GUIDANCE_SOURCE}.pdf"
sha256 = "{_CORPUS_SHA256}"
bytes = 1000
retrieved_at = 2025-01-01
source_url = "https://example.com/test-guidance"
review_status = "pending_review"
"""
    )


def _manifest_toml() -> str:
    return (
        "[modelo]\n"
        f'id = "{UNPUBLISHED_MODELO}"\n'
        'tax_domain = "iva"\n'
        'cadence = "annual"\n'
        'jurisdiction = "ES-AEAT"\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{DECLARED_RECORD_DESIGN_SOURCE}"]\n'
    )


def _revision_toml(filing_year: int) -> str:
    # Applicability grade: the revision answers which edition applies and owns
    # one casilla; it declares no export layout and no storage baseline, so it
    # is exactly a revision whose generated export tree was never published.
    revision = f'revisions."{UNPUBLISHED_REVISION}"'
    return f"""\
[{revision}]
valid_from = {filing_year}-01-01
period_selector = {{ year_from = {filing_year}, periods = ["0A"] }}
authority_grade = "applicability"
legal_refs = ["{_LEGAL_REF}"]
source_refs = ["{DECLARED_RECORD_DESIGN_SOURCE}"]
orden_aplicabilidad = ["{_LEGAL_REF}"]

[[{revision}.application_links]]
id = "unpublished-fixture-filing-link"
surface = "filing"
consumer = "cli.app"
requires_snapshot = true
legal_refs = ["{_LEGAL_REF}"]
source_refs = ["{_GUIDANCE_SOURCE}"]

[[{revision}.casillas]]
id = "01"
number = "01"
section = ["test"]
data_type = "integer"
legal_refs = ["{_LEGAL_REF}"]
source_refs = ["{DECLARED_RECORD_DESIGN_SOURCE}"]
"""


def _install_runtime_inputs(source_root: Path) -> None:
    """Copy the profile schema, tax-ID fact and runtime catalogues every compilation reads."""
    schema = source_root / "registry" / "cadrumo" / "user_profile" / "schema.toml"
    schema.parent.mkdir(parents=True, exist_ok=True)
    schema_text = bundled_path("registry", "cadrumo", "user_profile", "schema.toml").read_text(encoding="utf-8")
    schema.write_text(
        re.sub(r"legal_refs\s*=\s*\[[^\]]*\]", f'legal_refs = ["{_LEGAL_REF}"]', schema_text),
        encoding="utf-8",
    )
    for parts in (
        ("facts", "0102-spanish-tax-identifier-format.toml"),
        ("iva", "country_names.toml"),
        ("iva", "territories.toml"),
        ("iva", "territory_carve_outs.toml"),
        ("iva", "catalogues.toml"),
        ("iva", "place_of_supply.toml"),
        ("apoderamientos", "scopes.toml"),
        ("legal", "ley-58-2003-recargo-bands.toml"),
    ):
        target = source_root.joinpath("registry", "aeat", *parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundled_path("registry", "aeat", *parts), target)
    _install_cited_catalogue_entries(source_root)


def _install_cited_catalogue_entries(source_root: Path) -> None:
    """Carry the legal and source entries the copied runtime inputs cite, with their corpus files."""
    catalogues = compiled_bundled_authority().catalogues
    installed_text = "\n".join(path.read_text(encoding="utf-8") for path in (source_root / "registry").rglob("*.toml"))
    legal = {key: entry for key, entry in catalogues.legal.items() if f'"{key}"' in installed_text}
    sources = {key: entry for key, entry in catalogues.sources.items() if f'"{key}"' in installed_text}
    document: dict[str, object] = {
        "legal": {key: entry.model_dump(exclude_none=True, exclude={"id"}) for key, entry in legal.items()},
        "sources": {key: entry.model_dump(exclude_none=True, exclude={"id"}) for key, entry in sources.items()},
    }
    legal_dir = source_root / "registry" / "aeat" / "legal"
    legal_dir.mkdir(parents=True, exist_ok=True)
    (legal_dir / "cited-inputs.toml").write_text(render_toml(freeze_toml(document)), encoding="utf-8")
    corpus_paths = {entry.corpus_ref.split("#", 1)[0] for entry in legal.values() if entry.corpus_ref}
    corpus_paths.update(entry.corpus_path for entry in sources.values() if entry.corpus_path)
    for corpus_path in corpus_paths:
        bundled_file = bundled_path(*corpus_path.split("/"))
        for sibling in bundled_file.parent.glob(f"{bundled_file.name}*"):
            target = source_root.joinpath(*corpus_path.split("/")).with_name(sibling.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(sibling, target)


def write_unpublished_modelo_registry(source_root: Path) -> UnpublishedModeloRegistry:
    """Author and compile the isolated registry; the caller isolates governed-fact providers."""
    filing_year = max(_supported_years())
    registry_root = source_root / "registry" / "aeat"
    _install_runtime_inputs(source_root)
    corpus_dir = source_root / "corpus" / "test"
    corpus_dir.mkdir(parents=True)
    for source_ref in (DECLARED_RECORD_DESIGN_SOURCE, _GUIDANCE_SOURCE):
        (corpus_dir / f"{source_ref}.pdf").write_bytes(b"x" * 1000)
    legal_corpus = corpus_dir / "test-ley-001.html"
    legal_corpus.write_text("<html>test provision text</html>", encoding="utf-8")
    write_extracted_corpus_sidecar(legal_corpus, anchor="a1", text="test provision text")
    (registry_root / "legal" / "catalogue.toml").write_text(_catalogue_toml(), encoding="utf-8")
    modelo_root = registry_root / "modelos" / UNPUBLISHED_MODELO
    modelo_root.mkdir(parents=True)
    (modelo_root / "manifest.toml").write_text(_manifest_toml(), encoding="utf-8")
    write_fragmented_revision(modelo_root / "revisions" / UNPUBLISHED_REVISION, _revision_toml(filing_year))
    authority = compile_validated_authority(registry_root, source_root)
    return UnpublishedModeloRegistry(
        source_root=source_root,
        registry_root=registry_root,
        authority=authority,
        filing_year=filing_year,
    )
