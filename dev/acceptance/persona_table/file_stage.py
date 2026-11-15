"""What a surface's file stage says about a row the backend filed locally.

A surface line states the filed state with its optional ``file`` word. ``pass`` is the filed state shown; a recorded
``not-shown`` says the surface shows none, and any other stage word disagrees: each makes the row differ. A line with
no ``file`` word measured nothing: the row is neither matched nor different for it (it is counted and aged apart).
A row the backend did not file locally is not held to a file stage.
"""

from __future__ import annotations

NOT_SHOWN = "not-shown"
"""The file word of a surface that shows no filed state."""


def file_causes(filed_locally: bool, word: str | None, surface: str) -> list[str]:
    """The cause of a filed row when the surface's recorded ``word`` is not the filed state; none when unmeasured."""
    if not filed_locally or word in (None, "pass"):
        return []
    if word == NOT_SHOWN:
        return [f"file not shown by {surface}, table filed locally"]
    return [f"file {surface} {word}, table filed locally"]


def file_unmeasured(filed_locally: bool, word: str | None) -> bool:
    """Whether the line says nothing about the filed state of a row the backend filed locally."""
    return filed_locally and word is None
