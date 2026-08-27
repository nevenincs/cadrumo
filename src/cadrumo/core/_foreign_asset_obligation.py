"""Modelo 720 / 721 foreign-asset obligation-group semantic layer.

Typed abstraction over the raw Modelo 720 casilla bindings. The registry
declares the ``clave-tipo-de-bien-o-derecho`` field and a ``foreign_asset``
row source whose ``asset_class_code`` an operator otherwise reads as an opaque
one-character clave. This module lifts that clave onto the four regulatory
declaration bloques of the Reglamento General de Gestión e Inspección
(RD 1065/2007) — cuentas (art. 42 bis), valores/derechos/IIC/seguros/rentas
(art. 42 ter), inmuebles (art. 54 bis), and monedas virtuales (art. 42
quater, the Modelo 721 sibling).

It is a surfacing layer only. It does not aggregate observations, compute a
casilla value, apply a declarability gate, or resolve a binding. The
application's registry-resolved threshold bridge supplies those legal values.
The obligation group is still the legally load-bearing axis: the
``valor``/``seguro`` classes both belong to the single art. 42 ter valores bloque.

The :class:`ForeignAssetObligationGroup` enum is declared here (a closed value
set, per the core-authority architecture contract); it is the obligation-group
sibling of the per-clave :class:`~core.aggregation.ForeignAssetClass`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from .aggregation import ForeignAssetClass


class ForeignAssetObligationGroup(StrEnum):
    """Regulatory declaration bloques for foreign assets and rights (RGAT).

    Each member is one of the RD 1065/2007 information-obligation bloques that
    the Modelo 720 (and its monedas-virtuales sibling Modelo 721) partitions
    declared assets into. The 50.000 EUR declaration floor and the 20.000 EUR
    re-declaration delta apply INDEPENDENTLY per bloque, so this — not the
    per-clave :class:`~core.aggregation.ForeignAssetClass` — is the axis
    the declaration thresholds are keyed on.

    Members:
        CUENTAS: Cuentas en entidades financieras situadas en el extranjero
            (RD 1065/2007 art. 42 bis). Feeds :attr:`ForeignAssetClass.ACCOUNT`.
        VALORES_DERECHOS_SEGUROS: Valores, derechos, IIC, seguros y rentas
            depositados, gestionados u obtenidos en el extranjero
            (RD 1065/2007 art. 42 ter). Feeds
            :attr:`ForeignAssetClass.SECURITY`,
            :attr:`ForeignAssetClass.COLLECTIVE_INVESTMENT`, and
            :attr:`ForeignAssetClass.INSURANCE`, which share this single
            bloque umbral.
        INMUEBLES: Bienes inmuebles y derechos sobre bienes inmuebles situados
            en el extranjero (RD 1065/2007 art. 54 bis). Feeds
            :attr:`ForeignAssetClass.REAL_ESTATE`.
        MONEDAS_VIRTUALES: Monedas virtuales situadas en el extranjero
            (RD 1065/2007 art. 42 quater; declared via Modelo 721 from ejercicio
            2023). Feeds :attr:`ForeignAssetClass.VIRTUAL_CURRENCY`.
    """

    CUENTAS = "cuentas"
    VALORES_DERECHOS_SEGUROS = "valores_derechos_seguros"
    INMUEBLES = "inmuebles"
    MONEDAS_VIRTUALES = "monedas_virtuales"


FOREIGN_ASSET_OBLIGATION_GROUP_REGISTRY_SECTIONS: Final[
    Mapping[ForeignAssetObligationGroup, frozenset[str]]
] = MappingProxyType(
    {
        ForeignAssetObligationGroup.CUENTAS: frozenset({"cuentas"}),
        ForeignAssetObligationGroup.VALORES_DERECHOS_SEGUROS: frozenset({"valores"}),
        ForeignAssetObligationGroup.INMUEBLES: frozenset({"inmuebles"}),
        ForeignAssetObligationGroup.MONEDAS_VIRTUALES: frozenset({"moneda", "monedas"}),
    },
)
"""Registry ``section`` tokens whose presence declares a bloque is in scope.

The bloque vocabulary and the registry's own casilla ``section`` vocabulary are
not the same words -- the registry says ``valores`` where the RGAT bloque is
``valores_derechos_seguros``, and ``moneda`` where the bloque is
``monedas_virtuales``. Binding the two here, on the closed enum that owns the
taxonomy, is what lets the SCOPE of a modelo's obligation -- which bloques it
declares at all -- be read off the casillas the revision actually ships rather
than hand-listed in a feature module, where it could disagree with the registry
and nothing would notice.

This is a vocabulary binding, not a scope declaration: it says what a section
token means, never which modelo declares which bloque. That question is
answered by :func:`obligation_groups_declared_by_sections` against real registry
data, so a revision that adds or drops a bloque changes the answer without an
edit here.
"""


def obligation_groups_declared_by_sections(
    sections: Iterable[Sequence[str]],
) -> frozenset[ForeignAssetObligationGroup]:
    """Return the bloques the given casilla ``section`` paths put in scope.

    Args:
        sections: Each declared casilla's ``section`` path, as shipped by the
            registry revision.

    Returns:
        Every :class:`ForeignAssetObligationGroup` whose registry section token
        appears anywhere in those paths.
    """
    tokens = {str(part) for section in sections for part in section}
    return frozenset(
        group
        for group, group_tokens in FOREIGN_ASSET_OBLIGATION_GROUP_REGISTRY_SECTIONS.items()
        if tokens & group_tokens
    )


FOREIGN_ASSET_CLASS_OBLIGATION_GROUP: Final[Mapping[ForeignAssetClass, ForeignAssetObligationGroup]] = MappingProxyType(
    {
        ForeignAssetClass.ACCOUNT: ForeignAssetObligationGroup.CUENTAS,
        ForeignAssetClass.SECURITY: ForeignAssetObligationGroup.VALORES_DERECHOS_SEGUROS,
        ForeignAssetClass.COLLECTIVE_INVESTMENT: ForeignAssetObligationGroup.VALORES_DERECHOS_SEGUROS,
        ForeignAssetClass.INSURANCE: ForeignAssetObligationGroup.VALORES_DERECHOS_SEGUROS,
        ForeignAssetClass.REAL_ESTATE: ForeignAssetObligationGroup.INMUEBLES,
        ForeignAssetClass.VIRTUAL_CURRENCY: ForeignAssetObligationGroup.MONEDAS_VIRTUALES,
    },
)
"""Total map from each :class:`ForeignAssetClass` clave to its RGAT bloque.

Complete by construction: every :class:`ForeignAssetClass` member is a key, so
:func:`foreign_asset_obligation_group` is total and a new asset class cannot be
added without also declaring its bloque (the parity test fails otherwise). The
art. 42 ter valores bloque carries three Modelo 720 claves (``SECURITY``,
``COLLECTIVE_INVESTMENT``, ``INSURANCE``); cuentas and inmuebles carry one
Modelo 720 clave each; monedas virtuales is the Modelo 721 sibling and carries
no Modelo 720 clave.
"""


class M720AssetClassCode(StrEnum):
    """The five one-character Modelo 720 position-102 ``clave-tipo-de-bien-o-derecho`` values.

    The bundled AEAT record design limits Modelo 720's asset-row class code to
    ``C``/``V``/``I``/``S``/``B``; ``I`` is participaciones en instituciones de
    inversión colectiva, ``B`` is real estate. ``VIRTUAL_CURRENCY`` has no
    member here because RD 1065/2007 art. 42 quater is declared through the
    Modelo 721 sibling, not Modelo 720 -- this axis is the raw AEAT clave a
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


def foreign_asset_obligation_group(asset_class: ForeignAssetClass) -> ForeignAssetObligationGroup:
    """Return the RGAT :class:`ForeignAssetObligationGroup` bloque a foreign-asset clave belongs to.

    Total over :class:`ForeignAssetClass`. Use it to surface a Modelo 720
    ``foreign_asset`` row's opaque ``asset_class_code`` clave as its typed
    declaration bloque (e.g. ``SECURITY`` and ``INSURANCE`` both resolve to
    :attr:`ForeignAssetObligationGroup.VALORES_DERECHOS_SEGUROS`).
    """
    return FOREIGN_ASSET_CLASS_OBLIGATION_GROUP[asset_class]


__all__ = [
    "FOREIGN_ASSET_CLASS_OBLIGATION_GROUP",
    "FOREIGN_ASSET_OBLIGATION_GROUP_REGISTRY_SECTIONS",
    "MODELO_720_FOREIGN_ASSET_CLASS_CODES",
    "ForeignAssetObligationGroup",
    "M720AssetClassCode",
    "foreign_asset_obligation_group",
    "obligation_groups_declared_by_sections",
]
