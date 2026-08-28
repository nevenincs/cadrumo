"""Registry assembly for the portal catalogue.

Imports every ``_entries/portal_*.py`` module, collects its module-level
``ENTRY`` object, and freezes the result as the public
:data:`PORTAL_REGISTRY` mapping. Structural invariants are enforced at
import time via :func:`_finalise_registry`; any violation raises
:class:`cadrumo.domain.portals.errors.PortalIntegrityError` and aborts package
import.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from ...core.logging import get_logger
from ..calculations.registry.authority import bundled_authority
from ..calculations.registry.errors import RegistryError, RegistrySnapshotError
from ..calculations.registry.ids import RevisionId
from ..modelos import ModeloCode
from ..modelos.errors import ModeloValidationError
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
from ._metadata import PortalMetadata
from .errors import (
    PortalRegistryInvariant,
    UnknownPortalError,
    portal_integrity_error,
    unknown_modelo_error,
)

_LOG = get_logger(__name__)


_FILING_OR_BORRADOR: frozenset[PortalCategory] = frozenset({PortalCategory.FILING, PortalCategory.BORRADOR})

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
    # FILING / CENSO
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
            _LOG.error(
                "portal integrity: %s replaced_by %s which is not in registry",
                portal.value,
                target.value,
            )
            raise portal_integrity_error(
                PortalRegistryInvariant.REPLACED_BY_TARGET_REGISTERED,
                facts={
                    "portal": portal.value,
                    "replaced_by": target.value,
                    "target_registered": False,
                },
            )


def _finalise_registry(
    entries: tuple[PortalMetadata, ...],
) -> Mapping[Portal, PortalMetadata]:
    """Assemble the frozen registry mapping and enforce every invariant.

    Args:
        entries: The per-entry ``ENTRY`` objects loaded from
            :mod:`cadrumo.domain.portals._entries`.

    Returns:
        A :class:`types.MappingProxyType` from :class:`Portal` to
        :class:`PortalMetadata`, frozen and complete.

    Raises:
        PortalIntegrityError: If any structural invariant fails.
    """
    materialised: dict[Portal, PortalMetadata] = {}
    for entry in entries:
        if entry.portal in materialised:
            _LOG.error("portal registry: duplicate entry for portal %s", entry.portal.value)
            raise portal_integrity_error(
                PortalRegistryInvariant.PORTAL_ENTRY_UNIQUE,
                facts={"portal": entry.portal.value, "entry_unique": False},
            )
        materialised[entry.portal] = entry
    missing = set(Portal) - set(materialised)
    if missing:
        missing_values = sorted(p.value for p in missing)
        _LOG.error("portal registry: missing entries for portals %s", missing_values)
        raise portal_integrity_error(
            PortalRegistryInvariant.PORTAL_ENUM_COVERAGE_COMPLETE,
            facts={"missing_count": len(missing_values), "enum_coverage_complete": False},
        )
    extra = set(materialised) - set(Portal)
    if extra:
        extra_values = sorted(p.value for p in extra)
        _LOG.error("portal registry: unknown portals in entries %s", extra_values)
        raise portal_integrity_error(
            PortalRegistryInvariant.PORTAL_ENUM_COVERAGE_COMPLETE,
            facts={"extra_count": len(extra_values), "enum_coverage_complete": False},
        )
    for key, metadata in materialised.items():
        if metadata.portal is not key:
            _LOG.error(
                "portal registry: entry for %s has mismatched portal field %s",
                key.value,
                metadata.portal.value,
            )
            raise portal_integrity_error(
                PortalRegistryInvariant.ENTRY_PORTAL_MATCHES_MAPPING_KEY,
                facts={
                    "mapping_portal": key.value,
                    "entry_portal": metadata.portal.value,
                    "portal_matches_mapping_key": False,
                },
            )
    _check_replaced_by(materialised)
    _LOG.debug("loaded %d portal entries", len(materialised))
    return MappingProxyType(materialised)


PORTAL_REGISTRY: Mapping[Portal, PortalMetadata] = _finalise_registry(_ENTRIES)


def _portal_consumer_binding(modelo_id: str, revision_id: RevisionId, consumer: str) -> Portal | None:
    """Resolve registry application consumers that identify portal dispatch entries."""
    for enum_prefix in (f"{Portal.__module__}.{Portal.__qualname__}.", "cadrumo.domain.portals.Portal."):
        if consumer.startswith(enum_prefix):
            member_name = consumer.removeprefix(enum_prefix)
            try:
                return Portal[member_name]
            except KeyError as exc:
                raise portal_integrity_error(
                    PortalRegistryInvariant.PORTAL_ENUM_CONSUMER_RESOLVES,
                    facts={
                        "modelo": modelo_id,
                        "revision_id": str(revision_id),
                        "portal_enum_consumer_resolves": False,
                    },
                ) from exc
    if consumer.startswith("portal_"):
        try:
            return Portal(consumer)
        except ValueError as exc:
            raise portal_integrity_error(
                PortalRegistryInvariant.PORTAL_ID_CONSUMER_RESOLVES,
                facts={
                    "modelo": modelo_id,
                    "revision_id": str(revision_id),
                    "portal_id_consumer_resolves": False,
                },
            ) from exc
    return None


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


def _registry_portal_bindings_for_modelo(code: ModeloCode) -> frozenset[Portal]:
    """Return portal ids bound to ``code`` by validated registry data."""
    try:
        try:
            modelo = bundled_authority().validate_modelo(str(code))
        except RegistrySnapshotError:
            _LOG.debug(
                "portals: registry snapshot unavailable for modelo %s; no portal bindings",
                code,
            )
            return frozenset[Portal]()
        bound: set[Portal] = set()
        for revision in modelo.revisions.values():
            for link in revision.application_links:
                if link.surface != "portal":
                    continue
                portal = _portal_consumer_binding(modelo.id, revision.id, link.consumer)
                if portal is not None:
                    bound.add(portal)
        return frozenset(bound)
    except RegistryError as exc:
        raise portal_integrity_error(
            PortalRegistryInvariant.REGISTRY_PORTAL_BINDINGS_AVAILABLE,
            facts={
                "modelo": str(code),
                "registry_portal_bindings_available": False,
                "registry_error_type": type(exc).__name__,
            },
        ) from exc


def portals_for_modelo(code: ModeloCode | str) -> tuple[PortalMetadata, ...]:
    """Return every FILING or BORRADOR portal linked to ``code``.

    CENSO portals are intentionally excluded: ``portals_for_modelo``
    is a filing-dispatch helper, and the censo procedures (Modelo
    036/037) live in their own category so callers can look them up
    with :func:`portals_by_category` when needed.

    Args:
        code: A :class:`cadrumo.domain.modelos.ModeloCode` member or its string value.

    Returns:
        A tuple of matching :class:`PortalMetadata` entries declared by
        validated registry definitions and sorted by :class:`Portal`
        value for deterministic output.

    Raises:
        PortalValidationError: If ``code`` is not a recognised modelo identifier.
    """
    if isinstance(code, ModeloCode):
        member = code
    else:
        try:
            member = ModeloCode(code)
        except ModeloValidationError as exc:
            raise unknown_modelo_error(str(code)) from exc
    bound_portals = _registry_portal_bindings_for_modelo(member)
    matches = [
        metadata
        for metadata in PORTAL_REGISTRY.values()
        if metadata.category in _FILING_OR_BORRADOR and metadata.portal in bound_portals
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
