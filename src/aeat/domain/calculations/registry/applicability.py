"""Public non-cyclic access to registry-owned modelo applicability rules."""

from __future__ import annotations

from ._applicability import (
    _ATTRIBUTION_PASS_THROUGH_LEGAL_REFS,
    _INCOMPLETE_LEGAL_REFS,
    _INCOMPLETE_UNDECLARED_REASON,
    _INCOMPLETE_UNDETERMINED_REASON,
    _INCOMPLETE_UNRULED_REASON,
    _MODELO_APPLICABILITY_RULES,
    ApplicabilityVerdict,
    Modelo202Modality,
    Modelo202ModalityVerdict,
    ModeloApplicability,
    ModeloApplicabilityRule,
    PayerFact,
    TaxRoute,
    derive_modelo_202_modality,
    derive_modelo_applicability,
    derive_tax_route,
    has_applicability_rule,
    iter_modelo_applicability_rules,
    taxpayer_model_is_declared,
)

__all__ = [
    "ApplicabilityVerdict",
    "Modelo202Modality",
    "Modelo202ModalityVerdict",
    "ModeloApplicability",
    "ModeloApplicabilityRule",
    "PayerFact",
    "TaxRoute",
    "derive_modelo_202_modality",
    "derive_modelo_applicability",
    "derive_tax_route",
    "has_applicability_rule",
    "iter_modelo_applicability_rules",
    "taxpayer_model_is_declared",
]
