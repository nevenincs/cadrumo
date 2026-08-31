"""Test-fixture package root.

Makes the fixture subtrees proper packages so that identically-named test
modules (e.g. several ``test_generate.py``) import under unique dotted paths
under pytest's prepend import mode, rather than colliding on basename.

It also owns the fixture-provenance vocabulary shared by every synthetic
fixture generator and by the gates that police them. Provenance is *declared*
in each fixture's ``.json`` sidecar and *cross-checked* against the physical
``/Producer`` DocInfo of the committed PDF, so a mis-stamped sidecar fails
rather than passing on its own say-so.

That cross-check only discriminates while every synthetic generator writes
:data:`SYNTHETIC_FIXTURE_PRODUCER`. A real AEAT PDF carrying no ``/Producer``
is otherwise indistinguishable from a synthetic one whose generator never set
it, so a generator that omits the signature silently converts its own output
into apparent real-corpus evidence. The signature therefore lives here as one
constant rather than as a literal repeated per generator: three generators
previously disagreed about it, and the two that disagreed emitted producers
that made synthetic bytes read as real.
"""

from __future__ import annotations

import json
from pathlib import Path

import pdfplumber

SYNTHETIC_FIXTURE_PRODUCER = "aeat-test-fixture-generator"
"""``/Producer`` DocInfo value every synthetic fixture generator must set.

The provenance gates treat its presence as physical evidence of synthetic
origin and its absence as evidence of real origin, so a generator that omits
it disarms the discriminator for every fixture it writes.
"""

FIXTURE_PROVENANCE_SYNTHETIC = "synthetic_generated"
"""Sidecar ``provenance`` value for generator-produced bytes."""

FIXTURE_PROVENANCE_REAL = "real_corpus"
"""Sidecar ``provenance`` value for externally-authored (AEAT or bank) bytes."""

RECOGNISED_FIXTURE_PROVENANCES = frozenset(
    {FIXTURE_PROVENANCE_SYNTHETIC, FIXTURE_PROVENANCE_REAL},
)
"""The closed provenance set a gated fixture sidecar may declare."""


def producer_field(pdf_path: Path) -> str | None:
    """Return ``pdf_path``'s ``/Producer`` DocInfo value, if declared."""
    with pdfplumber.open(str(pdf_path)) as pdf:
        metadata = pdf.metadata or {}
        value = metadata.get("Producer")
        return str(value) if value else None


def sidecar_provenance(pdf_path: Path) -> str | None:
    """Return the sidecar's declared provenance, or ``None`` when undeclared.

    A missing sidecar and a sidecar without ``provenance`` deliberately collapse
    to the same result: neither declaration is sufficient for a gated fixture.
    """
    sidecar = pdf_path.with_suffix(".json")
    if not sidecar.is_file():
        return None
    value = json.loads(sidecar.read_text(encoding="utf-8")).get("provenance")
    return str(value) if value is not None else None


def provenance_mismatches(pdf_path: Path) -> list[str]:
    """Return every disagreement between a sidecar declaration and PDF bytes."""
    producer = producer_field(pdf_path)
    is_synthetic = SYNTHETIC_FIXTURE_PRODUCER in (producer or "").lower()
    provenance = sidecar_provenance(pdf_path)

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
