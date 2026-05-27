"""Modelo applicability re-export — canonical implementation lives in the domain.

All logic resides in
:mod:`aeat.domain.calculations.registry._applicability`.  This module
is a thin re-export so the application-layer and test imports
(``from ._applicability import …``) continue to resolve without
modification while the single authoritative definition sits in the
correct hexagonal layer.
"""

from __future__ import annotations

from aeat.domain.calculations.registry import (
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
    "_ATTRIBUTION_PASS_THROUGH_LEGAL_REFS",
    "_INCOMPLETE_LEGAL_REFS",
    "_INCOMPLETE_UNDECLARED_REASON",
    "_INCOMPLETE_UNDETERMINED_REASON",
    "_INCOMPLETE_UNRULED_REASON",
    "_MODELO_APPLICABILITY_RULES",
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
