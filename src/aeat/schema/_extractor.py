"""Pluggable :class:`Extractor` protocol for :mod:`aeat.schema`.

Every backend produces an :class:`~aeat.schema.Modelo` record from a
per-backend configuration. The Protocol is deliberately minimal so
downstream extractors (portal HTML probe, Manual práctico + LLM, XSD
wire) can be swapped without rewriting call sites.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ._models import Modelo


@runtime_checkable
class Extractor(Protocol):
    """Any object that knows how to build a :class:`Modelo` from a source."""

    def extract(self) -> Modelo:
        """Return the extracted :class:`Modelo` record.

        Raises:
            aeat.schema.SchemaExtractionError: On source-parse
                failures.
        """
        ...
