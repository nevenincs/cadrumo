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
  report it missing. The sweep therefore keys on the sidecar and delegates
  its declared-origin validation to :func:`validate_sidecar`.
* **The glob is shared.** Two curated ``units``-only overlay files
  (``.../renta/2025/*/source.pdf.extracted.md.extracted.json``) match
  ``*.extracted.json`` but are hand-authored augmentations, not extractor
  output, and carry no provenance fields at all. They are excluded by
  provenance shape, never by filename.

Freshness alone is not enough, because it is checked against the source the
record *names* rather than the one it sits *beside*. A sidecar written next
to payload A while declaring payload B reconciles perfectly against B - so
the sweep goes green while :func:`load_sidecar` (which hashes A) refuses it.
That is the stale-derivative failure wearing a different mask: a mis-stamped
locator instead of a mis-stamped digest, with the same downstream symptom of
grounding text that does not belong to the file it accompanies.
:func:`validate_sidecar` closes it by requiring the declared locator to equal
the sidecar's own position, and the sweep reports both dimensions together.

Three edge cases are handled explicitly rather than by accident:

* **A missing payload** - the declared source no longer exists - is reported
  as its own reason rather than crashing the hash.
* **A sidecar that will not validate** (a blank or malformed
  ``source_sha256``, an unsupported ``schema_version``) is reported as a
  named finding naming the file, not raised as a bare ``ValidationError``
  from inside discovery with nothing to identify the offender.
* **A multi-part sidecar** resolves to its base payload by stripping the
  ``.part-N`` infix, so the locality check admits the naming scheme
  :func:`part_stand_in_path` produces instead of false-firing on all of it.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path, PurePosixPath
from typing import Final

import pytest

from cadrumo.core.directory_scan import scan_directory
from dev._paths import REPO_ROOT, UTF_8
from dev.corpus.extract_corpus_sidecars import check_all as check_corpus_sidecars
from dev.corpus.extract_corpus_sidecars import extract_all as extract_corpus_sidecars

from ..normatives_html import build_outputs
from ..parts import part_stand_in_path
from ..schema import PreprocessOutput
from ..sidecar import (
    EXTRACTED_JSON_SUFFIX,
    PreprocessSidecarError,
    validate_sidecar,
    write_sidecar,
)

pytestmark = [pytest.mark.unit, pytest.mark.docs, pytest.mark.hex_core]

# dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py -> parents[4] is repo root.
_REPO_ROOT = REPO_ROOT
_CORPUS_ROOT = _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus"

# A single BOE article slice, small and single-part: the anti-tautology proof
# needs a source whose sidecar pair is addressable by source path.
_WORKED_EXAMPLE_HTML = _CORPUS_ROOT / "normatives" / "html" / "orden-hap-2250-2015-art-4.html"

# The sweep is meaningless if discovery silently returns nothing, so it asserts
# a floor. Set well below the 707 sidecars committed today: this guards against
# a broken glob or a moved corpus root, not against the corpus shrinking.
_MINIMUM_EXPECTED_SIDECARS = 400

#: Per-origin-kind floors over the same population. This corpus is NOT one
#: kind: its sidecars derive from five source families with three different
#: extractors behind them (``normatives_html``, ``_pdf``, ``workbook``).
#: Live: ``.html`` 470, ``.pdf`` 104, ``.xlsx`` 90, ``.xls`` 41, ``.xlsm`` 2.
#:
#: A floor over the UNION cannot see one family leave. The total is dominated
#: by ``.html``, so against 707 sidecars a floor of 400 leaves 307 of slack --
#: more than the other four families put together (237). Every one of them
#: could drop to zero, individually or all at once, and the total would still
#: read 470 and pass.
#:
#: That is not merely an uncounted family, it is an unchecked one: the three
#: sweeps below iterate this same population, so a vanished ``.pdf`` family
#: would have freshness, loadability and locality all reporting a clean corpus
#: having never opened a PDF.
#:
#: ``.xls`` is why this is not hypothetical. It is one of the six declared
#: preprocess rules, yet it appears in neither enumeration in ``test_hook.py``
#: -- the smallest committed ``.xls`` source carries no sidecar, so the
#: per-kind parity test cannot cover it -- and nothing else in the tree pins
#: it. Its 41 sidecars are the one family that could vanish with every other
#: gate still green.
#:
#: Each floor sits near two thirds of its live figure, so ordinary corpus
#: movement never reds the gate while a family losing most of itself always
#: does. ``.xlsm`` has two members; one is the floor that still means present.
_MINIMUM_SIDECARS_BY_ORIGIN_KIND: Final[dict[str, int]] = {
    ".html": 300,
    ".pdf": 70,
    ".xls": 27,
    ".xlsm": 1,
    ".xlsx": 60,
}

_UTF_8: Final[str] = UTF_8


def _origin_kind(output: PreprocessOutput) -> str:
    """Return the source family a sidecar derives from, as a lowercase suffix.

    Read from the record's declared ``source_relpath`` rather than from the
    sidecar filename, so the ``.part-N`` infix cannot be mistaken for an
    extension. Locality is gated separately, so the declared locator is the
    right authority for which extractor produced this record.
    """
    return PurePosixPath(output.source_relpath).suffix.lower()


def _provenance_bearing_sidecars(
    corpus_root: Path = _CORPUS_ROOT,
    *,
    repo_root: Path = _REPO_ROOT,
) -> tuple[list[tuple[Path, PreprocessOutput]], list[str]]:
    """Return validated provenance-bearing sidecars and named failures.

    A file matching the sidecar glob but carrying no provenance is a curated
    overlay rather than extractor output; it makes no freshness claim, so
    there is nothing here to verify. Excluding by SHAPE rather than by
    filename means a future overlay is handled without an allowlist.

    Schema, locality, source-digest, and rendered-text validation belong to
    :func:`validate_sidecar`; this discovery function only distinguishes
    provenance-bearing extractor output from curated overlays. A claimed
    record that fails the shared validator is a named finding rather than a
    crash, so the sweep reports every offender in one pass.
    """
    found: list[tuple[Path, PreprocessOutput]] = []
    unloadable: list[str] = []
    for json_path in scan_directory(corpus_root, pattern=f"*{EXTRACTED_JSON_SUFFIX}", recursive=True):
        raw = json_path.read_text(encoding=_UTF_8)
        try:
            document = json.loads(raw)
        except json.JSONDecodeError as exc:
            unloadable.append(f"{json_path.name}: is not valid JSON ({exc})")
            continue
        if "source_relpath" not in document:
            continue
        try:
            found.append((json_path, validate_sidecar(json_path, repo_root=repo_root)))
        except PreprocessSidecarError as exc:
            unloadable.append(f"{json_path.name}: {exc}")
    return found, unloadable


def test_sidecar_discovery_finds_the_committed_corpus() -> None:
    """Discovery reaches the corpus, and reaches every source family in it.

    The total is the anti-vacuity floor; the per-kind floors are what make it
    mean anything. A floor over the union of five extractor families cannot
    see one family leave, and the three sweeps below inherit that blindness
    exactly, because they iterate the population this test measures.
    """
    assert _CORPUS_ROOT.is_dir(), _CORPUS_ROOT
    found, _ = _provenance_bearing_sidecars()
    assert len(found) >= _MINIMUM_EXPECTED_SIDECARS

    live = collections.Counter(_origin_kind(output) for _, output in found)
    for kind, floor in _MINIMUM_SIDECARS_BY_ORIGIN_KIND.items():
        assert live[kind] >= floor, (
            f"only {live[kind]} committed sidecar(s) derive from a {kind} source, against a floor "
            f"of {floor}; the freshness, loadability and locality sweeps below iterate this same "
            f"population, so each would report a clean corpus without having read a {kind} at all"
        )


def test_owner_check_rejects_an_enrolled_source_without_sidecars(tmp_path: Path) -> None:
    """A newly enrolled source cannot read as fresh before it has a pair."""
    corpus = tmp_path / "corpus"
    source = corpus / "normatives" / "html" / "new-norm.html"
    source.parent.mkdir(parents=True)
    source.write_text(
        '<div id="textoxslt"><h5 class="articulo">Artículo 1.</h5><p>Texto.</p></div>',
        encoding="utf-8",
        newline="\n",
    )

    failures = check_corpus_sidecars(corpus_root=corpus, repo_root=tmp_path)
    assert any(failure.startswith("MISSING ") for failure in failures)

    assert extract_corpus_sidecars(corpus_root=corpus, repo_root=tmp_path) == 0
    assert check_corpus_sidecars(corpus_root=corpus, repo_root=tmp_path) == []


def test_the_per_kind_floors_name_exactly_the_families_the_corpus_ships() -> None:
    """Every source family in the corpus carries a floor, and every floor names one.

    The floors above are checked one row at a time, and that loop walks the
    ROSTER: it asks whether each listed family cleared its floor, never whether
    the list is the corpus. Its verdict is therefore independent of membership
    in either direction. Enumerated exhaustively over the 32 subsets of the five
    listed families, against the corpus as committed and against a corpus
    carrying a sixth family, the floor loop passes all 64 -- including the empty
    roster, which checks nothing at all and reports a corpus reaching every
    family in it.

    So a sixth extractor family landing in ``_data/corpus`` is not merely
    unfloored, it is unmeasured: the freshness, loadability and locality sweeps
    iterate the population this gate measures, and each would report a clean
    corpus having never opened a member of the new family, exactly as the
    per-kind floors were introduced to prevent for the five that exist.

    The two sides are independent roots. The floors are hand-authored in this
    module; the families are derived from the committed corpus through the
    production ``PreprocessOutput`` schema and the record's own declared
    ``source_relpath``. Neither can be edited into agreement with the other.

    The reverse direction -- a floor naming a family the corpus no longer ships
    -- is already caught by the loop above, but only incidentally, and only
    while every floor stays at one or more: a family at zero live sidecars
    clears a floor of zero. That is asserted here rather than assumed, which is
    what makes the incidental coverage a fact.
    """
    found, _ = _provenance_bearing_sidecars()
    live = collections.Counter(_origin_kind(output) for _, output in found)

    unfloored = sorted(set(live) - set(_MINIMUM_SIDECARS_BY_ORIGIN_KIND))
    assert not unfloored, (
        f"the corpus ships source families with no floor: {unfloored}; a family nobody "
        "listed is never asserted non-empty, and the sweeps that iterate this population "
        "would read clean having never opened one"
    )

    absent = sorted(set(_MINIMUM_SIDECARS_BY_ORIGIN_KIND) - set(live))
    assert not absent, (
        f"these families carry a floor but ship no sidecar at all: {absent}; a floor over "
        "a family the corpus no longer contains measures nothing"
    )

    vacuous = sorted(kind for kind, floor in _MINIMUM_SIDECARS_BY_ORIGIN_KIND.items() if floor < 1)
    assert not vacuous, (
        f"these floors are satisfied by an absent family: {vacuous}; a floor of zero is what "
        "would let a family leave the corpus without reddening the loop above"
    )


def test_every_committed_sidecar_passes_shared_generic_validation() -> None:
    """Every extractor sidecar passes the owner's generic contract.

    The shared validator checks the strict schema, repository containment,
    locality, source digest, and byte-exact rendered text. This sweep adds
    corpus discovery and family floors; it must not reproduce those checks.
    """
    _, unloadable = _provenance_bearing_sidecars()

    assert not unloadable, "invalid corpus sidecars:\n" + "\n".join(unloadable)


def test_shared_validator_rejects_a_source_changed_since_extraction(tmp_path: Path) -> None:
    """A same-length source edit is rejected by the shared validator."""
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

    with pytest.raises(PreprocessSidecarError, match="is stale"):
        validate_sidecar(json_path, repo_root=tmp_path)


def test_shared_validator_rejects_a_sidecar_not_local_to_its_source(tmp_path: Path) -> None:
    """A sidecar beside one payload but naming another is refused."""
    decoy = tmp_path / "decoy.html"
    decoy.write_bytes(_WORKED_EXAMPLE_HTML.read_bytes())
    decoy_output = build_outputs(decoy, repo_root=tmp_path)[0]

    neighbour = tmp_path / _WORKED_EXAMPLE_HTML.name
    neighbour.write_bytes(_WORKED_EXAMPLE_HTML.read_bytes() + b"<!-- differs -->")

    # The sidecar pair is written beside ``neighbour`` but carries ``decoy``'s
    # record: exactly the mis-stamped-locator shape.
    write_sidecar(neighbour, decoy_output)
    json_path = neighbour.with_name(neighbour.name + EXTRACTED_JSON_SUFFIX)

    with pytest.raises(PreprocessSidecarError, match="not local to its declared source"):
        validate_sidecar(json_path, repo_root=tmp_path)


def test_shared_validator_accepts_a_multi_part_sidecar(tmp_path: Path) -> None:
    """The shared validator strips ``.part-N`` when resolving locality."""
    source = tmp_path / _WORKED_EXAMPLE_HTML.name
    source.write_bytes(_WORKED_EXAMPLE_HTML.read_bytes())
    output = build_outputs(source, repo_root=tmp_path)[0]
    stand_in = part_stand_in_path(source, 1, 2)
    write_sidecar(stand_in, output)
    json_path = stand_in.with_name(stand_in.name + EXTRACTED_JSON_SUFFIX)

    assert validate_sidecar(json_path, repo_root=tmp_path) == output


def test_shared_validator_reports_a_missing_payload(tmp_path: Path) -> None:
    """A declared source that no longer exists is a named refusal, not a hash error."""
    source = tmp_path / _WORKED_EXAMPLE_HTML.name
    source.write_bytes(_WORKED_EXAMPLE_HTML.read_bytes())
    output = build_outputs(source, repo_root=tmp_path)[0]
    write_sidecar(source, output)
    json_path = source.with_name(source.name + EXTRACTED_JSON_SUFFIX)
    source.unlink()

    with pytest.raises(PreprocessSidecarError, match="names a missing source"):
        validate_sidecar(json_path, repo_root=tmp_path)


def test_a_provenance_claiming_sidecar_that_will_not_validate_is_reported(tmp_path: Path) -> None:
    """A forged or corrupt provenance record surfaces as a finding naming the file.

    Discovery must not raise here: a bare ``ValidationError`` escaping the
    walk names no file and aborts the sweep at the first offender, so the
    remaining corpus goes unchecked and reads as untested rather than green.
    """
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    source = corpus / _WORKED_EXAMPLE_HTML.name
    source.write_bytes(_WORKED_EXAMPLE_HTML.read_bytes())
    output = build_outputs(source, repo_root=tmp_path)[0]
    write_sidecar(source, output)
    json_path = source.with_name(source.name + EXTRACTED_JSON_SUFFIX)

    # Positive control: the untouched tree yields one loadable record and no findings.
    found, unloadable = _provenance_bearing_sidecars(corpus_root=corpus, repo_root=tmp_path)
    assert len(found) == 1
    assert unloadable == []

    document = json.loads(json_path.read_text(encoding=_UTF_8))
    document["source_sha256"] = ""
    json_path.write_text(json.dumps(document), encoding=_UTF_8)

    found, unloadable = _provenance_bearing_sidecars(corpus_root=corpus, repo_root=tmp_path)
    assert found == []
    assert len(unloadable) == 1
    assert "sidecar failed to load or validate" in unloadable[0]
    assert json_path.name in unloadable[0]


def test_the_part_infix_matches_what_the_producer_actually_emits() -> None:
    """Multi-part producer outputs remain distinct from their source filename.

    No committed sidecar currently carries an infix. This keeps the producer's
    multi-part behavior covered while the generic validator owns how it maps
    those generated names back to their source.
    """
    source = Path("corpus") / "ley-37-1992-art-90.html"
    total = 3

    for index in range(total):
        stand_in = part_stand_in_path(source, index, total)
        # Non-vacuity, and the failure the row names: a producer that stopped
        # infixing would satisfy the strip trivially, because stripping nothing
        # from an unchanged name also yields the source name.
        assert stand_in.name != source.name, (
            f"the producer emitted no distinguishing name for part {index + 1} of {total}, so the "
            f"strip below would pass by doing nothing and this gate would stop discriminating"
        )
    # A single-part source is named directly from the source.
    assert part_stand_in_path(source, 0, 1).name == source.name
