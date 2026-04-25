"""Casilla-domain exceptions."""

from __future__ import annotations

from pathlib import Path

from ..errors import AeatError


class CasillaError(AeatError):
    """Base class for every error raised by :mod:`aeat.casillas`."""


class CasillaParseError(CasillaError):
    """Raised when a casilla catalogue file cannot be parsed or validated."""

    def __init__(self, path: Path, message: str) -> None:
        """Initialize the parse error with the failing path and message.

        Args:
            path: Catalogue path that failed to parse.
            message: Human-readable parse failure summary.
        """
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


class VerifyError(CasillaError):
    """Base class for structured verification failures."""

    issue_code = "verify_error"

    def __init__(
        self,
        *,
        modelo: str,
        period: str,
        casilla_id: str | None,
        message: str,
    ) -> None:
        """Initialize the verification error.

        Args:
            modelo: Modelo identifier for the failing record.
            period: Period identifier for the failing record.
            casilla_id: Failing casilla identifier, if applicable.
            message: Human-readable failure summary.
        """
        self.modelo = modelo
        self.period = period
        self.casilla_id = casilla_id
        self.message = message
        self.__dict__["code"] = self.issue_code
        super().__init__(message)

    def __str__(self) -> str:
        """Render a compact, user-facing error string."""
        location = self.casilla_id or "<catalogue>"
        return f"{self.code}: {self.modelo}/{self.period}/{location}: {self.message}"


class UnreviewedRecordError(VerifyError):
    """Raised when a canonical record lacks required review metadata."""

    issue_code = "unreviewed_record"


class CrossReferenceError(VerifyError):
    """Raised when a record references another casilla that does not exist."""

    issue_code = "cross_reference"


class MissingFieldError(VerifyError):
    """Raised when a record is missing a required logical field."""

    issue_code = "missing_field"
