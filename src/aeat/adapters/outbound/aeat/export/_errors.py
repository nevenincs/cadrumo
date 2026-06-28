"""Shared exception types for AEAT export and preflight adapters."""

from __future__ import annotations

from .....core.errors import AeatError


class ExportError(AeatError):
    """Base class for every outbound AEAT export domain error."""


class AeatExportFormatError(ExportError, ValueError):
    """Raised when a filing draft cannot be serialised to a concrete BOE format.

    Inherits from ValueError to maintain compatibility with Pydantic
    validators and other standard library consumers that expect
    value-related failures.
    """
