"""Overview compatibility wrapper for registry-owned applicability rules."""

from __future__ import annotations

from ...domain.calculations.registry.applicability import (
    _ATTRIBUTION_PASS_THROUGH_LEGAL_REFS,
    _INCOMPLETE_LEGAL_REFS,
    _INCOMPLETE_UNDECLARED_REASON,
    _INCOMPLETE_UNDETERMINED_REASON,
    _INCOMPLETE_UNRULED_REASON,
    _MODELO_APPLICABILITY_RULES,
    ApplicabilityVerdict,
    ModeloApplicability,
    ModeloApplicabilityRule,
    PayerFact,
    TaxRoute,
    derive_modelo_applicability,
    derive_tax_route,
    has_applicability_rule,
    iter_modelo_applicability_rules,
    taxpayer_model_is_declared,
)

__all__ = [
    "_ATTRIBUTION_PASS_THROUGH_LEGAL_REFS",
    "_INCOMPLETE_LEGAL_REFS",
    "_INCOMPLETE_UNDECLARED_REASON",
    "_INCOMPLETE_UNDETERMINED_REASON",
    "_INCOMPLETE_UNRULED_REASON",
    "_MODELO_APPLICABILITY_RULES",
    "ApplicabilityVerdict",
    "ModeloApplicability",
    "ModeloApplicabilityRule",
    "PayerFact",
    "TaxRoute",
    "derive_modelo_applicability",
    "derive_tax_route",
    "has_applicability_rule",
    "iter_modelo_applicability_rules",
    "taxpayer_model_is_declared",
]
