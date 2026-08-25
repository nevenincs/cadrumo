"""The known-sanitised SHA catalogue must match the committed fixture tree.

``SANITIZED_SHAS`` is what makes ``sanitize_pdf`` refuse to re-sanitise a
document it has already produced. Its contract, in its own words, is "every
committed PDF under ``src/cadrumo/tests/fixtures/justificantes/``" — and it was
hand-maintained, so it drifted the moment anyone regenerated a fixture. A
regenerated fixture gets a new SHA; nothing made the list follow.

The drift was not marginal. When this gate was written the catalogue held 41
entries, of which **32 matched no committed fixture at all**, while **53 of the
62 committed fixtures were absent from it**. The guard therefore covered nine
fixtures and read, to anyone opening the file, as though it covered every one.
It failed in the safe direction — a missed refusal, not a wrong one — which is
exactly why nothing surfaced it: the only symptom was a guard quietly not
firing.

This is the same shape a sibling gate closed for version literals: a value that
must track a regenerated artefact, restated by hand in a second place, with
nothing binding the two. There the remedy was to bind the constant. Here the
artefact is bytes, so the remedy is to recompute and compare.

Set equality, not containment, and deliberately so. A superset hides entries for
fixtures that no longer exist, which is how 32 dead hashes accumulated unnoticed;
a subset hides fixtures the guard has stopped protecting. Both directions are
defects and both are reported separately, because the remedies differ.
"""

from __future__ import annotations

import hashlib

import pytest

from cadrumo.core.directory_scan import scan_directory
from cadrumo.tests import FIXTURES_DIR

from ..fixtures import SANITIZED_SHAS

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_JUSTIFICANTES = FIXTURES_DIR / "justificantes"


def _committed_fixture_digests() -> dict[str, str]:
    """Return ``sha256 -> relative path`` for every committed justificante PDF."""
    return {
        hashlib.sha256(path.read_bytes()).hexdigest(): path.relative_to(_JUSTIFICANTES).as_posix()
        for path in scan_directory(_JUSTIFICANTES, pattern="*.pdf", recursive=True)
    }


def test_the_fixture_corpus_is_not_empty() -> None:
    """Neither side may be silently empty, or equality below is vacuous.

    If the fixture directory moved, every assertion in this module would compare
    two empty sets and pass while measuring nothing.
    """
    assert _JUSTIFICANTES.is_dir(), f"fixture root is missing, so this gate measures nothing: {_JUSTIFICANTES}"
    digests = _committed_fixture_digests()
    assert len(digests) > 40, f"only {len(digests)} committed fixtures found; the walk has stopped matching"
    assert SANITIZED_SHAS, "the catalogue is empty, so the refuse-if-already-sanitised guard protects nothing"


def test_every_committed_fixture_is_catalogued() -> None:
    """A fixture absent from the catalogue is a fixture the guard will not refuse."""
    digests = _committed_fixture_digests()
    uncovered = sorted(name for sha, name in digests.items() if sha not in SANITIZED_SHAS)

    assert not uncovered, (
        f"{len(uncovered)} committed fixture(s) are absent from SANITIZED_SHAS, so pointing the "
        "sanitiser at them silently re-sanitises instead of refusing:\n"
        + "\n".join(f"  {name}" for name in uncovered)
        + "\n\nRegenerate the catalogue from the committed tree; do not add entries by hand."
    )


def test_the_catalogue_carries_no_entry_without_a_fixture() -> None:
    """A hash matching nothing is dead weight that hides the entries that matter.

    Kept separate from the coverage assertion above because the remedies differ:
    an uncovered fixture means the guard is too narrow, a stale entry means the
    catalogue is recording history rather than the tree.
    """
    digests = _committed_fixture_digests()
    stale = sorted(sha for sha in SANITIZED_SHAS if sha not in digests)

    assert not stale, (
        f"{len(stale)} catalogue entr(ies) match no committed fixture. Each is a hash of a file "
        "that no longer exists, almost certainly a fixture regenerated without updating this "
        f"list:\n" + "\n".join(f"  {sha}" for sha in stale[:10])
    )
