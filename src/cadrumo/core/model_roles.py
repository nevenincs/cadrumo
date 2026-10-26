"""The jobs a model is chosen for: Cadrumo's model-role vocabulary.

The roles are Cadrumo's; the models are not. The person selects a lane and a
model for each role from the agent's provider catalogue, and the agent service
stores and resolves that selection.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["ModelRole"]


class ModelRole(StrEnum):
    """The distinct jobs a model is selected for.

    Kept as roles rather than as one "the model" axis because the capability
    bars differ: only vision transcription needs image input, and the text
    roles must be satisfiable by a lane that reads no image at all. Each role
    has its own selection.

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
