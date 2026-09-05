"""Deterministic readers for structured electronic-invoice documents.

An e-invoice that already carries a machine-readable record is *read*, not
inferred. Parsing it is exact, model-free and costs nothing marginal: it runs on
the already-declared ``defusedxml``, needs no GPU, adds no licence exposure and
is available on a default install with no optional extra enabled.

That is why these readers sit in the deterministic core rather than behind the
inference boundary, and why they sit in ``adapters/inbound/`` beside the six
sibling packages that already parse externally-authored formats -- ``pdf``,
``financial``, ``borrador``, ``censo``, ``declaracion`` and ``justificante``.

The routing order this package enables is itself a control, and is recorded as
one so a later change optimising for latency does not discard it: **a document
carrying a structured record reaches no model at all**, which makes prompt
injection categorically impossible for that document rather than merely
mitigated. The corresponding hazard moves to the XML reader rather than
disappearing, and is bounded there -- see :mod:`.xml`.

Two properties are load-bearing and neither is an accuracy claim. The reader
**fails loudly**: a malformed document raises :class:`EInvoiceXmlParseError` and
yields no record, where a model handed the same bytes returns a confident,
plausible, wrong invoice. And it is **three to five orders of magnitude
faster** than a vision read of the same document.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
