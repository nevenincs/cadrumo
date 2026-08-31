"""Closed authority axes for IVA deduction facts.

These names identify the source family of an IVA deduction.  They are not an
IVA category, rate, flow, or prorrata classification; those remain independent
axes in :mod:`cadrumo.domain.iva`.
"""

from __future__ import annotations

from enum import StrEnum


class IvaDeductionFactKind(StrEnum):
    """The complete, non-inferable M303 deduction-source taxonomy."""

    DOMESTIC_CURRENT = "domestic_current"
    DOMESTIC_INVESTMENT = "domestic_investment"
    IMPORT_CURRENT = "import_current"
    IMPORT_INVESTMENT = "import_investment"
    INTRA_EU_CURRENT = "intra_eu_current"
    INTRA_EU_INVESTMENT = "intra_eu_investment"
    REAGP_COMPENSATION = "reagp_compensation"
    RECTIFICATION = "rectification"
    INVESTMENT_GOODS_REGULARISATION = "investment_goods_regularisation"

    @property
    def is_investment_acquisition(self) -> bool:
        """Whether this kind must have a reciprocal capital-good record."""
        return self in {
            self.DOMESTIC_INVESTMENT,
            self.IMPORT_INVESTMENT,
            self.INTRA_EU_INVESTMENT,
        }


class IvaDeductionEvidenceAuthority(StrEnum):
    """Authoritative evidence family that established a deduction kind."""

    INVOICE_EVIDENCE = "invoice_evidence"
    CUSTOMS_DECLARATION = "customs_declaration"
    INTRA_EU_SELF_ASSESSMENT = "intra_eu_self_assessment"
    REAGP_RECEIPT = "reagp_receipt"
    RECTIFICATION_EVIDENCE = "rectification_evidence"
    BIENES_INVERSION_REGISTER = "bienes_inversion_register"


__all__ = ["IvaDeductionEvidenceAuthority", "IvaDeductionFactKind"]
