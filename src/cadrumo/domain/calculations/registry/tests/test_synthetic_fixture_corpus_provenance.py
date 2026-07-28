"""Provenance gate for the fixture corpora outside ``justificantes/``.

The sibling justificante gate polices ``tests/fixtures/justificantes/`` because
that tree backs a registry ``verification_source`` tag. Two other committed PDF
corpora had neither a sidecar nor any gate at all:

- ``tests/fixtures/borrador/`` — three synthetic Modelo 100 borrador renders
  feeding the M100 verification chain.
- ``tests/fixtures/financial/n26/`` — three synthetic N26 savings statements
  feeding the financial-input PDF provider.

Both were generator-produced and neither said so. Worse, neither generator set
the ``/Producer`` signature the discriminator rests on: the borrador writer set
none at all (reportlab then stamped its own default) and the N26 writer set the
bare string ``"reportlab"``. An unsignatured producer is exactly the evidence
the discriminator reads as *real* origin, so six synthetic files presented as
externally-authored documents to any gate that asked — the N26 ones as real
bank statements.

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

import json
from pathlib import Path

import pdfplumber
import pytest

from .....core.resources import bundled_path
from .....tests.fixtures import (
    FIXTURE_PROVENANCE_REAL,
    FIXTURE_PROVENANCE_SYNTHETIC,
    RECOGNISED_FIXTURE_PROVENANCES,
    SYNTHETIC_FIXTURE_PRODUCER,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# bundled_path() resolves to src/cadrumo/_data; the fixture tree lives one
# level up, mirroring the derivation in the justificante gate.
_FIXTURE_ROOT = bundled_path().resolve().parents[0] / "tests" / "fixtures"

_GATED_CORPORA: tuple[tuple[str, Path], ...] = (
    ("borrador", _FIXTURE_ROOT / "borrador"),
    ("n26", _FIXTURE_ROOT / "financial" / "n26"),
)


def _producer_field(pdf_path: Path) -> str | None:
    """Return the ``/Producer`` DocInfo value for a PDF, or None if absent."""
    with pdfplumber.open(str(pdf_path)) as pdf:
        meta = pdf.metadata or {}
        value = meta.get("Producer")
        return str(value) if value else None


def _sidecar_provenance(pdf_path: Path) -> str | None:
    """Return the sidecar's declared ``provenance``, or None when undeclared.

    Absent sidecar and present-but-silent sidecar collapse to the same answer
    deliberately: both leave the fixture undeclared, which is the condition the
    gate refuses.
    """
    sidecar = pdf_path.with_suffix(".json")
    if not sidecar.is_file():
        return None
    value = json.loads(sidecar.read_text(encoding="utf-8")).get("provenance")
    return str(value) if value is not None else None


def provenance_mismatches(pdf_path: Path) -> list[str]:
    """Return every way ``pdf_path``'s declared provenance contradicts its bytes.

    An empty list means the fixture self-declares a recognised provenance and
    the physical ``/Producer`` evidence agrees with that declaration.

    Factored out of the tests so the anti-tautology proof below can drive it
    over deliberately-corrupt inputs and observe it *fail*. A gate whose
    discriminating logic exists only inside a passing assertion cannot be shown
    to discriminate at all.
    """
    producer = _producer_field(pdf_path)
    is_synthetic = SYNTHETIC_FIXTURE_PRODUCER in (producer or "").lower()
    provenance = _sidecar_provenance(pdf_path)

    if provenance is None:
        return [
            f"{pdf_path.name}: no sidecar provenance declared; every gated fixture "
            f"must self-declare {FIXTURE_PROVENANCE_REAL} or {FIXTURE_PROVENANCE_SYNTHETIC} "
            f"in {pdf_path.with_suffix('.json').name}",
        ]
    if provenance not in RECOGNISED_FIXTURE_PROVENANCES:
        return [
            f"{pdf_path.name}: sidecar provenance {provenance!r} is not one of "
            f"{sorted(RECOGNISED_FIXTURE_PROVENANCES)}",
        ]
    if provenance == FIXTURE_PROVENANCE_SYNTHETIC and not is_synthetic:
        return [
            f"{pdf_path.name}: sidecar declares {FIXTURE_PROVENANCE_SYNTHETIC} but "
            f"/Producer={producer!r} lacks the {SYNTHETIC_FIXTURE_PRODUCER!r} signature; "
            "an unsignatured producer reads as real origin",
        ]
    if provenance == FIXTURE_PROVENANCE_REAL and is_synthetic:
        return [
            f"{pdf_path.name}: sidecar declares {FIXTURE_PROVENANCE_REAL} but "
            f"/Producer={producer!r} carries the synthetic generator signature",
        ]
    return []


def _corpus_pdfs(corpus_dir: Path) -> list[Path]:
    """Return every committed PDF under ``corpus_dir``, sorted."""
    if not corpus_dir.is_dir():
        return []
    return sorted(corpus_dir.glob("*.pdf"))


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


def _write_probe_pdf(path: Path, *, producer: str | None) -> None:
    """Render a real one-page PDF at ``path``, optionally signing its producer."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=A4)
    if producer is not None:
        c.setProducer(producer)
    c.drawString(72, 720, "provenance discriminator probe")
    c.showPage()
    c.save()


def _write_sidecar(pdf_path: Path, provenance: str | None) -> None:
    """Write ``pdf_path``'s sidecar, omitting ``provenance`` when None."""
    payload: dict[str, str] = {} if provenance is None else {"provenance": provenance}
    pdf_path.with_suffix(".json").write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize(
    "producer,provenance,expected_fragment",
    [
        (None, FIXTURE_PROVENANCE_SYNTHETIC, "lacks the"),
        ("reportlab", FIXTURE_PROVENANCE_SYNTHETIC, "lacks the"),
        (SYNTHETIC_FIXTURE_PRODUCER, FIXTURE_PROVENANCE_REAL, "carries the synthetic generator signature"),
        (SYNTHETIC_FIXTURE_PRODUCER, None, "no sidecar provenance declared"),
        (SYNTHETIC_FIXTURE_PRODUCER, "invented_provenance", "is not one of"),
    ],
    ids=[
        "unsignatured-claiming-synthetic",
        "reportlab-producer-claiming-synthetic",
        "signatured-claiming-real",
        "signatured-but-undeclared",
        "unrecognised-provenance-value",
    ],
)
def test_the_discriminator_rejects_each_way_a_declaration_can_lie(
    tmp_path: Path,
    producer: str | None,
    provenance: str | None,
    expected_fragment: str,
) -> None:
    """Anti-tautology proof: the checker fails on each corrupt pairing.

    Every committed fixture currently passes, so the gate above cannot by
    itself show that it would catch anything. These cases drive the same
    checker over real PDFs written to carry each defect and assert it reports
    the mismatch — including the two shapes actually found in the tree before
    this work: an unsignatured producer, and the literal ``"reportlab"``.
    """
    pdf_path = tmp_path / "probe.pdf"
    _write_probe_pdf(pdf_path, producer=producer)
    _write_sidecar(pdf_path, provenance)

    mismatches = provenance_mismatches(pdf_path)

    assert mismatches, (
        f"the discriminator accepted producer={producer!r} against a sidecar declaring "
        f"{provenance!r}; it cannot detect this class of mis-declaration"
    )
    assert any(expected_fragment in m for m in mismatches), (
        f"expected a mismatch naming {expected_fragment!r}, got: {mismatches}"
    )


def test_the_discriminator_accepts_a_truthfully_declared_fixture(tmp_path: Path) -> None:
    """The mirror of the proof above: a correct pairing must not be flagged.

    Without this, a checker that returned a mismatch unconditionally would
    satisfy every case above while being useless.
    """
    pdf_path = tmp_path / "probe.pdf"
    _write_probe_pdf(pdf_path, producer=SYNTHETIC_FIXTURE_PRODUCER)
    _write_sidecar(pdf_path, FIXTURE_PROVENANCE_SYNTHETIC)

    assert provenance_mismatches(pdf_path) == []
