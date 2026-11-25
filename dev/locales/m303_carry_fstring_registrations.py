"""Bounded locale registration for Modelo 303 carry-ingress refusals."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .fstring_registry import FStringKeyRegistration


def m303_carry_error_registration() -> FStringKeyRegistration:
    """Build the closed M303 carry-ingress refusal registration."""
    from cadrumo.application.calculations.m303_carry_ingress import M303_CARRY_ERROR_NAMESPACE

    from .fstring_registry import FStringKeyRegistration

    return FStringKeyRegistration(
        # Bounded enumeration, pinned to the _translated_error codes in
        # application/calculations/m303_carry_ingress.py, which keys every
        # refusal under M303_CARRY_ERROR_NAMESPACE.
        description="application.calculations.m303_carry.errors.* (M303 carry ingress refusals)",
        key_factory=lambda v: f"{M303_CARRY_ERROR_NAMESPACE}.{v}",
        values=(
            "available_compensation_formula_missing",
            "carry_operands_disagree_with_formula",
            "casilla_id_invalid",
            "disposition_code_not_admitted",
            "disposition_code_undeclared",
            "disposition_result_sign_incompatible",
            "duplicate_header_facts",
            "envelope_not_normalized",
            "formula_mapping_required",
            "header_code_invalid",
            "header_code_not_admitted",
            "incomplete_supported_operands",
            "invalid_registry_observation",
            "local_disposition_header_disagreement",
            "local_filing_disposition_required",
            "local_filing_provenance_required",
            "non_target_modelo_envelope",
            "official_disposition_header_disagreement",
            "official_header_required",
            "registry_resolution_unavailable",
            "registry_scope_invalid",
            "result_casilla_required",
            "supplied_available_contradicts_derivation",
            "supplied_disposition_not_admitted",
            "supplied_pair_contradicts_derivation",
            "unsupported_provenance",
        ),
    )


__all__ = ["m303_carry_error_registration"]
