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

Freshness alone is not enough, because it is checked against the source the
record *names* rather than the one it sits *beside*. A sidecar written next
to payload A while declaring payload B reconciles perfectly against B - so
the sweep goes green while :func:`load_sidecar` (which hashes A) refuses it.
That is the stale-derivative failure wearing a different mask: a mis-stamped
locator instead of a mis-stamped digest, with the same downstream symptom of
grounding text that does not belong to the file it accompanies.
:func:`_locality_reason` closes it by requiring the declared locator to equal
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

import json
import re
from pathlib import Path
from typing import Final

import pytest
from pydantic import ValidationError

from cadrumo.core.directory_scan import scan_directory

from ...._paths import REPO_ROOT, UTF_8
from .._html import build_outputs
from .._parts import part_stand_in_path
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
_REPO_ROOT = REPO_ROOT
_CORPUS_ROOT = _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus"

# A single BOE article slice, small and single-part: the anti-tautology proof
# needs a source whose sidecar pair is addressable by source path.
_WORKED_EXAMPLE_HTML = _CORPUS_ROOT / "normatives" / "html" / "orden-hap-2250-2015-art-4.html"

# The sweep is meaningless if discovery silently returns nothing, so it asserts
# a floor. Set well below the 577 sidecars committed today: this guards against
# a broken glob or a moved corpus root, not against the corpus shrinking.
_MINIMUM_EXPECTED_SIDECARS = 400

#: Multi-part sidecars infix ``.part-N`` between the payload name and the
#: sidecar suffix (see ``_parts.part_stand_in_path``), so the payload a
#: sidecar sits beside is its name with that infix removed.
_PART_INFIX = re.compile(r"\.part-\d+$")

_UTF_8: Final[str] = UTF_8


def _payload_beside(json_path: Path) -> Path:
    """Return the payload file a sidecar physically sits beside.

    Strips the sidecar suffix and any multi-part infix, so every part of a
    split source resolves back to the one payload all its parts describe.
    """
    base = json_path.name[: -len(EXTRACTED_JSON_SUFFIX)]
    return json_path.with_name(_PART_INFIX.sub("", base))


def _provenance_bearing_sidecars(
    corpus_root: Path = _CORPUS_ROOT,
) -> tuple[list[tuple[Path, PreprocessOutput]], list[str]]:
    """Return provenance-bearing sidecars, plus a reason per unloadable one.

    A file matching the sidecar glob but carrying no provenance is a curated
    overlay rather than extractor output; it makes no freshness claim, so
    there is nothing here to verify. Excluding by SHAPE rather than by
    filename means a future overlay is handled without an allowlist.

    A file that DOES claim provenance and still fails to validate - a blank
    or malformed ``source_sha256``, an unsupported ``schema_version`` - is a
    finding, not a crash: it is returned as a reason naming the offending
    file so the sweep reports it beside every other defect in one pass.
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
            found.append((json_path, PreprocessOutput.model_validate_json(raw)))
        except ValidationError as exc:
            unloadable.append(
                f"{json_path.name}: claims provenance but fails schema validation ({exc.error_count()} errors)"
            )
    return found, unloadable


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


def _locality_reason(json_path: Path, output: PreprocessOutput, *, repo_root: Path = _REPO_ROOT) -> str | None:
    """Return why ``output`` names a payload other than the one beside it, or ``None``.

    Freshness is checked against the source the record NAMES; this checks
    that the named source is the one the sidecar sits BESIDE. Without it a
    mis-stamped locator passes the digest check against an unrelated file
    while ``load_sidecar`` - which hashes the neighbour - refuses the same
    sidecar, so the sweep would certify exactly what production rejects.
    """
    declared = output.source_relpath
    beside = _payload_beside(json_path)
    try:
        expected = beside.relative_to(repo_root).as_posix()
    except ValueError:
        return f"{json_path.name}: sits outside the repository root {repo_root}"
    if declared != expected:
        return (
            f"{json_path.name}: sits beside {expected} but records source_relpath={declared} - "
            f"the digest was reconciled against a file this sidecar does not accompany"
        )
    return None


def test_sidecar_discovery_finds_the_committed_corpus() -> None:
    """Discovery reaches the corpus (a silently empty sweep would pass vacuously)."""
    assert _CORPUS_ROOT.is_dir(), _CORPUS_ROOT
    found, _ = _provenance_bearing_sidecars()
    assert len(found) >= _MINIMUM_EXPECTED_SIDECARS


def test_every_committed_sidecar_loads() -> None:
    """Every sidecar claiming extractor provenance validates against the schema.

    A sidecar that claims provenance and cannot be loaded makes an
    unverifiable freshness claim, which is the same problem as a stale one:
    downstream readers cannot tell it apart from a current record.
    """
    _, unloadable = _provenance_bearing_sidecars()

    assert not unloadable, "unloadable corpus sidecars:\n" + "\n".join(unloadable)


def test_every_committed_sidecar_is_fresh_against_its_source() -> None:
    """No committed sidecar was left behind by an edit to the file it describes.

    The failure this catches is invisible by construction: a stale derivative
    reads as complete prose, so nothing downstream distinguishes it from the
    current text. Reported as the full list rather than the first offender,
    because a regeneration sweep wants the whole set in one pass.
    """
    found, _ = _provenance_bearing_sidecars()
    stale = [reason for json_path, output in found if (reason := _staleness_reason(json_path, output))]

    assert not stale, "stale corpus sidecars (source changed since extraction):\n" + "\n".join(stale)


def test_every_committed_sidecar_names_the_payload_it_sits_beside() -> None:
    """No sidecar reconciles its digest against a file it does not accompany.

    The complement of the freshness sweep: freshness proves the recorded
    digest still matches the named source, this proves the named source is
    the neighbour. Both are required, because either alone leaves a green
    reading over a sidecar ``load_sidecar`` would refuse.
    """
    found, _ = _provenance_bearing_sidecars()
    misplaced = [reason for json_path, output in found if (reason := _locality_reason(json_path, output))]

    assert not misplaced, "corpus sidecars naming a payload other than their neighbour:\n" + "\n".join(misplaced)


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
    sidecars, _ = _provenance_bearing_sidecars()
    json_path, output = sidecars[0]

    assert _staleness_reason(json_path, output) is None
    assert _locality_reason(json_path, output) is None
    assert sha256_of(_REPO_ROOT / output.source_relpath) == output.source_sha256


def test_the_locality_predicate_fires_on_a_sidecar_naming_a_neighbour_it_lacks(tmp_path: Path) -> None:
    """A sidecar beside one payload while naming another is flagged here AND refused by the loader.

    The mutation is deliberately the *undetectable-by-freshness* one: both
    payloads exist, both digests are internally consistent, so the staleness
    predicate returns ``None`` and only locality distinguishes them. Asserting
    that ``_staleness_reason`` stays silent is what proves the new check is
    load-bearing rather than a second spelling of the old one.
    """
    decoy = tmp_path / "decoy.html"
    decoy.write_bytes(_WORKED_EXAMPLE_HTML.read_bytes())
    decoy_output = build_outputs(decoy, repo_root=tmp_path)[0]

    neighbour = tmp_path / _WORKED_EXAMPLE_HTML.name
    neighbour.write_bytes(_WORKED_EXAMPLE_HTML.read_bytes() + b"<!-- differs -->")

    # The sidecar pair is written beside ``neighbour`` but carries ``decoy``'s
    # record: exactly the mis-stamped-locator shape.
    write_sidecar(neighbour, decoy_output)
    json_path = neighbour.with_name(neighbour.name + EXTRACTED_JSON_SUFFIX)

    assert _staleness_reason(json_path, decoy_output, repo_root=tmp_path) is None, (
        "the freshness predicate must NOT fire here - if it does, this proves nothing about locality"
    )

    reason = _locality_reason(json_path, decoy_output, repo_root=tmp_path)
    assert reason is not None, "the locality predicate failed to flag a mis-stamped locator"
    assert "does not accompany" in reason

    # ...and the production loader refuses the same sidecar, which is the
    # divergence the locality check exists to make visible.
    with pytest.raises(PreprocessSidecarError, match="is stale"):
        load_sidecar(neighbour)


def test_a_multi_part_sidecar_resolves_to_its_base_payload(tmp_path: Path) -> None:
    """The ``.part-N`` infix is stripped, so split sources do not false-fire on locality.

    Without this the locality check would flag every part of every split
    source, and the pressure would be to allowlist them - re-introducing the
    per-file exemption list this gate exists to avoid.
    """
    source = tmp_path / _WORKED_EXAMPLE_HTML.name
    source.write_bytes(_WORKED_EXAMPLE_HTML.read_bytes())
    output = build_outputs(source, repo_root=tmp_path)[0]
    stand_in = source.with_name(f"{source.name}.part-2")
    write_sidecar(stand_in, output)
    json_path = stand_in.with_name(stand_in.name + EXTRACTED_JSON_SUFFIX)

    assert _payload_beside(json_path) == source
    assert _locality_reason(json_path, output, repo_root=tmp_path) is None


def test_a_sidecar_naming_an_absent_payload_is_reported_not_crashed(tmp_path: Path) -> None:
    """A declared source that no longer exists is a named finding, not a hashing error."""
    source = tmp_path / _WORKED_EXAMPLE_HTML.name
    source.write_bytes(_WORKED_EXAMPLE_HTML.read_bytes())
    output = build_outputs(source, repo_root=tmp_path)[0]
    write_sidecar(source, output)
    json_path = source.with_name(source.name + EXTRACTED_JSON_SUFFIX)
    source.unlink()

    reason = _staleness_reason(json_path, output, repo_root=tmp_path)
    assert reason is not None
    assert "names a source that does not exist" in reason


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
    found, unloadable = _provenance_bearing_sidecars(corpus_root=corpus)
    assert len(found) == 1
    assert unloadable == []

    document = json.loads(json_path.read_text(encoding=_UTF_8))
    document["source_sha256"] = ""
    json_path.write_text(json.dumps(document), encoding=_UTF_8)

    found, unloadable = _provenance_bearing_sidecars(corpus_root=corpus)
    assert found == []
    assert len(unloadable) == 1
    assert "fails schema validation" in unloadable[0]
    assert json_path.name in unloadable[0]


def test_the_part_infix_matches_what_the_producer_actually_emits() -> None:
    """Pin the strip to the producer, so a naming change reds the consumer.

    ``_PART_INFIX`` is the only thing tying this gate to the extractor's
    part-naming scheme, and no committed sidecar carries the infix -- the whole
    corpus is single-part -- so nothing in the tree would red if the producer
    started naming parts differently. The gate would then either over-refuse,
    resolving a real part to a payload that does not exist, or, if the new name
    happened to strip clean, stop discriminating at all.

    Asserting against the producer's own output rather than against a literal
    is what makes it a contract instead of a convention observed twice.
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
        assert _PART_INFIX.sub("", stand_in.name) == source.name, (
            f"the part infix the producer emits ({stand_in.name!r}) is not the one this gate strips, "
            f"so every part sidecar would resolve to a payload that does not exist"
        )

    # A single-part source is named directly from the source, and the strip must
    # leave that alone rather than eat a legitimate part of the filename.
    assert part_stand_in_path(source, 0, 1).name == source.name
    assert _PART_INFIX.sub("", source.name) == source.name
