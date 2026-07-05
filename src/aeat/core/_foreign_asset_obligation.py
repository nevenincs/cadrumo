"""Modelo 720 / 721 foreign-asset obligation-group semantic layer.

Typed abstraction over the raw Modelo 720 casilla bindings. The registry
declares the ``clave-tipo-de-bien-o-derecho`` field and a ``foreign_asset``
row source whose ``asset_class_code`` an operator otherwise reads as an opaque
one-character clave. This module lifts that clave onto the four regulatory
declaration bloques of the Reglamento General de Gestión e Inspección
(RD 1065/2007) — cuentas (art. 42 bis), valores/derechos/IIC/seguros/rentas
(art. 42 ter), inmuebles (art. 54 bis), and monedas virtuales (art. 42
quater, the Modelo 721 sibling) — and carries each bloque's grounded
declaration thresholds: the 50.000 EUR initial declaration floor and the
20.000 EUR re-declaration increase delta.

It is a surfacing layer only. It does not aggregate observations, compute a
casilla value, apply the declarability gate, or resolve a binding; the M720
aggregation and its per-obligation-block threshold gate live in
:mod:`application.aggregation._foreign_assets`. The obligation group is
the legally load-bearing axis: the 50.000 EUR floor is a per-bloque umbral
(art. 42 bis/ter/54 bis/quater), so the ``valor``/``seguro`` classes both
belong to the single art. 42 ter valores bloque rather than two independent
thresholds.

The :class:`ForeignAssetObligationGroup` enum is declared here (a closed value
set, per the core-authority architecture contract); it is the obligation-group
sibling of the per-clave :class:`~core.aggregation.ForeignAssetClass`.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel, Field

from ._models import STRICT_FROZEN_CONFIG
from .aggregation import ForeignAssetClass
from .external_constants import MODELO_720_REPORTING_THRESHOLD_EUR

#: Modelo 720 / 721 re-declaration increase delta. Once a bloque has been
#: declared in a prior ejercicio, the obligation to re-declare it in a later
#: ejercicio arises only when the bloque's aggregate valuation has increased by
#: MORE than this amount over the last declared value (or a member was
#: extinguished/cancelled). Binding provision: RD 1065/2007 art. 42 bis.4 /
#: art. 42 ter.5 / art. 54 bis.6 (and art. 42 quater for monedas virtuales) —
#: "hubiese experimentado un incremento superior a 20.000 euros respecto del que
#: determinó la presentación de la última declaración". The legal registry entry
#: ``rd-1065-2007:art-42-quater`` records the same structure verbatim: "inicial
#: 50.000 EUR, re-declaracion si variacion > 20.000 EUR". The gate is STRICT
#: (> 20.000), mirroring the strict initial-floor gate
#: (:data:`~core.external_constants.MODELO_720_REPORTING_THRESHOLD_EUR`).
MODELO_720_REDECLARATION_INCREASE_THRESHOLD_EUR: Final[Decimal] = Decimal("20000.00")


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


MODELO_720_FOREIGN_ASSET_CLASS_CODES: Final[Mapping[ForeignAssetClass, str]] = MappingProxyType(
    {
        ForeignAssetClass.ACCOUNT: "C",
        ForeignAssetClass.SECURITY: "V",
        ForeignAssetClass.COLLECTIVE_INVESTMENT: "I",
        ForeignAssetClass.INSURANCE: "S",
        ForeignAssetClass.REAL_ESTATE: "B",
    },
)
"""Official Modelo 720 position-102 ``clave-tipo-de-bien-o-derecho`` map.

The bundled AEAT record design limits Modelo 720's asset-row class code to
``C``/``V``/``I``/``S``/``B``. ``I`` is participaciones en instituciones de
inversion colectiva, while real estate is ``B``. ``VIRTUAL_CURRENCY`` is
deliberately absent because RD 1065/2007 art. 42 quater is declared through the
Modelo 721 sibling, not Modelo 720.
"""


class ForeignAssetDeclarationThreshold(BaseModel):
    """Grounded declaration thresholds for one foreign-asset obligation bloque.

    A tiny closed carrier (per the core taxonomy convention) binding an
    obligation :class:`ForeignAssetObligationGroup` to its two RGAT umbrales —
    the 50.000 EUR initial declaration floor and the 20.000 EUR re-declaration
    increase delta — plus the ``legal_refs`` provenance that establishes them.
    Strict and frozen, matching the registry schema's
    :data:`~core.STRICT_FROZEN_CONFIG` convention, so an unknown group or a
    stray key is rejected at construction.

    Both umbral gates are STRICT in the law and in the aggregation gate: a bloque
    is declarable when its aggregate valuation is strictly ABOVE
    ``initial_declaration_floor_eur``, and re-declaration is required when the
    increase over the last declared value is strictly ABOVE
    ``redeclaration_increase_delta_eur``.
    """

    model_config = STRICT_FROZEN_CONFIG

    group: ForeignAssetObligationGroup
    initial_declaration_floor_eur: Decimal = Field(gt=Decimal("0"))
    redeclaration_increase_delta_eur: Decimal = Field(gt=Decimal("0"))
    legal_refs: tuple[str, ...] = Field(min_length=1)


_OBLIGATION_GROUP_LEGAL_REFS: Final[Mapping[ForeignAssetObligationGroup, tuple[str, ...]]] = MappingProxyType(
    {
        ForeignAssetObligationGroup.CUENTAS: (
            "rd-1065-2007:art-42-bis",
            "ley-58-2003:da-18",
            "orden-hap-72-2013:art-2",
        ),
        ForeignAssetObligationGroup.VALORES_DERECHOS_SEGUROS: (
            "rd-1065-2007:art-42-ter",
            "ley-58-2003:da-18",
            "orden-hap-72-2013:art-2",
        ),
        ForeignAssetObligationGroup.INMUEBLES: (
            "rd-1065-2007:art-54-bis",
            "ley-58-2003:da-18",
            "orden-hap-72-2013:art-2",
        ),
        ForeignAssetObligationGroup.MONEDAS_VIRTUALES: (
            "rd-1065-2007:art-42-quater",
            "ley-11-2021:da-10",
            "orden-hfp-886-2023:art-2",
        ),
    },
)


FOREIGN_ASSET_DECLARATION_THRESHOLDS: Final[Mapping[ForeignAssetObligationGroup, ForeignAssetDeclarationThreshold]] = (
    MappingProxyType(
        {
            group: ForeignAssetDeclarationThreshold(
                group=group,
                initial_declaration_floor_eur=MODELO_720_REPORTING_THRESHOLD_EUR,
                redeclaration_increase_delta_eur=MODELO_720_REDECLARATION_INCREASE_THRESHOLD_EUR,
                legal_refs=refs,
            )
            for group, refs in _OBLIGATION_GROUP_LEGAL_REFS.items()
        },
    )
)
"""Grounded declaration thresholds per obligation bloque.

Complete by construction over :class:`ForeignAssetObligationGroup`. Every bloque
shares the same two umbral VALUES (50.000 EUR floor, 20.000 EUR re-declaration
delta) because RD 1065/2007 fixes them identically across art. 42 bis/ter/54
bis/quater; the ``legal_refs`` differ per bloque because each cites its own
binding article.
"""


def foreign_asset_obligation_group(asset_class: ForeignAssetClass) -> ForeignAssetObligationGroup:
    """Return the RGAT :class:`ForeignAssetObligationGroup` bloque a foreign-asset clave belongs to.

    Total over :class:`ForeignAssetClass`. Use it to surface a Modelo 720
    ``foreign_asset`` row's opaque ``asset_class_code`` clave as its typed
    declaration bloque (e.g. ``SECURITY`` and ``INSURANCE`` both resolve to
    :attr:`ForeignAssetObligationGroup.VALORES_DERECHOS_SEGUROS`).
    """
    return FOREIGN_ASSET_CLASS_OBLIGATION_GROUP[asset_class]


def foreign_asset_declaration_threshold(
    group: ForeignAssetObligationGroup,
) -> ForeignAssetDeclarationThreshold:
    """Return the grounded :class:`ForeignAssetDeclarationThreshold` for an obligation bloque."""
    return FOREIGN_ASSET_DECLARATION_THRESHOLDS[group]


def foreign_asset_class_declaration_threshold(
    asset_class: ForeignAssetClass,
) -> ForeignAssetDeclarationThreshold:
    """Return the :class:`ForeignAssetDeclarationThreshold` for the bloque a clave belongs to.

    Convenience composition of :func:`foreign_asset_obligation_group` and
    :func:`foreign_asset_declaration_threshold`; the returned threshold is the
    per-bloque umbral, so two claves in the same bloque share one threshold.
    """
    return foreign_asset_declaration_threshold(foreign_asset_obligation_group(asset_class))


__all__ = [
    "FOREIGN_ASSET_CLASS_OBLIGATION_GROUP",
    "FOREIGN_ASSET_DECLARATION_THRESHOLDS",
    "MODELO_720_FOREIGN_ASSET_CLASS_CODES",
    "MODELO_720_REDECLARATION_INCREASE_THRESHOLD_EUR",
    "ForeignAssetDeclarationThreshold",
    "ForeignAssetObligationGroup",
    "foreign_asset_class_declaration_threshold",
    "foreign_asset_declaration_threshold",
    "foreign_asset_obligation_group",
]
