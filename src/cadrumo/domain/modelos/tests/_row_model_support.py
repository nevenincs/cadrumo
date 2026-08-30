from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import TypedDict

import pytest
from pydantic import ValidationError

from ....core.casilla_id import CasillaId

type RowModelCall = Callable[[], object]


type RevisionInputSnapshot = dict[str, str]


@dataclass(frozen=True)
class _ValidationErrorCase:
    case_id: str
    build: RowModelCall
    match: str | None = None


@dataclass(frozen=True)
class _BooleanCase:
    case_id: str
    nif: str
    pais: str
    expected: bool


@dataclass(frozen=True)
class _CountryContextCase:
    case_id: str
    call: Callable[[], None]
    match: str | None = None
    must_contain: str | None = None


class _BaseRevisionIdKwargs(TypedDict):
    work_unit_id: str
    input_values_by_casilla_id: RevisionInputSnapshot
    binding_overrides: dict[str, str]
    casilla_values: dict[CasillaId, Decimal]


def _assert_validation_error(case: _ValidationErrorCase) -> None:
    if case.match is None:
        with pytest.raises(ValidationError):
            case.build()
        return
    with pytest.raises(ValidationError, match=case.match):
        case.build()
