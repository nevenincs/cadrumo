"""Presentation stages for the profile's guided setup and review."""

from enum import StrEnum


class ProfileSetupStage(StrEnum):
    """The ordered destinations; answers and completion stay in the profile."""

    OVERVIEW = "overview"
    GET_DATA = "get_data"
    REQUIRED = "required"
    REVIEW = "review"
    READY = "ready"


SETUP_STAGES = tuple(ProfileSetupStage)
