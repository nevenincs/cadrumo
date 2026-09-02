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
from .._citation_blocklist import KnownBadCitation, _fold_diacritics, find_known_bad, known_bad_citations
from .._validate import RegistryValidator
from .._validate_evidence import EvidenceValidator
from ..corpus_catalogue import verify_source_catalogue, verify_source_file
from ..errors import RegistryValidationError
from ..legal import assert_legal_ref_ids_resolve, verify_legal_catalogue
from ..schema import RegistryCatalogues
from ..schema_base import EvidenceTier, SourceCitation
from ..schema_references import LegalReference, SourceReference
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


def test_known_bad_citation_role_substrings_are_pure_ascii_after_folding() -> None:
    """Every blocklist ``role_substring`` folds to plain ASCII.

    ``find_known_bad`` folds diacritics via the shared ``core.text_fold``
    primitive (NFKD-decompose + drop combining marks), not the
    ``encode("ascii", "ignore")`` transliteration this module used to run
    inline. The two agree on every real entry -- each one is ordinary
    accented Spanish prose, and standard Spanish accented letters always
    carry a canonical combining-mark decomposition -- so this asserts the
    folded form is unsurprising for a reader who has not seen the swap.
    A registry-authored ``role_substring`` containing a codepoint with no
    ASCII-compatible decomposition (an em dash, a currency sign) would fail
    this assertion, which is the intended tripwire: it means folding no
    longer produces the same comparison key the ascii-ignore predecessor did.
    """
    for blocked in known_bad_citations():
        folded = _fold_diacritics(blocked.role_substring)
        assert folded.isascii(), (blocked.role_substring, folded)


def test_known_bad_citation_matching_preserves_non_decomposable_characters() -> None:
    """Diacritic folding no longer discards a character NFKD cannot decompose.

    This is the deliberate behaviour difference from the retired
    ``encode("ascii", "ignore")`` implementation: an em dash or currency
    sign used to vanish from the comparison text; it now survives. That
    can only ever make a match easier to find (the token is compared as a
    substring, and removing noise around it never helps), never harder --
    unlike the live-scraped click-safety guard in
    ``adapters.outbound.aeat.sede.renta_web_open_safety``, this module
    reads registry-authored TOML prose, not browser-rendered text, so it
    carries none of that guard's soft-hyphen/decorative-glyph exposure.
    """
    blocked = find_known_bad("ley", "103", "la cuota diferencial – recalculada")

    assert blocked is not None
    assert blocked.article == "103"


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


def test_verify_legal_catalogue_refuses_sidecar_symlink_outside_corpus_root(tmp_path: Path) -> None:
    """A corpus-local sidecar name cannot make external evidence authoritative."""
    corpus_path = tmp_path / "corpus" / "normatives" / "html" / "symlinked-sidecar.html"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text("<p>official source</p>", encoding="utf-8")
    external_sidecar = tmp_path.parent / "external-sidecar.extracted.json"
    external_sidecar.write_text(
        json.dumps({"units": [{"anchor": "a1", "text": "external evidence"}]}), encoding="utf-8"
    )
    sidecar = corpus_path.with_name(corpus_path.name + ".extracted.json")
    sidecar.symlink_to(external_sidecar)
    reference = _legal_reference(ref_id="rd-439-2007:art-110-sidecar-symlink").model_copy(
        update={
            "corpus_ref": "corpus/normatives/html/symlinked-sidecar.html#a1",
            "required_text": ("external evidence",),
        },
    )

    assert sidecar.is_file(), "the exploit must present an apparently valid sidecar file"
    assert sidecar.resolve() == external_sidecar.resolve()
    with pytest.raises(RegistryValidationError, match="sidecar escapes repository root"):
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


def test_verify_legal_catalogue_rejects_forbidden_text_present_in_corpus(tmp_path: Path) -> None:
    """A forbidden-text clause refuses a corpus document that still carries the named phrase.

    This is the case the clause exists for: a repealed clause surviving in a
    cited document, which no set of must-be-present phrases could express.
    """
    corpus_path = tmp_path / "corpus" / "normatives" / "html" / "rd-439-2007-art-110.html"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text(
        "<p>current text carrying the current phrase and the repealed phrase</p>",
        encoding="utf-8",
    )
    _write_extracted_unit(
        corpus_path,
        anchor="a110",
        text="current text carrying the current phrase and the repealed phrase",
    )
    reference = _legal_reference().model_copy(
        update={
            "corpus_ref": "corpus/normatives/html/rd-439-2007-art-110.html#a110",
            "required_text": ("the current phrase",),
            "forbidden_text": ("the repealed phrase",),
        },
    )

    with pytest.raises(RegistryValidationError, match="corpus text contains forbidden text"):
        verify_legal_catalogue({reference.id: reference}, source_root=tmp_path)


def test_verify_legal_catalogue_accepts_forbidden_text_genuinely_absent_from_corpus(tmp_path: Path) -> None:
    """A declared forbidden-text clause must not fire when the phrase is genuinely absent.

    The negative clause must not over-reach: a document that carries the
    required text and none of the forbidden text passes cleanly.
    """
    corpus_path = tmp_path / "corpus" / "normatives" / "html" / "rd-439-2007-art-110.html"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text("<p>current text carrying only the current phrase</p>", encoding="utf-8")
    _write_extracted_unit(corpus_path, anchor="a110", text="current text carrying only the current phrase")
    reference = _legal_reference().model_copy(
        update={
            "corpus_ref": "corpus/normatives/html/rd-439-2007-art-110.html#a110",
            "required_text": ("the current phrase",),
            "forbidden_text": ("a phrase this document never contains",),
        },
    )

    assert verify_legal_catalogue({reference.id: reference}, source_root=tmp_path) is None


def test_verify_legal_catalogue_distinguishes_missing_required_from_present_forbidden(tmp_path: Path) -> None:
    """A missing required phrase and a present forbidden phrase diagnose opposite defects.

    One failure message must never claim the other clause's defect.
    """
    corpus_path = tmp_path / "corpus" / "normatives" / "html" / "rd-439-2007-art-110.html"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text("<p>text missing the sought phrase</p>", encoding="utf-8")
    _write_extracted_unit(corpus_path, anchor="a110", text="text missing the sought phrase")
    missing_required = _legal_reference(ref_id="rd-439-2007:art-110-missing").model_copy(
        update={
            "corpus_ref": "corpus/normatives/html/rd-439-2007-art-110.html#a110",
            "required_text": ("phrase this document lacks",),
        },
    )
    present_forbidden = _legal_reference(ref_id="rd-439-2007:art-110-forbidden").model_copy(
        update={
            "corpus_ref": "corpus/normatives/html/rd-439-2007-art-110.html#a110",
            "required_text": ("text missing the sought phrase",),
            "forbidden_text": ("the sought phrase",),
        },
    )

    with pytest.raises(RegistryValidationError, match="corpus text missing required text") as missing_exc:
        verify_legal_catalogue({missing_required.id: missing_required}, source_root=tmp_path)
    with pytest.raises(RegistryValidationError, match="corpus text contains forbidden text") as forbidden_exc:
        verify_legal_catalogue({present_forbidden.id: present_forbidden}, source_root=tmp_path)

    assert "contains forbidden text" not in str(missing_exc.value)
    assert "missing required text" not in str(forbidden_exc.value)


def test_legal_reference_rejects_forbidden_text_overlapping_required_text() -> None:
    """The same phrase cannot be both mandatory and forbidden on one entry."""
    reference = _legal_reference()
    payload = reference.model_dump(mode="python")
    payload["required_text"] = ("shared phrase",)
    payload["forbidden_text"] = ("shared phrase",)

    with pytest.raises(ValidationError, match="required_text and forbidden_text must not overlap"):
        LegalReference.model_validate(payload)


def test_legal_reference_rejects_blank_forbidden_text_entry() -> None:
    """A forbidden_text entry must carry real text, mirroring required_text."""
    reference = _legal_reference()
    payload = reference.model_dump(mode="python")
    payload["forbidden_text"] = ("   ",)

    with pytest.raises(ValidationError, match="forbidden_text entries must be non-empty"):
        LegalReference.model_validate(payload)


def test_legal_reference_rejects_duplicate_forbidden_text_entries() -> None:
    """Duplicate forbidden_text entries are rejected, mirroring required_text."""
    reference = _legal_reference()
    payload = reference.model_dump(mode="python")
    payload["forbidden_text"] = ("phrase", "phrase")

    with pytest.raises(ValidationError, match="forbidden_text entries must be unique"):
        LegalReference.model_validate(payload)


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
        review_status="pending_review",
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
        evidence_tier=EvidenceTier.LEGAL_AUTHORITY,
        authority="aeat",
        kind="manual",
        corpus_ref="corpus/manuals/renta/2020/part1/structure/sections/cap1/sec1.json#sec1",
        document_id="BOE-A-2020-0000",
        permalink=f"{Settings.external_constants().aeat.domains.sede}/",
        published_at=date(2020, 3, 31),
        effective_from=date(2020, 4, 1),
        review_status="operator_reviewed",
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


def test_assert_legal_ref_ids_resolve_refuses_an_id_absent_from_the_catalogue() -> None:
    """A declared id that resolves to no catalogue entry is refused, naming the id and its subject."""
    catalogue = _catalogues().legal

    with pytest.raises(RegistryValidationError, match=r"eligibility-rule advisory.*not-a-real-provision") as exc_info:
        assert_legal_ref_ids_resolve(
            ("not-a-real-provision",),
            legal=catalogue,
            subject="eligibility-rule advisory",
        )

    assert "not-a-real-provision" in str(exc_info.value)


def test_assert_legal_ref_ids_resolve_accepts_ids_the_catalogue_carries() -> None:
    """A declared id that resolves cleanly does not fire, and passes silently."""
    catalogue = _catalogues().legal
    real_id = next(iter(catalogue))

    assert assert_legal_ref_ids_resolve((real_id,), legal=catalogue, subject="eligibility-rule advisory") is None


def test_assert_legal_ref_ids_resolve_reports_every_missing_id_at_once() -> None:
    """A multi-id declaration names every absent id in one refusal, not just the first."""
    catalogue = _catalogues().legal

    with pytest.raises(RegistryValidationError) as exc_info:
        assert_legal_ref_ids_resolve(
            (next(iter(catalogue)), "bogus-one", "bogus-two"),
            legal=catalogue,
            subject="eligibility-rule advisory",
        )

    message = str(exc_info.value)
    assert "bogus-one" in message
    assert "bogus-two" in message
