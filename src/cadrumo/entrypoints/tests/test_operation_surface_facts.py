"""The recorded surface facts of every registered operation, held to the live registry.

A narrower MCP surface is derived from two facts recorded for each operation:
whether it can change the profile's records and whether it reaches the
network. This census makes the record and the live production registry answer
for each other: an operation with no recorded facts, facts for an operation
that is not registered, and a fact that contradicts what the definition
declares are each a finding.

A definition declares its permitted effects and its owned resources, so both
facts are held to those declarations where a declaration speaks. A definition
that permits more than its executor does, and one recorded as able to commit
although it declares no committed effect, are named here, each with the reason.

Like the exposure census beside it, this file passes on membership and shape
and never on a count.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from ...application.operations.capabilities import OperationOwnedResource
from ...application.operations.mcp_surface_facts import (
    OPERATION_SURFACE_FACTS,
    OperationSurfaceFacts,
    operation_surface_facts,
)
from ...application.operations.registry import OperationPublicDefinitionRegistrationV1
from ...core.operations import OperationEffect
from .test_operation_catalogue import _registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_COMMITTED_EFFECTS = frozenset({OperationEffect.UPDATED, OperationEffect.PARTIAL})

_PERMITS_MORE_THAN_IT_DOES: Mapping[str, str] = {
    "auth.local-read": "reads stored authentication state under an update capability set",
    "ledger.bienes_inversion.list": "lists the register under its family's update capability set",
    "ledger.inventory.list": "lists the register under its family's update capability set",
    "ledger.prorrata.list": "lists the register under its family's update capability set",
}
"""Definitions that permit a committed effect although the operation only reads.

Each is recorded as not changing records, from reading its executor. An entry
leaves this mapping when its definition stops permitting the effect; nothing
is added without reading the executor."""


_HOLDS_A_COMMIT_DOOR_WITHOUT_A_DECLARED_EFFECT: Mapping[str, str] = {
    definition_id: "its resolver holds the commit action for every submission, so a read-only surface refuses it"
    for definition_id in (
        "modelo.edit.apply_prerequisite",
        "modelo.edit.preflight",
        "modelo.edit.renew",
        "modelo.work.casilla_help",
        "modelo.work.form",
        "workbench.generation",
    )
}
"""Definitions recorded as able to commit although they permit no committed effect.

Reading did not settle that nothing is stored, so each is recorded under the
wider answer. An entry leaves this mapping when its resolver stops holding the
commit action, and the operation is then recorded as a read."""


def _registrations() -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    return _registry().public_registrations


def test_every_registered_operation_has_exactly_one_record_of_its_surface_facts() -> None:
    """The record and the registry name the same operations, both directions."""
    registered = {item.contract.definition_id for item in _registrations()}
    recorded = [facts.definition_id for facts in OPERATION_SURFACE_FACTS]
    assert len(set(recorded)) == len(recorded)
    unrecorded = sorted(registered - set(recorded))
    unregistered = sorted(set(recorded) - registered)
    assert not unrecorded, f"registered operations with no recorded surface facts: {unrecorded}"
    assert not unregistered, f"recorded surface facts for operations that are not registered: {unregistered}"


def _change_finding(
    facts: OperationSurfaceFacts,
    *,
    permitted: frozenset[OperationEffect],
    permits_more: bool,
    holds_a_commit_door: bool = False,
) -> str | None:
    """Say how the recorded change fact contradicts what the definition permits, if it does."""
    permits_commit = not permitted.isdisjoint(_COMMITTED_EFFECTS)
    if facts.changes_records:
        if permits_more:
            return "is recorded as changing records and also as permitting more than it does"
        if permits_commit:
            return "permits a committed effect and must leave the named commit doors" if holds_a_commit_door else None
        return None if holds_a_commit_door else "is recorded as changing records but permits no committed effect"
    if holds_a_commit_door:
        return "is recorded as not changing records and also as holding a commit door"
    if permits_commit and not permits_more:
        return "is recorded as not changing records but permits a committed effect"
    if permits_more and not permits_commit:
        return "no longer permits a committed effect and must leave the named exceptions"
    return None


def test_the_recorded_change_fact_agrees_with_every_definitions_permitted_effects() -> None:
    """A read may not permit a committed effect unless it is named as permitting more than it does."""
    registered = {item.contract.definition_id for item in _registrations()}
    unknown = sorted(set(_PERMITS_MORE_THAN_IT_DOES) - registered)
    assert not unknown, f"named as permitting more than it does, but not registered: {unknown}"
    unexplained = sorted(key for key, reason in _PERMITS_MORE_THAN_IT_DOES.items() if not reason.strip())
    assert not unexplained, f"named as permitting more than it does, with no reason: {unexplained}"
    unknown_doors = sorted(set(_HOLDS_A_COMMIT_DOOR_WITHOUT_A_DECLARED_EFFECT) - registered)
    assert not unknown_doors, f"named as holding a commit door, but not registered: {unknown_doors}"
    assert all(reason.strip() for reason in _HOLDS_A_COMMIT_DOOR_WITHOUT_A_DECLARED_EFFECT.values())
    findings = {
        item.contract.definition_id: finding
        for item in _registrations()
        if (
            finding := _change_finding(
                operation_surface_facts(item.contract.definition_id),
                permitted=item.contract.permitted_effects,
                permits_more=item.contract.definition_id in _PERMITS_MORE_THAN_IT_DOES,
                holds_a_commit_door=item.contract.definition_id in _HOLDS_A_COMMIT_DOOR_WITHOUT_A_DECLARED_EFFECT,
            )
        )
        is not None
    }
    assert not findings, f"recorded change facts that contradict the definition: {findings}"


def test_the_change_rule_detects_each_contradiction() -> None:
    """The rule fails an unnamed over-declaration, a stale exception and an unbacked change."""
    read = OperationSurfaceFacts(definition_id="domain.thing.list", changes_records=False, reaches_network=False)
    write = OperationSurfaceFacts(definition_id="domain.thing.set", changes_records=True, reaches_network=False)
    reading = frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    updating = reading | {OperationEffect.UPDATED}
    partial = reading | {OperationEffect.PARTIAL}

    assert _change_finding(read, permitted=reading, permits_more=False) is None
    assert _change_finding(read, permitted=updating, permits_more=True) is None
    assert _change_finding(write, permitted=updating, permits_more=False) is None
    assert _change_finding(write, permitted=partial, permits_more=False) is None
    assert _change_finding(read, permitted=updating, permits_more=False) is not None
    assert _change_finding(read, permitted=partial, permits_more=False) is not None
    assert _change_finding(read, permitted=reading, permits_more=True) is not None
    assert _change_finding(write, permitted=reading, permits_more=False) is not None
    assert _change_finding(write, permitted=updating, permits_more=True) is not None
    assert _change_finding(write, permitted=reading, permits_more=False, holds_a_commit_door=True) is None
    assert _change_finding(write, permitted=updating, permits_more=False, holds_a_commit_door=True) is not None
    assert _change_finding(read, permitted=reading, permits_more=False, holds_a_commit_door=True) is not None


def test_every_definition_that_owns_a_process_is_recorded_as_reaching_the_network() -> None:
    """The one resource a definition declares for a remote read is its browser process."""
    unrecorded = sorted(
        item.contract.definition_id
        for item in _registrations()
        if OperationOwnedResource.PROCESS in item.contract.owned_resources
        and not operation_surface_facts(item.contract.definition_id).reaches_network
    )
    assert not unrecorded, f"definitions that own a browser process but are recorded as local: {unrecorded}"
