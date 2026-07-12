"""Public non-cyclic access to registry-owned modelo applicability rules.

This module is the focused public surface for the applicability
subsystem. The underlying implementation in ``_applicability.py``
uses leading-underscore names on the legal-refs constants and the
applicability-rules table to mark them as INTERNAL state — i.e.,
not part of the registry-root public API, not stable across
implementation refactors, and not to be reached for through the
private module from outside the registry package.

Re-exporting those names through this focused module IS the
canonical public bridge. The underscore prefix on the source-side
identifiers is preserved here for two reasons:

  1. The constants are domain configuration data (legal-refs
     tuples + per-modelo rule table) that the application layer
     observes but should not mutate. Keeping the underscore prefix
     in consumer code signals "registry-owned, don't manipulate"
     even when the import path is the focused public module.
  2. A rename to public-style names (drop the underscore) would
     produce mechanical churn across 5 files without structural
     benefit — the public/private contradiction is resolved by
     this module's existence as the documented bridge, not by
     the source-side name choice.

Cross-package consumers MUST import from this module
(``aeat.domain.calculations.registry.applicability``), NOT from
``_applicability``. Imports of ``_applicability`` are flagged by
``test_public_api_boundaries.py::test_source_tree_does_not_use_absolute_registry_private_imports``.

"""

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
