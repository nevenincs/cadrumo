"""Authoring-time validators for the ``verification_predicates`` DSL operators.

Extracted from :mod:`~domain.calculations.registry._validate_surfaces` (which
stayed the single home for every registry surface validator until its own growth
pushed it past its reviewed complexity baseline). This module owns exactly the
per-operator arity/shape validators for the verification-predicate expression
DSL; the public entry point that walks a revision's declared predicates and
dispatches into these helpers,
:func:`~domain.calculations.registry._validate_surfaces.validate_verification_expectation_section`,
stays in the parent module and imports from here.

Each helper rejects a malformed arity, an unknown casilla reference, or an
unsupported literal at registry-load time rather than letting the runtime
evaluator's defensive bad-arity branch silently hold (or, for the ADVISORY
form, silently never fire) — see
:mod:`~application.modelo._verification_actions` for the runtime
counterpart these gates keep honest.

See Also:
    :data:`~domain.calculations.registry.KNOWN_VERIFICATION_PREDICATE_OPERATORS`
        Canonical operator set shared by the validator and runtime evaluator.
    :func:`~domain.calculations.registry._validate_surfaces.validate_verification_expectation_section`
        Parent dispatcher for revision-level reference closure.
    :func:`~application.modelo._verification_actions._evaluate_predicate_expression`
        Runtime evaluator these authoring-time shape checks keep in sync.
"""

from __future__ import annotations

import re as _re
from collections.abc import Mapping

from ._ids import CasillaId
from ._schema_scalars import registry_scalar_value_type
from ._schema_surfaces import CasillaDefinition
from ._schema_verification import KNOWN_PROFILE_FLAG_ADVISORY_FIELDS

__all__ = [
    "_CASILLA_LIST_OPERATORS",
    "_casilla_equals_implies_diverges_predicate_failures",
    "_casilla_equals_implies_nonzero_predicate_failures",
    "_casilla_equals_implies_profile_flag_predicate_failures",
    "_casilla_list_predicate_failures",
    "_deduccion_requires_adquisicion_before_predicate_failures",
    "_predicate_operator_name",
    "_profile_flag_enabled_predicate_failures",
    "_roll_forward_balances_predicate_arity_failures",
]


# The known predicate operator set was previously a module-level constant
# here that mirrored the runtime evaluator's regex set. Drift between the
# two was a silent-pass hazard. The canonical set now lives at
# cadrumo.domain.calculations.registry._schema_verification.KNOWN_VERIFICATION_PREDICATE_OPERATORS
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
# cadrumo.application.modelo._verification_actions._PREDICATE_ROLL_FORWARD_BALANCES;
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
    elif antecedent is not None and registry_scalar_value_type(antecedent.data_type) != "str":
        failures.append(
            f"{prefix}: {owner} casilla_equals_implies_nonzero antecedent casilla {antecedent_id!r} "
            f"must be a text-family casilla (scalar family 'str'), not data_type {antecedent.data_type!r}",
        )
    if not literal:
        failures.append(f"{prefix}: {owner} casilla_equals_implies_nonzero literal must be non-empty")
    consequent = casilla_by_id.get(consequent_id)
    if consequent_id not in casillas:
        failures.append(
            f"{prefix}: {owner} casilla_equals_implies_nonzero references unknown consequent casilla {consequent_id!r}",
        )
    elif consequent is not None and registry_scalar_value_type(consequent.data_type) == "str":
        failures.append(
            f"{prefix}: {owner} casilla_equals_implies_nonzero consequent casilla {consequent_id!r} "
            f"must be a numeric casilla, not a text-family one; declares data_type {consequent.data_type!r}",
        )
    return failures


# casilla_equals_implies_profile_flag(["antecedent_casilla_id", "literal",
# "profile_field"]) — categorical-antecedent / profile-state-consequent
# conditional advisory. Unlike casilla_equals_implies_nonzero, the third
# token is a TaxpayerProfile field/property name, not a casilla id, so it
# cannot route through the generic casilla-list validators. Mirrors
# profile_flag_enabled's allowlist check (KNOWN_PROFILE_FLAG_ADVISORY_FIELDS)
# combined with casilla_equals_implies_nonzero's antecedent shape: this
# authoring-time gate rejects a malformed arity, an unknown/non-text
# antecedent casilla, an empty literal, or an unsupported profile field at
# registry load, rather than letting the runtime evaluator's defensive
# bad-arity / unsupported-field branch (returns False — never fires)
# silently mask a typo.
_CASILLA_EQUALS_IMPLIES_PROFILE_FLAG_PREDICATE = _re.compile(
    r"^casilla_equals_implies_profile_flag\(\[(?P<ids>[^\]]*)\]\)$",
)


def _casilla_equals_implies_profile_flag_predicate_failures(
    prefix: str,
    owner: str,
    expression: str,
    casillas: set[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
) -> list[str]:
    """Return failures for a malformed ``casilla_equals_implies_profile_flag`` predicate."""
    match = _CASILLA_EQUALS_IMPLIES_PROFILE_FLAG_PREDICATE.match(expression.strip())
    if match is None:
        return [
            f"{prefix}: {owner} casilla_equals_implies_profile_flag expression {expression!r} is malformed; "
            'expected casilla_equals_implies_profile_flag(["antecedent_casilla_id", "literal", "profile_field"])',
        ]
    tokens = _parse_predicate_casilla_id_tokens(match.group("ids"))
    failures: list[str] = []
    if len(tokens) != 3:
        failures.append(
            f"{prefix}: {owner} casilla_equals_implies_profile_flag must name exactly three tokens "
            f"(antecedent casilla id, literal, profile field), got {len(tokens)}: {tokens!r}",
        )
        return failures
    antecedent_id, literal, field = tokens
    antecedent = casilla_by_id.get(antecedent_id)
    if antecedent_id not in casillas:
        failures.append(
            f"{prefix}: {owner} casilla_equals_implies_profile_flag references unknown "
            f"antecedent casilla {antecedent_id!r}",
        )
    elif antecedent is not None and registry_scalar_value_type(antecedent.data_type) != "str":
        failures.append(
            f"{prefix}: {owner} casilla_equals_implies_profile_flag antecedent casilla {antecedent_id!r} "
            f"must be a text-family casilla (scalar family 'str'), not data_type {antecedent.data_type!r}",
        )
    if not literal:
        failures.append(f"{prefix}: {owner} casilla_equals_implies_profile_flag literal must be non-empty")
    if field not in KNOWN_PROFILE_FLAG_ADVISORY_FIELDS:
        failures.append(
            f"{prefix}: {owner} casilla_equals_implies_profile_flag references unsupported profile field "
            f"{field!r}; supported fields: {sorted(KNOWN_PROFILE_FLAG_ADVISORY_FIELDS)!r}",
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
    elif antecedent is not None and registry_scalar_value_type(antecedent.data_type) != "str":
        failures.append(
            f"{prefix}: {owner} casilla_equals_implies_diverges antecedent casilla {antecedent_id!r} "
            f"must be a text-family casilla (scalar family 'str'), not data_type {antecedent.data_type!r}",
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
        elif consequent is not None and registry_scalar_value_type(consequent.data_type) == "str":
            failures.append(
                f"{prefix}: {owner} casilla_equals_implies_diverges {role} casilla {consequent_id!r} "
                f"must be a numeric casilla, not a text-family one; declares data_type {consequent.data_type!r}",
            )
    return failures


# deduccion_requires_adquisicion_before(["amount_id", "acquisition_date_id",
# "construction_date_id", "cutoff_iso"]) — eligibility-conditional advisory. Mixes three
# casilla ids with a trailing ISO-date literal, so it cannot route through the generic
# _casilla_list_predicate_failures (which validates every bracketed token as a casilla
# id). This authoring-time gate rejects a malformed arity, an unknown amount/date
# casilla, a date casilla whose family cannot carry a parseable date, or an unparseable
# cutoff at registry load rather than letting the runtime evaluator's defensive
# bad-arity / unparseable-cutoff branch (returns False — never fires) silently mask a typo.
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
        if casilla is not None and registry_scalar_value_type(casilla.data_type) not in {"str", "date"}:
            failures.append(
                f"{prefix}: {owner} deduccion_requires_adquisicion_before {role} casilla {date_id!r} "
                f"must carry a parseable date (scalar family 'str' or 'date'), not data_type {casilla.data_type!r}",
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
