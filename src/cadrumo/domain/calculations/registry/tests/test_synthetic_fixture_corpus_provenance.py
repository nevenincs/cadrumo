"""Provenance gate for the fixture corpora outside ``justificantes/``.

The sibling justificante gate polices ``tests/fixtures/justificantes/`` because
that tree backs a registry ``verification_source`` tag. One other committed PDF
corpus had neither a sidecar nor any gate at all:

- ``tests/fixtures/financial/n26/`` — three synthetic N26 savings statements
  feeding the financial-input PDF provider.

The files were generator-produced and did not say so. Worse, the generator set
the bare ``"reportlab"`` ``/Producer`` signature. An unsignatured producer is
exactly the evidence the discriminator reads as *real* origin, so synthetic
files presented as externally-authored bank statements to any gate that asked.

This module closes that by asserting the same contract the justificante gate
applies, against the same declared-then-cross-checked shape required of every
gated fixture: the sidecar declares provenance and the PDF's physical
``/Producer`` must agree with the declaration.

Enumeration is by directory glob rather than by a committed file list, so a
fixture added later without a sidecar fails here instead of passing unnoticed.

See Also:
    :mod:`~domain.calculations.registry.tests.test_verification_source_fixture_metadata`
        The same contract on the ``justificantes/`` corpus, keyed additionally
        to each profile's registry ``verification_source`` tag.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory
from .....core.resources.bundled_data import bundled_path
from .....tests.fixtures.provenance import (
    FIXTURE_PROVENANCE_SYNTHETIC,
    SYNTHETIC_FIXTURE_PRODUCER,
    producer_field,
    provenance_mismatches,
    sidecar_provenance,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# bundled_path() resolves to src/cadrumo/_data; the fixture tree lives one
# level up, mirroring the derivation in the justificante gate.
_FIXTURE_ROOT = bundled_path().resolve().parents[0] / "tests" / "fixtures"

_GATED_CORPORA: tuple[tuple[str, Path], ...] = (("n26", _FIXTURE_ROOT / "financial" / "n26"),)


def _corpus_pdfs(corpus_dir: Path) -> tuple[Path, ...]:
    """Return every committed PDF under ``corpus_dir``, sorted."""
    return scan_directory(corpus_dir, pattern="*.pdf")


_CASES: list[tuple[str, Path]] = [
    (corpus_name, pdf) for corpus_name, corpus_dir in _GATED_CORPORA for pdf in _corpus_pdfs(corpus_dir)
]


@pytest.mark.parametrize(
    "corpus_name,pdf_path",
    _CASES,
    ids=[f"{name}-{pdf.stem}" for name, pdf in _CASES],
)
def test_gated_fixture_provenance_agrees_with_producer_evidence(
    corpus_name: str,
    pdf_path: Path,
) -> None:
    """Each fixture self-declares provenance that its ``/Producer`` corroborates."""
    mismatches = provenance_mismatches(pdf_path)
    if mismatches:
        joined = "\n  ".join(mismatches)
        pytest.fail(f"{corpus_name} fixture provenance contradicts physical evidence:\n  {joined}")


@pytest.mark.parametrize("corpus_name,corpus_dir", _GATED_CORPORA, ids=[n for n, _d in _GATED_CORPORA])
def test_gated_corpus_is_not_empty(corpus_name: str, corpus_dir: Path) -> None:
    """A corpus that lost its PDFs would make the gate above silently vacuous.

    The parametrised gate enumerates by glob, so an emptied directory produces
    zero cases and reports green while checking nothing. This asserts the
    enumeration is actually populated.
    """
    assert _corpus_pdfs(corpus_dir), (
        f"{corpus_name} corpus at {corpus_dir} has no PDFs, so the provenance gate over it "
        "is dormant; restore the fixtures or retire this corpus from _GATED_CORPORA"
    )


@pytest.mark.parametrize(
    "pdf_path,expected_provenance",
    [(_FIXTURE_ROOT / "financial" / "n26" / "n26-savings-2024-06.pdf", FIXTURE_PROVENANCE_SYNTHETIC)],
    ids=["n26-synthetic"],
)
def test_shared_discriminator_accepts_committed_fixture_evidence(
    pdf_path: Path,
    expected_provenance: str,
) -> None:
    """The shared reader and discriminator accept committed fixture evidence."""
    assert sidecar_provenance(pdf_path) == expected_provenance
    assert (SYNTHETIC_FIXTURE_PRODUCER in (producer_field(pdf_path) or "").lower()) == (
        expected_provenance == FIXTURE_PROVENANCE_SYNTHETIC
    )
    assert provenance_mismatches(pdf_path) == []
