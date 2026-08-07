"""Tree-wide freshness proof for every committed corpus sidecar.

``load_sidecar`` already refuses a sidecar whose recorded ``source_sha256``
no longer matches its origin file, so the freshness *mechanism* has been in
place all along - but nothing ever ran it across the committed corpus. A
sidecar regenerated from an older revision of its source therefore survived
indefinitely, serving truncated text to every reader while looking complete.

That is worse than a missing sidecar, which announces itself. The real
instance: ``rd-439-2007-art-95.html`` gained apartados 2 and 3 (RIRPF art.
95.2.a, the clause *defining* what an actividad profesional is) without its
sidecars being regenerated. Both derivatives jumped from apartado 1 to
apartado 4, and because they are the ergonomic read, a grounding pass
concluded the corpus did not define the professional boundary at all and
wrote that conclusion into a docstring for the next reader to inherit.

The sweep below closes the gap: every committed sidecar is checked against
the live bytes of the source it names, so an edited source with a stale
derivative fails here rather than silently misinforming a grounding pass.

Two traps this gate has to route around, both real:

* **Multi-part sources are not addressable by source path.** A source whose
  units exceed the per-sidecar byte budget writes ``<file>.part-N.extracted.json``
  and no base ``<file>.extracted.json``, so ``load_sidecar(source)`` would
  report it missing. The sweep therefore keys on the sidecar and resolves the
  origin through the record's own ``source_relpath``, mirroring
  ``load_sidecar``'s freshness clause rather than calling it.
  :func:`test_the_freshness_predicate_matches_the_production_loader` pins the
  two together so this copy cannot drift from the loader it mirrors.
* **The glob is shared.** Two curated ``units``-only overlay files
  (``.../renta/2025/*/source.pdf.extracted.md.extracted.json``) match
  ``*.extracted.json`` but are hand-authored augmentations, not extractor
  output, and carry no provenance fields at all. They are excluded by
  provenance shape, never by filename.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .._html import build_outputs
from .._schema import PreprocessOutput
from .._sidecar import (
    EXTRACTED_JSON_SUFFIX,
    PreprocessSidecarError,
    load_sidecar,
    sha256_of,
    write_sidecar,
)

pytestmark = [pytest.mark.unit, pytest.mark.docs, pytest.mark.hex_core]

# dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py -> parents[4] is repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_CORPUS_ROOT = _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus"

# A single BOE article slice, small and single-part: the anti-tautology proof
# needs a source whose sidecar pair is addressable by source path.
_WORKED_EXAMPLE_HTML = _CORPUS_ROOT / "normatives" / "html" / "orden-hap-2250-2015-art-4.html"

# The sweep is meaningless if discovery silently returns nothing, so it asserts
# a floor. Set well below the ~568 sidecars committed today: this guards against
# a broken glob or a moved corpus root, not against the corpus shrinking.
_MINIMUM_EXPECTED_SIDECARS = 400


def _provenance_bearing_sidecars() -> list[tuple[Path, PreprocessOutput]]:
    """Return every committed sidecar that claims extractor provenance.

    A file matching the sidecar glob but carrying no provenance is a curated
    overlay rather than extractor output; it makes no freshness claim, so
    there is nothing here to verify. Excluding by SHAPE rather than by
    filename means a future overlay is handled without an allowlist.
    """
    found: list[tuple[Path, PreprocessOutput]] = []
    for json_path in sorted(_CORPUS_ROOT.rglob(f"*{EXTRACTED_JSON_SUFFIX}")):
        raw = json_path.read_text(encoding="utf-8")
        if "source_relpath" not in json.loads(raw):
            continue
        found.append((json_path, PreprocessOutput.model_validate_json(raw)))
    return found


def _staleness_reason(json_path: Path, output: PreprocessOutput, *, repo_root: Path = _REPO_ROOT) -> str | None:
    """Return why ``output`` is stale against its live source, or ``None``.

    Mirrors the freshness clause of :func:`load_sidecar` for sidecars that
    cannot be addressed by source path (see the module docstring on
    multi-part naming).

    ``repo_root`` is a parameter rather than the module constant so the
    mutation proof can drive THIS predicate against a tmp-tree source. A
    sweep whose own predicate is never made to fire is an instrument nobody
    checked, which is the failure this whole module exists to catch.
    """
    source = repo_root / output.source_relpath
    if not source.is_file():
        return f"{json_path.name}: names a source that does not exist ({output.source_relpath})"
    live = sha256_of(source)
    if live != output.source_sha256:
        return (
            f"{output.source_relpath}: sidecar records source_sha256={output.source_sha256} "
            f"but the source now hashes to {live} - regenerate the sidecar pair"
        )
    return None


def test_sidecar_discovery_finds_the_committed_corpus() -> None:
    """Discovery reaches the corpus (a silently empty sweep would pass vacuously)."""
    assert _CORPUS_ROOT.is_dir(), _CORPUS_ROOT
    assert len(_provenance_bearing_sidecars()) >= _MINIMUM_EXPECTED_SIDECARS


def test_every_committed_sidecar_is_fresh_against_its_source() -> None:
    """No committed sidecar was left behind by an edit to the file it describes.

    The failure this catches is invisible by construction: a stale derivative
    reads as complete prose, so nothing downstream distinguishes it from the
    current text. Reported as the full list rather than the first offender,
    because a regeneration sweep wants the whole set in one pass.
    """
    stale = [
        reason
        for json_path, output in _provenance_bearing_sidecars()
        if (reason := _staleness_reason(json_path, output))
    ]

    assert not stale, "stale corpus sidecars (source changed since extraction):\n" + "\n".join(stale)


def test_the_freshness_predicate_matches_the_production_loader(tmp_path: Path) -> None:
    """A source edited after extraction is flagged here AND refused by ``load_sidecar``.

    Anti-tautology and anti-drift in one: the mutation is same-length, so a
    size-based proxy would miss it, and asserting both surfaces react pins this
    module's mirrored predicate to the loader it mirrors. If the loader's
    freshness rule ever changes, this fails rather than quietly diverging.
    """
    source_copy = tmp_path / _WORKED_EXAMPLE_HTML.name
    source_copy.write_bytes(_WORKED_EXAMPLE_HTML.read_bytes())
    output = build_outputs(source_copy, repo_root=tmp_path)[0]
    write_sidecar(source_copy, output)
    json_path = source_copy.with_name(source_copy.name + EXTRACTED_JSON_SUFFIX)

    original = source_copy.read_bytes()
    mutated = original.replace(b"modelo 184", b"modelo 999", 1)
    assert len(mutated) == len(original), "the mutation must not change length"
    assert mutated != original, "the mutation must actually change the bytes"
    source_copy.write_bytes(mutated)

    # The sweep's own predicate must fire on the mutated source, driven against
    # the tmp tree the sidecar's relpath is recorded against.
    reason = _staleness_reason(json_path, output, repo_root=tmp_path)
    assert reason is not None, "the sweep predicate failed to flag a genuinely stale sidecar"
    assert "regenerate the sidecar pair" in reason

    # ...and the production loader agrees, which is what pins the two together.
    with pytest.raises(PreprocessSidecarError, match="is stale"):
        load_sidecar(source_copy)


def test_the_sweep_passes_only_because_sources_are_unchanged() -> None:
    """An unmodified source hashes to exactly what its sidecar recorded.

    Proves the green sweep above is load-bearing rather than an artefact of a
    predicate that can never fire: the same predicate returns ``None`` here
    only because the recorded and live hashes genuinely agree.
    """
    sidecars = _provenance_bearing_sidecars()
    json_path, output = sidecars[0]

    assert _staleness_reason(json_path, output) is None
    assert sha256_of(_REPO_ROOT / output.source_relpath) == output.source_sha256
