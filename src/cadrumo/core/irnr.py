"""Typed axes for the IRNR (non-resident income tax) treaty surface.

The closed conceptual axes governing the Modelo 210 IRNR rate-resolution path
remain :class:`enum.StrEnum` values here. Registry-owned payer-mode membership
is represented by an opaque token and projected at the domain boundary rather
than enumerated in this core module:

* :class:`TipoRentaIrnr` — the income-type axis an IRNR filer tags each item
  with. It keys the TRLIRNR baseline rate table, the treaty override rows, and
  the Art. 25.1.b pension tariff branch. It was previously a free-text casilla
  value with no enum home, which forced adjacent verification work to route a
  categorical-equality predicate around the untyped axis.

* :class:`ConvenioOverrideKind` — an opaque token projected from the governed
  ``irnr.convenio.override`` fact. Keeping the token typed lets consumers make
  the "más favorable" / limitation-of-benefits decision without duplicating the
  catalogue's value set here.

Both IRNR axes are consumed by the cross-cutting ``irnr.convenio.override``
authored fact and its :class:`~domain.calculations.registry.ConvenioAuthority`
projection. The registry TOML stays free-form (a plain string token); the
loader hydrates typed tokens at the boundary.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from .errors.hierarchy import CoreValidationError


class TipoRentaIrnr(str):
    """Opaque IRNR income-type token projected from governed fact 0080.

    The value set and its Modelo 210 code projection belong to the dated facts
    catalogue.  This wire type deliberately carries no Python member list;
    callers must obtain instances through the typed registry resolver.
    """

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        if not _registry_validated:
            raise TypeError("TipoRentaIrnr tokens must be projected from the registry")
        if not isinstance(value, str) or not value:
            raise ValueError("TipoRentaIrnr token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def _from_registry(cls, value: str) -> Self:
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("TipoRentaIrnr must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[object],
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Accept only a projected token and serialize it as text."""
        del source_type, handler
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def value(self) -> str:
        """Return the canonical wire token."""
        return str(self)

    @property
    def name(self) -> str:
        """Return the canonical token for diagnostics."""
        return str(self)


class M210PayerMode(str):
    """Opaque Modelo 210 payer-mode token projected from the registry.

    The selected detail catalogue owns payer-mode membership, descriptions, and
    the code-35 applicability rule.  This core type carries only the typed wire
    token; callers must obtain values through the registry projection.
    """

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        if not _registry_validated:
            raise TypeError("M210PayerMode tokens must be projected from the registry")
        if not isinstance(value, str) or not value:
            raise ValueError("M210PayerMode token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def _from_registry(cls, value: str) -> Self:
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("M210PayerMode must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[object],
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Accept only a projected token and serialize it as text."""
        del source_type, handler
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def value(self) -> str:
        """Return the canonical wire token."""
        return str(self)

    @property
    def name(self) -> str:
        """Return the canonical token for diagnostics."""
        return str(self)


class M210GrossIncomeSourceMode(StrEnum):
    """Authority selected for Modelo 210 ``rendimientos_integros`` on one revision."""

    MANUAL = "manual"
    LEDGER = "ledger"


class ConvenioOverrideKind(str):
    """Opaque treaty-override token projected from ``irnr.convenio.override``.

    The governed catalogue owns the available override values. Keeping this
    type opaque prevents a second, closed Python taxonomy from drifting away
    from that catalogue; registry consumers must receive their token through
    ``_from_registry``.
    """

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        if not _registry_validated:
            raise TypeError("ConvenioOverrideKind tokens must be projected from the registry")
        if not isinstance(value, str) or not value:
            raise ValueError("ConvenioOverrideKind token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def _from_registry(cls, value: str) -> Self:
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("ConvenioOverrideKind must be projected from the governed registry")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def value(self) -> str:
        return str(self)

    @property
    def name(self) -> str:
        return str(self)
