"""Closed enumeration of Spanish-tax taxonomic domains used by the modelo registry.

Every :class:`~aeat.domain.calculations.registry.ModeloDefinition` declares the
broad tax family it belongs to via its ``tax_domain`` field. The exported
:class:`TaxDomain` enum closes that value set so loader hydration rejects typos
and unknown values at registry-load time rather than at any downstream branch on
the string. It is the tax-family sibling of :class:`~aeat.core.Modelo`: one enum
names the modelo identifier, the other names the registry taxonomy attached to
that modelo definition.
"""

from __future__ import annotations

from enum import StrEnum


class TaxDomain(StrEnum):
    """Spanish-tax taxonomic domains."""

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


__all__ = ["TaxDomain"]
