"""Modelo 720 / 721 foreign-asset obligation-group semantic layer.

Typed abstraction over the raw Modelo 720 casilla bindings. The registry
declares the ``clave-tipo-de-bien-o-derecho`` field and a ``foreign_asset``
row source whose ``asset_class_code`` an operator otherwise reads as an opaque
one-character clave. This module lifts that clave onto the four regulatory
declaration bloques of the Reglamento General de Gestión e Inspección
(RD 1065/2007). The selected fact revision owns the concrete group vocabulary
and the provisions that establish each obligation.

It is a surfacing layer only. It does not aggregate observations, compute a
casilla value, apply a declarability gate, or resolve a binding. The
application's registry-resolved threshold bridge supplies those legal values.
The obligation group is still the legally load-bearing axis; this module keeps
only the opaque token boundary and the unchanged Modelo 720 code projection.

The :class:`ForeignAssetObligationGroup` token is declared here as an opaque
wire type; its values and establishing provisions are projected from the
facts-registry taxonomy by the domain resolver. It is the obligation-group
sibling of the per-clave :class:`~core.aggregation.ForeignAssetClass`.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from .aggregation import ForeignAssetClass
from .errors.hierarchy import CoreValidationError


class ForeignAssetObligationGroup(str):
    """Opaque RGAT obligation-group token projected from fact 0132.

    The four group values and their establishing legal references are governed
    facts. This core type deliberately carries no member list or citation
    table; callers obtain instances from the typed registry projection.
    """

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Create a validated foreign-asset obligation token."""
        if not _registry_validated:
            raise TypeError("ForeignAssetObligationGroup tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value:
            raise ValueError("ForeignAssetObligationGroup token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def _from_registry(cls, value: str) -> Self:
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("ForeignAssetObligationGroup must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Expose the projected foreign-asset token to Pydantic."""
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def value(self) -> str:
        """Return the canonical foreign-asset obligation token text."""
        return str(self)

    @property
    def name(self) -> str:
        """Return the canonical foreign-asset obligation token name."""
        return str(self)


class M720AssetClassCode(StrEnum):
    """The five one-character Modelo 720 position-102 ``clave-tipo-de-bien-o-derecho`` values.

    The bundled AEAT record design limits Modelo 720's asset-row class code to
    ``C``/``V``/``I``/``S``/``B``; ``I`` is participaciones en instituciones de
    inversión colectiva, ``B`` is real estate. ``VIRTUAL_CURRENCY`` has no
    member here because it is declared through the Modelo 721 sibling, not
    Modelo 720 -- this axis is the raw AEAT clave a
    ``foreign_asset`` row carries, distinct from the semantic
    :class:`ForeignAssetClass` it is derived from one-to-one via
    :data:`MODELO_720_FOREIGN_ASSET_CLASS_CODES`.
    """

    CUENTA = "C"
    VALOR = "V"
    INSTITUCION_INVERSION_COLECTIVA = "I"
    SEGURO = "S"
    BIEN_INMUEBLE = "B"


MODELO_720_FOREIGN_ASSET_CLASS_CODES: Final[Mapping[ForeignAssetClass, M720AssetClassCode]] = MappingProxyType(
    {
        ForeignAssetClass.ACCOUNT: M720AssetClassCode.CUENTA,
        ForeignAssetClass.SECURITY: M720AssetClassCode.VALOR,
        ForeignAssetClass.COLLECTIVE_INVESTMENT: M720AssetClassCode.INSTITUCION_INVERSION_COLECTIVA,
        ForeignAssetClass.INSURANCE: M720AssetClassCode.SEGURO,
        ForeignAssetClass.REAL_ESTATE: M720AssetClassCode.BIEN_INMUEBLE,
    },
)
"""Official Modelo 720 position-102 ``clave-tipo-de-bien-o-derecho`` map.

Total over the Modelo-720-bearing :class:`ForeignAssetClass` members (every
member except ``VIRTUAL_CURRENCY``, the Modelo 721 sibling with no Modelo 720
clave).
"""


__all__ = [
    "MODELO_720_FOREIGN_ASSET_CLASS_CODES",
    "ForeignAssetObligationGroup",
    "M720AssetClassCode",
]
