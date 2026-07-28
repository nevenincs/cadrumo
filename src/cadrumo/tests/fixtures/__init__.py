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

__all__ = [
    "FIXTURE_PROVENANCE_REAL",
    "FIXTURE_PROVENANCE_SYNTHETIC",
    "RECOGNISED_FIXTURE_PROVENANCES",
    "SYNTHETIC_FIXTURE_PRODUCER",
]
