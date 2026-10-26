"""Both directions of the evidence-corpus payload/provenance pair.

Every fixture in the ledger evidence corpus is two files: the payload, and a
``.provenance.json`` beside it naming the source, the licence and the content
address. The existing gates all start from the payload -- their listing filters
the sidecars out by suffix before iterating -- so they answer "does this fixture
declare its origin" and nothing answers "does this declaration still have a
fixture". A licence and a source URL attached to bytes that are gone is an
attestation with nothing under it, and the next file added at that name inherits
it silently.

The corpus has already survived the removal-and-restoration shape once: eight
payloads and their eight sidecars were deleted and re-added on the same day, in
two commits carrying the same subject. Both halves happened to move together.
Nothing made them.

Run via::

    uv run --no-sync pytest dev/corpus/tests/test_evidence_corpus_provenance_pairing.py -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..build_evidence_corpus import PROVENANCE_SIDECAR_SUFFIX, orphaned_provenance_sidecars

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# dev/corpus/tests/test_...py -> parents[3] is the repository root. Stated here
# because the arithmetic retargets silently on a move; the fixture below fails
# the gate rather than letting it measure an empty tree.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CORPUS = _REPO_ROOT / "src" / "cadrumo" / "application" / "ledger" / "tests" / "_evidence_corpus"


@pytest.fixture(autouse=True)
def _corpus_root_resolved() -> None:
    """Fail rather than pass vacuously if the corpus moved out from under this module."""
    assert _CORPUS.is_dir(), f"the evidence corpus is not where this gate looks: {_CORPUS}"


def _payloads() -> list[Path]:
    return sorted(p for p in _CORPUS.iterdir() if p.is_file() and not p.name.endswith(PROVENANCE_SIDECAR_SUFFIX))


def _sidecars() -> list[Path]:
    return sorted(_CORPUS.glob(f"*{PROVENANCE_SIDECAR_SUFFIX}"))


def test_the_corpus_holds_both_halves_of_a_real_pair() -> None:
    """Neither side may be empty, or the equality below measures nothing."""
    payloads, sidecars = _payloads(), _sidecars()
    assert len(payloads) > 10, f"only {len(payloads)} payload(s) found; the walk has stopped matching"
    assert sidecars, "no provenance sidecars found; every assertion here would be vacuous"


def test_no_declaration_outlives_the_file_it_attests() -> None:
    """The unwalked direction: a sidecar whose payload is gone.

    Reported by name rather than by count, because the remedy differs per entry:
    a sidecar for a deliberately retired fixture should go, and one for a fixture
    that was meant to come back means the restoration was half-done.
    """
    orphans = orphaned_provenance_sidecars(_CORPUS)

    assert not orphans, (
        f"{len(orphans)} provenance sidecar(s) attest a file the corpus no longer holds. Each carries a "
        "licence, a source URL and a content address for bytes that are not there, and a future fixture "
        "added at that name would inherit the claim:\n" + "\n".join(f"  {name}" for name in orphans)
    )


def test_every_payload_still_carries_its_declaration() -> None:
    """The walked direction, restated here so this module holds the whole pair.

    Duplicated deliberately: the sibling assertion lives with the parsing tests
    in ``src`` and could be narrowed or moved without anything noticing that the
    pair had lost a side. Two gates over one relationship is the cheap way to
    keep the relationship, rather than one gate, owned.
    """
    undeclared = [p.name for p in _payloads() if not (_CORPUS / f"{p.name}{PROVENANCE_SIDECAR_SUFFIX}").is_file()]

    assert not undeclared, (
        "these corpus payloads carry no provenance sidecar, so nothing records their source or licence:\n"
        + "\n".join(f"  {name}" for name in undeclared)
    )


def test_the_walk_reports_a_declaration_left_behind_by_its_payload(tmp_path: Path) -> None:
    """Detector teeth, on an isolated tree rather than the committed corpus.

    The defect is built the way it actually happens: a pair is written, then the
    payload alone is removed, as a bulk retirement that reverted only the file it
    immediately needed would leave it.
    """
    payload = tmp_path / "invoice.pdf"
    payload.write_bytes(b"%PDF-1.4\n")
    sidecar = tmp_path / f"invoice.pdf{PROVENANCE_SIDECAR_SUFFIX}"
    sidecar.write_text(
        json.dumps({"provenance": "real_corpus", "licence": "CC0", "source": "wikimedia-commons"}),
        encoding="utf-8",
    )
    assert orphaned_provenance_sidecars(tmp_path) == (), "a complete pair must not be reported"

    payload.unlink()

    assert orphaned_provenance_sidecars(tmp_path) == (sidecar.name,)


def test_a_directory_standing_in_for_the_payload_does_not_satisfy_the_declaration(tmp_path: Path) -> None:
    """A sidecar attests bytes, so only a file discharges it."""
    (tmp_path / "invoice.pdf").mkdir()
    sidecar = tmp_path / f"invoice.pdf{PROVENANCE_SIDECAR_SUFFIX}"
    sidecar.write_text("{}", encoding="utf-8")

    assert orphaned_provenance_sidecars(tmp_path) == (sidecar.name,)


def test_an_absent_corpus_root_reports_nothing_rather_than_raising(tmp_path: Path) -> None:
    """A missing tree is the caller's finding to make, not this walk's crash."""
    assert orphaned_provenance_sidecars(tmp_path / "not-here") == ()
