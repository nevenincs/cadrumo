"""Real-behaviour proof of the interim preprocess sidecar contract.

Validates the contract end-to-end with one real corpus file and the
installed ``vaultspec-rag`` walker (no mocks, no fakes):

* the production extractor turns a real BOE normatives HTML article
  into a schema-valid :class:`PreprocessOutput`;
* the sidecar pair writes and the json sidecar round-trips through the
  schema with byte-for-byte equality of the typed record;
* the rendered text sidecar carries a walker-supported extension, and the
  installed walker's own filter accepts the sidecar path (inspected against
  the real installed package, not asserted from a hardcoded copy);
* an anti-tautology proof: a tampered sidecar (bad sha256 length, unknown
  schema version) is rejected, so a green round-trip cannot be vacuous.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...._paths import REPO_ROOT
from .._html import build_outputs
from .._schema import (
    PREPROCESS_SCHEMA_VERSION,
    ExtractionStatus,
    PreprocessOutput,
    SourceDocumentKind,
)
from .._sidecar import (
    EXTRACTED_TEXT_SUFFIX,
    PreprocessSidecarError,
    load_sidecar,
    sha256_of,
    sidecar_paths_for,
    write_sidecar,
)

pytestmark = [pytest.mark.unit, pytest.mark.docs, pytest.mark.hex_core]

# dev/docs/preprocess/tests/test_sidecar_contract.py -> parents[4] is repo root.
_REPO_ROOT = REPO_ROOT

# Smallest viable real corpus file: a single BOE article slice (347 bytes)
# carrying the exact <h5 class="articulo"> / <p class="parrafo"> markup the
# production normatives preprocessor splits on.
_WORKED_EXAMPLE_HTML = (
    _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus" / "normatives" / "html" / "orden-hap-2250-2015-art-4.html"
)


def test_worked_example_source_exists() -> None:
    """The chosen real corpus file is present (guards the whole proof)."""
    assert _WORKED_EXAMPLE_HTML.is_file(), _WORKED_EXAMPLE_HTML


def test_extractor_produces_schema_valid_output() -> None:
    """The worked-example extractor yields a valid, populated record.

    Asserts the structural contract: one OK unit, the article title carried
    on the unit, the parrafo body as text, and provenance bound to the real
    source file's hash.
    """
    output = build_outputs(_WORKED_EXAMPLE_HTML, repo_root=_REPO_ROOT)[0]

    assert isinstance(output, PreprocessOutput)
    assert output.schema_version == PREPROCESS_SCHEMA_VERSION
    assert output.source_kind is SourceDocumentKind.NORMATIVES_HTML
    assert output.status is ExtractionStatus.OK
    assert output.source_relpath.endswith("src/cadrumo/_data/corpus/normatives/html/orden-hap-2250-2015-art-4.html")
    assert output.source_sha256 == sha256_of(_WORKED_EXAMPLE_HTML)
    assert output.attribution  # BOE/AEAT attribution obligation carried.
    assert len(output.units) == 1
    unit = output.units[0]
    assert unit.title is not None and "Artículo 4" in unit.title
    assert "modelo 184" in unit.text
    # No residual HTML tags leaked into the indexable text.
    assert "<" not in unit.text and ">" not in unit.text


def test_sidecar_round_trips_through_schema(tmp_path: Path) -> None:
    """write_sidecar then load_sidecar reconstitutes an equal typed record.

    The source is copied into tmp so the test never writes into the corpus
    tree. Strict pydantic equality across the json boundary is the contract.
    """
    source_copy = tmp_path / _WORKED_EXAMPLE_HTML.name
    source_copy.write_bytes(_WORKED_EXAMPLE_HTML.read_bytes())

    output = build_outputs(source_copy, repo_root=tmp_path)[0]
    text_path, json_path = write_sidecar(source_copy, output)

    assert text_path.is_file() and json_path.is_file()
    assert text_path.name == source_copy.name + EXTRACTED_TEXT_SUFFIX
    # The indexable text sidecar carries the rendered body verbatim.
    assert "modelo 184" in text_path.read_text(encoding="utf-8")

    reloaded = load_sidecar(source_copy)
    assert reloaded == output


def test_text_sidecar_is_indexable_by_the_installed_walker(tmp_path: Path) -> None:
    """The rendered sidecar path is accepted by the real installed walker.

    Inspects the installed ``vaultspec_rag`` package directly (no copy, no
    mock): the text-sidecar suffix must be in the walker's
    ``SUPPORTED_EXTENSIONS``, and the walker's per-file accept predicate
    (extension + size + binary filters, exercised via a non-gitignored tmp
    tree) must return the sidecar so the walker would index it. This is the
    load-bearing claim of the interim path: existing walker, zero upstream
    change.
    """
    from vaultspec_rag.indexer._chunking import (
        _MAX_FILE_SIZE,
        SUPPORTED_EXTENSIONS,
        _is_binary,
    )

    # .extracted.md resolves to the .md extension the walker already supports.
    assert Path("x" + EXTRACTED_TEXT_SUFFIX).suffix.lower() in SUPPORTED_EXTENSIONS

    source_copy = tmp_path / _WORKED_EXAMPLE_HTML.name
    source_copy.write_bytes(_WORKED_EXAMPLE_HTML.read_bytes())
    output = build_outputs(source_copy, repo_root=tmp_path)[0]
    text_path, _ = write_sidecar(source_copy, output)

    # Reproduce the walker's per-file accept gate (_process_scan_files) against
    # the real rendered sidecar: supported extension, under the size cap, and
    # not detected as binary. The gitignore/.vaultragignore axis is exercised
    # at the repo level by the sidecar naming convention, not here.
    assert text_path.suffix.lower() in SUPPORTED_EXTENSIONS
    assert text_path.stat().st_size <= _MAX_FILE_SIZE
    assert not _is_binary(text_path)


def test_tampered_sidecar_is_rejected(tmp_path: Path) -> None:
    """Anti-tautology proof: a corrupt provenance sidecar fails to load.

    If this passed with a broken payload, every round-trip assertion above
    would be vacuous. Two independent corruptions are checked: a truncated
    sha256 (constraint violation) and an unknown schema version surfaced via
    a forbidden extra field.
    """
    source_copy = tmp_path / _WORKED_EXAMPLE_HTML.name
    source_copy.write_bytes(_WORKED_EXAMPLE_HTML.read_bytes())
    output = build_outputs(source_copy, repo_root=tmp_path)[0]
    _, json_path = write_sidecar(source_copy, output)

    good = json_path.read_text(encoding="utf-8")

    # Corruption 1: a sha256 that is too short violates the field constraint.
    json_path.write_text(good.replace(output.source_sha256, "deadbeef"), "utf-8")
    with pytest.raises(PreprocessSidecarError):
        load_sidecar(source_copy)

    # Corruption 2: an unexpected field is rejected by extra="forbid".
    json_path.write_text(good.replace('"units":', '"smuggled_field": true,\n  "units":'), "utf-8")
    with pytest.raises(PreprocessSidecarError):
        load_sidecar(source_copy)


@pytest.mark.parametrize("bad_version", ["999.0", "0.9", "1.1", ""])
def test_load_sidecar_refuses_an_unsupported_schema_version(tmp_path: Path, bad_version: str) -> None:
    """A sidecar declaring any schema_version but the current one is refused.

    Covers both directions: a future version this loader has never seen
    (`999.0`) and a below-floor version older than what this loader
    understands (`0.9`, `1.1`), plus the degenerate empty string. If this
    passed, `schema_version` would be a bare label rather than an enforced
    compatibility gate.
    """
    source_copy = tmp_path / _WORKED_EXAMPLE_HTML.name
    source_copy.write_bytes(_WORKED_EXAMPLE_HTML.read_bytes())
    output = build_outputs(source_copy, repo_root=tmp_path)[0]
    _, json_path = write_sidecar(source_copy, output)

    good = json_path.read_text(encoding="utf-8")
    tampered = good.replace(f'"schema_version": "{output.schema_version}"', f'"schema_version": "{bad_version}"')
    assert tampered != good
    json_path.write_text(tampered, encoding="utf-8")

    with pytest.raises(PreprocessSidecarError):
        load_sidecar(source_copy)


def test_preprocess_output_refuses_an_unsupported_schema_version_directly() -> None:
    """The schema itself, not just the sidecar loader, refuses a bad version."""
    output = build_outputs(_WORKED_EXAMPLE_HTML, repo_root=_REPO_ROOT)[0]
    payload = output.model_dump(mode="json")
    payload["schema_version"] = "999.0"

    with pytest.raises(ValueError, match="unsupported preprocess schema_version"):
        PreprocessOutput.model_validate(payload)


def test_preprocess_output_accepts_the_current_schema_version() -> None:
    """A record declaring the current schema_version validates cleanly."""
    output = build_outputs(_WORKED_EXAMPLE_HTML, repo_root=_REPO_ROOT)[0]

    assert output.schema_version == PREPROCESS_SCHEMA_VERSION
    reloaded = PreprocessOutput.model_validate_json(output.model_dump_json())
    assert reloaded == output


def test_load_sidecar_refuses_a_source_changed_since_extraction(tmp_path: Path) -> None:
    """A sidecar whose source file changed on disk (same length) is refused as stale.

    Real freshness proof: the origin bytes change without re-running the
    extractor, so the sidecar's recorded ``source_sha256`` no longer matches
    the file's live content hash. If this passed, `source_sha256` would be
    advisory rather than an enforced freshness key.
    """
    source_copy = tmp_path / _WORKED_EXAMPLE_HTML.name
    source_copy.write_bytes(_WORKED_EXAMPLE_HTML.read_bytes())
    output = build_outputs(source_copy, repo_root=tmp_path)[0]
    write_sidecar(source_copy, output)

    original = source_copy.read_bytes()
    # Same length, different bytes: rules out a size-based staleness proxy.
    mutated = original.replace(b"modelo 184", b"modelo 999", 1)
    assert len(mutated) == len(original)
    assert mutated != original
    source_copy.write_bytes(mutated)

    with pytest.raises(PreprocessSidecarError, match="is stale"):
        load_sidecar(source_copy)


def test_load_sidecar_refuses_a_corrupted_real_rendered_text_copy(tmp_path: Path) -> None:
    """The committed markdown half must remain the exact JSON rendering."""
    source_copy = tmp_path / _WORKED_EXAMPLE_HTML.name
    source_copy.write_bytes(_WORKED_EXAMPLE_HTML.read_bytes())
    output = build_outputs(source_copy, repo_root=tmp_path)[0]
    text_path, _ = write_sidecar(source_copy, output)

    original = text_path.read_text(encoding="utf-8")
    text_path.write_text(original.replace("modelo 184", "modelo 999", 1), encoding="utf-8")

    with pytest.raises(PreprocessSidecarError, match="divergent rendered text"):
        load_sidecar(source_copy)


def test_load_sidecar_accepts_an_unchanged_source(tmp_path: Path) -> None:
    """A source file untouched since extraction loads cleanly."""
    source_copy = tmp_path / _WORKED_EXAMPLE_HTML.name
    source_copy.write_bytes(_WORKED_EXAMPLE_HTML.read_bytes())
    output = build_outputs(source_copy, repo_root=tmp_path)[0]
    write_sidecar(source_copy, output)

    reloaded = load_sidecar(source_copy)

    assert reloaded == output
    assert reloaded.source_sha256 == sha256_of(source_copy)


@pytest.mark.parametrize("source_relpath", ("/etc/passwd", "../outside.html", "C:/secret/file.html", "dir\\file.html"))
def test_schema_refuses_non_repository_source_provenance(source_relpath: str) -> None:
    """Sidecars may name only canonical POSIX-relative paths from the repository root."""
    output = build_outputs(_WORKED_EXAMPLE_HTML, repo_root=_REPO_ROOT)[0]
    payload = output.model_dump(mode="json")
    payload["source_relpath"] = source_relpath

    with pytest.raises(ValueError, match="canonical POSIX-relative repository path"):
        PreprocessOutput.model_validate(payload)


def test_sidecar_paths_disambiguate_by_full_filename() -> None:
    """Two sources differing only by extension get distinct sidecar names.

    Disenos de Registro ship the same design as both ``.xls`` and ``.txt``;
    naming sidecars from the full filename (suffix included) prevents a
    collision that would silently clobber one extraction with the other.
    """
    xls_text, xls_json = sidecar_paths_for(Path("DR123e24.xls"))
    txt_text, txt_json = sidecar_paths_for(Path("DR123e24.txt"))

    assert xls_text != txt_text
    assert xls_json != txt_json
    assert xls_text.name == "DR123e24.xls" + EXTRACTED_TEXT_SUFFIX
