"""Closed enumeration of Spanish-tax taxonomic domains used by the modelo registry.

Every :class:`~domain.calculations.registry.ModeloDefinition` declares the
broad tax family it belongs to via its ``tax_domain`` field. The exported
:class:`TaxDomain` enum closes that value set so loader hydration rejects typos
and unknown values at registry-load time rather than at any downstream branch on
the string. It is the tax-family sibling of :class:`~core.Modelo`: one enum
names the modelo identifier, the other names the registry taxonomy attached to
that modelo definition.

Hydration happens at the registry boundary:
:func:`~domain.calculations.registry.load_registry_tree` parses the TOML
manifest string into :attr:`~domain.calculations.registry.ModeloDefinition.tax_domain`.
The enum is therefore a schema contract for registry authors and readers, not a
calculation-class switch and not an applicability verdict.
"""

from __future__ import annotations

from enum import StrEnum


class TaxDomain(StrEnum):
    """Spanish-tax taxonomic domains accepted by modelo registry manifests.

    Members use Spanish stems for tax-system concepts (``iva``, ``irpf``,
    ``is``) and classify :class:`~domain.calculations.registry.ModeloDefinition`
    records at the broad family level. A domain groups a modelo in the registry;
    it does not decide whether a taxpayer must file that modelo.
    """

    CENSO = "censo"
    """Censo / structural registrations (modelo 036, 037)."""

    IRPF = "irpf"
    """Impuesto sobre la Renta de las Personas Físicas."""

    IAE = "iae"
    """Impuesto sobre Actividades Económicas."""

    INFORMATIVE = "informative"
    """Informative-only filings (no own liquidación)."""

    IVA = "iva"
    """Impuesto sobre el Valor Añadido."""

    IS = "is"
    """Impuesto sobre Sociedades."""

    IRNR = "irnr"
    """Impuesto sobre la Renta de no Residentes."""

    PATRIMONIO = "patrimonio"
    """Impuesto sobre el Patrimonio (modelo 714)."""

    CROSS_TAX = "cross_tax"
    """Retentions / pagos a cuenta that feed both IRPF and IS."""

    IDSD = "idsd"
    """Impuesto sobre Determinados Servicios Digitales (modelo 490)."""

    ITF = "itf"
    """Impuesto sobre las Transacciones Financieras (modelo 604)."""

    JUEGO = "juego"
    """Impuesto sobre actividades de juego (modelo 763)."""

    PLASTICO = "plastico"
    """Impuesto especial sobre envases de plástico no reutilizables (modelo 592)."""

    IEDMT = "iedmt"
    """Impuesto Especial sobre Determinados Medios de Transporte (modelo 576)."""


__all__ = ["TaxDomain"]
