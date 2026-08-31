"""The per-field extraction provenance closed value set.

Every field an ingestion path proposes for a draft carries one origin token
recording HOW the value was obtained. The axis is declared as a
:class:`enum.StrEnum` in ``core`` per the core-authority discipline (closed
axes live in ``core/``, hydrated at boundaries, asserted as members in tests):
the readers that produce values, the application layer that projects them, and
the CLI that shows them to the operator all sit in different packages, and
``core`` is the only home all three can reach without one depending on another.

Each member's value is byte-identical to its stored token, so a persisted
origin hydrates back to its member and an unknown token is refused at the
boundary rather than silently accepted.

Deliberately absent: any numeric model self-confidence. A model's confidence
estimate is not evidence — it is the model's opinion of its own output, which
cannot corroborate that output. The trustworthy axes are *how the value was
obtained* (this enum) and *what verification it passed*, and both are facts.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["FieldOrigin"]


class FieldOrigin(StrEnum):
    """How one field's value was obtained from a source document.

    Closed by construction. The distinction is load-bearing rather than
    descriptive: a value read from a document's own machine-readable record is
    EXACT, while a value a model read off a rendered page is probabilistic, and
    a persisted record must be able to answer which it was. An exactly-read
    value therefore stays distinguishable from a model-read one all the way
    from the byte source to the operator's screen; nothing may launder the
    latter into the former.
    """

    EXACT_STRUCTURED = "exact_structured"
    """Read from the document's own machine-readable record. Exact."""

    TEXT_LAYER = "text_layer"
    """Recovered by grounded heuristics over an extracted PDF text layer."""

    VISION = "vision"
    """Read by a local vision model from a rasterised page. Probabilistic."""

    TABULAR_MAPPED = "tabular_mapped"
    """Copied from a tabular cell under a model-assigned column-role mapping.

    The model assigns roles to columns, never touches a cell value, and
    deterministic code performs the copy — so the cell content is exact while
    the column's meaning is model-assigned.
    """

    OPERATOR = "operator"
    """Supplied or corrected by the operator at the confirm boundary."""

    DERIVED = "derived"
    """Concluded deterministically from other values already on the record.

    Not a reading. Every other member here answers "how was this copied off the
    document"; this one answers "what followed from what was copied", and the
    distinction has to survive because a derived value has no printed form to
    point at. It is not weaker evidence than a read value -- the derivation is
    deterministic code over inputs that were themselves read and anchored -- but
    it is evidence ABOUT those inputs rather than about the page, so an operator
    auditing it must be sent to the inputs rather than to a highlighted phrase.

    A derived value therefore records the inputs it followed from in place of an
    anchor, and can never claim the ANCHORED outcome; see the provenance
    envelope's validators.
    """
