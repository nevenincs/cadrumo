"""Enumeration of AEAT portal identifiers tracked by the portal registry.

The :class:`Portal` members name every portal that the v1 catalogue
materialises under :mod:`cadrumo.domain.portals`. Member values are the member
name lowercased (e.g. ``"portal_m303_iva_autoliquidacion"``), which
gives callers a stable, machine-predictable identifier safe to emit
over CLI / JSON without further mapping.

- 8 AUTH entry points (Sede root, Mi área personal, Cl@ve + cert + DNIe
  gateways).
- FILING / CENSO procedures for curated Sede entries, including the inactive
  Modelo 037 simplificada history entry.
- 2 BORRADOR entries (Renta Web borrador, Pre303 ayuda).
- 4 CONSULTATION entries (Mis expedientes, Mis notificaciones, Mis datos
  censales, Documentos pendientes de firma).
- 5 PAYMENT entries (cuenta, tarjeta/Bizum, liquidaciones, domiciliación,
  consulta).
- 2 CALENDAR_REFERENCE entries (calendario, presentar-consultar index).
"""

from __future__ import annotations

from enum import StrEnum


class Portal(StrEnum):
    """Canonical AEAT portal identifier.

    Values are the member name lowercased. Adding a new member is a
    first-class enum widening and must be accompanied by a new entry
    file under :mod:`cadrumo.domain.portals._entries` or registry assembly will
    abort with :class:`cadrumo.domain.portals.PortalIntegrityError`.
    """

    # Authentication (8)
    PORTAL_SEDE_ROOT = "portal_sede_root"
    PORTAL_MI_AREA_PERSONAL = "portal_mi_area_personal"
    PORTAL_CLAVE_SEDE_ENTRY = "portal_clave_sede_entry"
    PORTAL_CLAVE_GESTIONES = "portal_clave_gestiones"
    PORTAL_CLAVE_IDP_ROOT = "portal_clave_idp_root"
    PORTAL_CERT_SELECTION = "portal_cert_selection"
    PORTAL_CERT_VALIDATION_REST = "portal_cert_validation_rest"
    PORTAL_DNIE_SEDE_ENTRY = "portal_dnie_sede_entry"

    # Filing / censo
    PORTAL_M036_CENSAL = "portal_m036_censal"
    PORTAL_M037_CENSAL_SIMPLIFICADA = "portal_m037_censal_simplificada"
    PORTAL_M100_RENTA = "portal_m100_renta"
    PORTAL_M111_RETENCIONES_TRABAJO = "portal_m111_retenciones_trabajo"
    PORTAL_M115_RETENCIONES_ARRENDAMIENTOS = "portal_m115_retenciones_arrendamientos"
    PORTAL_M123_RETENCIONES_CAPITAL = "portal_m123_retenciones_capital"
    PORTAL_M130_PAGO_FRACCIONADO_ED = "portal_m130_pago_fraccionado_ed"
    PORTAL_M131_PAGO_FRACCIONADO_EO = "portal_m131_pago_fraccionado_eo"
    PORTAL_M180_RESUMEN_ARRENDAMIENTOS = "portal_m180_resumen_arrendamientos"
    PORTAL_M190_RESUMEN_TRABAJO = "portal_m190_resumen_trabajo"
    PORTAL_M193_RESUMEN_CAPITAL = "portal_m193_resumen_capital"
    PORTAL_M200_SOCIEDADES_ANUAL = "portal_m200_sociedades_anual"
    PORTAL_M202_SOCIEDADES_FRACCIONADO = "portal_m202_sociedades_fraccionado"
    PORTAL_M232_VINCULADAS = "portal_m232_vinculadas"
    PORTAL_M303_IVA_AUTOLIQUIDACION = "portal_m303_iva_autoliquidacion"
    PORTAL_M347_OPERACIONES_TERCEROS = "portal_m347_operaciones_terceros"
    PORTAL_M349_INTRACOMUNITARIAS = "portal_m349_intracomunitarias"
    PORTAL_M369_OSS_IOSS = "portal_m369_oss_ioss"
    PORTAL_M390_RESUMEN_IVA = "portal_m390_resumen_iva"
    PORTAL_M720_BIENES_EXTRANJERO = "portal_m720_bienes_extranjero"
    PORTAL_M840_IAE = "portal_m840_iae"

    # Borrador / pre-filled (2)
    PORTAL_RENTA_WEB_BORRADOR = "portal_renta_web_borrador"
    PORTAL_PRE303_AYUDA = "portal_pre303_ayuda"

    # Consultation (3)
    PORTAL_MIS_EXPEDIENTES = "portal_mis_expedientes"
    PORTAL_MIS_NOTIFICACIONES = "portal_mis_notificaciones"
    PORTAL_MIS_DOCUMENTOS_PENDIENTES_FIRMA = "portal_mis_documentos_pendientes_firma"

    # Payment (5)
    PORTAL_PAGO_AUTOLIQUIDACION_CUENTA = "portal_pago_autoliquidacion_cuenta"
    PORTAL_PAGO_AUTOLIQUIDACION_TARJETA_BIZUM = "portal_pago_autoliquidacion_tarjeta_bizum"
    PORTAL_PAGO_LIQUIDACIONES_DEUDAS = "portal_pago_liquidaciones_deudas"
    PORTAL_DOMICILIACION_BANCARIA = "portal_domiciliacion_bancaria"
    PORTAL_CONSULTA_PAGOS = "portal_consulta_pagos"

    # Calendar / reference (2)
    PORTAL_CALENDARIO_CONTRIBUYENTE = "portal_calendario_contribuyente"
    PORTAL_PRESENTAR_CONSULTAR_INDEX = "portal_presentar_consultar_index"
