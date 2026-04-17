"""Domain errors raised by :mod:`aeat.schema`.

Every error inherits from :class:`aeat.errors.AeatError` so the root
``AeatError`` exception is the single catch-all for the project's
domain failures.
"""

from __future__ import annotations

from ..errors import AeatError


class SchemaError(AeatError):
    """Base class for every :mod:`aeat.schema` domain error."""


class SchemaExtractionError(SchemaError):
    """Raised when an :class:`Extractor` fails to parse its source.

    Messages should include the BOE reference (or equivalent source
    identifier) and, when relevant, the page number that triggered the
    failure so a human reviewer can investigate without re-running the
    extractor.
    """


class SchemaCacheError(SchemaError):
    """Raised when on-disk schema persistence fails.

    Covers dirty cache filenames, missing parent directories, and
    :mod:`httpx` transport failures surfaced by :func:`fetch_boe_pdf`.
    """


class SchemaValidationError(SchemaError):
    """Raised when a cached :class:`Modelo` JSON blob fails validation."""
