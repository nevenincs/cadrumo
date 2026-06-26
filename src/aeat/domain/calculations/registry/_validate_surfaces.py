"""Registry surface validation helpers for links, parity, deadlines, and references.

Validates cross-reference, workbook-parity, verification-expectation,
application-link, and deadline-window sections declared on a
:class:`ModeloRevision` for reference closure and evidence-tier requirements.
"""

from __future__ import annotations

import re as _re
from collections.abc import Mapping

from ._ids import CasillaId
from ._schema import (
    KNOWN_VERIFICATION_PREDICATE_OPERATORS,
    LegalReference,
    ModeloRevision,
    SourceReference,
)
from ._validate_evidence import EvidenceValidator
from ._validate_helpers import _missing_refs


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
        if workbook.formula_coverage != "formula_form" and source.evidence_tier == "executable_parity_evidence":
            failures.append(
                f"{prefix}: workbook parity {workbook.id!r} non-formula workbook must not use "
                "executable parity evidence source",
            )


# The known predicate operator set was previously a module-level constant
# here that mirrored the runtime evaluator's regex set. Drift between the
# two was a silent-pass hazard. The canonical set now lives at
# aeat.domain.calculations.registry._schema.KNOWN_VERIFICATION_PREDICATE_OPERATORS
# and both the validator (here) and a gate test against the runtime
# evaluator reference it.
def _predicate_operator_name(expression: str) -> str | None:
    """Return the leading operator name of a predicate expression, or None."""
    stripped = expression.strip()
    paren_idx = stripped.find("(")
    if paren_idx <= 0:
        return None
    return stripped[:paren_idx]


# equals(["lhs", "rhs"]) — the consistency operator must name EXACTLY two casilla
# ids. The shape mirrors the runtime regex in
# aeat.application.modelo._verification_actions._PREDICATE_EQUALS; this validator
# is the authoring-time gate so a malformed arity fails registry load rather than
# silently holding at evaluation time.
_EQUALS_PREDICATE = _re.compile(r"^equals\(\[(?P<ids>[^\]]*)\]\)$")


def _equals_predicate_arity_failures(prefix: str, owner: str, expression: str) -> list[str]:
    """Return failures for a malformed ``equals`` predicate (not exactly two ids)."""
    match = _EQUALS_PREDICATE.match(expression.strip())
    if match is None:
        return [
            f'{prefix}: {owner} equals expression {expression!r} is malformed; expected equals(["lhs_id", "rhs_id"])',
        ]
    ids = [token.strip().strip('"').strip("'") for token in match.group("ids").split(",") if token.strip()]
    if len(ids) != 2:
        return [
            f"{prefix}: {owner} equals expression must name exactly two casilla ids, got {len(ids)}: {ids!r}",
        ]
    return []


# roll_forward_balances(["closing", "opening", "applied", "base"]) — the
# carry-forward continuity operator must name EXACTLY four casilla ids, each an
# existing casilla on the revision. Mirrors the runtime regex in
# aeat.application.modelo._verification_actions._PREDICATE_ROLL_FORWARD_BALANCES;
# this authoring-time gate fails a malformed arity / typo'd id at registry load
# rather than letting the runtime evaluator's bad-arity branch silently hold (or,
# for the ADVISORY form, silently never fire).
_ROLL_FORWARD_BALANCES_PREDICATE = _re.compile(r"^roll_forward_balances\(\[(?P<ids>[^\]]*)\]\)$")


def _roll_forward_balances_predicate_arity_failures(
    prefix: str,
    owner: str,
    expression: str,
    casillas: set[CasillaId],
) -> list[str]:
    """Return failures for a malformed ``roll_forward_balances`` predicate."""
    match = _ROLL_FORWARD_BALANCES_PREDICATE.match(expression.strip())
    if match is None:
        return [
            f"{prefix}: {owner} roll_forward_balances expression {expression!r} is malformed; expected "
            'roll_forward_balances(["closing_id", "opening_id", "applied_id", "base_id"])',
        ]
    ids = [token.strip().strip('"').strip("'") for token in match.group("ids").split(",") if token.strip()]
    failures: list[str] = []
    if len(ids) != 4:
        failures.append(
            f"{prefix}: {owner} roll_forward_balances must name exactly four casilla ids "
            f"(closing, opening, applied, base), got {len(ids)}: {ids!r}",
        )
    for casilla_id in ids:
        if casilla_id not in casillas:
            failures.append(f"{prefix}: {owner} roll_forward_balances references unknown casilla {casilla_id!r}")
    return failures


def validate_verification_expectation_section(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    casillas: set[CasillaId],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
) -> None:
    for expectation in revision.verification_expectations:
        owner = f"verification expectation {expectation.id}"
        failures.extend(_missing_refs(prefix, owner, expectation.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, expectation.source_refs, source_refs, "source"))
        for casilla_id in expectation.computed_casilla_ids:
            if casilla_id not in casillas:
                failures.append(f"{prefix}: {owner} references unknown casilla {casilla_id!r}")
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
            failures.extend(_equals_predicate_arity_failures(prefix, owner, predicate.expression))
        elif op_name == "roll_forward_balances":
            # roll_forward_balances(["closing", "opening", "applied", "base"]) is a
            # four-casilla continuity check; reject a malformed arity or unknown
            # casilla id at authoring time rather than letting the runtime
            # evaluator's bad-arity branch silently hold / never fire.
            failures.extend(
                _roll_forward_balances_predicate_arity_failures(prefix, owner, predicate.expression, casillas),
            )


def validate_application_link_section(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
) -> None:
    for link in revision.application_links:
        owner = f"application link {link.id}"
        failures.extend(_missing_refs(prefix, owner, link.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, link.source_refs, source_refs, "source"))


def validate_deadline_window_section(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
) -> None:
    for window in revision.deadline_windows:
        owner = f"deadline window {window.id}"
        failures.extend(_missing_refs(prefix, owner, window.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, window.source_refs, source_refs, "source"))
        for condition in window.applicability_conditions:
            condition_owner = f"deadline condition for {window.id}"
            failures.extend(_missing_refs(prefix, condition_owner, condition.legal_refs, legal_refs, "legal"))
            failures.extend(_missing_refs(prefix, condition_owner, condition.source_refs, source_refs, "source"))
