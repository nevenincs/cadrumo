"""Errors raised when built documentation cannot be packaged."""


class DocsPackagingError(RuntimeError):
    """A documentation root cannot enter the package."""
