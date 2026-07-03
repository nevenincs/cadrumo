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
    KNOWN_PROFILE_FLAG_ADVISORY_FIELDS,
    KNOWN_VERIFICATION_PREDICATE_OPERATORS,
    LegalReference,
    ModeloRevision,
    SourceReference,
)
from ._schema_surfaces import CasillaDefinition
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


_CASILLA_LIST_PREDICATE = _re.compile(r"^(?P<operator>[a-z_]+)\(\[(?P<ids>[^\]]*)\]\)$")
_EXACT_CASILLA_LIST_ARITY: Mapping[str, int] = {
    # advisory_when_positive names exactly one casilla id and routes through the
    # generic single-casilla validation (exact arity 1 + unknown-casilla check).
    "advisory_when_positive": 1,
    "advisory_when_computed_diverges": 2,
    "cap_le_when_positive": 2,
    "equals": 2,
    "implies_nonzero": 2,
    "roll_forward_balances": 4,
}
_MIN_CASILLA_LIST_ARITY: Mapping[str, int] = {
    "all_nonzero": 1,
    "at_most_one_positive": 2,
    "any_nonzero": 1,
    "implies_any_nonzero": 2,
}
_CASILLA_LIST_OPERATORS = frozenset(_EXACT_CASILLA_LIST_ARITY) | frozenset(_MIN_CASILLA_LIST_ARITY)
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


def _parse_predicate_casilla_id_tokens(ids_fragment: str) -> list[str]:
    return [token.strip().strip('"').strip("'") for token in ids_fragment.split(",") if token.strip()]


def _casilla_list_predicate_failures(
    prefix: str,
    owner: str,
    expression: str,
    *,
    operator_name: str,
    casillas: set[CasillaId],
) -> list[str]:
    match = _CASILLA_LIST_PREDICATE.match(expression.strip())
    if match is None or match.group("operator") != operator_name:
        return [
            f"{prefix}: {owner} {operator_name} expression {expression!r} is malformed; expected "
            f'{operator_name}(["casilla_id", ...])',
        ]
    ids = _parse_predicate_casilla_id_tokens(match.group("ids"))
    failures: list[str] = []
    expected_arity = _EXACT_CASILLA_LIST_ARITY.get(operator_name)
    if expected_arity is not None and len(ids) != expected_arity:
        failures.append(
            f"{prefix}: {owner} {operator_name} expression must name exactly {expected_arity} "
            f"casilla ids, got {len(ids)}: {ids!r}",
        )
    min_arity = _MIN_CASILLA_LIST_ARITY.get(operator_name)
    if min_arity is not None and len(ids) < min_arity:
        failures.append(
            f"{prefix}: {owner} {operator_name} expression must name at least {min_arity} "
            f"casilla ids, got {len(ids)}: {ids!r}",
        )
    for casilla_id in ids:
        if casilla_id not in casillas:
            failures.append(f"{prefix}: {owner} {operator_name} references unknown casilla {casilla_id!r}")
    return failures


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
    ids = _parse_predicate_casilla_id_tokens(match.group("ids"))
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


# casilla_equals_implies_nonzero(["antecedent_casilla_id", "literal",
# "consequent_casilla_id"]) — categorical-conditional material implication.
# Unlike the other casilla-list operators, the middle token is a literal
# string, not a casilla id, so it cannot route through the generic
# _casilla_list_predicate_failures (which validates every bracketed token as
# a casilla id). Mirrors roll_forward_balances's bespoke-validator shape:
# this authoring-time gate rejects a malformed arity, an unknown antecedent
# or consequent casilla id, or an empty literal at registry load, rather than
# letting the runtime evaluator's defensive bad-arity branch (returns False —
# never fires) silently mask a typo.
_CASILLA_EQUALS_IMPLIES_NONZERO_PREDICATE = _re.compile(
    r"^casilla_equals_implies_nonzero\(\[(?P<ids>[^\]]*)\]\)$",
)


def _casilla_equals_implies_nonzero_predicate_failures(
    prefix: str,
    owner: str,
    expression: str,
    casillas: set[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
) -> list[str]:
    """Return failures for a malformed ``casilla_equals_implies_nonzero`` predicate."""
    match = _CASILLA_EQUALS_IMPLIES_NONZERO_PREDICATE.match(expression.strip())
    if match is None:
        return [
            f"{prefix}: {owner} casilla_equals_implies_nonzero expression {expression!r} is malformed; "
            'expected casilla_equals_implies_nonzero(["antecedent_casilla_id", "literal", "consequent_casilla_id"])',
        ]
    tokens = _parse_predicate_casilla_id_tokens(match.group("ids"))
    failures: list[str] = []
    if len(tokens) != 3:
        failures.append(
            f"{prefix}: {owner} casilla_equals_implies_nonzero must name exactly three tokens "
            f"(antecedent casilla id, literal, consequent casilla id), got {len(tokens)}: {tokens!r}",
        )
        return failures
    antecedent_id, literal, consequent_id = tokens
    antecedent = casilla_by_id.get(antecedent_id)
    if antecedent_id not in casillas:
        failures.append(
            f"{prefix}: {owner} casilla_equals_implies_nonzero references unknown antecedent casilla {antecedent_id!r}",
        )
    elif antecedent is not None and antecedent.data_type != "text":
        failures.append(
            f"{prefix}: {owner} casilla_equals_implies_nonzero antecedent casilla {antecedent_id!r} "
            "must have data_type 'text'",
        )
    if not literal:
        failures.append(f"{prefix}: {owner} casilla_equals_implies_nonzero literal must be non-empty")
    consequent = casilla_by_id.get(consequent_id)
    if consequent_id not in casillas:
        failures.append(
            f"{prefix}: {owner} casilla_equals_implies_nonzero references unknown consequent casilla {consequent_id!r}",
        )
    elif consequent is not None and consequent.data_type == "text":
        failures.append(
            f"{prefix}: {owner} casilla_equals_implies_nonzero consequent casilla {consequent_id!r} "
            "must not have data_type 'text'",
        )
    return failures


# casilla_equals_implies_diverges(["antecedent_casilla_id", "literal",
# "casilla_a_id", "casilla_b_id"]) — categorical-conditional divergence
# check. Unlike the other casilla-list operators, the second token is a
# literal string, not a casilla id, so it cannot route through the generic
# _casilla_list_predicate_failures. Mirrors
# casilla_equals_implies_nonzero's bespoke-validator shape: this
# authoring-time gate rejects a malformed arity, an unknown antecedent or
# consequent-pair casilla id, a non-text antecedent, a text consequent
# casilla, or an empty literal at registry load, rather than letting the
# runtime evaluator's defensive bad-arity branch (returns False — never
# fires) silently mask a typo.
_CASILLA_EQUALS_IMPLIES_DIVERGES_PREDICATE = _re.compile(
    r"^casilla_equals_implies_diverges\(\[(?P<ids>[^\]]*)\]\)$",
)


def _casilla_equals_implies_diverges_predicate_failures(
    prefix: str,
    owner: str,
    expression: str,
    casillas: set[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
) -> list[str]:
    """Return failures for a malformed ``casilla_equals_implies_diverges`` predicate."""
    match = _CASILLA_EQUALS_IMPLIES_DIVERGES_PREDICATE.match(expression.strip())
    if match is None:
        return [
            f"{prefix}: {owner} casilla_equals_implies_diverges expression {expression!r} is malformed; "
            'expected casilla_equals_implies_diverges(["antecedent_casilla_id", "literal", '
            '"casilla_a_id", "casilla_b_id"])',
        ]
    tokens = _parse_predicate_casilla_id_tokens(match.group("ids"))
    failures: list[str] = []
    if len(tokens) != 4:
        failures.append(
            f"{prefix}: {owner} casilla_equals_implies_diverges must name exactly four tokens "
            f"(antecedent casilla id, literal, casilla_a id, casilla_b id), got {len(tokens)}: {tokens!r}",
        )
        return failures
    antecedent_id, literal, casilla_a_id, casilla_b_id = tokens
    antecedent = casilla_by_id.get(antecedent_id)
    if antecedent_id not in casillas:
        failures.append(
            f"{prefix}: {owner} casilla_equals_implies_diverges references unknown antecedent "
            f"casilla {antecedent_id!r}",
        )
    elif antecedent is not None and antecedent.data_type != "text":
        failures.append(
            f"{prefix}: {owner} casilla_equals_implies_diverges antecedent casilla {antecedent_id!r} "
            "must have data_type 'text'",
        )
    if not literal:
        failures.append(f"{prefix}: {owner} casilla_equals_implies_diverges literal must be non-empty")
    for role, consequent_id in (("casilla_a", casilla_a_id), ("casilla_b", casilla_b_id)):
        consequent = casilla_by_id.get(consequent_id)
        if consequent_id not in casillas:
            failures.append(
                f"{prefix}: {owner} casilla_equals_implies_diverges references unknown {role} casilla "
                f"{consequent_id!r}",
            )
        elif consequent is not None and consequent.data_type == "text":
            failures.append(
                f"{prefix}: {owner} casilla_equals_implies_diverges {role} casilla {consequent_id!r} "
                "must not have data_type 'text'",
            )
    return failures


# deduccion_requires_adquisicion_before(["amount_id", "acquisition_date_id",
# "construction_date_id", "cutoff_iso"]) — eligibility-conditional advisory.
# Mixes three casilla ids with a trailing ISO-date literal, so it cannot route
# through the generic _casilla_list_predicate_failures (which validates every
# bracketed token as a casilla id). This authoring-time gate rejects a malformed
# arity, an unknown amount/date casilla, a non-text date casilla, or an
# unparseable cutoff at registry load rather than letting the runtime evaluator's
# defensive bad-arity / unparseable-cutoff branch (returns False — never fires)
# silently mask a typo.
_DEDUCCION_REQUIRES_ADQUISICION_BEFORE_PREDICATE = _re.compile(
    r"^deduccion_requires_adquisicion_before\(\[(?P<ids>[^\]]*)\]\)$",
)
_ISO_DATE_LITERAL = _re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PROFILE_FLAG_ENABLED_PREDICATE = _re.compile(r'^profile_flag_enabled\("(?P<field>[^"]+)"\)$')


def _deduccion_requires_adquisicion_before_predicate_failures(
    prefix: str,
    owner: str,
    expression: str,
    casillas: set[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
) -> list[str]:
    """Return failures for a malformed ``deduccion_requires_adquisicion_before`` predicate."""
    match = _DEDUCCION_REQUIRES_ADQUISICION_BEFORE_PREDICATE.match(expression.strip())
    if match is None:
        return [
            f"{prefix}: {owner} deduccion_requires_adquisicion_before expression {expression!r} is malformed; "
            'expected deduccion_requires_adquisicion_before(["amount_casilla_id", '
            '"acquisition_date_casilla_id", "construction_date_casilla_id", "cutoff_iso"])',
        ]
    tokens = _parse_predicate_casilla_id_tokens(match.group("ids"))
    failures: list[str] = []
    if len(tokens) != 4:
        failures.append(
            f"{prefix}: {owner} deduccion_requires_adquisicion_before must name exactly four tokens "
            f"(amount casilla id, acquisition-date casilla id, construction-date casilla id, cutoff ISO date), "
            f"got {len(tokens)}: {tokens!r}",
        )
        return failures
    amount_id, acquisition_date_id, construction_date_id, cutoff = tokens
    if amount_id not in casillas:
        failures.append(
            f"{prefix}: {owner} deduccion_requires_adquisicion_before references unknown amount casilla {amount_id!r}",
        )
    for role, date_id in (("acquisition-date", acquisition_date_id), ("construction-date", construction_date_id)):
        if date_id not in casillas:
            failures.append(
                f"{prefix}: {owner} deduccion_requires_adquisicion_before references unknown "
                f"{role} casilla {date_id!r}",
            )
            continue
        casilla = casilla_by_id.get(date_id)
        if casilla is not None and casilla.data_type != "text":
            failures.append(
                f"{prefix}: {owner} deduccion_requires_adquisicion_before {role} casilla {date_id!r} "
                "must have data_type 'text'",
            )
    if not _ISO_DATE_LITERAL.match(cutoff):
        failures.append(
            f"{prefix}: {owner} deduccion_requires_adquisicion_before cutoff {cutoff!r} "
            "must be an ISO date literal (YYYY-MM-DD)",
        )
    return failures


def _profile_flag_enabled_predicate_failures(prefix: str, owner: str, expression: str) -> list[str]:
    """Return failures for a malformed ``profile_flag_enabled`` advisory."""
    match = _PROFILE_FLAG_ENABLED_PREDICATE.match(expression.strip())
    if match is None:
        return [
            f"{prefix}: {owner} profile_flag_enabled expression {expression!r} is malformed; expected "
            'profile_flag_enabled("profile_field_name")',
        ]
    field = match.group("field")
    if field not in KNOWN_PROFILE_FLAG_ADVISORY_FIELDS:
        return [
            f"{prefix}: {owner} profile_flag_enabled references unsupported profile field {field!r}; "
            f"supported fields: {sorted(KNOWN_PROFILE_FLAG_ADVISORY_FIELDS)!r}",
        ]
    return []


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
