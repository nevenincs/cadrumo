"""Registry surface validation helpers for links, parity, deadlines, and references."""

from __future__ import annotations

from collections.abc import Mapping

from ._schema import LegalReference, ModeloRevision, SourceReference
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
            )
        )
        if cross_reference.oracle_id is not None:
            prior = oracle_bindings.get(cross_reference.oracle_id)
            if prior is not None:
                failures.append(
                    f"{prefix}: cross-references {prior!r} and {cross_reference.id!r} "
                    f"both bind oracle_id {cross_reference.oracle_id!r}; "
                    f"each oracle id may be bound by at most one cross-reference per revision"
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
                f"{prefix}: workbook parity {workbook.id!r} references unknown source {workbook.workbook_source!r}"
            )
            continue
        source = source_refs[workbook.workbook_source]
        if workbook.formula_coverage == "formula_form" and source.evidence_tier != "executable_parity_evidence":
            failures.append(
                f"{prefix}: workbook parity {workbook.id!r} formula workbook requires "
                "executable parity evidence source"
            )
        if workbook.formula_coverage != "formula_form" and source.evidence_tier == "executable_parity_evidence":
            failures.append(
                f"{prefix}: workbook parity {workbook.id!r} non-formula workbook must not use "
                "executable parity evidence source"
            )


def validate_verification_expectation_section(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    casillas: set[str],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
) -> None:
    for expectation in revision.verification_expectations:
        owner = f"verification expectation {expectation.id}"
        failures.extend(_missing_refs(prefix, owner, expectation.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, expectation.source_refs, source_refs, "source"))
        for casilla_id in expectation.computed_casillas:
            if casilla_id not in casillas:
                failures.append(f"{prefix}: {owner} references unknown casilla {casilla_id!r}")
        for total_kind, casilla_id in expectation.reconciliation_totals.items():
            if casilla_id not in casillas:
                failures.append(
                    f"{prefix}: {owner} reconciliation total {total_kind!r} references unknown casilla "
                    f"{casilla_id!r}"
                )
            if casilla_id not in expectation.computed_casillas:
                failures.append(
                    f"{prefix}: {owner} reconciliation total {total_kind!r} must be one of computed_casillas"
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


