"""Domain exception hierarchy for the AEAT package.

Every subpackage should raise subclasses of AeatError to ensure
predictable error handling throughout the application.
"""


class AeatError(Exception):
    """Base exception for all AEAT domain errors."""

    pass
