"""Bundled AEAT artefacts still match the digests recorded when they were fetched.

WHAT THIS PROVES, AND THE LIMIT IS THE POINT
--------------------------------------------
It proves ONE thing: **the bytes have not changed since we fetched them.** Each
artefact is re-hashed and compared against the ``sha256`` its manifest recorded.

It does **NOT** prove the bytes match AEAT's current publication. A digest
recomputed from our own file can only ever agree with a digest we ourselves
recorded from that same file -- the comparison never leaves this repository, so
it cannot see AEAT republishing, silently correcting, or withdrawing a document.
Upstream fidelity is the bottom rung of the provenance ladder and no in-repo
check reaches it; only re-fetching and comparing does.

**Do not cite a green run here as evidence that an artefact matches AEAT.** That
over-reading is exactly what produced a false hand-editing report: a `grep` over
two different complexTypes was read as one relaxed value, and the corpus was
accused of tampering it had not suffered. The check below would have refuted that
in seconds -- which is why it now runs -- but a green result answers "unchanged
since fetch", never "faithful to AEAT".

The same distinction is already reasoned through in
:func:`~core.corpus_manifest.verify_corpus_bundle`'s signing counterpart, which
re-hashes archived members rather than trusting a digest taken over recorded
hashes. This gate applies that discipline to the shipped record-design tree,
which that bundle verifier does not cover.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from ..core.directory_scan import scan_directory
from ..core.hashing import sha256_file
from ..core.resources import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DISENOS_ROOT = bundled_path("corpus", "aeat_official", "disenos_registro")
#: Floors below which the walk has collapsed rather than found nothing wrong.
_MIN_ARTEFACTS = 200
_MIN_NAMED_ARTEFACTS = 190
#: ``stored_path`` shape the naming check can read: ``files/NN-slug.ext``.
_STORED_PATH_SHAPE = re.compile(r"^files/\d+-.+\.[A-Za-z0-9]+$")
_UPDATED_STAMP: re.Pattern[str] = re.compile(r"actualizado[-\s]+(\d{1,2})[-\s](\d{1,2})[-\s](\d{2,4})")
_SIZE_TOKEN: re.Pattern[str] = re.compile(r"(\d+)[-\s]*kb")


def _manifest_rows() -> list[tuple[Path, dict[str, object]]]:
    rows: list[tuple[Path, dict[str, object]]] = []
    for manifest in scan_directory(_DISENOS_ROOT, pattern="manifest.json", recursive=True):
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        artefacts = payload.get("artefacts")
        if not isinstance(artefacts, list):
            continue
        rows.extend((manifest, row) for row in artefacts if isinstance(row, dict))
    return rows


def _publication_tokens(text: str) -> tuple[tuple[str, str, str] | None, str | None]:
    """Return the (day, month, year) stamp and size token that identify a publication.

    Only these two are compared. A whole-slug comparison reports title FORMAT
    churn -- an index prefix, a trailing ``-xls`` -- as a publication conflict,
    which produced roughly twenty findings where there is one real defect.
    """
    stamp = _UPDATED_STAMP.search(text.lower())
    size = _SIZE_TOKEN.search(text.lower())
    normalised = None
    if stamp is not None:
        day = str(stamp.group(1))
        month = str(stamp.group(2))
        year = str(stamp.group(3))
        normalised = (day.lstrip("0"), month.lstrip("0"), year[-2:])
    return normalised, str(size.group(1)) if size is not None else None


#: Rows whose ``stored_path`` predates the ``files/NN-slug.ext`` convention and
#: therefore encodes no publication stamp to compare. They ARE digest-checked;
#: only the naming check skips them. Pinned by name so a NEW unnamed row joins
#: this list by a reviewed decision rather than by silently falling out of scope.
_NAMING_EXEMPT_STORED_PATHS = frozenset(
    {
        "modelo_145/files/dr145v20.pdf",
        "modelo_210/dr210_2011.pdf",
        "modelo_280/files/DR_280_2022.pdf",
        "modelo_714/files/DR714_2025.xls",
    },
)


def test_naming_check_skips_exactly_the_declared_rows() -> None:
    """The naming check's blind spot is a declared list, never an accident.

    A row that carries no publication stamp cannot be naming-checked, but a row
    quietly acquiring an unreadable ``stored_path`` would leave the check
    silently narrower than it reads. Pinning the set makes that a failure.
    """
    unnamed = {
        f"{manifest.parent.name}/{row.get('stored_path')}"
        for manifest, row in _manifest_rows()
        if not _STORED_PATH_SHAPE.match(str(row.get("stored_path", "")))
    }

    assert unnamed == _NAMING_EXEMPT_STORED_PATHS, (
        "the set of artefacts excluded from the publication-naming check changed.\n"
        f"  now excluded but not declared: {sorted(unnamed - _NAMING_EXEMPT_STORED_PATHS)}\n"
        f"  declared but no longer present: {sorted(_NAMING_EXEMPT_STORED_PATHS - unnamed)}\n\n"
        "These rows are still digest-checked. Prefer giving a new artefact a stored_path that carries its "
        "publication stamp over widening this list."
    )


def test_corpus_walk_is_not_vacuous() -> None:
    """A manifest-parse collapse must not read as a clean corpus."""
    rows = _manifest_rows()
    assert len(rows) >= _MIN_ARTEFACTS, f"only {len(rows)} artefact rows found; the walk below would be vacuous"
    named = [row for _m, row in rows if _STORED_PATH_SHAPE.match(str(row.get("stored_path", "")))]
    assert len(named) >= _MIN_NAMED_ARTEFACTS, f"only {len(named)} rows carry a readable stored_path shape"


def test_every_bundled_artefact_matches_its_recorded_digest() -> None:
    """Re-hash every artefact; any drift means the bytes changed after fetch."""
    mismatched: list[str] = []
    missing: list[str] = []
    for manifest, row in _manifest_rows():
        stored = str(row.get("stored_path", ""))
        recorded = str(row.get("sha256", ""))
        path = manifest.parent / stored
        if not path.is_file():
            missing.append(f"{manifest.parent.name}/{stored}")
            continue
        actual = sha256_file(path)
        if actual != recorded:
            mismatched.append(f"{manifest.parent.name}/{stored}: recorded {recorded[:12]} != actual {actual[:12]}")

    assert missing == [], "manifest rows point at files that are not present:\n  " + "\n  ".join(missing)
    assert mismatched == [], (
        "bundled artefact bytes no longer match the digest recorded when they were fetched:\n  "
        + "\n  ".join(mismatched)
        + "\n\nThe corpus is evidence. Re-fetch through the corpus sync tool rather than editing a file "
        "in place, and never 'fix' a mismatch by rewriting the recorded digest to match edited bytes."
    )


def test_stored_path_asserts_the_same_publication_as_its_title() -> None:
    """A filename claiming a different publication than its title misleads every reader.

    Compares only the ``actualizado`` stamp and the ``NNN-kb`` size -- the tokens
    that identify WHICH publication the bytes are. Title format churn (an index
    prefix, a trailing format suffix) names the same artefact and is not a
    conflict.
    """
    conflicts: list[str] = []
    for manifest, row in _manifest_rows():
        stored = str(row.get("stored_path", ""))
        if not _STORED_PATH_SHAPE.match(stored):
            continue
        title = str(row.get("title", ""))
        stored_stamp, stored_size = _publication_tokens(stored)
        title_stamp, title_size = _publication_tokens(title)
        if stored_stamp is not None and title_stamp is not None and stored_stamp != title_stamp:
            conflicts.append(f"{manifest.parent.name}/{stored}: name says {stored_stamp}, title says {title_stamp}")
        elif stored_size is not None and title_size is not None and stored_size != title_size:
            conflicts.append(f"{manifest.parent.name}/{stored}: name says {stored_size}kb, title says {title_size}kb")

    assert conflicts == [], (
        "a stored filename asserts a different AEAT publication than its manifest title:\n  "
        + "\n  ".join(conflicts)
        + "\n\nThe bytes are whichever publication was last fetched; the title is refreshed on re-fetch and "
        "the filename is not. Rename the file and update stored_path to match the title -- never edit the "
        "artefact, and never edit the title to match a stale filename."
    )
