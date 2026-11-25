"""The kind a document appears to be, derived from its bytes and offered, never applied.

Whether a document is the movement's purchase invoice or an ordinary document
is the person's choice. Its bytes can support one answer: a document carrying a
structured single-invoice record (an EN16931 CII or UBL invoice, a Facturae
invoice, or a PDF embedding one) is an invoice by its own content. That is
offered as a proposal naming the recognised shape it rests on. Nothing else is
proposed: a plain PDF or an image says nothing about what it is, and a file's
name is never read as evidence of its kind.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, model_validator

from ...core.document_shape import STRUCTURED_DOCUMENT_SHAPES, DocumentShape
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

__all__ = ["EvidenceKindProposalV1", "derived_evidence_kind"]


class EvidenceKindProposalV1(BaseModel):
    """A document kind the bytes support, with the recognised shape it is derived from."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["purchase_invoice"] = "purchase_invoice"
    basis: DocumentShape
    """The structured single-invoice shape the probe recognised in the bytes."""

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _rests_on_a_structured_invoice(self) -> Self:
        if self.basis not in STRUCTURED_DOCUMENT_SHAPES:
            raise ValueError("a document kind proposal rests on a structured single-invoice shape")
        return self


def derived_evidence_kind(shape: DocumentShape | None) -> EvidenceKindProposalV1 | None:
    """Return the kind ``shape`` supports, or ``None`` when the bytes support no kind."""
    if shape is None or shape not in STRUCTURED_DOCUMENT_SHAPES:
        return None
    return EvidenceKindProposalV1(basis=shape)
