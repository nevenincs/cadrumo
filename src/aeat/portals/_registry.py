"""Registry assembly for the portal catalogue.

Imports every ``_entries/portal_*.py`` module, collects its module-level
``ENTRY`` object, and freezes the result as the public
:data:`PORTAL_REGISTRY` mapping. Structural invariants are enforced at
import time via :func:`_finalise_registry`; any violation raises
:class:`aeat.portals._errors.PortalIntegrityError` and aborts package
import.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from ..logging import get_logger
from ..models import ModeloCode, UnknownModeloError
from ._categories import PortalCategory
from ._codes import Portal
from ._entries import (
    portal_calendario_contribuyente,
    portal_cert_selection,
    portal_cert_validation_rest,
    portal_clave_gestiones,
    portal_clave_idp_root,
    portal_clave_sede_entry,
    portal_consulta_pagos,
    portal_dnie_sede_entry,
    portal_domiciliacion_bancaria,
    portal_m036_censal,
    portal_m037_censal_simplificada,
    portal_m100_renta,
    portal_m111_retenciones_trabajo,
    portal_m115_retenciones_arrendamientos,
    portal_m123_retenciones_capital,
    portal_m130_pago_fraccionado_ed,
    portal_m131_pago_fraccionado_eo,
    portal_m180_resumen_arrendamientos,
    portal_m190_resumen_trabajo,
    portal_m193_resumen_capital,
    portal_m200_sociedades_anual,
    portal_m202_sociedades_fraccionado,
    portal_m232_vinculadas,
    portal_m303_iva_autoliquidacion,
    portal_m347_operaciones_terceros,
    portal_m349_intracomunitarias,
    portal_m369_oss_ioss,
    portal_m390_resumen_iva,
    portal_m720_bienes_extranjero,
    portal_m840_iae,
    portal_mi_area_personal,
    portal_mis_datos_censales,
    portal_mis_documentos_pendientes_firma,
    portal_mis_expedientes,
    portal_mis_notificaciones,
    portal_pago_autoliquidacion_cuenta,
    portal_pago_autoliquidacion_tarjeta_bizum,
    portal_pago_liquidaciones_deudas,
    portal_pre303_ayuda,
    portal_presentar_consultar_index,
    portal_renta_web_borrador,
    portal_sede_root,
)
from ._errors import PortalIntegrityError, UnknownPortalError
from ._metadata import PortalMetadata

_LOG = get_logger(__name__)


_CATEGORIES_REQUIRING_MODELO: frozenset[PortalCategory] = frozenset(
    {PortalCategory.FILING, PortalCategory.CENSUS, PortalCategory.BORRADOR}
)
_FILING_OR_BORRADOR: frozenset[PortalCategory] = frozenset({PortalCategory.FILING, PortalCategory.BORRADOR})
_FILING_OR_CENSUS: frozenset[PortalCategory] = frozenset({PortalCategory.FILING, PortalCategory.CENSUS})

_ENTRIES: tuple[PortalMetadata, ...] = (
    # AUTH
    portal_sede_root.ENTRY,
    portal_mi_area_personal.ENTRY,
    portal_clave_sede_entry.ENTRY,
    portal_clave_gestiones.ENTRY,
    portal_clave_idp_root.ENTRY,
    portal_cert_selection.ENTRY,
    portal_cert_validation_rest.ENTRY,
    portal_dnie_sede_entry.ENTRY,
    # FILING / CENSUS
    portal_m036_censal.ENTRY,
    portal_m037_censal_simplificada.ENTRY,
    portal_m100_renta.ENTRY,
    portal_m111_retenciones_trabajo.ENTRY,
    portal_m115_retenciones_arrendamientos.ENTRY,
    portal_m123_retenciones_capital.ENTRY,
    portal_m130_pago_fraccionado_ed.ENTRY,
    portal_m131_pago_fraccionado_eo.ENTRY,
    portal_m180_resumen_arrendamientos.ENTRY,
    portal_m190_resumen_trabajo.ENTRY,
    portal_m193_resumen_capital.ENTRY,
    portal_m200_sociedades_anual.ENTRY,
    portal_m202_sociedades_fraccionado.ENTRY,
    portal_m232_vinculadas.ENTRY,
    portal_m303_iva_autoliquidacion.ENTRY,
    portal_m347_operaciones_terceros.ENTRY,
    portal_m349_intracomunitarias.ENTRY,
    portal_m369_oss_ioss.ENTRY,
    portal_m390_resumen_iva.ENTRY,
    portal_m720_bienes_extranjero.ENTRY,
    portal_m840_iae.ENTRY,
    # BORRADOR
    portal_renta_web_borrador.ENTRY,
    portal_pre303_ayuda.ENTRY,
    # CONSULTATION
    portal_mis_expedientes.ENTRY,
    portal_mis_notificaciones.ENTRY,
    portal_mis_datos_censales.ENTRY,
    portal_mis_documentos_pendientes_firma.ENTRY,
    # PAYMENT
    portal_pago_autoliquidacion_cuenta.ENTRY,
    portal_pago_autoliquidacion_tarjeta_bizum.ENTRY,
    portal_pago_liquidaciones_deudas.ENTRY,
    portal_domiciliacion_bancaria.ENTRY,
    portal_consulta_pagos.ENTRY,
    # CALENDAR_REFERENCE
    portal_calendario_contribuyente.ENTRY,
    portal_presentar_consultar_index.ENTRY,
)


def _check_replaced_by(entries: Mapping[Portal, PortalMetadata]) -> None:
    """Verify every ``replaced_by`` pointer resolves inside ``entries``.

    Args:
        entries: The assembled registry mapping.

    Raises:
        PortalIntegrityError: If any entry's ``replaced_by`` points at
            a :class:`Portal` that is not a key of ``entries``.
    """
    for portal, metadata in entries.items():
        target = metadata.replaced_by
        if target is None:
            continue
        if target not in entries:
            raise PortalIntegrityError(f"portal {portal.value} replaced_by {target.value} which is not in the registry")


def _check_modelo_closure(entries: Mapping[Portal, PortalMetadata]) -> None:
    """Verify every :class:`ModeloCode` is covered by a FILING or CENSUS portal.

    ``ModeloCode.MODELO_037`` is permitted to have only an ``active=False``
    backing portal (its simplificada procedure was suppressed on
    2025-02-03). Every other member must have at least one active
    FILING or CENSUS portal.

    Args:
        entries: The assembled registry mapping.

    Raises:
        PortalIntegrityError: If any :class:`ModeloCode` member has no
            FILING / CENSUS portal, or the M037 active carve-out is
            violated (i.e. M037 inadvertently gains an active portal).
    """
    coverage: dict[ModeloCode, list[PortalMetadata]] = {code: [] for code in ModeloCode}
    for metadata in entries.values():
        if metadata.category in _FILING_OR_CENSUS and metadata.related_modelo is not None:
            coverage[metadata.related_modelo].append(metadata)

    for code, portals in coverage.items():
        if not portals:
            raise PortalIntegrityError(f"modelo {code.value} has no FILING/CENSUS portal entry")
        if code is ModeloCode.MODELO_037:
            if any(p.active for p in portals):
                raise PortalIntegrityError(
                    "modelo 037 must not have an active FILING/CENSUS portal "
                    "(suppressed 2025-02-03 by Orden HAC/1526/2024)"
                )
        else:
            if not any(p.active for p in portals):
                raise PortalIntegrityError(f"modelo {code.value} has no active FILING/CENSUS portal entry")


def _check_related_modelo_roundtrip(entries: Mapping[Portal, PortalMetadata]) -> None:
    """Verify every ``related_modelo`` round-trips through :class:`ModeloCode`.

    The field is already typed as :class:`ModeloCode`, so the check is
    a defence-in-depth against future schema drift.

    Args:
        entries: The assembled registry mapping.

    Raises:
        PortalIntegrityError: If any ``related_modelo`` does not
            resolve back through :class:`ModeloCode`.
    """
    valid = frozenset(ModeloCode)
    for portal, metadata in entries.items():
        code = metadata.related_modelo
        if code is None:
            continue
        if code not in valid:
            raise PortalIntegrityError(f"portal {portal.value} related_modelo {code!r} is not a known ModeloCode")


def _finalise_registry(
    entries: tuple[PortalMetadata, ...],
) -> Mapping[Portal, PortalMetadata]:
    """Assemble the frozen registry mapping and enforce every invariant.

    Args:
        entries: The per-entry ``ENTRY`` objects loaded from
            :mod:`aeat.portals._entries`.

    Returns:
        A :class:`types.MappingProxyType` from :class:`Portal` to
        :class:`PortalMetadata`, frozen and complete.

    Raises:
        PortalIntegrityError: If any structural invariant fails.
    """
    materialised: dict[Portal, PortalMetadata] = {}
    for entry in entries:
        if entry.portal in materialised:
            raise PortalIntegrityError(f"duplicate registry entry for portal {entry.portal.value}")
        materialised[entry.portal] = entry
    missing = set(Portal) - set(materialised)
    if missing:
        missing_values = sorted(p.value for p in missing)
        raise PortalIntegrityError(f"registry is missing entries for portals: {missing_values}")
    extra = set(materialised) - set(Portal)
    if extra:
        extra_values = sorted(p.value for p in extra)
        raise PortalIntegrityError(f"registry contains unknown portals: {extra_values}")
    for key, metadata in materialised.items():
        if metadata.portal is not key:
            raise PortalIntegrityError(f"entry for {key.value} has mismatched portal {metadata.portal.value}")
    _check_replaced_by(materialised)
    _check_related_modelo_roundtrip(materialised)
    _check_modelo_closure(materialised)
    _LOG.debug("loaded %d portal entries", len(materialised))
    return MappingProxyType(materialised)


PORTAL_REGISTRY: Mapping[Portal, PortalMetadata] = _finalise_registry(_ENTRIES)


def get_portal(portal: Portal | str) -> PortalMetadata:
    """Return the registry entry for a portal.

    Accepts either a :class:`Portal` member or its canonical string
    value. Any failure — unknown identifier, failed coercion — raises
    :class:`UnknownPortalError`.

    Args:
        portal: A :class:`Portal` member or its string value.

    Returns:
        The authoritative :class:`PortalMetadata` for ``portal``.

    Raises:
        UnknownPortalError: If ``portal`` is not a registered portal.
    """
    if isinstance(portal, Portal):
        member = portal
    else:
        try:
            member = Portal(portal)
        except ValueError as exc:
            raise UnknownPortalError(portal) from exc
    try:
        return PORTAL_REGISTRY[member]
    except KeyError as exc:
        raise UnknownPortalError(member.value) from exc


def portals_for_modelo(code: ModeloCode | str) -> tuple[PortalMetadata, ...]:
    """Return every FILING or BORRADOR portal cross-referencing ``code``.

    CENSUS portals are intentionally excluded: ``portals_for_modelo``
    is a filing-dispatch helper, and the census procedures (Modelo
    036/037) live in their own category so callers can look them up
    with :func:`portals_by_category` when needed.

    Args:
        code: A :class:`ModeloCode` member or its string value.

    Returns:
        A tuple of matching :class:`PortalMetadata` entries sorted by
        :class:`Portal` value for deterministic output.

    Raises:
        UnknownModeloError: If ``code`` is not a registered modelo.
    """
    if isinstance(code, ModeloCode):
        member = code
    else:
        try:
            member = ModeloCode(code)
        except ValueError as exc:
            raise UnknownModeloError(str(code)) from exc
    matches = [
        metadata
        for metadata in PORTAL_REGISTRY.values()
        if metadata.category in _FILING_OR_BORRADOR and metadata.related_modelo is member
    ]
    matches.sort(key=lambda m: m.portal.value)
    return tuple(matches)


def portals_by_category(category: PortalCategory) -> tuple[PortalMetadata, ...]:
    """Return every portal in ``category`` sorted by :class:`Portal` value.

    Args:
        category: The :class:`PortalCategory` to filter by.

    Returns:
        A tuple of matching :class:`PortalMetadata` entries.
    """
    matches = [metadata for metadata in PORTAL_REGISTRY.values() if metadata.category is category]
    matches.sort(key=lambda m: m.portal.value)
    return tuple(matches)
