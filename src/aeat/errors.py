"""Domain exception hierarchy for the AEAT package.

Every subpackage should raise subclasses of AeatError to ensure
predictable error handling throughout the application.
"""


class AeatError(Exception):
    """Base exception for all AEAT domain errors."""

    pass


class FixtureProvisioningError(AeatError):
    """Raised when Google Workspace test-fixture provisioning fails.

    Thrown by the provisioning and teardown scripts under ``scripts/``
    whenever a Drive / Sheets / Docs call cannot satisfy the catalogued
    intent (missing parent, quota exhausted, unexpected dedup result, etc).
    """

    pass
