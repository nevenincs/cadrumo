"""The jobs a model is chosen for: Cadrumo's model-role vocabulary.

The roles are Cadrumo's internal vocabulary; the models are not. Nobody chooses
a model per role: the agent service derives each role's model from the
person's local model list by the capability the role needs.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["ModelRole"]


class ModelRole(StrEnum):
    """The distinct jobs a model is selected for.

    Kept as roles rather than as one "the model" axis because the capability
    bars differ: only vision transcription needs image input, and the text
    roles must be satisfiable by a lane that reads no image at all. Each role
    resolves to its own model.

    ``VISION_TRANSCRIPTION`` reads a scanned or photographed page;
    ``TEXT_EXTRACTION`` classifies an already-extracted text layer;
    ``COLUMN_ROLE_MAPPING`` names the columns of a delimited table from their
    header strings; and ``SUPPLY_NATURE_PROPOSAL`` proposes whether invoice
    lines supply goods or services for an operator to confirm.
    """

    VISION_TRANSCRIPTION = "vision_transcription"
    TEXT_EXTRACTION = "text_extraction"
    COLUMN_ROLE_MAPPING = "column_role_mapping"
    SUPPLY_NATURE_PROPOSAL = "supply_nature_proposal"
