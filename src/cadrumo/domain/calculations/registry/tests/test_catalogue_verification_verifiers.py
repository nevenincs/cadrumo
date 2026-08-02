"""Focused verifier tests split from catalogue verification."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.config import Settings
from .._citation_blocklist import KnownBadCitation, find_known_bad, known_bad_citations
from .._corpus_catalogue import verify_source_catalogue, verify_source_file
from .._errors import RegistryValidationError
from .._legal import verify_legal_catalogue
from .._schema import LegalReference, RegistryCatalogues, SourceCitation, SourceReference
from .._validate import RegistryValidator
from .._validate_evidence import EvidenceValidator
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _catalogues() -> RegistryCatalogues:
    _modelos, catalogues = _committed_registry_tree()
    return catalogues


def _legal_reference(
    *,
    ref_id: str = "rd-439-2007:art-110",
    kind: str = "real_decreto",
    article: str | None = "110",
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


def _write_extracted_unit(corpus_path: Path, *, anchor: str, text: str) -> None:
    """Write the canonical selected-unit artefact used by legal verification."""
    corpus_path.with_name(corpus_path.name + ".extracted.json").write_text(
        json.dumps({"units": [{"anchor": anchor, "text": text}]}),
        encoding="utf-8",
    )


def test_verify_source_file_checks_hash_and_size(tmp_path: Path) -> None:
    payload = b"official"
    source_path = tmp_path / "corpus" / "source.xlsx"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(payload)

    reference = _source_reference("corpus/source.xlsx", payload)
    assert source_path.read_bytes() == payload
    assert reference.sha256, "reference must carry a hash for verification to be meaningful"
    verify_source_file(tmp_path, reference)


def test_verify_source_file_rejects_hash_mismatch(tmp_path: Path) -> None:
    source_path = tmp_path / "corpus" / "source.xlsx"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"changed")

    with pytest.raises(RegistryValidationError, match=r"byte count mismatch|sha256 mismatch"):
        verify_source_file(tmp_path, _source_reference("corpus/source.xlsx", b"official"))


def test_verify_source_file_rehashes_same_size_timestamp_restored_replacement(tmp_path: Path) -> None:
    """Byte verification must not reuse a digest after metadata-preserving tampering."""

    payload = b"official"
    source_path = tmp_path / "corpus" / "source.xlsx"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(payload)
    reference = _source_reference("corpus/source.xlsx", payload)
    verify_source_file(tmp_path, reference)

    original_stat = source_path.stat()
    source_path.write_bytes(b"tampered")
    os.utime(source_path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

    with pytest.raises(RegistryValidationError, match="sha256 mismatch"):
        verify_source_file(tmp_path, reference)


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
    verify_source_catalogue(tmp_path, catalogue)


def test_verify_legal_catalogue_rejects_known_bad_citation_role() -> None:
    reference = _legal_reference(
        ref_id="ley-35-2006:art-103",
        kind="ley",
        article="103",
        notes="cuota diferencial",
    )

    with pytest.raises(RegistryValidationError, match="known-bad citation"):
        verify_legal_catalogue({reference.id: reference})


@pytest.mark.parametrize("blocked", known_bad_citations())
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


def test_legal_reference_requires_required_text() -> None:
    reference = _legal_reference()
    payload = reference.model_dump(mode="python")
    payload.pop("required_text")

    with pytest.raises(ValidationError, match="required_text"):
        LegalReference.model_validate(payload)


def test_legal_reference_rejects_empty_required_text() -> None:
    reference = _legal_reference()
    payload = reference.model_dump(mode="python")
    payload["required_text"] = ()

    with pytest.raises(ValidationError, match="at least 1 item"):
        LegalReference.model_validate(payload)


def test_legal_reference_requires_review_stamp() -> None:
    reference = _legal_reference()
    payload = reference.model_dump(mode="python")
    payload.pop("reviewed_at")

    with pytest.raises(ValidationError, match="reviewed_at"):
        LegalReference.model_validate(payload)


def test_legal_reference_rejects_blank_reviewer() -> None:
    reference = _legal_reference()
    payload = reference.model_dump(mode="python")
    payload["reviewed_by"] = ""

    with pytest.raises(ValidationError, match="at least 1 character"):
        LegalReference.model_validate(payload)


def test_verify_legal_catalogue_checks_required_local_corpus_text(tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus" / "normatives" / "html" / "rd-439-2007-art-110.html"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text("<p>other legal text</p>", encoding="utf-8")
    _write_extracted_unit(corpus_path, anchor="a110", text="other legal text")
    reference = _legal_reference().model_copy(
        update={
            "corpus_ref": "corpus/normatives/html/rd-439-2007-art-110.html#a110",
            "required_text": ("20 por ciento del rendimiento neto",),
        },
    )

    with pytest.raises(RegistryValidationError, match="corpus text missing required text"):
        verify_legal_catalogue({reference.id: reference}, source_root=tmp_path)


def test_verify_legal_catalogue_checks_required_text_when_article_is_absent(tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus" / "normatives" / "html" / "orden-hfp-1359-2023-da-5.html"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text("<p>official text without the disposition phrase</p>", encoding="utf-8")
    _write_extracted_unit(corpus_path, anchor="da5", text="official text without the disposition phrase")
    reference = _legal_reference(
        ref_id="orden-hfp-1359-2023:da-5",
        kind="orden",
        article=None,
    ).model_copy(
        update={
            "corpus_ref": "corpus/normatives/html/orden-hfp-1359-2023-da-5.html#da5",
            "required_text": ("Disposicion adicional quinta",),
        },
    )

    with pytest.raises(RegistryValidationError, match="corpus text missing required text"):
        verify_legal_catalogue({reference.id: reference}, source_root=tmp_path)


def test_verify_legal_catalogue_checks_required_text_for_treaty_refs(tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus" / "normatives" / "html" / "convenio-es-gb-2013-art-6.html"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text("<p>official treaty text without the property-income phrase</p>", encoding="utf-8")
    _write_extracted_unit(corpus_path, anchor="art-6", text="official treaty text without the property-income phrase")
    reference = _legal_reference(
        ref_id="convenio-es-gb-2013:art-6",
        kind="acuerdo_internacional",
        article="6",
    ).model_copy(
        update={
            "corpus_ref": "corpus/normatives/html/convenio-es-gb-2013-art-6.html#art-6",
            "required_text": ("Rentas inmobiliarias",),
        },
    )

    with pytest.raises(RegistryValidationError, match="corpus text missing required text"):
        verify_legal_catalogue({reference.id: reference}, source_root=tmp_path)


def test_verify_legal_catalogue_refuses_a_corpus_file_with_no_extracted_sidecar(tmp_path: Path) -> None:
    """A raw corpus file is not evidence; the anchored extraction is.

    Legal verification resolves ONE anchored unit out of the sidecar and matches
    ``required_text`` against that unit alone, rather than against the whole
    document. The refusal is what stops a reference falling back to a
    document-wide substring match, which would ground a provision on text from
    an unrelated article of the same law.

    This is the negative control for that guard: without it the refusal could be
    deleted and every fixture that writes a sidecar would still pass.
    """
    corpus_path = tmp_path / "corpus" / "normatives" / "html" / "no-sidecar.html"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text("<p>20 por ciento del rendimiento neto</p>", encoding="utf-8")
    reference = _legal_reference(ref_id="rd-439-2007:art-110-no-sidecar").model_copy(
        update={
            "corpus_ref": "corpus/normatives/html/no-sidecar.html#a110",
            "required_text": ("20 por ciento del rendimiento neto",),
        },
    )

    assert corpus_path.exists(), "the corpus file itself must exist, so only the sidecar is missing"
    assert not corpus_path.with_name(corpus_path.name + ".extracted.json").exists()

    with pytest.raises(RegistryValidationError, match="missing extracted corpus sidecar"):
        verify_legal_catalogue({reference.id: reference}, source_root=tmp_path)


def test_verify_legal_catalogue_accepts_required_local_corpus_text(tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus" / "normatives" / "html" / "rd-439-2007-art-110.html"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text(
        "<p>20 por ciento del rendimiento neto</p>",
        encoding="utf-8",
    )
    _write_extracted_unit(corpus_path, anchor="a110", text="20 por ciento del rendimiento neto")
    reference = _legal_reference().model_copy(
        update={
            "corpus_ref": "corpus/normatives/html/rd-439-2007-art-110.html#a110",
            "required_text": ("20 por ciento del rendimiento neto",),
        },
    )

    assert reference.required_text, "reference must declare required_text for the verifier to check"
    assert corpus_path.exists(), "corpus file must be written before verification"
    result = verify_legal_catalogue({reference.id: reference}, source_root=tmp_path)
    assert result is None


def test_verify_legal_catalogue_refuses_an_anchor_that_would_widen_to_another_unit(tmp_path: Path) -> None:
    """Required text in a sibling unit cannot validate an absent cited anchor."""
    corpus_path = tmp_path / "corpus" / "normatives" / "html" / "rd-439-2007-art-110.html"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.with_name(corpus_path.name + ".extracted.json").write_text(
        json.dumps(
            {
                "units": [
                    {"anchor": "a109", "text": "20 por ciento del rendimiento neto"},
                    {"anchor": "a111", "text": "unrelated legal text"},
                ],
            },
        ),
        encoding="utf-8",
    )
    reference = _legal_reference().model_copy(
        update={
            "corpus_ref": "corpus/normatives/html/rd-439-2007-art-110.html#a110",
            "required_text": ("20 por ciento del rendimiento neto",),
        },
    )

    with pytest.raises(RegistryValidationError, match="cannot resolve one corpus unit"):
        verify_legal_catalogue({reference.id: reference}, source_root=tmp_path)


def test_legal_corpus_text_cache_is_path_scoped_for_same_size_files(tmp_path: Path) -> None:
    """Same-name, same-size corpus files must not share cached legal text."""
    alpha_path = tmp_path / "corpus" / "normatives" / "alpha" / "same-size-cache-collision.html"
    bravo_path = tmp_path / "corpus" / "normatives" / "bravo" / "same-size-cache-collision.html"
    alpha_path.parent.mkdir(parents=True)
    bravo_path.parent.mkdir(parents=True)
    alpha_path.write_text("<p>alpha required</p>", encoding="utf-8")
    bravo_path.write_text("<p>bravo required</p>", encoding="utf-8")
    _write_extracted_unit(alpha_path, anchor="a", text="alpha required")
    _write_extracted_unit(bravo_path, anchor="b", text="bravo required")

    assert alpha_path.name == bravo_path.name
    assert alpha_path.stat().st_size == bravo_path.stat().st_size

    alpha = _legal_reference(ref_id="rd-439-2007:art-110-alpha").model_copy(
        update={
            "corpus_ref": "corpus/normatives/alpha/same-size-cache-collision.html#a",
            "required_text": ("alpha required",),
        },
    )
    bravo = _legal_reference(ref_id="rd-439-2007:art-110-bravo").model_copy(
        update={
            "corpus_ref": "corpus/normatives/bravo/same-size-cache-collision.html#b",
            "required_text": ("bravo required",),
        },
    )

    verify_legal_catalogue({alpha.id: alpha}, source_root=tmp_path)
    verify_legal_catalogue({bravo.id: bravo}, source_root=tmp_path)


def test_legal_corpus_text_rereads_same_size_timestamp_restored_sidecar(tmp_path: Path) -> None:
    """A metadata-preserving sidecar replacement must not serve cached legal text.

    ``st_size`` and ``st_mtime_ns`` are forgeable together, so the extracted
    sidecar is keyed by a content digest as well. Without it the cache keeps
    returning the superseded text as the evidence behind a filing.
    """
    corpus_path = tmp_path / "corpus" / "normatives" / "html" / "same-mtime-sidecar.html"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text("<p>article 1 official</p>", encoding="utf-8")
    _write_extracted_unit(corpus_path, anchor="a1", text="article 1 official")
    reference = _legal_reference(ref_id="rd-439-2007:art-110-sidecar-digest").model_copy(
        update={
            "corpus_ref": "corpus/normatives/html/same-mtime-sidecar.html#a1",
            "required_text": ("article 1 official",),
        },
    )
    verify_legal_catalogue({reference.id: reference}, source_root=tmp_path)

    sidecar = corpus_path.with_name(corpus_path.name + ".extracted.json")
    original_stat = sidecar.stat()
    # Same character count, so the sidecar keeps its byte length exactly.
    _write_extracted_unit(corpus_path, anchor="a1", text="article 1 tampered")
    os.utime(sidecar, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

    assert sidecar.stat().st_size == original_stat.st_size
    assert sidecar.stat().st_mtime_ns == original_stat.st_mtime_ns

    with pytest.raises(RegistryValidationError, match="corpus text missing required text"):
        verify_legal_catalogue({reference.id: reference}, source_root=tmp_path)


def test_legal_corpus_text_accepts_valid_sidecar_after_metadata_preserving_rewrite(tmp_path: Path) -> None:
    """The digest refuses only changed content, not an unchanged re-write.

    The positive control for the tamper regression above: rewriting the same
    bytes with the same stat metadata must still verify, so the refusal is
    attributable to the changed content rather than to the re-write itself.
    """
    corpus_path = tmp_path / "corpus" / "normatives" / "html" / "same-mtime-unchanged.html"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text("<p>article 2 official</p>", encoding="utf-8")
    _write_extracted_unit(corpus_path, anchor="a2", text="article 2 official")
    reference = _legal_reference(ref_id="rd-439-2007:art-110-sidecar-unchanged").model_copy(
        update={
            "corpus_ref": "corpus/normatives/html/same-mtime-unchanged.html#a2",
            "required_text": ("article 2 official",),
        },
    )
    verify_legal_catalogue({reference.id: reference}, source_root=tmp_path)

    sidecar = corpus_path.with_name(corpus_path.name + ".extracted.json")
    original_stat = sidecar.stat()
    _write_extracted_unit(corpus_path, anchor="a2", text="article 2 official")
    os.utime(sidecar, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

    assert sidecar.stat().st_size == original_stat.st_size
    assert verify_legal_catalogue({reference.id: reference}, source_root=tmp_path) is None


def test_legal_corpus_text_cache_is_anchor_scoped_within_one_sidecar(tmp_path: Path) -> None:
    """Sibling anchors must never reuse the first selected extracted unit."""
    corpus_path = tmp_path / "corpus" / "normatives" / "html" / "two-articles.html"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text("<p>two legal units</p>", encoding="utf-8")
    corpus_path.with_name(corpus_path.name + ".extracted.json").write_text(
        json.dumps(
            {
                "units": [
                    {"anchor": "a110", "text": "first article required text"},
                    {"anchor": "a111", "text": "second article required text"},
                ],
            },
        ),
        encoding="utf-8",
    )
    first = _legal_reference(ref_id="rd-439-2007:art-110-first").model_copy(
        update={
            "corpus_ref": "corpus/normatives/html/two-articles.html#a110",
            "required_text": ("first article required text",),
        },
    )
    second = _legal_reference(ref_id="rd-439-2007:art-111-second").model_copy(
        update={
            "corpus_ref": "corpus/normatives/html/two-articles.html#a111",
            "required_text": ("second article required text",),
        },
    )

    verify_legal_catalogue({first.id: first, second.id: second}, source_root=tmp_path)


def test_source_citation_text_cache_is_path_scoped_for_same_size_files(tmp_path: Path) -> None:
    """Same-name, same-size official sources must not share cached citation text."""
    basename = f"{tmp_path.name}-same-size-citation.html"
    alpha_path = tmp_path / "corpus" / "sources" / "alpha" / basename
    bravo_path = tmp_path / "corpus" / "sources" / "bravo" / basename
    alpha_path.parent.mkdir(parents=True)
    bravo_path.parent.mkdir(parents=True)
    alpha_payload = b"<p>alpha required</p>"
    bravo_payload = b"<p>bravo required</p>"
    alpha_path.write_bytes(alpha_payload)
    bravo_path.write_bytes(bravo_payload)

    assert alpha_path.name == bravo_path.name
    assert alpha_path.stat().st_size == bravo_path.stat().st_size

    alpha = _source_reference(f"corpus/sources/alpha/{basename}", alpha_payload).model_copy(
        update={"id": "source-alpha", "evidence_tier": "official_source_guidance"},
    )
    bravo = _source_reference(f"corpus/sources/bravo/{basename}", bravo_payload).model_copy(
        update={"id": "source-bravo", "evidence_tier": "official_source_guidance"},
    )
    validator = EvidenceValidator(
        legal_refs={},
        source_refs={alpha.id: alpha, bravo.id: bravo},
        source_root=tmp_path,
    )

    alpha_failures = validator.validate_source_citations(
        "scope",
        "alpha",
        (alpha.id,),
        (SourceCitation(source_ref=alpha.id, required_text=("alpha required",)),),
        "official_source_guidance",
    )
    bravo_failures = validator.validate_source_citations(
        "scope",
        "bravo",
        (bravo.id,),
        (SourceCitation(source_ref=bravo.id, required_text=("bravo required",)),),
        "official_source_guidance",
    )

    assert alpha_failures == []
    assert bravo_failures == []


def test_source_citation_text_rejects_path_escape(tmp_path: Path) -> None:
    source_root = tmp_path / "bundle"
    source_root.mkdir()
    outside_payload = b"<p>escaped required text</p>"
    outside_path = tmp_path / "escaped-source.html"
    outside_path.write_bytes(outside_payload)
    source = _source_reference("corpus/../../escaped-source.html", outside_payload).model_copy(
        update={
            "id": "source-escape",
            "evidence_tier": "official_source_guidance",
            "kind": "instructions",
        },
    )
    validator = EvidenceValidator(
        legal_refs={},
        source_refs={source.id: source},
        source_root=source_root,
    )

    failures = validator.validate_source_citations(
        "scope",
        "escape",
        (source.id,),
        (SourceCitation(source_ref=source.id, required_text=("escaped required text",)),),
        "official_source_guidance",
    )

    assert failures == [
        f"scope: escape source citation {source.id!r} cannot be read: source {source.id!r} escapes source root",
    ]


def test_source_citation_fails_absent_binary_and_html_sources(tmp_path: Path) -> None:
    """Every absent cited source fails, including mandatory-companion binaries."""
    binary = _source_reference("corpus/manuals/example/source.pdf", b"pdf payload").model_copy(
        update={"id": "source-companion-pdf", "evidence_tier": "official_source_guidance", "kind": "instructions"},
    )
    html = _source_reference("corpus/normatives/html/example.html", b"<p>html payload</p>").model_copy(
        update={"id": "source-runtime-html", "evidence_tier": "official_source_guidance", "kind": "instructions"},
    )
    validator = EvidenceValidator(
        legal_refs={},
        source_refs={binary.id: binary, html.id: html},
        source_root=tmp_path,
    )

    binary_failures = validator.validate_source_citations(
        "scope",
        "companion",
        (binary.id,),
        (SourceCitation(source_ref=binary.id, required_text=("unevaluable phrase",)),),
        "official_source_guidance",
    )
    html_failures = validator.validate_source_citations(
        "scope",
        "runtime",
        (html.id,),
        (SourceCitation(source_ref=html.id, required_text=("required phrase",)),),
        "official_source_guidance",
    )

    assert len(binary_failures) == 1
    assert "cannot be read" in binary_failures[0]
    assert len(html_failures) == 1
    assert "cannot be read" in html_failures[0]


def test_verify_legal_catalogue_rejects_missing_required_text_on_single_path(tmp_path: Path) -> None:
    """Legal catalogue verification always enforces required_text against corpus."""
    corpus_path = tmp_path / "corpus" / "normatives" / "html" / "rd-439-2007-art-110.html"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text(
        "<p>other legal text without the phrase</p>",
        encoding="utf-8",
    )
    _write_extracted_unit(corpus_path, anchor="a110", text="other legal text without the phrase")
    reference = _legal_reference().model_copy(
        update={
            "corpus_ref": "corpus/normatives/html/rd-439-2007-art-110.html#a110",
            "required_text": ("phrase absent from corpus",),
        },
    )

    assert reference.required_text, "reference must declare required_text for the check to be meaningful"
    with pytest.raises(RegistryValidationError, match="corpus text missing required text"):
        verify_legal_catalogue({reference.id: reference}, source_root=tmp_path)


def test_registry_validator_rejects_missing_required_text(tmp_path: Path) -> None:
    """RegistryValidator must not admit a legal reference whose required_text is absent."""
    corpus_path = tmp_path / "corpus" / "normatives" / "html" / "rd-439-2007-art-110.html"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text(
        "<p>other legal text without the phrase</p>",
        encoding="utf-8",
    )
    _write_extracted_unit(corpus_path, anchor="a110", text="other legal text without the phrase")
    reference = _legal_reference().model_copy(
        update={
            "corpus_ref": "corpus/normatives/html/rd-439-2007-art-110.html#a110",
            "required_text": ("phrase absent from corpus",),
        },
    )
    minimal_catalogues = RegistryCatalogues(
        legal={reference.id: reference},
        sources={},
    )

    with pytest.raises(RegistryValidationError, match="corpus text missing required text"):
        RegistryValidator(minimal_catalogues, source_root=tmp_path).validate_registry(())


def test_verify_source_file_checks_manual_structure(tmp_path: Path) -> None:
    """verify_source_file must fail if a manual_pdf source reference points to an invalid manual structure."""
    pdf_path = tmp_path / "corpus" / "manuals" / "renta" / "2020" / "part1" / "source.pdf"
    pdf_path.parent.mkdir(parents=True)
    payload = b"%PDF-1.4 manual structure sample bytes"
    pdf_path.write_bytes(payload)

    source = SourceReference(
        id="aeat-renta-2020-manual-parte1",
        evidence_tier="official_source_guidance",
        authority="aeat",
        kind="manual_pdf",
        corpus_path="corpus/manuals/renta/2020/part1/source.pdf",
        sha256=hashlib.sha256(payload).hexdigest(),
        bytes=len(payload),
        retrieved_at=date(2026, 5, 6),
        source_url=f"{Settings.external_constants().aeat.domains.sede}/Manual.pdf",
        review_status="reviewed",
    )

    with pytest.raises(RegistryValidationError, match="manual structure check failed"):
        verify_source_file(tmp_path, source)

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
    section_path = (
        tmp_path / "corpus" / "manuals" / "renta" / "2020" / "part1" / "structure" / "sections" / "cap1" / "sec1.json"
    )
    section_path.parent.mkdir(parents=True)
    section_path.write_text("{corrupt json", encoding="utf-8")

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
        required_text=("Seccion 1",),
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
    _write_extracted_unit(section_path, anchor="sec1", text="Seccion 1")

    verify_legal_catalogue({reference.id: reference}, source_root=tmp_path)
