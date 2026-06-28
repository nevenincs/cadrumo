"""Tests for registry source and legal catalogue verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from .....core.config import Settings
from .....core.paths import PROJECT_ROOT
from .....core.resources import bundled_path
from .._citation_blocklist import _KNOWN_BAD_CITATIONS, KnownBadCitation, find_known_bad
from .._corpus_catalogue import verify_source_catalogue, verify_source_file
from .._coverage import audit_registry_model_law_coverage
from .._errors import RegistryValidationError
from .._legal import verify_legal_catalogue
from .._loader import load_registry_tree
from .._schema import LegalReference, RegistryCatalogues, SourceReference
from .._validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FORMAL_WITHHOLDING_MODELOS = frozenset({"111", "115", "123", "180", "190", "193"})
_M100_WITHHOLDING_IMPORT_SECTIONS = frozenset({"bindings", "relations", "dependency_classifications"})
_FORMAL_WITHHOLDING_ARTICLE_REF = "rd-439-2007:art-108"
_FRACTIONAL_PAYMENT_ARTICLE_REF = "rd-439-2007:art-109"


def _catalogues() -> RegistryCatalogues:
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return catalogues


def test_committed_registry_tree_has_coherent_shared_catalogues() -> None:
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))

    assert len(modelos) >= 5, "committed registry must declare several modelos"
    assert len(catalogues.legal) > 0, "shared legal catalogue must be non-empty"
    assert len(catalogues.sources) > 0, "shared sources catalogue must be non-empty"
    verify_legal_catalogue(catalogues.legal, source_root=bundled_path())
    verify_source_catalogue(PROJECT_ROOT, catalogues.sources)
    validator = RegistryValidator(catalogues, source_root=bundled_path())
    validator.validate_registry(modelos)


def test_committed_registry_tree_has_required_model_law_coverage() -> None:
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))

    audit = audit_registry_model_law_coverage(modelos, catalogues, source_root=bundled_path())

    assert audit.ok
    assert audit.required_gate_failures == ()
    assert len(audit.ledgers) == sum(len(modelo.revisions) for modelo in modelos)
    for ledger in audit.ledgers:
        gates = {gate.tier: gate for gate in ledger.gates}
        assert gates["legal_authority"].status == "satisfied", ledger
        assert gates["official_source_guidance"].status == "satisfied", ledger
        assert gates["layout_authority"].status == "satisfied", ledger


def test_committed_aeat_record_design_sources_match_corpus_manifests() -> None:
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    checked: list[str] = []

    for source in catalogues.sources.values():
        path = Path(source.corpus_path)
        parts = path.parts
        if len(parts) < 5 or parts[:3] != ("corpus", "aeat_official", "disenos_registro"):
            continue
        # corpus_path is stored relative to the bundled corpus root
        # (src/aeat/_data/), so resolve via bundled_path rather than
        # PROJECT_ROOT to find the on-disk manifest.
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


def test_modelo_100_record_design_sources_match_manifest() -> None:
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
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
        verify_source_file(PROJECT_ROOT, source)
        checked.append(source.id)

    assert len(checked) == 18


def test_renta_manual_sources_match_manifest() -> None:
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    sources_by_path = {source.corpus_path: source for source in catalogues.sources.values()}
    manual_roots = (
        bundled_path("corpus", "manuals", "renta", "2025", "part1"),
        bundled_path("corpus", "manuals", "renta", "2025", "part2-deducciones-autonomicas"),
    )
    checked: list[str] = []

    for root in manual_roots:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        # corpus_path on registry sources is bundled-corpus-relative
        # (i.e. begins with ``corpus/...``), so relativise against the
        # bundle root rather than PROJECT_ROOT.
        corpus_path = root.joinpath(manifest["relative_pdf_path"]).relative_to(bundled_path()).as_posix()
        source = sources_by_path.get(corpus_path)

        assert source is not None, f"Renta manual corpus artefact has no registry source: {corpus_path}"
        assert source.sha256 == manifest["sha256"]
        assert source.bytes == manifest["content_length"]
        assert source.source_url == manifest["source_pdf_url"]
        assert source.evidence_tier == "official_source_guidance"
        assert source.kind == "manual_pdf"
        verify_source_file(PROJECT_ROOT, source)
        checked.append(source.id)

    assert checked == ["aeat-renta-2025-manual-parte1", "aeat-renta-2025-manual-deducciones-autonomicas"]


def test_renta_economic_activity_legal_basis_links_to_corpus() -> None:
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))

    assert {
        "ley-35-2006:art-27",
        "ley-35-2006:art-28",
        "ley-35-2006:art-30",
        "ley-35-2006:art-31",
        "ley-35-2006:art-32",
    }.issubset(catalogues.legal)
    verify_legal_catalogue(catalogues.legal, source_root=bundled_path())


def test_ley_31_2022_da_70_rib_reference_links_to_bundled_boe_corpus() -> None:
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    reference = catalogues.legal["ley-31-2022:da-70"]

    assert reference.corpus_ref == "corpus/normatives/html/ley-31-2022-da-70.html#da-70"
    assert reference.permalink.endswith("#da-70")
    assert reference.required_text == (
        "Reserva para inversiones en las Illes Balears",
        "El importe de la reserva pendiente de materialización",
        "Los contribuyentes del Impuesto sobre la Renta de las Personas Físicas",
        "tendrán derecho a una deducción en la cuota íntegra",
    )
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


def test_rd_439_art_109_legal_basis_links_to_pago_fraccionado_corpus() -> None:
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    reference = catalogues.legal["rd-439-2007:art-109"]

    assert reference.corpus_ref == "corpus/normatives/html/rd-439-2007-art-109.html#a109"
    assert reference.notes is not None
    assert "obligados al pago fraccionado" in reference.notes.lower()
    assert "obligaciones formales del retenedor" not in reference.notes.lower()
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())

    corpus = json.loads(bundled_path("corpus", "normatives", "rd-439-2007.json").read_text(encoding="utf-8"))
    article_109 = next(article for article in corpus["articulos"] if article["numero"] == "109")

    assert article_109["titulo"]["es"] == "Obligados al pago fraccionado"
    assert "autoliquidar e ingresar pagos fraccionados" in article_109["summary"]["es"]
    assert "obligaciones formales" not in article_109["summary"]["es"].lower()


def test_formal_withholding_modelos_do_not_cite_fractional_payment_article() -> None:
    modelos_root = bundled_path("registry", "aeat", "modelos")
    offenders: list[str] = []
    missing_formal_article: list[str] = []

    for modelo_id in sorted(_FORMAL_WITHHOLDING_MODELOS):
        modelo_root = modelos_root / modelo_id
        assert modelo_root.is_dir(), modelo_id
        has_formal_article = False

        for path in sorted(modelo_root.rglob("*.toml")):
            text = path.read_text(encoding="utf-8")
            if _FRACTIONAL_PAYMENT_ARTICLE_REF in text:
                offenders.append(path.relative_to(modelos_root).as_posix())
            if _FORMAL_WITHHOLDING_ARTICLE_REF in text:
                has_formal_article = True

        if not has_formal_article:
            missing_formal_article.append(modelo_id)

    assert offenders == []
    assert missing_formal_article == []


def test_modelo_100_withholding_imports_use_formal_withholding_article() -> None:
    modelo_root = bundled_path("registry", "aeat", "modelos", "100")
    offenders: list[str] = []
    missing_formal_article: list[str] = []
    checked: list[str] = []

    for path in sorted(modelo_root.rglob("*.toml")):
        if not (set(path.parts) & _M100_WITHHOLDING_IMPORT_SECTIONS):
            continue

        text = path.read_text(encoding="utf-8")
        if "retenciones" not in text.lower():
            continue
        if not any(f'source_modelo = "{modelo_id}"' in text for modelo_id in _FORMAL_WITHHOLDING_MODELOS):
            continue

        rel_path = path.relative_to(modelo_root).as_posix()
        checked.append(rel_path)
        if _FRACTIONAL_PAYMENT_ARTICLE_REF in text:
            offenders.append(rel_path)
        if _FORMAL_WITHHOLDING_ARTICLE_REF not in text:
            missing_formal_article.append(rel_path)

    assert len(checked) == 72
    assert offenders == []
    assert missing_formal_article == []


def test_modelo_100_retention_credit_formulas_do_not_cite_fractional_payment_article() -> None:
    modelo_root = bundled_path("registry", "aeat", "modelos", "100")
    offenders: list[str] = []
    checked: list[str] = []

    for path in sorted(modelo_root.rglob("formulas/*.toml")):
        text = path.read_text(encoding="utf-8")
        formula_id = next((line for line in text.splitlines() if line.startswith("id = ")), "")
        if "retenciones" not in formula_id.lower():
            continue

        rel_path = path.relative_to(modelo_root).as_posix()
        checked.append(rel_path)
        if _FRACTIONAL_PAYMENT_ARTICLE_REF in text:
            offenders.append(rel_path)

    assert "revisions/2025/formulas/0068-renta-2025-retenciones-arrendamientos-urbanos.toml" in checked
    assert offenders == []


def _legal_reference(
    *,
    ref_id: str = "rd-439-2007:art-110",
    kind: str = "real_decreto",
    article: str = "110",
    notes: str | None = None,
) -> LegalReference:
    reference = next(iter(_catalogues().legal.values()))
    return reference.model_copy(
        update={
            "id": ref_id,
            "kind": kind,
            "article": article,
            "notes": reference.notes if notes is None else notes,
        },
    )


def _source_reference(path: str, payload: bytes) -> SourceReference:
    source = next(iter(_catalogues().sources.values()))
    return source.model_copy(
        update={
            "corpus_path": path,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        },
    )


def test_verify_source_file_checks_hash_and_size(tmp_path: Path) -> None:
    payload = b"official"
    source_path = tmp_path / "corpus" / "source.xlsx"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(payload)

    reference = _source_reference("corpus/source.xlsx", payload)
    assert source_path.read_bytes() == payload
    assert reference.sha256, "reference must carry a hash for verification to be meaningful"
    result = verify_source_file(tmp_path, reference)
    assert result is None


def test_verify_source_file_rejects_hash_mismatch(tmp_path: Path) -> None:
    source_path = tmp_path / "corpus" / "source.xlsx"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"changed")

    with pytest.raises(RegistryValidationError, match=r"byte count mismatch|sha256 mismatch"):
        verify_source_file(tmp_path, _source_reference("corpus/source.xlsx", b"official"))


def test_verify_source_file_rejects_path_escape(tmp_path: Path) -> None:
    source = _source_reference("../outside.xlsx", b"x")

    with pytest.raises(RegistryValidationError, match="escapes repository root"):
        verify_source_file(tmp_path, source)


def test_verify_source_catalogue_checks_every_entry(tmp_path: Path) -> None:
    payload = b"official"
    source_path = tmp_path / "corpus" / "source.xlsx"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(payload)

    catalogue = {"aeat-source": _source_reference("corpus/source.xlsx", payload)}
    assert len(catalogue) == 1
    result = verify_source_catalogue(tmp_path, catalogue)
    assert result is None


def test_verify_legal_catalogue_rejects_known_bad_citation_role() -> None:
    reference = _legal_reference(
        ref_id="ley-35-2006:art-103",
        kind="ley",
        article="103",
        notes="cuota diferencial",
    )

    with pytest.raises(RegistryValidationError, match="known-bad citation"):
        verify_legal_catalogue({reference.id: reference})


@pytest.mark.parametrize("blocked", _KNOWN_BAD_CITATIONS)
def test_verify_legal_catalogue_rejects_every_blocklisted_role(blocked: KnownBadCitation) -> None:
    reference = _legal_reference(
        ref_id=f"{blocked.source}:{blocked.article}",
        kind=blocked.source,
        article=blocked.article,
        notes=blocked.role_substring,
    )
    text = " ".join(part for part in (reference.section, reference.notes) if part)

    assert find_known_bad(blocked.source, blocked.article, text) == blocked
    with pytest.raises(RegistryValidationError, match="known-bad citation"):
        verify_legal_catalogue({reference.id: reference})


def test_known_bad_citation_matching_is_diacritic_insensitive() -> None:
    blocked = find_known_bad("ley", "77", "cuota integra autonomica")

    assert blocked is not None
    assert blocked.role_substring == "cuota íntegra autonómica"


def test_known_bad_citation_matching_allows_different_role_for_same_article() -> None:
    assert find_known_bad("ley", "77", "cuota líquida autonómica total") is None


def test_verify_legal_catalogue_rejects_key_mismatch() -> None:
    reference = _legal_reference()

    with pytest.raises(RegistryValidationError, match="does not match reference id"):
        verify_legal_catalogue({"other-id": reference})


def test_verify_legal_catalogue_accepts_reviewed_reference() -> None:
    reference = _legal_reference()

    assert reference.id, "reference must have an id for verification to be meaningful"
    result = verify_legal_catalogue({reference.id: reference})
    assert result is None


def test_verify_legal_catalogue_checks_required_local_corpus_text(tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus" / "normatives" / "rd-439-2007.json"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text('{"articulos": [{"numero": "110", "text_es": "other legal text"}]}', encoding="utf-8")
    reference = _legal_reference().model_copy(
        update={
            "corpus_ref": "corpus/normatives/rd-439-2007.json#art-110",
            "required_text": ("20 por ciento del rendimiento neto",),
        },
    )

    with pytest.raises(RegistryValidationError, match="corpus text missing required text"):
        verify_legal_catalogue({reference.id: reference}, source_root=tmp_path)


def test_verify_legal_catalogue_accepts_required_local_corpus_text(tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus" / "normatives" / "rd-439-2007.json"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text(
        '{"articulos": [{"numero": "110", "text_es": "20 por ciento del rendimiento neto"}]}',
        encoding="utf-8",
    )
    reference = _legal_reference().model_copy(
        update={
            "corpus_ref": "corpus/normatives/rd-439-2007.json#art-110",
            "required_text": ("20 por ciento del rendimiento neto",),
        },
    )

    assert reference.required_text, "reference must declare required_text for the verifier to check"
    assert corpus_path.exists(), "corpus file must be written before verification"
    result = verify_legal_catalogue({reference.id: reference}, source_root=tmp_path)
    assert result is None


def test_verify_legal_catalogue_corpus_strict_false_skips_required_text(tmp_path: Path) -> None:
    """Production authority (corpus_strict=False) must not abort on a pending required_text annotation.

    This guards the forward contract: adding a required_text to any legal reference
    must not block bindings list, work calculate, or any other user-facing verb until
    verify_registry_tree (corpus_strict=True) is run explicitly.
    """
    # Corpus file exists but does NOT contain the required phrase.
    corpus_path = tmp_path / "corpus" / "normatives" / "rd-439-2007.json"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text(
        '{"articulos": [{"numero": "110", "text_es": "other legal text without the phrase"}]}',
        encoding="utf-8",
    )
    reference = _legal_reference().model_copy(
        update={
            "corpus_ref": "corpus/normatives/rd-439-2007.json#art-110",
            "required_text": ("phrase absent from corpus",),
        },
    )

    assert reference.required_text, "reference must declare required_text for the check to be meaningful"
    # Strict mode raises — the pending annotation IS a defect when checked explicitly.
    with pytest.raises(RegistryValidationError, match="corpus text missing required text"):
        verify_legal_catalogue({reference.id: reference}, source_root=tmp_path, corpus_strict=True)
    # Non-strict mode (production authority path) must not raise.
    result = verify_legal_catalogue({reference.id: reference}, source_root=tmp_path, corpus_strict=False)
    assert result is None


def test_registry_validator_corpus_strict_false_does_not_abort(tmp_path: Path) -> None:
    """RegistryValidator(catalogue_corpus_strict=False) must not abort on a pending required_text.

    Mirrors the production authority construction in _load_authority so that a
    new required_text annotation never breaks bindings list / work calculate.
    """
    # Build a minimal corpus tree: one file that exists but lacks the required phrase.
    corpus_path = tmp_path / "corpus" / "normatives" / "rd-439-2007.json"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text(
        '{"articulos": [{"numero": "110", "text_es": "other legal text without the phrase"}]}',
        encoding="utf-8",
    )
    reference = _legal_reference().model_copy(
        update={
            "corpus_ref": "corpus/normatives/rd-439-2007.json#art-110",
            "required_text": ("phrase absent from corpus",),
        },
    )
    # Wrap in minimal catalogues (no sources needed for this check).
    from .._schema import RegistryCatalogues

    minimal_catalogues = RegistryCatalogues(
        legal={reference.id: reference},
        sources={},
    )

    # Strict validator returns the corpus failure — gated functions raise from this.
    strict = RegistryValidator(minimal_catalogues, source_root=tmp_path, catalogue_corpus_strict=True)
    strict_failures = strict._validate_catalogues()
    assert any("corpus text missing required text" in f for f in strict_failures), strict_failures

    # Non-strict validator (production authority path) returns no failures.
    non_strict = RegistryValidator(minimal_catalogues, source_root=tmp_path, catalogue_corpus_strict=False)
    failures = non_strict._validate_catalogues()
    assert failures == ()


def test_verify_source_file_checks_manual_structure(tmp_path: Path) -> None:
    """verify_source_file must fail if a manual_pdf source reference points to an invalid manual structure."""
    from datetime import date

    pdf_path = tmp_path / "corpus" / "manuals" / "renta" / "2020" / "part1" / "source.pdf"
    pdf_path.parent.mkdir(parents=True)
    payload = b"%PDF-1.4 manual structure sample bytes"
    pdf_path.write_bytes(payload)

    sha = hashlib.sha256(payload).hexdigest()

    source = SourceReference(
        id="aeat-renta-2020-manual-parte1",
        evidence_tier="official_source_guidance",
        authority="aeat",
        kind="manual_pdf",
        corpus_path="corpus/manuals/renta/2020/part1/source.pdf",
        sha256=sha,
        bytes=len(payload),
        retrieved_at=date(2026, 5, 6),
        source_url=f"{Settings.external_constants().aeat.domains.sede}/Manual.pdf",
        review_status="reviewed",
    )

    # Check 1: Should fail because structure/manual.json is missing
    with pytest.raises(RegistryValidationError, match="manual structure check failed"):
        verify_source_file(tmp_path, source)

    # Check 2: Write valid manual structure and it should pass
    structure_dir = tmp_path / "corpus" / "manuals" / "renta" / "2020" / "part1" / "structure"
    structure_dir.mkdir(parents=True)

    (structure_dir / "manual.json").write_text(
        json.dumps(
            {
                "manual_id": "renta",
                "year": 2020,
                "part": "part1",
                "title": "Manual Renta 2020",
                "summary": "Resumen",
                "source_pdf_url": f"{Settings.external_constants().aeat.domains.sede}/Manual.pdf",
                "source_html_url": None,
                "fetched_at": "2026-05-06T00:00:00Z",
                "definition_reviewed_by": "operator",
                "definition_reviewed_at": "2026-06-08",
            },
        ),
        encoding="utf-8",
    )

    (structure_dir / "chapters.json").write_text(
        json.dumps([{"chapter_id": "cap1", "title": "Capitulo 1", "summary": "Resumen", "sections": []}]),
        encoding="utf-8",
    )

    verify_source_file(tmp_path, source)


def test_verify_legal_reference_checks_manual_section_json(tmp_path: Path) -> None:
    """verify_legal_reference must fail if a manual legal reference points to an invalid section JSON file."""
    from datetime import date

    section_path = (
        tmp_path / "corpus" / "manuals" / "renta" / "2020" / "part1" / "structure" / "sections" / "cap1" / "sec1.json"
    )
    section_path.parent.mkdir(parents=True)
    section_path.write_text("{corrupt json", encoding="utf-8")

    from .._schema import LegalReference

    reference = LegalReference(
        id="renta-2020-manual:sec1",
        evidence_tier="legal_authority",
        authority="aeat",
        kind="manual",
        corpus_ref="corpus/manuals/renta/2020/part1/structure/sections/cap1/sec1.json#sec1",
        document_id="BOE-A-2020-0000",
        permalink=f"{Settings.external_constants().aeat.domains.sede}/",
        published_at=date(2020, 3, 31),
        effective_from=date(2020, 4, 1),
        review_status="reviewed",
        reviewed_at=date(2026, 5, 6),
        reviewed_by="operator",
        notes="Notes",
    )

    with pytest.raises(RegistryValidationError, match="manual section JSON validation failed"):
        verify_legal_catalogue({reference.id: reference}, source_root=tmp_path)

    section_path.write_text(
        json.dumps(
            {
                "section_id": "sec1",
                "chapter_id": "cap1",
                "title": "Seccion 1",
                "summary": "Resumen",
                "prose": [],
                "rules": [],
                "references_sections": [],
                "references_legal_acts": [],
                "source": {"manual_url": f"{Settings.external_constants().aeat.domains.sede}/", "page": 1},
                "definition_reviewed_by": "operator",
                "definition_reviewed_at": "2026-06-08",
            },
        ),
        encoding="utf-8",
    )

    verify_legal_catalogue({reference.id: reference}, source_root=tmp_path)
