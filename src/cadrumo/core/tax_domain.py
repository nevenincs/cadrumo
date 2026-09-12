"""Closed tax-domain identifier values shared by registry boundaries.

The :class:`TaxDomain` enum is deliberately dependency-free: it carries stable
identifier values used by core and registry schemas. Authority-backed
membership and metadata resolution belong to the validated AEAT registry,
outside this core value module.
"""

from __future__ import annotations

from enum import StrEnum


class TaxDomain(StrEnum):
    """Spanish-tax taxonomic domains accepted by registry manifests.

    Members use Spanish stems for tax-system concepts (``iva``, ``irpf``,
    ``is``) and classify :class:`~domain.calculations.registry.ModeloDefinition`
    records at the broad family level. A domain groups a modelo in the
    registry; it does not decide whether a taxpayer must file that modelo.
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
    """Retenciones / pagos a cuenta that feed both IRPF and IS."""

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
