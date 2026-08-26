"""Public defining module for the Modelo 145 communication period token.

The period token is carried on
:class:`M145CommunicationRecord` and on the
``modelo m145 create`` command surface, and the CLI command spec resolves this
enum by name at parameter-build time, so the contract is required outside its
owning package and lives in a public module of its own.
"""

from __future__ import annotations

from enum import StrEnum


class M145CommunicationPeriod(StrEnum):
    """Registry-backed local communication period tokens for Modelo 145."""

    COMMUNICATION = "comunicacion"
    VARIATION = "variacion"


__all__ = ["M145CommunicationPeriod"]
