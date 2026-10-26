"""Closed progress states for the modelo work review projection."""

from enum import StrEnum


class ModeloWorkProgressState(StrEnum):
    """Progress of one modelo revision against its declared manifest."""

    COMPLETE = "complete"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    UNDEFINED = "undefined"


__all__ = ["ModeloWorkProgressState"]
