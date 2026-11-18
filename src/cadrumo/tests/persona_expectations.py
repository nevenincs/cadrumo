"""Parse a persona's expected obligations, deadlines, values and refusals."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final, Literal, cast

from .persona_identities import _Roles
from .persona_toml import (
    _amount_map,
    _choice,
    _date,
    _keys,
    _optional_string,
    _string,
    _string_map,
    _strings,
    _Table,
    _tables,
)
from .persona_types import (
    Expectations,
    ExpectedDeadline,
    ExpectedObligation,
    ExpectedValue,
    PersonaCatalogueError,
    YearEnvelope,
    YearToken,
    _fail,
)

#: An application error or refusal code, the token a refused operation settles with.
_ERROR_CODE: Final = re.compile(r"(?:ERROR|REFUSED)(?:_[A-Z0-9]+)+")


#: A calendar coverage advice the overview gives for a modelo it cannot place in a window.
_CALENDAR_ADVICE: Final = ("applicable_window_missing", "applicability_undetermined")


_GROUNDING: tuple[Literal["verified", "cited", "unverified"], ...] = ("verified", "cited", "unverified")


_REFUSAL_STAGES: tuple[Literal["calculate", "verify", "export"], ...] = ("calculate", "verify", "export")


def _expectations(document: _Table, where: str, persona_id: str, roles: _Roles) -> Expectations:
    _keys(
        document,
        where,
        required=frozenset({"format", "persona"}),
        optional=frozenset({"obligations", "deadlines", "values"}),
    )
    if document["persona"] != persona_id:
        raise _fail(where, "persona differs from its directory")
    obligations: list[ExpectedObligation] = []
    for index, table in enumerate(_tables(document.get("obligations"), where)):
        here = f"{where} obligations[{index}]"
        _keys(
            table,
            here,
            required=frozenset({"modelo", "periods", "year", "applicable", "reason", "legal_ref", "grounding"}),
            optional=frozenset({"calendar_advice"}),
        )
        applicable = table["applicable"]
        if not isinstance(applicable, bool) and applicable != "unknown":
            raise _fail(here, 'applicable must be a boolean or "unknown"')
        calendar_advice = _optional_string(table, "calendar_advice", here)
        if calendar_advice is not None:
            calendar_advice = _choice(calendar_advice, _CALENDAR_ADVICE, f"{here}.calendar_advice")
            if applicable is not True:
                raise _fail(here, "a calendar advice stands in for the window row of an owed modelo")
        obligations.append(
            ExpectedObligation(
                modelo=_string(table, "modelo", here),
                periods=_strings(table, "periods", here),
                year=YearToken.parse(table["year"], where=f"{here}.year"),
                applicable=cast(bool | Literal["unknown"], applicable),
                reason=_string(table, "reason", here),
                legal_ref=_strings(table, "legal_ref", here),
                grounding=_choice(_string(table, "grounding", here), _GROUNDING, here),
                calendar_advice=calendar_advice,
            )
        )
    deadlines: list[ExpectedDeadline] = []
    for index, table in enumerate(_tables(document.get("deadlines"), where)):
        here = f"{where} deadlines[{index}]"
        _keys(
            table,
            here,
            required=frozenset({"modelo", "period", "year", "statutory_end"}),
            optional=frozenset({"note", "legal_ref", "grounding"}),
        )
        deadlines.append(
            ExpectedDeadline(
                modelo=_string(table, "modelo", here),
                period=_string(table, "period", here),
                year=YearToken.parse(table["year"], where=f"{here}.year"),
                statutory_end=_date(table["statutory_end"], f"{here}.statutory_end", biographical=False),
                note=_optional_string(table, "note", here),
                legal_ref=_strings(table, "legal_ref", here) if "legal_ref" in table else (),
                grounding=_choice(_string(table, "grounding", here), _GROUNDING, here)
                if "grounding" in table
                else None,
            )
        )
    values: list[ExpectedValue] = []
    for index, table in enumerate(_tables(document.get("values"), where)):
        here = f"{where} values[{index}]"
        _keys(
            table,
            here,
            required=frozenset({"modelo", "period", "year", "legal_ref", "grounding"}),
            optional=frozenset(
                {
                    "counterparty",
                    "casillas",
                    "concepts",
                    "parameters",
                    "derivation",
                    "reason",
                    "refusal",
                    "refusal_stage",
                    "not_sourced",
                    "governed_by",
                    "roles",
                }
            ),
        )
        grounding = _choice(_string(table, "grounding", here), _GROUNDING, here)
        governed_by = _optional_string(table, "governed_by", here)
        legal_ref = _strings(table, "legal_ref", here)
        if governed_by is not None and governed_by not in legal_ref:
            raise _fail(here, "the provision a value is governed by is one of its legal references")
        reason = _optional_string(table, "reason", here)
        if grounding == "unverified" and reason is None:
            raise _fail(here, "an unverified expectation says what is missing in its reason")
        refusal = _optional_string(table, "refusal", here)
        if refusal is not None:
            if _ERROR_CODE.fullmatch(refusal) is None:
                raise _fail(here, "a refusal names the application error code")
            if reason is None:
                raise _fail(here, "a refusal says in its reason why the application refuses")
        refusal_stage = _choice(_optional_string(table, "refusal_stage", here) or "calculate", _REFUSAL_STAGES, here)
        if refusal is None and "refusal_stage" in table:
            raise _fail(here, "a refusal stage belongs to a stated refusal")
        casillas = _string_map(table, "casillas", here)
        not_sourced = _string_map(table, "not_sourced", here)
        if not_sourced:
            if reason is None:
                raise _fail(here, "a not-sourced casilla says in its reason what source is missing")
            if refusal is not None:
                raise _fail(here, "a refused period sources no casilla, so it states none as not sourced")
            if {casilla for casilla, _amount in not_sourced} & {casilla for casilla, _amount in casillas}:
                raise _fail(here, "a casilla is either compared or stated as not sourced")
        values.append(
            ExpectedValue(
                modelo=_string(table, "modelo", here),
                period=_string(table, "period", here),
                year=YearToken.parse(table["year"], where=f"{here}.year"),
                counterparty=roles(table["counterparty"], here) if "counterparty" in table else None,
                casillas=casillas,
                concepts=_string_map(table, "concepts", here),
                parameters=_string_map(table, "parameters", here),
                derivation=_optional_string(table, "derivation", here),
                legal_ref=legal_ref,
                grounding=grounding,
                reason=reason,
                refusal=refusal,
                refusal_stage=refusal_stage,
                not_sourced=not_sourced,
                governed_by=governed_by,
                roles=_amount_map(table, "roles", here),
            )
        )
    return Expectations(obligations=tuple(obligations), deadlines=tuple(deadlines), values=tuple(values))


def _value_key(value: ExpectedValue) -> tuple[str, str, str, str | None]:
    return (value.modelo, value.period, str(value.year), value.counterparty)


def per_period_modelos(obligations: Iterable[ExpectedObligation]) -> frozenset[str]:
    """The modelos whose obligations of one year state different applicability for different periods.

    An overview explanation states one verdict per modelo and year, so these
    are asserted per period from the calendar, suppressed obligations shown.
    """
    stated: dict[str, set[bool | str]] = {}
    for item in obligations:
        stated.setdefault(item.modelo, set()).add(item.applicable)
    return frozenset(modelo for modelo, held in stated.items() if len(held) > 1)


def values_in_force(values: tuple[ExpectedValue, ...], envelope: YearEnvelope) -> tuple[tuple[int, ExpectedValue], ...]:
    """Each stated value with its resolved year, as the law of that year holds it.

    Values limited to a provision (``governed_by``) replace every plain value of their
    modelo, period, year and counterparty in a year the provision governs, and are dropped
    in the other years. Values of one key following two different provisions in the same
    year are refused, since the catalogue could not say which law the figures follow.
    """
    resolved: list[tuple[int, ExpectedValue]] = []
    for value in values:
        year = value.year.resolve(envelope)
        governing = {
            other.governed_by
            for other in values
            if other.governed_by is not None
            and _value_key(other) == _value_key(value)
            and envelope.governs(other.governed_by, year)
        }
        if len(governing) > 1:
            raise PersonaCatalogueError(
                f"{value.modelo} {value.period} {value.year}: values follow {sorted(governing)} in the same year"
            )
        if value.governed_by is None if not governing else value.governed_by in governing:
            resolved.append((year, value))
    return tuple(resolved)


__all__ = [
    "per_period_modelos",
    "values_in_force",
]
