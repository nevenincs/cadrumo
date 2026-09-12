"""Domain-facing setup answer projection seam.

The answer catalogue itself is resolved by
``registry.setup_profile_bindings``.  This module keeps deadline consumers on
the domain side of the boundary while reusing the core model and its lazy
registry-backed mapping; it does not define a second catalogue.
"""

from __future__ import annotations

from ...core.setup_answers import (
    PROFILE_OUTPUT_LANGUAGE_PATH,
    SETUP_ANSWER_FIELDS,
    SetupAnswers,
    SetupFieldSpec,
    project_setup_answers,
)

__all__ = [
    "PROFILE_OUTPUT_LANGUAGE_PATH",
    "SETUP_ANSWER_FIELDS",
    "SetupAnswers",
    "SetupFieldSpec",
    "project_setup_answers",
]
