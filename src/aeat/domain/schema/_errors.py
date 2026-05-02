"""Domain errors raised by :mod:`aeat.domain.schema`.

Every error inherits from :class:`aeat.core.errors.AeatError` so the root
``AeatError`` exception is the single catch-all for the project's
domain failures.
"""

from __future__ import annotations

from ...core.errors import AeatError


class SchemaError(AeatError):
    """Base class for every :mod:`aeat.domain.schema` domain error."""


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
    :mod:`httpx` transport failures surfaced by the inbound schema fetcher.
    """


class SchemaValidationError(SchemaError):
    """Raised when a cached :class:`Modelo` JSON blob fails validation."""


class SchemaEvaluationError(SchemaError):
    """Raised when :func:`evaluate` cannot compute a formula AST.

    Distinct from :class:`SchemaExtractionError` (which covers
    source-parse failures) and :class:`SchemaValidationError` (which
    covers cached-blob validation): evaluation failures surface at
    runtime when a fully-extracted formula cannot be resolved against
    a concrete ``values`` mapping — typically division by zero or a
    casilla_id that the caller did not provide.
    """
