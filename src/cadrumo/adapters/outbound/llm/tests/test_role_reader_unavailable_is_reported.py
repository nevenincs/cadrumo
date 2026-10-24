"""A column-mapping or supply-nature model that cannot be asked is reported, not declined.

Both readers run on the local AI runtime. When the runtime does not answer, or
answers without the role's model, the person must learn that a component is
missing and that setup supplies it -- not that their file could not be mapped,
and not that the document said nothing. A model that answered and established
nothing is a different outcome and stays a decline.

The runtime is a real Ollama-shaped loopback serving ``/api/tags`` and
``/api/chat``; the reader probe, the production client and the local transport
all run for real. Each case controls only what the runtime holds.
"""

from __future__ import annotations

import json
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path
from typing import override

import pytest

from .....application.ledger.column_roles import ColumnRoleReaderUnavailable
from .....application.local_reader import role_model_targets
from .....application.provisioning import select_model_for_role
from .....application.provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID, ProvisioningPreconditionCondition
from .....core.config import Settings, override_settings
from .....core.field_role import FieldRole
from .....core.model_catalogue import ModelRole
from .....core.tabular import NormalizedTable, normalize_tabular_bytes
from .....domain.iva.supply_nature import SupplyNature
from .....tests.fixtures.settings import EnvFileFreeSettings
from .....tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from ..client import LLMClient
from ..column_role_mapping import ColumnRoleProposal, SemanticColumnRoleMapper, resolve_column_roles
from ..errors import LLMProviderError
from ..supply_nature_proposal import SupplyNatureProposer
from .load_headroom_support import admitting_client, admitting_hardware_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

#: A port nothing listens on, so the runtime genuinely does not answer.
_CLOSED_ENDPOINT = "http://127.0.0.1:1/api/chat"

_TABLE_BYTES = b"fecha;concepto;importe\n2026-01-05;Cuota mensual;-12,50\n"
_DESCRIPTIONS = ("Licencia anual de software", "Soporte remoto")


@dataclass
class _RuntimeState:
    """What the loopback runtime holds, and what it was asked."""

    #: Successive ``/api/tags`` answers; the last one repeats.
    tags: list[list[str]]
    #: The chat reply text, or ``None`` for the runtime's model-not-found answer.
    chat_reply: str | None
    chat_requests: list[object] = field(default_factory=list)


@contextmanager
def _runtime(state: _RuntimeState) -> Generator[str]:
    """Serve an Ollama-shaped runtime over loopback that answers from ``state``."""

    class _Runtime(SilentLoopbackHandler):
        @override
        def do_GET(self) -> None:
            if self.path != "/api/tags":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            names = state.tags[0] if len(state.tags) == 1 else state.tags.pop(0)
            write_json_response(self, {"models": [{"name": name, "size": 1} for name in names]}, status=HTTPStatus.OK)

        @override
        def do_POST(self) -> None:
            body = read_json_body(self)
            if self.path != "/api/chat":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            state.chat_requests.append(body)
            if state.chat_reply is None:
                write_json_response(self, {"error": "model not found"}, status=HTTPStatus.NOT_FOUND)
                return
            write_json_response(
                self, ollama_chat_reply(state.chat_reply, prompt_eval_count=20, eval_count=10), status=HTTPStatus.OK
            )

    with serving_loopback(_Runtime, path="/api/chat") as endpoint:
        yield endpoint


def _role_model(role: ModelRole) -> str:
    model = select_model_for_role(role).runtime_id
    assert model is not None, f"the {role.value} role selects no model on this host"
    return model


def _settings(tmp_path: Path, endpoint: str, *, mapping_model: str | None = None) -> Settings:
    return EnvFileFreeSettings(
        cadrumo_llm_ollama_chat_url=endpoint,
        cadrumo_llm_ollama_mapping_model=mapping_model or _role_model(ModelRole.COLUMN_ROLE_MAPPING),
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_record_dir=tmp_path / "run-record",
    )


@contextmanager
def _mapper(tmp_path: Path, endpoint: str, *, mapping_model: str | None = None) -> Generator[SemanticColumnRoleMapper]:
    """A mapper on the production client, admitted under a measured reading for its model.

    The local transport reads its chat URL from the process-wide settings, so
    the endpoint is overridden there as well as injected. ``mapping_model`` is
    an operator-set mapping model; the role's selection otherwise.
    """
    settings = _settings(tmp_path, endpoint, mapping_model=mapping_model)
    model = mapping_model or _role_model(ModelRole.COLUMN_ROLE_MAPPING)
    client = LLMClient(
        settings=settings,
        hardware_profile=admitting_hardware_profile(model, settings=settings),
        runtime_residents=(),
    )
    with override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        yield SemanticColumnRoleMapper(client=client, settings=settings)


@contextmanager
def _proposer(tmp_path: Path, endpoint: str) -> Generator[SupplyNatureProposer]:
    """A supply-nature proposer on the production client, admitted for its role's model."""
    settings = _settings(tmp_path, endpoint)
    client = admitting_client(
        _role_model(ModelRole.SUPPLY_NATURE_PROPOSAL),
        settings=settings,
        caller="cadrumo.adapters.outbound.llm.supply_nature_proposal",
        prompt_id="invoice-supply-nature-proposal",
    )
    with override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        yield SupplyNatureProposer(client=client, settings=settings)


def _table() -> NormalizedTable:
    return normalize_tabular_bytes(_TABLE_BYTES)


def _mapping_reply(assignments: Sequence[tuple[int, FieldRole]]) -> str:
    return json.dumps({"assignments": [{"column_index": index, "role": role.value} for index, role in assignments]})


def _assert_setup_offered(unavailable: object, condition: ProvisioningPreconditionCondition) -> None:
    assert isinstance(unavailable, ColumnRoleReaderUnavailable), unavailable
    verdict = unavailable.precondition_verdict
    assert verdict.failed_condition_id == condition.value
    assert verdict.action is not None
    assert verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID


# -- Column-role mapping ---------------------------------------------------------


def test_an_unanswering_runtime_is_reported_with_the_local_ai_setup(tmp_path: Path) -> None:
    with _mapper(tmp_path, _CLOSED_ENDPOINT) as mapper:
        outcome = resolve_column_roles(_table(), mapper=mapper)

    _assert_setup_offered(outcome, ProvisioningPreconditionCondition.RUNTIME_REACHABLE)


def test_a_missing_mapping_model_is_reported_before_any_mapping_call(tmp_path: Path) -> None:
    state = _RuntimeState(tags=[[]], chat_reply=_mapping_reply([(0, FieldRole.BOOKED_DATE)]))
    with _runtime(state) as endpoint, _mapper(tmp_path, endpoint) as mapper:
        outcome = resolve_column_roles(_table(), mapper=mapper)

    _assert_setup_offered(outcome, ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED)
    assert state.chat_requests == [], "a reader known to be missing must not be asked"


def test_a_model_lost_after_the_check_is_reported_after_the_failed_call(tmp_path: Path) -> None:
    model = _role_model(ModelRole.COLUMN_ROLE_MAPPING)
    state = _RuntimeState(tags=[[model], []], chat_reply=None)
    with _runtime(state) as endpoint, _mapper(tmp_path, endpoint) as mapper:
        outcome = resolve_column_roles(_table(), mapper=mapper)

    _assert_setup_offered(outcome, ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED)
    assert len(state.chat_requests) == 1


def test_a_model_that_answers_unusably_declines_rather_than_reporting_a_missing_reader(tmp_path: Path) -> None:
    state = _RuntimeState(tags=[[_role_model(ModelRole.COLUMN_ROLE_MAPPING)]], chat_reply="I cannot label these.")
    with _runtime(state) as endpoint, _mapper(tmp_path, endpoint) as mapper:
        outcome = resolve_column_roles(_table(), mapper=mapper)

    assert outcome is None
    assert len(state.chat_requests) == 1


def test_an_installed_mapping_model_maps_the_table(tmp_path: Path) -> None:
    """Positive control: the same runtime holding the model yields a mapping, not a refusal."""
    reply = _mapping_reply([(0, FieldRole.BOOKED_DATE), (1, FieldRole.NOTES), (2, FieldRole.MOVEMENT_AMOUNT)])
    state = _RuntimeState(tags=[[_role_model(ModelRole.COLUMN_ROLE_MAPPING)]], chat_reply=reply)
    with _runtime(state) as endpoint, _mapper(tmp_path, endpoint) as mapper:
        outcome = resolve_column_roles(_table(), mapper=mapper)

    assert isinstance(outcome, ColumnRoleProposal)
    assert outcome.roles == (FieldRole.BOOKED_DATE, FieldRole.NOTES, FieldRole.MOVEMENT_AMOUNT)


def test_a_role_this_computer_cannot_serve_is_reported_without_a_setup_action() -> None:
    """Setup cannot change the hardware, so the report names no action."""
    with override_settings(cadrumo_llm_ollama_num_ctx=1_000_000, cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT):
        outcome = resolve_column_roles(_table())

    assert isinstance(outcome, ColumnRoleReaderUnavailable)
    verdict = outcome.precondition_verdict
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE.value
    assert verdict.action is None


#: A catalogued mapping candidate other than the role's selection, set by an operator.
_OPERATOR_MAPPING_MODEL = "qwen2.5:3b"


def _sent_model(request: object) -> object:
    assert isinstance(request, dict)
    return request.get("model")


def test_an_operator_set_mapping_model_is_the_model_sent_and_checked(tmp_path: Path) -> None:
    """The mapper sends the model setup provisions and the probe checks, not the role's default."""
    assert _role_model(ModelRole.COLUMN_ROLE_MAPPING) != _OPERATOR_MAPPING_MODEL
    reply = _mapping_reply([(0, FieldRole.BOOKED_DATE), (1, FieldRole.NOTES), (2, FieldRole.MOVEMENT_AMOUNT)])
    state = _RuntimeState(tags=[[_OPERATOR_MAPPING_MODEL]], chat_reply=reply)
    with (
        _runtime(state) as endpoint,
        _mapper(tmp_path, endpoint, mapping_model=_OPERATOR_MAPPING_MODEL) as mapper,
    ):
        outcome = resolve_column_roles(_table(), mapper=mapper)
        (target,) = role_model_targets(
            (ModelRole.COLUMN_ROLE_MAPPING,), _settings(tmp_path, endpoint, mapping_model=_OPERATOR_MAPPING_MODEL)
        )

    assert isinstance(outcome, ColumnRoleProposal)
    assert [_sent_model(request) for request in state.chat_requests] == [_OPERATOR_MAPPING_MODEL]
    assert target.model == _OPERATOR_MAPPING_MODEL


def test_the_probe_checks_the_mapping_model_the_mapper_would_send(tmp_path: Path) -> None:
    """A runtime holding only the role's default does not satisfy an operator-set mapping model."""
    state = _RuntimeState(
        tags=[[_role_model(ModelRole.COLUMN_ROLE_MAPPING)]],
        chat_reply=_mapping_reply([(0, FieldRole.BOOKED_DATE)]),
    )
    with (
        _runtime(state) as endpoint,
        _mapper(tmp_path, endpoint, mapping_model=_OPERATOR_MAPPING_MODEL) as mapper,
    ):
        outcome = resolve_column_roles(_table(), mapper=mapper)

    _assert_setup_offered(outcome, ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED)
    assert isinstance(outcome, ColumnRoleReaderUnavailable)
    assert [evidence.values.get("model") for evidence in outcome.precondition_verdict.evidence] == [
        _OPERATOR_MAPPING_MODEL
    ]
    assert state.chat_requests == [], "a reader known to be missing must not be asked"


# -- Supply-nature proposal ------------------------------------------------------


def test_a_missing_supply_nature_model_is_reported_on_the_proposal(tmp_path: Path) -> None:
    state = _RuntimeState(tags=[[]], chat_reply='{"supply_nature": "services", "reason": "software"}')
    with _runtime(state) as endpoint, _proposer(tmp_path, endpoint) as proposer:
        proposal = proposer.propose(_DESCRIPTIONS)

    assert proposal.nature is None
    assert proposal.declined is False
    assert proposal.reader_unavailable is not None
    assert proposal.reader_unavailable.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED
    assert proposal.reader_unavailable.action is not None
    assert proposal.reader_unavailable.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
    assert state.chat_requests == [], "a reader known to be missing must not be asked"


def test_an_unanswering_runtime_is_reported_on_the_proposal(tmp_path: Path) -> None:
    with _proposer(tmp_path, _CLOSED_ENDPOINT) as proposer:
        proposal = proposer.propose(_DESCRIPTIONS)

    assert proposal.reader_unavailable is not None
    assert proposal.reader_unavailable.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE
    assert proposal.reader_unavailable.action is not None
    assert proposal.reader_unavailable.action.action_id == LOCAL_AI_PROVISION_ACTION_ID


def test_a_supply_nature_model_lost_after_the_check_is_reported_after_the_failed_call(tmp_path: Path) -> None:
    state = _RuntimeState(tags=[[_role_model(ModelRole.SUPPLY_NATURE_PROPOSAL)], []], chat_reply=None)
    with _runtime(state) as endpoint, _proposer(tmp_path, endpoint) as proposer:
        proposal = proposer.propose(_DESCRIPTIONS)

    assert proposal.reader_unavailable is not None
    assert proposal.reader_unavailable.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED
    assert len(state.chat_requests) == 1


def test_a_failure_the_probe_cannot_explain_stays_the_clients_error(tmp_path: Path) -> None:
    """A runtime that still lists the model but refuses the call is not reported as missing setup."""
    state = _RuntimeState(tags=[[_role_model(ModelRole.SUPPLY_NATURE_PROPOSAL)]], chat_reply=None)
    with (
        _runtime(state) as endpoint,
        _proposer(tmp_path, endpoint) as proposer,
        pytest.raises(LLMProviderError),
    ):
        proposer.propose(_DESCRIPTIONS)


def test_an_installed_supply_nature_model_proposes(tmp_path: Path) -> None:
    """Positive control: with the model installed the proposal carries a nature and no refusal."""
    state = _RuntimeState(
        tags=[[_role_model(ModelRole.SUPPLY_NATURE_PROPOSAL)]],
        chat_reply='{"supply_nature": "services", "reason": "software licence"}',
    )
    with _runtime(state) as endpoint, _proposer(tmp_path, endpoint) as proposer:
        proposal = proposer.propose(_DESCRIPTIONS)

    assert proposal.nature is SupplyNature.SERVICES
    assert proposal.reader_unavailable is None
    assert len(state.chat_requests) == 1
