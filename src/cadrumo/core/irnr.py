"""Typed axes for the IRNR (non-resident income tax) treaty surface.

Registry-owned axes governing the Modelo 210 IRNR rate-resolution path are
represented here by opaque string types. Their membership is projected at the
domain boundary rather than enumerated in this core module:

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
authored fact and its :class:`~domain.calculations.registry.convenio.ConvenioAuthority`
projection. The registry TOML stays free-form (a plain string token); the
loader hydrates typed tokens at the boundary.
"""

from __future__ import annotations

from enum import StrEnum

from .registry_token import StrictRegistryToken


class TipoRentaIrnr(StrictRegistryToken):
    """Opaque IRNR income-type token projected from governed fact 0080.

    The value set and its Modelo 210 code projection belong to the dated facts
    catalogue.  This wire type deliberately carries no Python member list;
    callers must obtain instances through the typed registry resolver.
    """

    __slots__ = ()

    _projection_source = "registry"


class M210PayerMode(StrictRegistryToken):
    """Opaque Modelo 210 payer-mode token projected from the registry.

    The selected detail catalogue owns payer-mode membership, descriptions, and
    the code-35 applicability rule.  This core type carries only the typed wire
    token; callers must obtain values through the registry projection.
    """

    __slots__ = ()

    _projection_source = "registry"


class M210GrossIncomeSourceMode(StrEnum):
    """Authority selected for Modelo 210 ``rendimientos_integros`` on one revision."""

    MANUAL = "manual"
    LEDGER = "ledger"


class ConvenioOverrideKind(StrictRegistryToken):
    """Opaque treaty-override token projected from ``irnr.convenio.override``.

    The governed catalogue owns the available override values. Keeping this
    type opaque prevents a second, closed Python taxonomy from drifting away
    from that catalogue; registry consumers must receive their token through
    ``from_registry``.
    """

    __slots__ = ()

    _projection_source = "registry"
