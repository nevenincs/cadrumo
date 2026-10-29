"""Missing prerequisites for the live desktop lane."""


class UnavailableError(Exception):
    """A prerequisite of the lane is absent; the run cannot say pass or fail."""
