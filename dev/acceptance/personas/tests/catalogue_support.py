"""Catalogue personas read under the published authority's envelope, for the journey's unit tests."""

from __future__ import annotations

from dataclasses import replace
from functools import cache

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.tests.persona_materialisation import year_envelope
from cadrumo.tests.personas import (
    ExpectedDeadline,
    ExpectedObligation,
    ExpectedValue,
    Persona,
    YearEnvelope,
    read_persona,
)


@cache
def envelope() -> YearEnvelope:
    """The registry's supported filing-year envelope."""
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation)


@cache
def persona(persona_id: str) -> Persona:
    """One catalogue persona under the registry's envelope."""
    return read_persona(persona_id, envelope=envelope())


def value_with_casillas() -> ExpectedValue:
    """A catalogue value that states casillas alone: no role, no not-sourced figure and no refusal.

    The persona may also state the value's figures under registry roles; those are
    dropped here so the tests read casillas only, whatever the catalogue re-keys.
    """
    sample = next(
        value
        for value in persona("autonomo-fontanero").expectations.values
        if value.casillas and value.refusal is None and value.grounding != "unverified"
    )
    return replace(sample, roles=(), not_sourced=())


def obligation(applicable: bool) -> ExpectedObligation:
    """A catalogue obligation the fontanero is, or is not, liable for, with no calendar advice."""
    return next(
        item
        for item in persona("autonomo-fontanero").expectations.obligations
        if item.applicable is applicable and item.calendar_advice is None and item.grounding != "unverified"
    )


def deadline() -> ExpectedDeadline:
    """A catalogue deadline the fontanero states."""
    return next(item for item in persona("autonomo-fontanero").expectations.deadlines if item.grounding != "unverified")
