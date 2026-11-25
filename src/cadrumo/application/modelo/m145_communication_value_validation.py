"""Registry-defined value shapes and constraints for Modelo 145 communications."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from decimal import InvalidOperation

from ...core.decimal.coercion import coerce_decimal_strict
from ...core.errors.error_codes import resolve_error_message
from ...core.identity.documents import IdentityError
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.calculations.registry.tax_id_runtime import validate_runtime_spanish_tax_id

_FOUR_DIGIT_YEAR_PATTERN = re.compile(r"^\d{4}$")
_ISO_DATE_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
_AEAT_DATE_PATTERN = re.compile(r"^(0[1-9]|[12]\d|3[01])(0[1-9]|1[0-2])\d{4}$")
M145_COMPLEMENTARY_PAGE_ROLE = "modelo_145_pagina_complementaria"


def _nif_value_shape_issue(value: str) -> str | None:
    try:
        validate_runtime_spanish_tax_id(value)
    except IdentityError as exc:
        return resolve_error_message(exc)
    return None


def _year_value_shape_issue(value: str) -> str | None:
    if not _FOUR_DIGIT_YEAR_PATTERN.fullmatch(value):
        return "value must be a four-digit year"
    return None


def _date_value_shape_issue(value: str) -> str | None:
    if not (_ISO_DATE_PATTERN.fullmatch(value) or _AEAT_DATE_PATTERN.fullmatch(value)):
        return "value must be ISO yyyy-mm-dd or AEAT ddmmaaaa"
    return None


def _integer_value_shape_issue(value: str) -> str | None:
    if not value.isdecimal():
        return "value must contain only decimal digits"
    return None


def _money_value_shape_issue(value: str) -> str | None:
    try:
        # DECIMAL-TEXT-RATIONALE-M145-SHAPE-PREDICATE: inverted use --
        # the result is discarded and only the raise is read, so this
        # asks "is this parseable at all", not "what number is it".
        # Routing it through the strict grammar would make the guard
        # REFUSE more, which is the shape the rule-3 declarante-selector
        # and Renta-WEB-oracle exemptions record.
        coerce_decimal_strict(value)
    except (InvalidOperation, ValueError) as exc:
        return f"value is not a valid decimal amount: {type(exc).__name__}"
    return None


_VALUE_SHAPE_VALIDATORS: Mapping[str, Callable[[str], str | None]] = {
    "nif": _nif_value_shape_issue,
    "year": _year_value_shape_issue,
    "date": _date_value_shape_issue,
    "integer": _integer_value_shape_issue,
    "money": _money_value_shape_issue,
}


def m145_value_shape_issue(casilla: CasillaDefinition, value: str) -> str | None:
    """Return the registry field's primitive shape refusal, preserving optional blanks."""
    stripped = value.strip()
    if not stripped:
        # Optional text can carry an explicit blank wire token (DR145 page 2).
        # Required fields and role-specific value constraints are checked separately.
        if casilla.data_type == "text" and not casilla.required:
            return None
        return "value must not be blank"
    validator = _VALUE_SHAPE_VALIDATORS.get(casilla.data_type)
    return None if validator is None else validator(stripped)


def m145_constraint_issue(casilla: CasillaDefinition, value: str) -> str | None:
    """Check the declared text and numeric constraints, preserving the page marker's wire token."""
    if casilla.constraints is None:
        return None
    if casilla.semantic_role == M145_COMPLEMENTARY_PAGE_ROLE and casilla.data_type == "text" and not casilla.required:
        # DR145 v2.0 row 2 is one byte: blanco or "C". The optional marker's
        # enum constrains its present token; an explicit ordinary-page blank
        # has the same meaning as absence. Keep the raw wire token here so
        # tabs, multiple spaces and padded "C" cannot pass and fail at export.
        if value in {"", " "}:
            return None
    else:
        value = value.strip()
    text_issue = casilla.constraints.violates_text(value)
    if text_issue is not None:
        return text_issue
    if casilla.data_type not in {"integer", "money"}:
        return None
    try:
        # DECIMAL-TEXT-RATIONALE-M145-CONSTRAINT-RESIDUAL: declared as a
        # residual, not as clean. Unlike its shape-predicate sibling above this
        # one READS the parsed magnitude, and the value is operator-written, so
        # a Spanish ``1.000`` is compared as one euro against the casilla's
        # constraint. It is bounded rather than harmless: the output is a
        # validation issue, never a declared amount, and Modelo 145 is a
        # communication to the payer that this application does not file.
        # The coherent fix belongs to the shape predicate above -- refusing the
        # ambiguous form before it reaches any comparison -- because narrowing
        # only here would turn an ambiguous value into no constraint check at
        # all, which is a silent pass rather than a refusal. That is a change to
        # what Modelo 145 accepts and needs its own decision.
        numeric = coerce_decimal_strict(value)
    except (InvalidOperation, ValueError):
        return None
    return casilla.constraints.violates(numeric)
