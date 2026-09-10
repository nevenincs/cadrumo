"""Every committed AEAT corpus payload must have a recorded origin.

The corpus-local gate (``cadrumo._data.corpus.tests.test_corpus_provenance``)
checks that a provenance document, where one exists, is complete and
well-formed. It deliberately does not ask whether a directory carrying NO
provenance document is nevertheless provenanced, because answering that
requires the registry, which a data package must not import.

This is that question, asked where the registry is already in scope.

THREE MECHANISMS RECORD ORIGIN in this repository, and a payload covered by
any one of them is provenanced:

1. A registry ``SourceReference.corpus_path`` -- the strongest, since it pins
   ``sha256``, ``bytes``, ``retrieved_at`` and ``source_url``.
2. A sibling ``manifest.json`` ``artefacts[].stored_path`` -- what the
   ``disenos_registro`` sync generator writes, carrying url + digest + date.
3. A sibling ``PROVENANCE.md`` naming the file -- hand-authored prose, the
   weakest but still an audit trail.

Requiring all three would be false precision; requiring none is the state that
let the Modelo 840 printed form ship in the wheel for months with no digest,
no URL, and no retrieval date, as the sole grounding for a ``fail_hard``
extraction profile. Requiring AT LEAST ONE is the contract.

GENERATED DERIVATIVES ARE NOT PAYLOAD. The ``.extracted.json`` / ``.extracted.md``
sidecars are owned and freshness-gated by ``dev.docs.preprocess``; they are
regenerated from the payload beside them and are not independently sourced, so
demanding provenance for them would manufacture findings.

NO COUNT IS PINNED. Per the standing project directive and the sibling gate
``test_every_bundled_record_design_is_registered``, a red signal over a genuine
unprovenanced population is the correct report -- scoping this gate to the
already-covered set would make it pass vacuously and remove the exact
visibility it exists to provide.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import DirectoryEntryKind, iter_directory, scan_directory
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.record_design_sources import _CORRECTION_SUFFIX, _DECLARED_NON_RECORD_SHEETS_FILENAME
from ._catalogue_verification_support import _catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_AEAT_ROOT_PARTS = ("corpus", "aeat_official")

#: Name fragments marking a file as a derivative of the payload it sits beside
#: rather than an independently sourced document.
#:
#: The correction sidecar is imported from the loader that defines it rather
#: than respelled here, so the gate cannot drift from the suffix the parser
#: actually reads. It is hand-authored, not machine-generated, but it belongs
#: in this list for the same reason: it is project reasoning ABOUT a payload,
#: derived from the binary beside it, with no AEAT origin of its own to record.
#: The corpus sync tool classifies it identically
#: (``dev/corpus/sync_aeat_record_design_corpus.py``, ``_DERIVED_SUFFIXES``).
_DERIVATIVE_MARKERS = (".extracted.json", ".extracted.md", _CORRECTION_SUFFIX)


def _aeat_root() -> Path:
    return bundled_path(*_AEAT_ROOT_PARTS)


def _is_derivative(path: Path) -> bool:
    return any(marker in path.name for marker in _DERIVATIVE_MARKERS)


#: Metadata documents that are provenance ABOUT payload rather than sourced
#: payload themselves, and so are never owed a record of their own.
#:
#: The two declaration files carry project-authored classification -- which
#: sheets are not record designs, which historical URLs fall outside the
#: supported window -- together with the reasoning behind it. They are our
#: assertions about AEAT content, not AEAT content, which is why the corpus
#: sync tool likewise expects no manifest artefact to describe them
#: (``dev/corpus/sync_aeat_record_design_corpus.py``, ``_DECLARATION_NAMES``).
#:
#: ``.gitattributes`` is version-control configuration that happens to sit in a
#: payload directory (it pins ``eol=lf`` and marks binaries ``-diff``). It is
#: not corpus content and has no origin to record.
#:
#: Listed by NAME rather than sniffed by shape on purpose. The two category-root
#: declarations share a ``schema_version``/``disposition`` structure, so a
#: structural test would classify future ones automatically -- and silently, which
#: is the failure mode this gate exists to prevent. A new unrecognised file at a
#: corpus root SHOULD redden here until someone decides what it is.
_NON_PAYLOAD = frozenset(
    {
        "PROVENANCE.md",
        "manifest.json",
        "README.md",
        ".gitattributes",
        _DECLARED_NON_RECORD_SHEETS_FILENAME,
        "historical_exclusions.json",
        "off_host_sources.json",
    }
)


def _payloads(aeat_root: Path | None = None) -> tuple[Path, ...]:
    """Every sourced payload file anywhere under ``aeat_official``.

    Walked recursively and shape-agnostically rather than by assuming a
    ``files/`` child. The corpus ships at least five layouts --
    ``category/files/``, ``category/modelo_N/files/``, payloads directly at a
    category root (``groi_response_samples``), a single file at a category root
    (``renta_web_open``), and named subdirectories
    (``einvoice_record_schemas/sii``). An earlier draft required a ``files/``
    child and so silently skipped three of them, which is exactly the
    unmeasured-family blindness this gate exists to remove.

    ``aeat_root`` is a parameter rather than a module constant so the defect
    proofs drive THIS predicate against a tmp tree.
    """
    root = aeat_root or _aeat_root()
    if not root.is_dir():
        return ()
    return tuple(
        path
        for path in scan_directory(root, recursive=True, select=DirectoryEntryKind.FILES)
        if not _is_derivative(path) and path.name not in _NON_PAYLOAD
    )


#: The keys a corpus manifest uses to name an artefact's committed location.
#: TWO shapes ship, and this is corpus inconsistency rather than a choice:
#: ``disenos_registro`` (60 manifests, generator-written) uses ``stored_path``,
#: while ``einvoice_record_schemas`` (hand-authored) uses ``path``. Reading
#: only one of them made every schema under ``sii/`` and ``verifactu/`` look
#: unprovenanced, even though that manifest pins each by URL, namespace,
#: sha256 and bytes -- and its own ``provenance_note`` records that it is
#: their ONLY provenance, since they carry no registry entry. Accepting both
#: keys is what makes the sweep truthful; unifying the manifest schema is a
#: separate change, deliberately not smuggled into a test helper.
_ARTEFACT_LOCATION_KEYS = ("stored_path", "path")


def _manifest_stored_paths(subdir: Path) -> frozenset[str]:
    manifest_path = subdir / "manifest.json"
    if not manifest_path.is_file():
        return frozenset[str]()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return frozenset(
        located
        for artefact in manifest.get("artefacts", ())
        for key in _ARTEFACT_LOCATION_KEYS
        # ``json.loads`` yields ``Any``; requiring ``str`` types the value at
        # this boundary and also refuses a malformed location -- a non-string
        # entry names no file, so silently keeping it would credit a payload
        # with provenance no artefact actually points at.
        if isinstance(located := artefact.get(key), str)
    )


def _recorded_by_an_ancestor(payload: Path, root: Path) -> bool:
    """Whether a ``manifest.json`` or ``PROVENANCE.md`` above ``payload`` records it.

    Attribution walks UP from the payload to the corpus root rather than
    assuming the document sits at a fixed depth, because the document's depth
    varies by category: ``disenos_registro/modelo_N/manifest.json`` sits one
    level above ``files/``, while ``einvoice_record_schemas/manifest.json`` sits
    two above its payloads and ``groi_response_samples/PROVENANCE.md`` sits
    beside them.
    """
    for ancestor in (payload.parent, *payload.parents):
        if not ancestor.is_relative_to(root):
            break
        if payload.relative_to(ancestor).as_posix() in _manifest_stored_paths(ancestor):
            return True
        provenance = ancestor / "PROVENANCE.md"
        if provenance.is_file() and payload.name in provenance.read_text(encoding="utf-8"):
            return True
    return False


def _unprovenanced(
    *,
    aeat_root: Path | None = None,
    enrolled_corpus_paths: frozenset[str] | None = None,
    bundle_root: Path | None = None,
) -> list[str]:
    """Return the corpus-relative path of every payload no mechanism records."""
    root = aeat_root or _aeat_root()
    bundle = bundle_root or bundled_path()
    enrolled = enrolled_corpus_paths if enrolled_corpus_paths is not None else _enrolled_corpus_paths()

    return [
        payload.relative_to(root).as_posix()
        for payload in _payloads(root)
        if payload.relative_to(bundle).as_posix() not in enrolled and not _recorded_by_an_ancestor(payload, root)
    ]


def _enrolled_corpus_paths() -> frozenset[str]:
    return frozenset(source.corpus_path for source in _catalogues().sources.values())


def test_the_payload_enumeration_reaches_every_corpus_category() -> None:
    """Anti-vacuity, per category: the sweep below iterates this population.

    The per-category assertion is what makes the total meaningful. The count is
    dominated by ``disenos_registro`` and ``instructions``, so a total-only
    floor cannot see a small category leave -- and three of the corpus's five
    layout shapes live in small categories, which is how an earlier draft of
    this walk skipped them while still reporting a healthy number.
    """
    root = _aeat_root()
    assert root.is_dir(), root
    payloads = _payloads()
    assert payloads, "no corpus payload was enumerated at all"

    reached = {payload.relative_to(root).parts[0] for payload in payloads}
    every_category = {
        entry.name
        for entry in scan_directory(root, select=DirectoryEntryKind.DIRECTORIES)
        if any(iter_directory(entry))
    }
    unreached = sorted(every_category - reached)
    assert not unreached, (
        f"these corpus categories ship content the payload walk never reached: {unreached}; "
        "a category nobody enumerates is one the coverage sweep reports clean without opening"
    )


def test_both_committed_manifest_artefact_location_keys_are_honoured() -> None:
    """Both manifest shapes in the corpus must actually resolve payloads.

    Not a style check: reading only ``stored_path`` silently turned every
    ``einvoice_record_schemas`` payload into a false finding. This asserts each
    key is live in the committed corpus, so dropping either from
    ``_ARTEFACT_LOCATION_KEYS`` reddens here rather than in a flood of bogus
    coverage findings.
    """
    manifests = scan_directory(_aeat_root(), pattern="manifest.json", recursive=True, select=DirectoryEntryKind.FILES)
    assert manifests, "no corpus manifest was discovered at all"

    keys_seen: set[str] = set()
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for artefact in manifest.get("artefacts", ()):
            keys_seen.update(key for key in _ARTEFACT_LOCATION_KEYS if key in artefact)

    assert keys_seen == set(_ARTEFACT_LOCATION_KEYS), (
        f"the corpus uses artefact location key(s) {sorted(keys_seen)} but this module honours "
        f"{sorted(_ARTEFACT_LOCATION_KEYS)}; an unhonoured key makes provenanced payloads read as gaps"
    )


def test_generated_derivatives_are_excluded_from_the_payload_population() -> None:
    """The exclusion must actually bite, and must not swallow real payloads.

    If ``_is_derivative`` stopped matching, the sweep would demand provenance
    for every ``.extracted.json`` in the corpus and drown the real finding in
    hundreds of false ones -- the failure mode that gets a gate switched off.
    """
    all_files = scan_directory(_aeat_root(), recursive=True, select=DirectoryEntryKind.FILES)
    payloads = _payloads()

    assert len(payloads) < len(all_files), "no derivative was excluded; the marker list has stopped matching"
    assert payloads, "the exclusion swallowed every file; the marker list is too broad"
    assert not any(_is_derivative(path) for path in payloads)


def test_every_exclusion_from_the_payload_population_is_live_in_the_committed_corpus() -> None:
    """Every name this module refuses to police must match a real committed file.

    An exclusion is the only way this gate can under-report, so each one is
    asserted individually rather than in aggregate. A name matching nothing is
    dead weight that reads as caution while protecting nothing, and it is also
    how a future exclusion added to quiet a finding would hide: the finding
    disappears, the total looks healthier, and no assertion notices. Requiring
    each entry to be live means an exclusion must be justified against content
    that actually ships, and a corpus that stops carrying a class reddens here
    -- pointing at the stale exclusion -- instead of silently widening.
    """
    all_files = scan_directory(_aeat_root(), recursive=True, select=DirectoryEntryKind.FILES)
    assert all_files, "no corpus file was discovered at all"

    unmatched = sorted(
        excluded
        for excluded in (*_NON_PAYLOAD, *_DERIVATIVE_MARKERS)
        if not any(excluded in path.name for path in all_files)
    )
    assert not unmatched, (
        f"these names are excluded from the payload population but match nothing in the committed "
        f"corpus: {unmatched}; an exclusion that protects no real file only narrows the sweep"
    )


def test_every_committed_corpus_payload_has_a_recorded_origin() -> None:
    """THE WORKLIST. Lands red if a genuine gap exists; the gap is the finding.

    Close an entry by authoring the missing registry ``[sources."..."]`` entry,
    the missing ``manifest.json`` artefact, or the missing ``PROVENANCE.md``
    line -- never by narrowing this enumeration.
    """
    findings = _unprovenanced()
    assert not findings, (
        f"{len(findings)} committed corpus payload(s) have no recorded origin in the registry, in a "
        "sibling manifest.json, or in a sibling PROVENANCE.md. Each ships in the wheel as evidence "
        "whose source cannot be established:\n  " + "\n  ".join(findings)
    )


# ---------------------------------------------------------------------------
# Detector teeth. The sweep's own predicate, driven against a tmp tree.
# ---------------------------------------------------------------------------


def _decoy(tmp_path: Path, *, manifest: object | None, provenance: str | None) -> Path:
    root = tmp_path / "aeat_official"
    subdir = root / "instructions" / "modelo_999"
    (subdir / "files").mkdir(parents=True)
    (subdir / "files" / "payload.html").write_text("x", encoding="utf-8")
    (subdir / "files" / "payload.html.extracted.md").write_text("derived", encoding="utf-8")
    if manifest is not None:
        (subdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if provenance is not None:
        (subdir / "PROVENANCE.md").write_text(provenance, encoding="utf-8")
    return root


def test_a_payload_recorded_by_no_mechanism_is_reported(tmp_path: Path) -> None:
    """DETECTOR TEETH: exactly the Modelo 840 defect -- a payload nothing records."""
    root = _decoy(tmp_path, manifest=None, provenance=None)

    assert _unprovenanced(aeat_root=root, enrolled_corpus_paths=frozenset[str](), bundle_root=tmp_path) == [
        "instructions/modelo_999/files/payload.html"
    ]


@pytest.mark.parametrize(
    ("manifest", "provenance", "enrolled"),
    [
        pytest.param(
            {"artefacts": [{"stored_path": "files/payload.html"}]},
            None,
            frozenset[str](),
            id="manifest-entry",
        ),
        pytest.param(None, "# p\n- `files/payload.html`\n", frozenset[str](), id="provenance-line"),
        pytest.param(
            None,
            None,
            frozenset({"aeat_official/instructions/modelo_999/files/payload.html"}),
            id="registry-enrolment",
        ),
    ],
)
def test_any_single_mechanism_provenances_a_payload(
    tmp_path: Path,
    manifest: object | None,
    provenance: str | None,
    enrolled: frozenset[str],
) -> None:
    """Each of the three mechanisms independently satisfies the contract.

    Parameterised rather than asserted once so a mechanism silently ceasing to
    count -- which would turn a provenanced corpus into a false worklist -- is
    caught per mechanism.
    """
    root = _decoy(tmp_path, manifest=manifest, provenance=provenance)

    assert not _unprovenanced(aeat_root=root, enrolled_corpus_paths=enrolled, bundle_root=tmp_path)


def test_the_derivative_beside_an_unrecorded_payload_is_never_itself_a_finding(tmp_path: Path) -> None:
    """The exclusion holds on the failing path too, not just the passing one."""
    root = _decoy(tmp_path, manifest=None, provenance=None)

    findings = _unprovenanced(aeat_root=root, enrolled_corpus_paths=frozenset[str](), bundle_root=tmp_path)

    assert not any("extracted" in finding for finding in findings)
