"""Opaque CCAA tokens projected from the governed tax-residence catalogue.

The community membership and the retired ISO aliases are filing facts.  This
module keeps only the token type and compatibility-shaped parsing mechanics;
the dated vocabulary is resolved by :mod:`ccaa_catalogue`.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ...core.errors.hierarchy import CoreValidationError, ProfileAnswerTypeError, pydantic_validation_boundary


class _CCAAType(type):
    """Expose registry-projected choices through the historical type surface."""

    def __iter__(cls: _CCAAType) -> Iterator[CCAA]:
        from ..calculations.registry.ccaa_catalogue import resolve_ccaa_catalogue

        return iter(resolve_ccaa_catalogue().choices)

    def __getattr__(cls, name: str) -> CCAA:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        from ..calculations.registry.ccaa_catalogue import resolve_ccaa_catalogue

        try:
            return resolve_ccaa_catalogue().require_member_name(name)
        except (KeyError, ValueError) as exc:
            raise AttributeError(name) from exc


class CCAA(str, metaclass=_CCAAType):
    """Registry-projected ordinary common-regime CCAA token.

    Instantiation is deliberately fail-closed: arbitrary strings cannot become
    CCAA values without passing through the selected dated facts catalogue.
    ``from_registry`` is private to the typed projection module.
    """

    __slots__ = ()

    def __new__(cls, value: object, *, _registry_validated: bool = False) -> Self:
        """Construct only registry-projected CCAA tokens."""
        if _registry_validated:
            if not isinstance(value, str) or not value:
                raise ValueError("CCAA token must be a non-empty string")
            return str.__new__(cls, value)
        from ..calculations.registry.ccaa_catalogue import resolve_ccaa_catalogue
        from ..calculations.registry.errors import RegistryValidationError

        try:
            return cls.from_registry(str(resolve_ccaa_catalogue().require(value)))
        except RegistryValidationError as exc:
            raise ValueError(str(exc)) from exc

    @classmethod
    def from_registry(cls, value: str) -> Self:
        """Construct the typed value from its canonical registry token."""
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("CCAA must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[object],
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Accept only a projected CCAA token and serialize it as text."""
        del source_type, handler
        return core_schema.no_info_plain_validator_function(
            pydantic_validation_boundary(cls._require_registry_token),
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def from_iso_code(cls, code: str) -> Self:
        """Resolve one of the registry-declared three-letter aliases."""
        from ..calculations.registry.ccaa_catalogue import resolve_ccaa_catalogue

        return cls.from_registry(str(resolve_ccaa_catalogue().from_iso_code(code)))

    @classmethod
    def from_label(cls, label: str) -> Self:
        """Resolve a canonical token, normalized label, or ISO alias."""
        from ..calculations.registry.ccaa_catalogue import resolve_ccaa_catalogue
        from ..calculations.registry.errors import RegistryValidationError

        try:
            return cls.from_registry(str(resolve_ccaa_catalogue().from_label(label)))
        except (KeyError, RegistryValidationError) as exc:
            raise ProfileAnswerTypeError(str(exc)) from exc

    @property
    def value(self) -> str:
        """Return the canonical token used by profile and registry bindings."""
        return str(self)

    @property
    def name(self) -> str:
        """Return the canonical token as a diagnostic name."""
        return str(self)


__all__ = ["CCAA"]
