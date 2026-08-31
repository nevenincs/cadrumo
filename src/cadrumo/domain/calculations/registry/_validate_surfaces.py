"""Registry surface validation helpers for links, parity, deadlines, and references.

Validates cross-reference, workbook-parity, verification-expectation,
application-link, and deadline-window sections declared on a
:class:`ModeloRevision` for reference closure and evidence-tier requirements.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping

from ....core import CasillaId
from ._validate_evidence import EvidenceValidator
from ._validate_helpers import missing_refs as _missing_refs
from ._validate_official_source_guidance_content import deadline_window_content_failures
from ._validate_verification_predicates import (
    _CASILLA_LIST_OPERATORS,
    _advisory_when_ratio_ge_predicate_failures,
    _casilla_equals_implies_diverges_predicate_failures,
    _casilla_equals_implies_nonzero_predicate_failures,
    _casilla_equals_implies_profile_flag_predicate_failures,
    _casilla_list_predicate_failures,
    _deduccion_requires_adquisicion_before_predicate_failures,
    _profile_field_required_predicate_failures,
    _profile_flag_enabled_predicate_failures,
)
from .schema import ModeloRevision
from .schema_references import LegalReference, SourceReference
from .schema_surfaces import CasillaDefinition
from .schema_verification import (
    KNOWN_VERIFICATION_PREDICATE_OPERATORS,
    VerificationExpectationDefinition,
    verification_predicate_operator_name,
)

# Operators mixing casilla ids with literal tokens, so they cannot route through the
# generic casilla-list validators. advisory_when_ratio_ge is the sharpest case: the
# runtime builds its threshold with a bare Decimal and compares outside its own except
# clause, so an unvalidated literal either never fires (Infinity) or raises uncaught (NaN).
_MIXED_TOKEN_PREDICATE_VALIDATORS: dict[
    str,
    Callable[[str, str, str, set[CasillaId], Mapping[CasillaId, CasillaDefinition]], list[str]],
] = {
    "casilla_equals_implies_nonzero": _casilla_equals_implies_nonzero_predicate_failures,
    "casilla_equals_implies_profile_flag": _casilla_equals_implies_profile_flag_predicate_failures,
    "casilla_equals_implies_diverges": _casilla_equals_implies_diverges_predicate_failures,
    "deduccion_requires_adquisicion_before": _deduccion_requires_adquisicion_before_predicate_failures,
    "advisory_when_ratio_ge": _advisory_when_ratio_ge_predicate_failures,
}

_PROFILE_PREDICATE_VALIDATORS: dict[str, Callable[[str, str, str], list[str]]] = {
    "profile_flag_enabled": _profile_flag_enabled_predicate_failures,
    "profile_field_required": _profile_field_required_predicate_failures,
}


def validate_cross_reference_section(
    *,
    prefix: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> list[str]:
    failures: list[str] = []
    oracle_bindings: dict[str, str] = {}
    for cross_reference in revision.live_cross_references:
        owner = f"cross-reference {cross_reference.id}"
        failures.extend(_missing_refs(prefix, owner, cross_reference.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, cross_reference.source_refs, source_refs, "source"))
        failures.extend(
            evidence.require_source_tier(
                prefix,
                owner,
                cross_reference.source_refs,
                cross_reference.evidence_tier,
            ),
        )
        for predicate in cross_reference.applicability_predicates:
            predicate_owner = f"{owner} applicability predicate {predicate.field!r}"
            failures.extend(_missing_refs(prefix, predicate_owner, predicate.legal_refs, legal_refs, "legal"))
            failures.extend(_missing_refs(prefix, predicate_owner, predicate.source_refs, source_refs, "source"))
            failures.extend(
                evidence.require_source_tier(
                    prefix,
                    predicate_owner,
                    predicate.source_refs,
                    "official_source_guidance",
                ),
            )
        if cross_reference.oracle_id is not None:
            prior = oracle_bindings.get(cross_reference.oracle_id)
            if prior is not None:
                failures.append(
                    f"{prefix}: cross-references {prior!r} and {cross_reference.id!r} "
                    f"both bind oracle_id {cross_reference.oracle_id!r}; "
                    f"each oracle id may be bound by at most one cross-reference per revision",
                )
            else:
                oracle_bindings[cross_reference.oracle_id] = cross_reference.id
    return failures


def validate_workbook_parity_section(
    *,
    prefix: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
) -> list[str]:
    failures: list[str] = []
    for workbook in revision.workbook_parity_refs:
        owner = f"workbook parity {workbook.id}"
        failures.extend(_missing_refs(prefix, owner, workbook.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, workbook.source_refs, source_refs, "source"))
        if workbook.workbook_source not in source_refs:
            failures.append(
                f"{prefix}: workbook parity {workbook.id!r} references unknown source {workbook.workbook_source!r}",
            )
            continue
        source = source_refs[workbook.workbook_source]
        if workbook.formula_coverage == "formula_form" and source.evidence_tier != "executable_parity_evidence":
            failures.append(
                f"{prefix}: workbook parity {workbook.id!r} formula workbook "
                "requires executable parity evidence source",
            )
        if workbook.formula_coverage != "formula_form" and source.evidence_tier != "layout_authority":
            failures.append(
                f"{prefix}: workbook parity {workbook.id!r} non-formula workbook "
                "requires layout_authority source evidence",
            )
    return failures


_APPLICATION_LINK_ALLOWED_SOURCE_TIERS: Mapping[str, tuple[str, ...]] = {
    "export": ("layout_authority",),
    "extractor": ("layout_authority", "official_source_guidance"),
    "portal": ("official_source_guidance", "executable_parity_evidence"),
}
_DEFAULT_APPLICATION_LINK_SOURCE_TIERS = ("official_source_guidance",)


def _allowed_application_link_source_tiers(surface: str) -> tuple[str, ...]:
    return _APPLICATION_LINK_ALLOWED_SOURCE_TIERS.get(surface, _DEFAULT_APPLICATION_LINK_SOURCE_TIERS)


def _application_link_source_tier_failures(
    prefix: str,
    owner: str,
    refs: tuple[str, ...],
    *,
    surface: str,
    source_refs: Mapping[str, SourceReference],
) -> list[str]:
    allowed_tiers = _allowed_application_link_source_tiers(surface)
    for ref in refs:
        source = source_refs.get(ref)
        if source is not None and source.evidence_tier in allowed_tiers:
            return []
    if len(allowed_tiers) == 1:
        requirement = f"{allowed_tiers[0]} source evidence"
    else:
        requirement = f"one of {', '.join(allowed_tiers)} source evidence"
    return [f"{prefix}: {owner} requires {requirement}"]


def validate_verification_expectation_section(
    *,
    prefix: str,
    revision: ModeloRevision,
    casillas: set[CasillaId],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> list[str]:
    failures: list[str] = []
    casilla_by_id = {casilla.id: casilla for casilla in revision.casillas}

    for expectation in revision.verification_expectations:
        owner = f"verification expectation {expectation.id}"
        failures.extend(_missing_refs(prefix, owner, expectation.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, expectation.source_refs, source_refs, "source"))
        failures.extend(
            evidence.require_source_tier(
                prefix,
                owner,
                expectation.source_refs,
                "official_source_guidance",
            ),
        )
        failures.extend(_expectation_casilla_failures(prefix, owner, expectation, casillas))

    for predicate in revision.verification_predicates:
        owner = f"verification predicate {predicate.predicate_id}"
        failures.extend(_missing_refs(prefix, owner, predicate.legal_refs, legal_refs, "legal"))
        failures.extend(
            _verification_predicate_expression_failures(
                prefix,
                owner,
                predicate.expression,
                casillas=casillas,
                casilla_by_id=casilla_by_id,
            ),
        )
    return failures


def _unknown_casilla_failures(
    prefix: str,
    owner: str,
    casilla_ids: Iterable[CasillaId],
    casillas: set[CasillaId],
    *,
    qualifier: str = "",
) -> list[str]:
    label = f"{qualifier} " if qualifier else ""
    return [
        f"{prefix}: {owner} {label}references unknown casilla {casilla_id!r}"
        for casilla_id in casilla_ids
        if casilla_id not in casillas
    ]


def _expectation_casilla_failures(
    prefix: str,
    owner: str,
    expectation: VerificationExpectationDefinition,
    casillas: set[CasillaId],
) -> list[str]:
    failures = _unknown_casilla_failures(prefix, owner, expectation.computed_casilla_ids, casillas)
    failures.extend(
        _unknown_casilla_failures(
            prefix,
            owner,
            expectation.reconcile_when_present_casilla_ids,
            casillas,
            qualifier="reconcile-when-present",
        ),
    )
    failures.extend(
        _unknown_casilla_failures(
            prefix,
            owner,
            expectation.externally_grounded_casilla_ids,
            casillas,
            qualifier="externally-grounded",
        ),
    )
    for total_kind, casilla_id in expectation.reconciliation_total_casilla_ids.items():
        if casilla_id not in casillas:
            failures.append(
                f"{prefix}: {owner} reconciliation total {total_kind!r} references unknown casilla {casilla_id!r}",
            )
        if casilla_id not in expectation.computed_casilla_ids:
            failures.append(
                f"{prefix}: {owner} reconciliation total {total_kind!r} must be one of computed_casilla_ids",
            )
    return failures


def _verification_predicate_expression_failures(
    prefix: str,
    owner: str,
    expression: str,
    *,
    casillas: set[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
) -> list[str]:
    op_name = verification_predicate_operator_name(expression)
    if op_name is None:
        return [
            f"{prefix}: {owner} expression {expression!r} is not a recognised "
            "DSL call (missing operator name or opening paren)",
        ]
    if op_name not in KNOWN_VERIFICATION_PREDICATE_OPERATORS:
        return [
            f"{prefix}: {owner} expression uses unknown operator {op_name!r}; known operators: "
            f"{sorted(KNOWN_VERIFICATION_PREDICATE_OPERATORS)!r}",
        ]
    mixed_token_validator = _MIXED_TOKEN_PREDICATE_VALIDATORS.get(op_name)
    if mixed_token_validator is not None:
        return mixed_token_validator(prefix, owner, expression, casillas, casilla_by_id)
    profile_validator = _PROFILE_PREDICATE_VALIDATORS.get(op_name)
    if profile_validator is not None:
        return profile_validator(prefix, owner, expression)
    if op_name in _CASILLA_LIST_OPERATORS:
        # Includes equals(["lhs_id", "rhs_id"]), a binary consistency check whose
        # malformed arity must be rejected at authoring time rather than letting the
        # runtime evaluator silently hold (its <2-id defensive branch returns True).
        return _casilla_list_predicate_failures(
            prefix,
            owner,
            expression,
            operator_name=op_name,
            casillas=casillas,
        )
    return []


def validate_application_link_section(
    *,
    prefix: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> list[str]:
    failures: list[str] = []
    for link in revision.application_links:
        owner = f"application link {link.id}"
        failures.extend(_missing_refs(prefix, owner, link.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, link.source_refs, source_refs, "source"))
        failures.extend(
            _application_link_source_tier_failures(
                prefix,
                owner,
                link.source_refs,
                surface=link.surface,
                source_refs=source_refs,
            ),
        )
    return failures


def validate_deadline_window_section(
    *,
    prefix: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> list[str]:
    failures: list[str] = []
    for window in revision.deadline_windows:
        owner = f"deadline window {window.id}"
        failures.extend(_missing_refs(prefix, owner, window.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, window.source_refs, source_refs, "source"))
        failures.extend(evidence.require_source_tier(prefix, owner, window.source_refs, "official_source_guidance"))
        failures.extend(
            deadline_window_content_failures(prefix, window, source_refs=source_refs, evidence=evidence),
        )
        for condition in window.applicability_conditions:
            condition_owner = f"deadline condition for {window.id}"
            failures.extend(_missing_refs(prefix, condition_owner, condition.legal_refs, legal_refs, "legal"))
            failures.extend(_missing_refs(prefix, condition_owner, condition.source_refs, source_refs, "source"))
            failures.extend(
                evidence.require_source_tier(
                    prefix,
                    condition_owner,
                    condition.source_refs,
                    "official_source_guidance",
                ),
            )
    return failures
