"""Opaque prorrata-register axes projected from facts authority.

The register regime, special-prorrata transition, art. 105 provenance, and
differentiated-sector letter vocabularies are governing-body facts. This core
module retains only their structural token contracts. Registry membership and
legal meaning, including whether a regime apportions a deduction, are projected
by ``domain.calculations.registry.prorrata_register_catalogue``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self


class ProrrataRegisterRegime(str):
    """Opaque registry-projected regime token for one register ejercicio."""

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Create a validated register-regime token."""
        if not _registry_validated:
            raise TypeError("ProrrataRegisterRegime tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value:
            raise ValueError("prorrata register regime token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def from_registry(cls, value: str) -> Self:
        """Construct the typed value from its canonical registry token."""
        return cls(value, _registry_validated=True)

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: object, _handler: object) -> object:
        """Expose the projected register-regime token to Pydantic."""
        from pydantic_core import core_schema

        return core_schema.no_info_after_validator_function(
            cls._project_pydantic,
            core_schema.str_schema(min_length=1),
        )

    @classmethod
    def _project_pydantic(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls.from_registry(value.strip())
            except (TypeError, ValueError) as exc:
                raise ValueError("prorrata register regime must be a non-empty structural token") from exc
        raise TypeError("prorrata register regime must be a string token")

    @property
    def value(self) -> str:
        """Return the canonical register-regime token text."""
        return str(self)


class ProrrataEspecialTransitionKind(str):
    """Opaque registry-projected special-prorrata transition token."""

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Create a validated special-prorrata transition token."""
        if not _registry_validated:
            raise TypeError("ProrrataEspecialTransitionKind tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value:
            raise ValueError("prorrata transition token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def from_registry(cls, value: str) -> Self:
        """Construct the typed value from its canonical registry token."""
        return cls(value, _registry_validated=True)

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: object, _handler: object) -> object:
        """Expose the projected transition token to Pydantic."""
        from pydantic_core import core_schema

        return core_schema.no_info_after_validator_function(
            cls._project_pydantic,
            core_schema.str_schema(min_length=1),
        )

    @classmethod
    def _project_pydantic(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls.from_registry(value.strip())
            except (TypeError, ValueError) as exc:
                raise ValueError("prorrata transition must be a non-empty structural token") from exc
        raise TypeError("prorrata transition must be a string token")

    @property
    def value(self) -> str:
        """Return the canonical transition token text."""
        return str(self)


class ProrrataActivityRowType(StrEnum):
    """Official Modelo 303 token for one per-activity prorrata row."""

    GENERAL = "G"
    ESPECIAL = "E"


class ProrrataProvisionalProvenance(str):
    """Opaque registry-projected art. 105 provisional-provenance token."""

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Create a validated provisional-provenance token."""
        if not _registry_validated:
            raise TypeError("ProrrataProvisionalProvenance tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value:
            raise ValueError("prorrata provisional provenance token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def from_registry(cls, value: str) -> Self:
        """Construct the typed value from its canonical registry token."""
        return cls(value, _registry_validated=True)

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: object, _handler: object) -> object:
        """Expose the projected provenance token to Pydantic."""
        from pydantic_core import core_schema

        return core_schema.no_info_after_validator_function(
            cls._project_pydantic,
            core_schema.str_schema(min_length=1),
        )

    @classmethod
    def _project_pydantic(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls.from_registry(value.strip())
            except (TypeError, ValueError) as exc:
                raise ValueError("prorrata provenance must be a non-empty structural token") from exc
        raise TypeError("prorrata provenance must be a string token")

    @property
    def value(self) -> str:
        """Return the canonical provenance token text."""
        return str(self)


class SectorDiferenciadoLetra(str):
    """Opaque registry-projected LIVA art. 9.1.c sector-letter token."""

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Create a validated differentiated-sector letter token."""
        if not _registry_validated:
            raise TypeError("SectorDiferenciadoLetra tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value:
            raise ValueError("differentiated-sector letter must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def from_registry(cls, value: str) -> Self:
        """Construct the typed value from its canonical registry token."""
        return cls(value, _registry_validated=True)

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: object, _handler: object) -> object:
        """Expose the projected sector-letter token to Pydantic."""
        from pydantic_core import core_schema

        return core_schema.no_info_after_validator_function(
            cls._project_pydantic,
            core_schema.str_schema(min_length=1),
        )

    @classmethod
    def _project_pydantic(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls.from_registry(value.strip())
            except (TypeError, ValueError) as exc:
                raise ValueError("sector letter must be a non-empty structural token") from exc
        raise TypeError("sector letter must be a string token")

    @property
    def value(self) -> str:
        """Return the canonical sector-letter token text."""
        return str(self)


__all__ = [
    "ProrrataActivityRowType",
    "ProrrataEspecialTransitionKind",
    "ProrrataProvisionalProvenance",
    "ProrrataRegisterRegime",
    "SectorDiferenciadoLetra",
]
