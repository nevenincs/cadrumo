"""Shared bounded identifiers and field labels for evidence follow-up contracts."""

from typing import Annotated

from pydantic import Field

EvidenceFollowupReference = Annotated[str, Field(min_length=1, max_length=64)]


EvidenceFollowupText = Annotated[str, Field(min_length=1, max_length=2_048)]


EvidenceReviewFieldName = Annotated[str, Field(min_length=1, max_length=128)]
