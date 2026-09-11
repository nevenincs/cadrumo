"""Modelo 303 registry test support owned by the colocated registry test family."""

from __future__ import annotations

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....tests.aeat_literal_fixtures import aeat_host
from ..authority import bundled_authority
from ..schema import ModeloDefinition, RegistryCatalogues

_WWW1_HOST = aeat_host("www1")
_WWW6_HOST = aeat_host("www6")


_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores"
)
_M303_COMPENSACION_APLICADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-aplicada-periodo")
_M303_POSTERIOR_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-pendiente-periodos-posteriores")
_M303_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_M303_GENERADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-generada-periodo")
_M303_DISPONIBLE_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-disponible-fin-periodo")
_M303_AUTOCONSUMO_PROMOTOR_BASE_CASILLA: CasillaId = validated_casilla_id("iva.autoconsumo.promotor.base")
_M303_AUTOCONSUMO_PROMOTOR_CUOTA_CASILLA: CasillaId = validated_casilla_id("iva.autoconsumo.promotor.cuota")
_M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_M303_PRORRATA_VOLUMEN_CON_DERECHO_CASILLA: CasillaId = validated_casilla_id("iva.prorrata-volumen-con-derecho")
_M303_PRORRATA_VOLUMEN_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.prorrata-volumen-total")
_M303_PRORRATA_PORCENTAJE_CASILLA: CasillaId = validated_casilla_id("iva.prorrata-porcentaje")
_M303_BIENES_INVERSION_REGULARIZACION_CASILLA: CasillaId = validated_casilla_id("43")
_M303_BIENES_INVERSION_REGULARIZACION_BINDING = "modelo-303-bienes-inversion-regularizacion-casilla-43"
_M303_PRORRATA_REGULARIZACION_CASILLA: CasillaId = validated_casilla_id("44")
_M303_PRORRATA_REGULARIZACION_BINDING = "modelo-303-prorrata-regularizacion-casilla-44"
_M303_PRORRATA_REGULARIZACION_SOURCE_CASILLAS: tuple[CasillaId, ...] = (
    _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    _M303_PRORRATA_VOLUMEN_CON_DERECHO_CASILLA,
    _M303_PRORRATA_VOLUMEN_TOTAL_CASILLA,
    _M303_PRORRATA_PORCENTAJE_CASILLA,
)
_M303_PRORRATA_REGULARIZACION_SOURCE_PERIODS = ("1T", "2T", "3T", "4T")
_M303_EXPLICIT_RECORD_DESIGN_REVISIONS = (
    "2023",
    "2024-hasta-08-y-2t",
    "2024-desde-09-y-3t",
    "2025",
    "2026-y-siguientes",
)
_M303_RECORD_DESIGN_SOURCE_BY_REVISION = {
    # `aeat-dr-303-2022`, not 2025. The 2022 revision borrowed a later design
    # while it was still the open-ended 2009-2022 span with none of its own;
    # it now cites the 2022 diseno, which is the one that governs its year.
    "2022": "aeat-dr-303-2022",
    "2023": "aeat-dr-303-2023",
    "2024-hasta-08-y-2t": "aeat-dr-303-2024-early",
    "2024-desde-09-y-3t": "aeat-dr-303-2024-late",
    "2025": "aeat-dr-303-2025",
    "2026-y-siguientes": "aeat-dr-303-2026",
}
_M303_ANNUAL_ORDEN_SOURCE_BY_REVISION = {
    "2023": "boe-orden-hfp-1172-2022-iva-authority",
    "2024-hasta-08-y-2t": "boe-orden-hfp-1359-2023-iva-authority",
    "2024-desde-09-y-3t": "boe-orden-hfp-1359-2023-iva-authority",
    "2025": "boe-orden-hac-1347-2024-iva-authority",
    "2026-y-siguientes": "boe-orden-hac-1425-2025-iva-authority",
}
_M303_EXTRACTION_PROFILE_TARGET_LEGAL_REFS_BY_REVISION = {
    "2022": frozenset(
        {
            "ley-37-1992:art-88",
            "ley-37-1992:art-90",
            "ley-37-1992:art-91",
            "ley-37-1992:art-92",
            "ley-37-1992:art-94",
            "ley-37-1992:art-95",
            "orden-eha-3786-2008:art-1",
            "rd-1624-1992:art-71",
        }
    ),
}
_M303_CURRENT_RECORD_DESIGN_LEGAL_REFS = frozenset(
    {
        "ley-37-1992:art-88",
        "ley-37-1992:art-90",
        "ley-37-1992:art-91",
        "ley-37-1992:art-92",
        "ley-37-1992:art-94",
        "ley-37-1992:art-95",
        "ley-37-1992:art-99",
        "ley-37-1992:art-115",
        "ley-37-1992:art-116",
        "ley-37-1992:art-122",
        "ley-37-1992:art-123",
        "ley-37-1992:art-124",
        "orden-eha-3786-2008:art-1",
        "rd-1624-1992:art-29",
        "rd-1624-1992:art-30",
        "rd-1624-1992:art-71",
    }
)
_M303_RECORD_DESIGN_LAYOUT_MODIFICATION_LEGAL_REF = "orden-hac-819-2024:art-unico"
for _revision_id in _M303_EXPLICIT_RECORD_DESIGN_REVISIONS:
    _M303_EXTRACTION_PROFILE_TARGET_LEGAL_REFS_BY_REVISION[_revision_id] = _M303_CURRENT_RECORD_DESIGN_LEGAL_REFS


def load_modelo_303() -> tuple[ModeloDefinition, RegistryCatalogues]:
    authority = bundled_authority()
    return authority.modelo("303"), authority.catalogues
