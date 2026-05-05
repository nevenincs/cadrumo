"""Tests for registry source and legal catalogue verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from aeat.core.paths import PROJECT_ROOT

from ._citation_blocklist import _KNOWN_BAD_CITATIONS, find_known_bad
from ._errors import RegistryValidationError
from ._legal import verify_legal_catalogue
from ._loader import load_registry_tree
from ._schema import LegalReference, RegistryCatalogues, SourceReference
from ._sources import verify_source_catalogue, verify_source_file
from ._validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _catalogues() -> RegistryCatalogues:
    _, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    return catalogues


def test_committed_registry_tree_has_coherent_shared_catalogues() -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")

    assert modelos
    assert catalogues.legal
    assert catalogues.sources
    verify_legal_catalogue(catalogues.legal, source_root=PROJECT_ROOT)
    verify_source_catalogue(PROJECT_ROOT, catalogues.sources)
    validator = RegistryValidator(catalogues, source_root=PROJECT_ROOT)
    for modelo in modelos:
        validator.validate_modelo(modelo)


def test_committed_aeat_record_design_sources_match_corpus_manifests() -> None:
    _, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    checked: list[str] = []

    for source in catalogues.sources.values():
        path = Path(source.corpus_path)
        parts = path.parts
        if len(parts) < 5 or parts[:3] != ("corpus", "aeat_official", "disenos_registro"):
            continue
        modelo_dir = PROJECT_ROOT.joinpath(*parts[:4])
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
        }
    )


def _source_reference(path: str, payload: bytes) -> SourceReference:
    source = next(iter(_catalogues().sources.values()))
    return source.model_copy(
        update={
            "corpus_path": path,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
    )


def test_verify_source_file_checks_hash_and_size(tmp_path: Path) -> None:
    payload = b"official"
    source_path = tmp_path / "corpus" / "source.xlsx"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(payload)

    verify_source_file(tmp_path, _source_reference("corpus/source.xlsx", payload))


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

    verify_source_catalogue(tmp_path, {"aeat-source": _source_reference("corpus/source.xlsx", payload)})


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
def test_verify_legal_catalogue_rejects_every_blocklisted_role(blocked) -> None:
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

    verify_legal_catalogue({reference.id: reference})


def test_verify_legal_catalogue_checks_required_local_corpus_text(tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus" / "normatives" / "rd-439-2007.json"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text('{"articulos": [{"numero": "110", "text_es": "other legal text"}]}', encoding="utf-8")
    reference = _legal_reference().model_copy(
        update={
            "corpus_ref": "corpus/normatives/rd-439-2007.json#art-110",
            "required_text": ("20 por ciento del rendimiento neto",),
        }
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
        }
    )

    verify_legal_catalogue({reference.id: reference}, source_root=tmp_path)
