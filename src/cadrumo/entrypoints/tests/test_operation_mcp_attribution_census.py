"""Every request field that names who acted is accounted for, on every registered operation.

An agent's execution must record the label derived from its session, never a
name the request typed, and every registered operation is open to an agent. A
request field that attributes an act (an actor, an author, a reviewer, an
asserting party) is found by name at any depth in the request model of every
registered definition. Each such definition is then required to appear in
exactly one of two explicit tables: the definitions proven to record the
session-derived label for an agent, each naming the test that proves it, and
the fields that are not attribution, each with its reason.

A definition that gains such a field and is in neither table fails here, so no
operation can leave a caller-typed attribution behind. The census reads
request fields. A write that records a label with no request field to carry
it is proven beside the others, in the tests that run the real executor under
a session host.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from functools import cache
from typing import Annotated, TypeAliasType, get_args, get_origin

import pytest
from pydantic import BaseModel

from .test_operation_catalogue import _registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _unwrapped(annotation: object) -> object:
    """Strip a type alias or an ``Annotated`` wrapper to the type beneath it."""
    while True:
        if isinstance(annotation, TypeAliasType):
            annotation = annotation.__value__
        elif get_origin(annotation) is Annotated:
            annotation = get_args(annotation)[0]
        else:
            return annotation


@cache
def _public_models(definition_id: str) -> tuple[type[BaseModel], type[BaseModel] | None]:
    """The registered request model and, when one is declared, the registered result model."""
    registry = _registry()
    contract = registry.lookup_public_contract(definition_id)
    request = registry.lookup_public_schema_binding(contract.request_schema).model_type
    result = (
        None
        if contract.result_schema is None
        else registry.lookup_public_schema_binding(contract.result_schema).model_type
    )
    return request, result


_ATTRIBUTION_NAMES: frozenset[str] = frozenset(
    {
        "actor",
        "actor_ref",
        "approved_by",
        "asserted_by",
        "author",
        "captured_by",
        "classified_by",
        "confirmed_by",
        "created_by",
        "decided_by",
        "filed_by",
        "operator",
        "performed_by",
        "recorded_by",
        "reviewed_by",
        "signed_by",
        "submitted_by",
        "verified_by",
    }
)
"""Field names read as naming who acted. A name ending in ``_by`` is read the same way unless listed below."""

_NOT_ATTRIBUTION_SUFFIX_NAMES: Mapping[str, str] = {
    "sort_by": "the sort key of a listing, not a party",
}
"""Names that end in ``_by`` and are not attribution, each with the reason."""


@dataclass(frozen=True, slots=True)
class _Proof:
    """The request fields of a definition that carry a typed attribution, and the test proving what it records."""

    fields: frozenset[str]
    module: str
    test: str


_ENTRYPOINT_TESTS = "cadrumo.entrypoints.tests"
_ACTOR_LABELS = f"{_ENTRYPOINT_TESTS}.test_operation_actor_label_by_frontend"
_CLASSIFICATION_ACTOR = f"{_ENTRYPOINT_TESTS}.test_ledger_classification_actor_by_frontend"
_ROW_MUTATION = f"{_ENTRYPOINT_TESTS}.test_ledger_row_mutation_mcp_admission"
_LOCAL_RECORDS = f"{_ENTRYPOINT_TESTS}.test_modelo_local_records_mcp_admission"
_MODELO_WORK = f"{_ENTRYPOINT_TESTS}.test_modelo_work_mcp_admission"
_PERSONS_WORK = f"{_ENTRYPOINT_TESTS}.test_ledger_persons_work_frontend_parity"
_LEDGER_WRITES = f"{_ENTRYPOINT_TESTS}.test_ledger_write_actor_by_frontend"

_ACTOR = frozenset({"actor"})

_LIFECYCLE_TEST = "test_each_lifecycle_mutation_records_the_session_and_is_put_back_by_the_operations_its_result_names"
_ATTACHMENT_TEST = "test_a_detachment_keeps_the_stored_attachment_and_attaching_it_again_puts_the_link_back"
_SPLIT_TEST = "test_a_split_records_the_session_keeps_its_parent_stored_and_is_not_undone_by_a_restore"
_REVIEW_TEST = "test_a_review_run_to_its_commit_stores_the_session_label_for_an_agent_and_the_typed_label_for_a_person"
_WORK_STEPS_TEST = (
    "test_creation_calculation_and_rename_record_the_session_label_for_an_agent_and_the_supplied_one_otherwise"
)
_LEDGER_WRITE_TEST = "test_a_ledger_write_records_the_session_label_for_an_agent_and_the_persons_label_otherwise"
_MODELO_WRITE_TEST = "test_a_modelo_write_stores_the_session_label_for_an_agent_and_the_supplied_label_for_a_person"

_RECORDS_THE_SESSION_LABEL: Mapping[str, _Proof] = {
    # One test runs each of these writes on every frontend and reads the label from the events it stored.
    **{
        definition_id: _Proof(_ACTOR, _LEDGER_WRITES, _LEDGER_WRITE_TEST)
        for definition_id in (
            "ledger.add",
            "ledger.allocate",
            "ledger.classify.single",
            "ledger.export",
            "ledger.merge",
            "ledger.remove",
            "ledger.reset",
            "ledger.update",
        )
    },
    "ledger.archive": _Proof(_ACTOR, _ROW_MUTATION, _LIFECYCLE_TEST),
    "ledger.stash": _Proof(_ACTOR, _ROW_MUTATION, _LIFECYCLE_TEST),
    "ledger.restore": _Proof(_ACTOR, _ROW_MUTATION, _LIFECYCLE_TEST),
    "ledger.exclude": _Proof(_ACTOR, _ROW_MUTATION, _LIFECYCLE_TEST),
    "ledger.attach": _Proof(_ACTOR, _ROW_MUTATION, _ATTACHMENT_TEST),
    "ledger.detach": _Proof(_ACTOR, _ROW_MUTATION, _ATTACHMENT_TEST),
    "ledger.split.manual": _Proof(_ACTOR, _ROW_MUTATION, _SPLIT_TEST),
    "ledger.classify.bulk": _Proof(
        _ACTOR, _CLASSIFICATION_ACTOR, "test_bulk_classification_records_the_session_label_for_an_agent"
    ),
    "ledger.rule.add": _Proof(_ACTOR, _CLASSIFICATION_ACTOR, "test_rule_add_records_the_session_label_for_an_agent"),
    "ledger.rule.apply": _Proof(
        _ACTOR, _CLASSIFICATION_ACTOR, "test_rule_apply_records_the_session_label_for_an_agent"
    ),
    "ledger.classify.iva-derive": _Proof(
        _ACTOR, _ACTOR_LABELS, "test_operator_iva_derivation_records_the_session_label_for_an_agent"
    ),
    "ledger.link": _Proof(_ACTOR, _ACTOR_LABELS, "test_ledger_link_records_the_session_label_for_an_agent"),
    "ledger.counterparty": _Proof(
        frozenset({"asserted_by"}),
        _ACTOR_LABELS,
        "test_counterparty_confirmation_records_the_session_label_for_an_agent",
    ),
    "ledger.inventory.closing-authority.record": _Proof(
        frozenset({"authority_record.decision.actor"}),
        _ACTOR_LABELS,
        "test_inventory_closing_authority_records_the_session_label_for_an_agent",
    ),
    # Each review is run to its commit through the real executor and store, and the label is read
    # from the events and rows the commit stored.
    "ledger.classify.review": _Proof(_ACTOR, _PERSONS_WORK, _REVIEW_TEST),
    "ledger.split.review": _Proof(_ACTOR, _PERSONS_WORK, _REVIEW_TEST),
    "modelo.reconcile.import": _Proof(
        _ACTOR, _ACTOR_LABELS, "test_reconciliation_import_records_the_session_label_for_an_agent"
    ),
    "modelo.reconcile.pull": _Proof(
        _ACTOR, _ACTOR_LABELS, "test_reconciliation_pull_records_the_session_label_for_an_agent"
    ),
    "modelo.m145.create": _Proof(
        _ACTOR,
        _LOCAL_RECORDS,
        "test_a_draft_is_a_created_record_whose_event_carries_the_session_label_for_an_agent",
    ),
    "modelo.observation.local": _Proof(
        _ACTOR,
        _LOCAL_RECORDS,
        "test_a_recorded_figure_carries_the_session_label_for_an_agent_and_never_reads_as_official",
    ),
    "modelo.work.verify": _Proof(
        _ACTOR,
        _MODELO_WORK,
        "test_verification_stores_the_session_label_for_an_agent_and_the_supplied_label_for_a_person",
    ),
    "modelo.work.calculate": _Proof(_ACTOR, _MODELO_WORK, _WORK_STEPS_TEST),
    "modelo.work.create": _Proof(_ACTOR, _MODELO_WORK, _WORK_STEPS_TEST),
    "modelo.work.rename": _Proof(_ACTOR, _MODELO_WORK, _WORK_STEPS_TEST),
    # One test runs each of these writes under an MCP and a command-line session host and reads the
    # label from the events it stored.
    **{
        definition_id: _Proof(_ACTOR, _MODELO_WORK, _MODELO_WRITE_TEST)
        for definition_id in (
            "modelo.export",
            "modelo.filing_record.import",
            "modelo.m145.export",
            "modelo.m145.mark_delivered_to_payer",
            "modelo.m145.mark_locally_completed",
            "modelo.quickfile",
            "modelo.review_package.build",
            "modelo.work.amend",
            "modelo.work.discard",
            "modelo.work.file",
        )
    },
    "modelo.work.wizard_attempt": _Proof(frozenset({"calculation.actor"}), _MODELO_WORK, _MODELO_WRITE_TEST),
    "modelo.work.m303_attestation": _Proof(
        _ACTOR, _MODELO_WORK, "test_the_modelo_390_attestation_is_captured_under_the_session_label_for_an_agent"
    ),
    "modelo.review_package.encrypt_feedback": _Proof(
        frozenset({"submitted_by"}),
        _MODELO_WORK,
        "test_review_feedback_names_the_session_label_as_its_submitter_for_an_agent",
    ),
}
"""Definitions whose request types a name, each with the test proving an agent's run stores the session label."""

_NOT_ATTRIBUTION: Mapping[str, Mapping[str, str]] = {
    "profile.history": {
        "actor": "a filter that selects the events one actor recorded; the read stores nothing",
    },
    "profile.history.timeline": {
        "actor": "a filter that selects the events one actor recorded; the read stores nothing",
    },
}
"""Attribution-named fields that do not record who acted, each with the reason."""


def _model_types(annotation: object) -> Iterator[type[BaseModel]]:
    """Yield every model a field's annotation names, through aliases, wrappers, unions and containers."""
    annotation = _unwrapped(annotation)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield annotation
        return
    for argument in getattr(annotation, "__args__", ()):
        yield from _model_types(argument)


def _members(
    model: type[BaseModel], prefix: str = "", chain: frozenset[type] = frozenset()
) -> Iterator[tuple[str, str]]:
    """Yield ``(dotted path, field name)`` of every field at any depth, models and scalars alike."""
    for declared, field in model.model_fields.items():
        name = str(declared)
        path = f"{prefix}.{name}" if prefix else name
        yield path, name
        for nested in _model_types(field.annotation):
            if nested not in chain and nested is not model:
                yield from _members(nested, path, chain | {model})


def _is_attribution_name(name: str) -> bool:
    if name in _ATTRIBUTION_NAMES:
        return True
    return name.endswith("_by") and name not in _NOT_ATTRIBUTION_SUFFIX_NAMES


def _attribution_fields(model: type[BaseModel]) -> frozenset[str]:
    """The dotted paths of the fields of a request model that read as naming who acted."""
    return frozenset(path for path, name in _members(model) if _is_attribution_name(name))


def _found_on_registered_definitions() -> dict[str, frozenset[str]]:
    found: dict[str, frozenset[str]] = {}
    for registration in _registry().public_registrations:
        definition_id = registration.contract.definition_id
        request, _result = _public_models(definition_id)
        fields = _attribution_fields(request)
        if fields:
            found[definition_id] = fields
    return found


def _accounted_for(definition_id: str) -> frozenset[str]:
    proven = _RECORDS_THE_SESSION_LABEL.get(definition_id)
    explained = _NOT_ATTRIBUTION.get(definition_id)
    accounted = frozenset[str]()
    if proven is not None:
        accounted |= proven.fields
    if explained is not None:
        accounted |= frozenset(explained)
    return accounted


def _unaccounted(found: Mapping[str, frozenset[str]]) -> dict[str, frozenset[str]]:
    """The attribution fields no table accounts for, by definition id."""
    return {
        definition_id: fields - _accounted_for(definition_id)
        for definition_id, fields in found.items()
        if fields - _accounted_for(definition_id)
    }


def test_every_attribution_field_of_a_registered_operation_is_proven_or_explained() -> None:
    """A registered definition with an attribution-named field is in a table, field for field."""
    found = _found_on_registered_definitions()
    assert found, "no registered operation carries an attribution field, so the detection found nothing to judge"

    unaccounted = {item: sorted(fields) for item, fields in _unaccounted(found).items()}
    assert not unaccounted, f"request fields naming who acted that no table accounts for: {unaccounted}"


def test_the_tables_name_only_registered_definitions_and_fields_that_are_still_declared() -> None:
    """A table entry that no longer matches a registered definition's request model is removed, not kept."""
    found = _found_on_registered_definitions()

    stale_definitions = sorted((set(_RECORDS_THE_SESSION_LABEL) | set(_NOT_ATTRIBUTION)) - set(found))
    assert not stale_definitions, (
        f"table entries for definitions that are not registered or no longer carry such a field: {stale_definitions}"
    )
    stale_fields = {
        definition_id: sorted(_accounted_for(definition_id) - found[definition_id])
        for definition_id in found
        if _accounted_for(definition_id) - found[definition_id]
    }
    assert not stale_fields, f"table fields that the request model no longer declares: {stale_fields}"


def test_no_field_is_both_proven_and_explained() -> None:
    """A field is either recorded as the session label or not attribution, never both."""
    overlapping = {
        definition_id: sorted(_RECORDS_THE_SESSION_LABEL[definition_id].fields & set(reasons))
        for definition_id, reasons in _NOT_ATTRIBUTION.items()
        if definition_id in _RECORDS_THE_SESSION_LABEL
        and _RECORDS_THE_SESSION_LABEL[definition_id].fields & set(reasons)
    }
    assert not overlapping, f"fields in both tables: {overlapping}"


def test_every_proof_names_a_test_that_exists() -> None:
    """The named test is a function of the named module, so a rename or removal is a finding."""
    missing: list[str] = []
    for definition_id, proof in _RECORDS_THE_SESSION_LABEL.items():
        candidate = getattr(importlib.import_module(proof.module), proof.test, None)
        if not callable(candidate):
            missing.append(f"{definition_id}: {proof.module}::{proof.test}")
    assert not missing, f"proofs naming a test that does not exist: {missing}"


class _Nested(BaseModel):
    reviewed_by: str


class _Wrapper(BaseModel):
    items: tuple[_Nested, ...] = ()
    sort_by: str = "date"
    note: str = ""


class _Synthetic(BaseModel):
    profile_id: str
    wrapper: _Wrapper | None = None
    author: str | None = None


def test_the_detection_reads_a_name_at_any_depth_and_a_gained_field_is_unaccounted() -> None:
    """A field gained at depth, or one ending in ``_by``, is found; the listed non-party name is not."""
    assert _attribution_fields(_Synthetic) == {"author", "wrapper.items.reviewed_by"}

    gained = {
        "ledger.archive": frozenset({"actor", "approved_by"}),
        "synthetic.operation": frozenset({"author"}),
    }
    assert _unaccounted(gained) == {
        "ledger.archive": frozenset({"approved_by"}),
        "synthetic.operation": frozenset({"author"}),
    }
