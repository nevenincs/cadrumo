"""A branch on a form asks the registry which form holds the role, and a model decides only in scope."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import pytest
from pydantic import AfterValidator, BaseModel, ValidationError

from cadrumo.core.errors.hierarchy import InternalInvariantError

from ..authority import bundled_indexed_authority
from ..form_codes import (
    differs_from_role,
    form_for_role,
    form_for_role_in_scope,
    form_role_validator,
    resolve_form_codes,
)
from ..governed_fact_scope import governed_facts_in_scope, validating_governed_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MODELOS = Path(__file__).resolve().parents[4] / "_data" / "registry" / "aeat" / "modelos"


def _operation():
    return bundled_indexed_authority().operation()


def test_every_routed_form_is_a_form_the_registry_declares() -> None:
    with _operation() as operation:
        entries = resolve_form_codes("modelo-role-routing", authority=operation).entries
    routed = {form for value in entries.values() for form in value.split(",")}
    declared = {path.name for path in _MODELOS.iterdir() if path.is_dir()}
    assert routed
    assert routed <= declared


def test_a_role_outside_every_scope_has_no_answer_and_a_strict_read_refuses() -> None:
    assert governed_facts_in_scope() is None
    assert form_for_role_in_scope("iva.periodic") is None
    assert differs_from_role("000", "iva.periodic") is False
    with pytest.raises(InternalInvariantError):
        form_for_role("iva.periodic")


def test_inside_a_scope_a_role_tells_its_form_from_another() -> None:
    with _operation() as operation, validating_governed_facts(operation):
        holder = form_for_role("iva.periodic")
        assert form_for_role_in_scope("iva.periodic") == holder
        assert differs_from_role(holder, "iva.periodic") is False
        assert differs_from_role(form_for_role("renta.annual"), "iva.periodic") is True


class _Selector(BaseModel):
    modelo: Annotated[str, AfterValidator(form_role_validator("renta.annual"))]


def test_a_role_validator_enforces_in_scope_and_stays_out_of_a_client() -> None:
    with _operation() as operation, validating_governed_facts(operation):
        holder = form_for_role("renta.annual")
        other = form_for_role("iva.periodic")
        assert _Selector(modelo=holder).modelo == holder
        with pytest.raises(ValidationError):
            _Selector(modelo=other)
    assert _Selector(modelo=other).modelo == other
