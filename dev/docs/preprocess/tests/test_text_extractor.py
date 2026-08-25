"""Real-behaviour proof of the unsupported-text-extension extractor.

Exercises real corpus text-tail files through the production extractor (no
mocks):

* a real Modelo 100 ``.properties`` diccionario (cp1252-encoded) decodes to
  readable text with accented Spanish intact, proving the encoding fallback;
* a real Modelo 349 ``.txt`` instruction file extracts to readable text;
* attribution resolves from the sibling Diseno manifest where catalogued and
  falls back to the standing attribution otherwise;
* the written text sidecar carries a walker-supported extension and the
  installed walker's own filter accepts it (real installed package, no mock);
* anti-tautology: a tampered provenance sidecar is rejected.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...._paths import REPO_ROOT
from .._schema import (
    ExtractionStatus,
    PreprocessOutput,
    SourceDocumentKind,
)
from .._sidecar import (
    EXTRACTED_TEXT_SUFFIX,
    PreprocessSidecarError,
    load_sidecar,
    sidecar_paths_for,
)
from .._text import (
    SUPPORTED_TEXT_EXTENSIONS,
    TEXT_EXTRACTOR_ID,
    build_outputs,
    extract_text_file,
)

pytestmark = [pytest.mark.unit, pytest.mark.docs, pytest.mark.hex_core]

# dev/docs/preprocess/tests/test_text_extractor.py -> parents[4] is repo root.
_REPO_ROOT = REPO_ROOT
_CORPUS = _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus"

# A real Modelo 100 .properties diccionario (cp1252) with a catalogued
# manifest artefact, and a real Modelo 349 .txt instruction (no manifest).
_PROPERTIES = (
    _CORPUS
    / "aeat_official"
    / "disenos_registro"
    / "modelo_100"
    / "files"
    / "01-100-diccionario-declaracion-individual-ejercicio-2025-actualizado-14-04-2026-416-kb-otros-fi.properties"
)
_TXT = _CORPUS / "aeat_official" / "instructions" / "modelo_349" / "files" / "instr_mod_349.txt"


def test_target_files_exist() -> None:
    """The real corpus text-tail files are present (guards the proof)."""
    assert _PROPERTIES.is_file(), _PROPERTIES
    assert _TXT.is_file(), _TXT


def test_passthrough_is_retired_now_walker_covers_the_text_tail() -> None:
    """The walker subsumed the text tail, so the passthrough sweep is retired.

    The interim passthrough covered the walker-invisible tail (``.txt`` /
    ``.xml`` / ``.xsd`` / ``.properties``). The resident vaultspec-rag walker
    now natively indexes all four raw - the documented retirement trigger - so
    the sweep set is empty (nothing swept, no raw-vs-sidecar double-index) and
    the whole former tail is walker-covered. If the walker ever DROPS one of
    the four, the completeness assertion fails and the sweep must re-cover it
    (and regenerate its sidecars).
    """
    from vaultspec_rag.indexer._chunking import SUPPORTED_EXTENSIONS

    former_tail = {".txt", ".xml", ".xsd", ".properties"}
    # Retired: nothing swept, so nothing overlaps the walker's raw index.
    assert frozenset() == SUPPORTED_TEXT_EXTENSIONS
    for ext in SUPPORTED_TEXT_EXTENSIONS:
        assert ext not in SUPPORTED_EXTENSIONS, ext
    # Completeness: the whole former tail is now walker-covered (the reason the
    # passthrough is retired); catches a walker regression that drops one.
    assert former_tail <= SUPPORTED_EXTENSIONS


def test_properties_decodes_cp1252_with_accents() -> None:
    """The cp1252 .properties diccionario decodes to readable accented text.

    Asserts the casilla-path-to-description grounding the diccionario carries,
    with accents intact (proving the UTF-8 -> cp1252 fallback ran).
    """
    outputs = build_outputs(_PROPERTIES, repo_root=_REPO_ROOT)

    assert len(outputs) == 1
    output = outputs[0]
    assert isinstance(output, PreprocessOutput)
    assert output.source_kind is SourceDocumentKind.UNSUPPORTED_TEXT
    assert output.status is ExtractionStatus.OK
    assert output.preprocessor_id == TEXT_EXTRACTOR_ID
    assert output.source_relpath.endswith(".properties")

    text = output.units[0].text
    # The diccionario key=value grounding rows are present verbatim.
    assert "DPNIF_D=" in text
    assert "Primer Declarante: NIF" in text
    # A cp1252-encoded accented description decodes to the real characters
    # (declaracion individual -> with the i-acute) rather than mojibake.
    assert "declaración individual" in text
    assert "�" not in text  # no replacement char from a bad decode

    # Catalogued in the Diseno manifest, so attribution pins the official URL.
    assert "AEAT" in output.attribution
    assert "agenciatributaria.gob.es" in output.attribution


def test_txt_extracts_readable_text_with_fallback_attribution() -> None:
    """A manifest-less .txt extracts readable text with base attribution."""
    output = build_outputs(_TXT, repo_root=_REPO_ROOT)[0]
    assert output.status is ExtractionStatus.OK
    text = output.units[0].text
    assert "INSTRUCCIONES DEL MODELO 349" in text
    # No manifest for this file, so the standing attribution (no URL).
    assert "AEAT" in output.attribution
    assert "Official source:" not in output.attribution


def test_sidecar_round_trips_and_is_walker_indexable(tmp_path: Path) -> None:
    """Written sidecar reloads equal and the .md is accepted by the walker.

    Copies the file into tmp so no sidecar lands in the corpus tree. Inspects
    the real installed walker (no mock): the rendered .md must pass the
    extension, size-cap, and binary filters.
    """
    from vaultspec_rag.indexer._chunking import (
        _MAX_FILE_SIZE,
        SUPPORTED_EXTENSIONS,
        _is_binary,
    )

    source_copy = tmp_path / _TXT.name
    source_copy.write_bytes(_TXT.read_bytes())

    written = extract_text_file(source_copy, repo_root=tmp_path)
    assert len(written) == 1
    text_path = written[0]
    assert text_path.name == source_copy.name + EXTRACTED_TEXT_SUFFIX

    reloaded = load_sidecar(source_copy)
    assert reloaded.source_kind is SourceDocumentKind.UNSUPPORTED_TEXT
    assert reloaded.status is ExtractionStatus.OK
    assert reloaded.units

    assert text_path.suffix.lower() in SUPPORTED_EXTENSIONS
    assert text_path.stat().st_size <= _MAX_FILE_SIZE
    assert not _is_binary(text_path)


def test_tampered_sidecar_is_rejected(tmp_path: Path) -> None:
    """Anti-tautology: a corrupt provenance sidecar fails to load.

    If this passed with a broken payload the round-trip assertions would be
    vacuous. A truncated sha256 violates the field constraint.
    """
    source_copy = tmp_path / _TXT.name
    source_copy.write_bytes(_TXT.read_bytes())
    extract_text_file(source_copy, repo_root=tmp_path)

    _, json_path = sidecar_paths_for(source_copy)
    good = json_path.read_text(encoding="utf-8")
    output = load_sidecar(source_copy)
    json_path.write_text(good.replace(output.source_sha256, "deadbeef"), "utf-8")
    with pytest.raises(PreprocessSidecarError):
        load_sidecar(source_copy)
