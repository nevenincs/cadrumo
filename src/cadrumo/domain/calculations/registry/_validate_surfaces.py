"""Registry surface validation helpers for links, parity, deadlines, and references.

Validates cross-reference, workbook-parity, verification-expectation,
application-link, and deadline-window sections declared on a
:class:`ModeloRevision` for reference closure and evidence-tier requirements.
"""

from __future__ import annotations

from collections.abc import Mapping

from ._ids import CasillaId
from ._schema import LegalReference, ModeloRevision, SourceReference
from ._schema_verification import KNOWN_VERIFICATION_PREDICATE_OPERATORS
from ._validate_evidence import EvidenceValidator
from ._validate_helpers import _missing_refs
from ._validate_verification_predicates import (
    _CASILLA_LIST_OPERATORS,
    _casilla_equals_implies_diverges_predicate_failures,
    _casilla_equals_implies_nonzero_predicate_failures,
    _casilla_equals_implies_profile_flag_predicate_failures,
    _casilla_list_predicate_failures,
    _deduccion_requires_adquisicion_before_predicate_failures,
    _predicate_operator_name,
    _profile_flag_enabled_predicate_failures,
    _roll_forward_balances_predicate_arity_failures,
)


def validate_cross_reference_section(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
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


def validate_workbook_parity_section(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
) -> None:
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
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    casillas: set[CasillaId],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
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
        for casilla_id in expectation.computed_casilla_ids:
            if casilla_id not in casillas:
                failures.append(f"{prefix}: {owner} references unknown casilla {casilla_id!r}")
        for casilla_id in expectation.reconcile_when_present_casilla_ids:
            if casilla_id not in casillas:
                failures.append(
                    f"{prefix}: {owner} reconcile-when-present references unknown casilla {casilla_id!r}",
                )
        for casilla_id in expectation.externally_grounded_casilla_ids:
            if casilla_id not in casillas:
                failures.append(
                    f"{prefix}: {owner} externally-grounded references unknown casilla {casilla_id!r}",
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

    for predicate in revision.verification_predicates:
        owner = f"verification predicate {predicate.predicate_id}"
        failures.extend(_missing_refs(prefix, owner, predicate.legal_refs, legal_refs, "legal"))
        op_name = _predicate_operator_name(predicate.expression)
        if op_name is None:
            failures.append(
                f"{prefix}: {owner} expression {predicate.expression!r} is not a recognised "
                "DSL call (missing operator name or opening paren)",
            )
        elif op_name not in KNOWN_VERIFICATION_PREDICATE_OPERATORS:
            failures.append(
                f"{prefix}: {owner} expression uses unknown operator {op_name!r}; known operators: "
                f"{sorted(KNOWN_VERIFICATION_PREDICATE_OPERATORS)!r}",
            )
        elif op_name == "equals":
            # equals(["lhs_id", "rhs_id"]) is a binary consistency check; reject a
            # malformed arity at authoring time rather than letting the runtime
            # evaluator silently hold (its <2-id defensive branch returns True).
            failures.extend(
                _casilla_list_predicate_failures(
                    prefix,
                    owner,
                    predicate.expression,
                    operator_name=op_name,
                    casillas=casillas,
                ),
            )
        elif op_name == "roll_forward_balances":
            # roll_forward_balances(["closing", "opening", "applied", "base"]) is a
            # four-casilla continuity check; reject a malformed arity or unknown
            # casilla id at authoring time rather than letting the runtime
            # evaluator's bad-arity branch silently hold / never fire.
            failures.extend(
                _roll_forward_balances_predicate_arity_failures(prefix, owner, predicate.expression, casillas),
            )
        elif op_name == "casilla_equals_implies_nonzero":
            # casilla_equals_implies_nonzero(["antecedent_id", "literal",
            # "consequent_id"]) mixes two casilla ids with a literal string;
            # reject a malformed arity, an unknown antecedent/consequent
            # casilla, or an empty literal at authoring time.
            failures.extend(
                _casilla_equals_implies_nonzero_predicate_failures(
                    prefix,
                    owner,
                    predicate.expression,
                    casillas,
                    casilla_by_id,
                ),
            )
        elif op_name == "casilla_equals_implies_profile_flag":
            # casilla_equals_implies_profile_flag(["antecedent_id", "literal",
            # "profile_field"]) mixes a casilla id, a literal, and a
            # TaxpayerProfile field/property name; reject a malformed arity,
            # an unknown/non-text antecedent casilla, an empty literal, or an
            # unsupported profile field at authoring time.
            failures.extend(
                _casilla_equals_implies_profile_flag_predicate_failures(
                    prefix,
                    owner,
                    predicate.expression,
                    casillas,
                    casilla_by_id,
                ),
            )
        elif op_name == "casilla_equals_implies_diverges":
            # casilla_equals_implies_diverges(["antecedent_id", "literal",
            # "casilla_a_id", "casilla_b_id"]) mixes three casilla ids with a
            # literal string; reject a malformed arity, an unknown
            # antecedent/consequent-pair casilla, a non-text antecedent, a
            # text consequent, or an empty literal at authoring time.
            failures.extend(
                _casilla_equals_implies_diverges_predicate_failures(
                    prefix,
                    owner,
                    predicate.expression,
                    casillas,
                    casilla_by_id,
                ),
            )
        elif op_name == "deduccion_requires_adquisicion_before":
            # deduccion_requires_adquisicion_before(["amount_id",
            # "acquisition_date_id", "construction_date_id", "cutoff_iso"]) mixes
            # three casilla ids with a trailing ISO-date literal; reject a
            # malformed arity, an unknown amount/date casilla, a non-text date
            # casilla, or an unparseable cutoff at authoring time.
            failures.extend(
                _deduccion_requires_adquisicion_before_predicate_failures(
                    prefix,
                    owner,
                    predicate.expression,
                    casillas,
                    casilla_by_id,
                ),
            )
        elif op_name == "profile_flag_enabled":
            failures.extend(_profile_flag_enabled_predicate_failures(prefix, owner, predicate.expression))
        elif op_name in _CASILLA_LIST_OPERATORS:
            failures.extend(
                _casilla_list_predicate_failures(
                    prefix,
                    owner,
                    predicate.expression,
                    operator_name=op_name,
                    casillas=casillas,
                ),
            )


def validate_application_link_section(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
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


def validate_deadline_window_section(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
    for window in revision.deadline_windows:
        owner = f"deadline window {window.id}"
        failures.extend(_missing_refs(prefix, owner, window.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, window.source_refs, source_refs, "source"))
        failures.extend(evidence.require_source_tier(prefix, owner, window.source_refs, "official_source_guidance"))
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
