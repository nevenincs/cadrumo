"""Every bundled published-form file must be enrolled and provenanced.

``formularios_publicados/`` holds the AEAT-published printed form facsimiles.
They are cited as evidence like any other corpus artefact, but nothing on disk
forced them to be: the category was created by hand, outside every ingestion
pipeline in ``dev/corpus/``, so it inherited the generic text-sidecar treatment
and none of the provenance contract its sibling categories carry.

The concrete defect this gate exists to catch already happened. The Modelo 840
printed form shipped in the wheel for months with **no** registry enrolment at
all -- no digest, no byte count, no retrieval date, no source URL -- while being
the sole grounding for the M840 declaration-PDF extraction profile's label
patterns, which run at ``confidence = "strict"`` with
``failure_semantics = "fail_hard"``. The approving Orden HTML does not reproduce
the form's numbered boxes, so nothing else in the corpus could substitute. A
strict, fail-hard parser contract was grounded on a file nothing verified, and
the only trace of the dependency was a TOML comment.

THE ENUMERATION IS INDEPENDENT of the catalogue: it walks the corpus for
payload suffixes and asks the sources catalogue nothing about what it already
knows, so it cannot inherit a narrowing the catalogue acquired. NO COUNT IS
PINNED -- a tally would encode this moment and detect nothing afterward.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.resources.bundled_data import bundled_path
from ._catalogue_verification_support import _catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FORM_ROOT_PARTS = ("corpus", "aeat_official", "formularios_publicados")

#: Payload suffixes a published form ships under. Declared locally so a change
#: to a sibling gate's suffix set cannot silently narrow this enumeration. The
#: generated text sidecars (``.extracted.json`` / ``.extracted.md``) are
#: deliberately excluded: they are derivatives, owned and freshness-gated by
#: ``dev.docs.preprocess``, and are not independently enrollable evidence.
_FORM_PAYLOAD_SUFFIXES = frozenset({".pdf"})


def _form_root() -> Path:
    return bundled_path(*_FORM_ROOT_PARTS)


def _bundled_form_payloads(root: Path | None = None) -> tuple[Path, ...]:
    """Every payload-suffixed file under ``formularios_publicados/``.

    ``root`` is a parameter rather than the module constant so the defect
    proofs below can drive THESE predicates against a tmp tree. A gate whose
    own predicate is never made to fire is an instrument nobody checked.
    """
    return tuple(
        path
        for path in scan_directory(root or _form_root(), recursive=True, select=DirectoryEntryKind.FILES)
        if path.suffix.lower() in _FORM_PAYLOAD_SUFFIXES
    )


def _modelo_directories(root: Path | None = None) -> tuple[Path, ...]:
    """Every ``modelo_*`` directory that actually carries a populated ``files/``."""
    return tuple(
        subdir
        for subdir in scan_directory(root or _form_root(), select=DirectoryEntryKind.DIRECTORIES)
        if (subdir / "files").is_dir()
    )


def _missing_provenance_documents(root: Path) -> list[str]:
    """Return ``modelo/document`` for each required provenance file absent under ``root``."""
    missing: list[str] = []
    for modelo_dir in _modelo_directories(root):
        for required in ("manifest.json", "PROVENANCE.md"):
            if not (modelo_dir / required).is_file():
                missing.append(f"{modelo_dir.name}/{required}")
    return missing


def _undocumented_payloads(root: Path) -> list[str]:
    """Return payloads under ``root`` that their sibling manifest does not record."""
    undocumented: list[str] = []
    for modelo_dir in _modelo_directories(root):
        manifest_path = modelo_dir / "manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        stored = {artefact.get("stored_path") for artefact in manifest.get("artefacts", ())}
        for payload in scan_directory(modelo_dir / "files", select=DirectoryEntryKind.FILES):
            if payload.suffix.lower() not in _FORM_PAYLOAD_SUFFIXES:
                continue
            relative = payload.relative_to(modelo_dir).as_posix()
            if relative not in stored:
                undocumented.append(f"{modelo_dir.name}: {relative}")
    return undocumented


def _decoy_category(tmp_path: Path, *, manifest: dict[str, object] | None) -> Path:
    """Build a minimal published-form tree carrying one payload.

    Written to a tmp directory, never to the contributor's corpus.
    """
    modelo_dir = tmp_path / "modelo_999"
    (modelo_dir / "files").mkdir(parents=True)
    (modelo_dir / "files" / "decoy.pdf").write_bytes(b"%PDF-1.4 decoy")
    if manifest is not None:
        (modelo_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (modelo_dir / "PROVENANCE.md").write_text("# decoy\n", encoding="utf-8")
    return tmp_path


def test_the_published_form_enumeration_is_not_empty() -> None:
    """Anti-vacuity: every sweep below iterates this population.

    If the category is renamed or emptied, the sweeps would each report a clean
    corpus having never opened a file, which is the exact blindness the gates
    are here to remove.
    """
    root = _form_root()
    assert root.is_dir(), f"{root} is missing; the published-form category has moved or been renamed"
    assert _bundled_form_payloads(), "no published-form payload was enumerated; the suffix set or path has moved"
    assert _modelo_directories(), "no modelo directory with a populated files/ child was found"


def test_every_bundled_published_form_is_enrolled_by_a_source() -> None:
    """A payload no ``SourceReference.corpus_path`` names is unverifiable inventory.

    It cannot be hash-pin verified, no consumer of the sources catalogue can
    see it, and any grounding claim that leans on it rests on a comment rather
    than on a declaration. Close a gap by authoring the missing
    ``[sources."..."]`` entry, never by narrowing this enumeration.
    """
    enrolled = frozenset(source.corpus_path for source in _catalogues().sources.values())
    payloads = _bundled_form_payloads()
    unenrolled = [
        path.relative_to(bundled_path()).as_posix()
        for path in payloads
        if path.relative_to(bundled_path()).as_posix() not in enrolled
    ]
    assert not unenrolled, (
        f"{len(unenrolled)} of {len(payloads)} bundled published-form payload(s) carry no registered "
        "SourceReference. Each ships in the wheel as evidence nothing can verify:\n  " + "\n  ".join(unenrolled)
    )


def test_every_enrolled_published_form_verifies_against_its_declaration() -> None:
    """The enrolment must be TRUE, not merely present.

    ``test_every_bundled_published_form_is_enrolled_by_a_source`` proves a
    declaration names the file; this proves the declaration's digest and byte
    count are the file's. Without it, an entry authored with a placeholder or a
    copied digest would satisfy the enrolment sweep while pinning nothing.
    """
    root_relative = {path.relative_to(bundled_path()).as_posix(): path for path in _bundled_form_payloads()}
    mismatched: list[str] = []
    for source in _catalogues().sources.values():
        payload = root_relative.get(source.corpus_path)
        if payload is None:
            continue
        actual_bytes = payload.stat().st_size
        if actual_bytes != source.bytes:
            mismatched.append(f"{source.corpus_path}: declares bytes={source.bytes} but the file is {actual_bytes}")
    assert not mismatched, "published-form enrolments disagree with the committed files:\n  " + "\n  ".join(mismatched)


def test_every_published_form_modelo_carries_a_manifest_and_provenance() -> None:
    """The category is inside the corpus provenance contract, not beside it.

    ``manifest.json`` is the machine-readable provenance home (mirroring
    ``disenos_registro/``); ``PROVENANCE.md`` carries the human-facing source,
    dating, and locale narrative. The Modelo 840 form was captured with neither,
    which is why its source URL had to be reconstructed after the fact rather
    than read.
    """
    missing = _missing_provenance_documents(_form_root())
    assert not missing, (
        "published-form directories missing their provenance documents: "
        + ", ".join(missing)
        + "; author them before landing a corpus capture"
    )


def test_every_published_form_manifest_documents_every_payload_beside_it() -> None:
    """A payload absent from its manifest has no recorded origin.

    Files added to the corpus without a manifest entry are structural drift:
    the binary is real, it opens, it looks correct, and nothing fails until
    somebody needs to know where it came from -- at which point, as happened
    with Modelo 840, the answer is no longer in the repository.
    """
    undocumented = _undocumented_payloads(_form_root())
    assert not undocumented, (
        "published-form payloads absent from their manifest's artefacts:\n  "
        + "\n  ".join(undocumented)
        + "\nadd a manifest entry recording the source URL, digest, and retrieval date"
    )


def test_a_capture_landed_without_provenance_documents_is_reported(tmp_path: Path) -> None:
    """DETECTOR TEETH: the exact Modelo 840 defect, replayed against a tmp tree.

    A payload dropped into the category with no ``manifest.json`` and no
    ``PROVENANCE.md`` -- how the M840 form actually landed -- must be named by
    the predicate the gate above uses, not merely by a differently written
    check.
    """
    root = _decoy_category(tmp_path, manifest=None)

    assert _bundled_form_payloads(root), "the decoy payload was not even enumerated"
    assert sorted(_missing_provenance_documents(root)) == [
        "modelo_999/PROVENANCE.md",
        "modelo_999/manifest.json",
    ]


def test_a_payload_absent_from_its_manifest_is_reported(tmp_path: Path) -> None:
    """DETECTOR TEETH: a manifest that documents a DIFFERENT file still fails.

    The nastier half of the defect: provenance documents exist, so the
    structural sweep reads clean, while the payload beside them is unrecorded.
    """
    root = _decoy_category(
        tmp_path,
        manifest={"modelo": "999", "artefacts": [{"stored_path": "files/something-else.pdf"}]},
    )

    assert not _missing_provenance_documents(root), "the structural sweep should be satisfied here"
    assert _undocumented_payloads(root) == ["modelo_999: files/decoy.pdf"]


def test_a_fully_documented_capture_is_accepted(tmp_path: Path) -> None:
    """The normal path passes in the same suite, so the proofs above are not tautologies."""
    root = _decoy_category(
        tmp_path,
        manifest={"modelo": "999", "artefacts": [{"stored_path": "files/decoy.pdf"}]},
    )

    assert not _missing_provenance_documents(root)
    assert not _undocumented_payloads(root)
