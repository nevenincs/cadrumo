"""A column-mapping or supply-nature model that cannot be asked is reported, not declined.

Both readers run on the person's role selection through the agent service. When
the service refuses the run -- the role has no selection, its lane is
unavailable, its model is not installed, no service answers -- the person must
learn which selection or component is missing, not that their file could not be
mapped, and not that the document said nothing. No other lane or model is
tried. A model that answered and established nothing is a different outcome and
stays a decline.

The production client and agent adapter run for real against a recording
stand-in for the service behind the model-run port. Each case controls only
what the service answers.
"""

from __future__ import annotations

import json
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path

import pytest

from cadrumo_client.contracts.model_runs import ModelRunRefusal, ModelRunRefusalCode

from .....application.ledger.column_roles import ColumnRoleReaderUnavailable
from .....application.operator_actions.models import PreconditionVerdict
from .....application.provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID
from .....core.config import Settings
from .....core.field_role import FieldRole
from .....core.model_roles import ModelRole
from .....core.tabular import NormalizedTable, normalize_tabular_bytes
from .....domain.iva.supply_nature import SupplyNature
from .....tests.fixtures.settings import EnvFileFreeSettings
from ..client import LLMClient
from ..column_role_mapping import ColumnRoleProposal, SemanticColumnRoleMapper, resolve_column_roles
from ..errors import LLMProviderError
from ..providers.agent import model_run_refusal_verdict
from ..supply_nature_proposal import SupplyNatureProposer
from .model_run_support import ON_HOST_LANE, RecordingModelRuns, serving_agent

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_TABLE_BYTES = b"fecha;concepto;importe\n2026-01-05;Cuota mensual;-12,50\n"
_DESCRIPTIONS = ("Licencia anual de software", "Soporte remoto")

#: Refusals the service answers at lookup, before any run is attempted.
_LOOKUP_REFUSALS = (
    ModelRunRefusalCode.NO_SELECTION,
    ModelRunRefusalCode.LANE_UNAVAILABLE,
    ModelRunRefusalCode.MODEL_NOT_INSTALLED,
    ModelRunRefusalCode.NOT_SIGNED_IN,
)


def _settings(tmp_path: Path) -> Settings:
    return EnvFileFreeSettings(
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_record_dir=tmp_path / "run-record",
    )


@contextmanager
def _service(
    reply: str = "{}",
    *,
    lookup_refusal: ModelRunRefusalCode | None = None,
    run_refusal: ModelRunRefusalCode | None = None,
) -> Generator[RecordingModelRuns]:
    with serving_agent(
        replies=(reply,), lane=ON_HOST_LANE, lookup_refusal=lookup_refusal, run_refusal=run_refusal
    ) as service:
        yield service


def _mapper(tmp_path: Path) -> SemanticColumnRoleMapper:
    settings = _settings(tmp_path)
    return SemanticColumnRoleMapper(client=LLMClient(settings=settings), settings=settings)


def _proposer(tmp_path: Path) -> SupplyNatureProposer:
    settings = _settings(tmp_path)
    return SupplyNatureProposer(client=LLMClient(settings=settings), settings=settings)


def _table() -> NormalizedTable:
    return normalize_tabular_bytes(_TABLE_BYTES)


def _mapping_reply(assignments: Sequence[tuple[int, FieldRole]]) -> str:
    return json.dumps({"assignments": [{"column_index": index, "role": role.value} for index, role in assignments]})


def _assert_refusal(verdict: PreconditionVerdict | None, code: ModelRunRefusalCode, role: ModelRole) -> None:
    """The reported verdict is the model-run verdict for ``code`` and ``role``, as its builder makes it."""
    assert verdict == model_run_refusal_verdict(ModelRunRefusal(code=code), role=role)
    assert verdict.evidence[0].values["model_run_refusal"] == code.value
    assert verdict.evidence[0].values["model_role"] == role.value
    if code is ModelRunRefusalCode.MODEL_NOT_INSTALLED:
        assert verdict.action is not None
        assert verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
    else:
        assert verdict.action is None
    if code is ModelRunRefusalCode.NO_SELECTION:
        assert verdict.evidence[0].values["role_selection_required"] is True


# -- Column-role mapping ---------------------------------------------------------


@pytest.mark.parametrize("code", _LOOKUP_REFUSALS, ids=lambda code: code.value)
def test_a_refused_lookup_is_reported_with_its_typed_verdict(tmp_path: Path, code: ModelRunRefusalCode) -> None:
    with _service(lookup_refusal=code) as service:
        outcome = resolve_column_roles(_table(), mapper=_mapper(tmp_path))

    assert isinstance(outcome, ColumnRoleReaderUnavailable)
    _assert_refusal(outcome.precondition_verdict, code, ModelRole.COLUMN_ROLE_MAPPING)
    assert service.lookups == [ModelRole.COLUMN_ROLE_MAPPING], "no other role is asked in its place"
    assert service.runs == [], "a reader known to be missing must not be asked"


def test_no_running_service_is_reported_as_service_unavailable(tmp_path: Path) -> None:
    outcome = resolve_column_roles(_table(), mapper=_mapper(tmp_path))

    assert isinstance(outcome, ColumnRoleReaderUnavailable)
    _assert_refusal(
        outcome.precondition_verdict, ModelRunRefusalCode.SERVICE_UNAVAILABLE, ModelRole.COLUMN_ROLE_MAPPING
    )


def test_a_model_lost_after_the_lookup_is_reported_after_the_refused_run(tmp_path: Path) -> None:
    with _service(run_refusal=ModelRunRefusalCode.MODEL_NOT_INSTALLED) as service:
        outcome = resolve_column_roles(_table(), mapper=_mapper(tmp_path))

    assert isinstance(outcome, ColumnRoleReaderUnavailable)
    _assert_refusal(
        outcome.precondition_verdict, ModelRunRefusalCode.MODEL_NOT_INSTALLED, ModelRole.COLUMN_ROLE_MAPPING
    )
    assert len(service.runs) == 1


def test_a_model_that_answers_unusably_declines_rather_than_reporting_a_missing_reader(tmp_path: Path) -> None:
    with _service('{"assignments": "none"}') as service:
        outcome = resolve_column_roles(_table(), mapper=_mapper(tmp_path))

    assert outcome is None
    assert len(service.runs) == 1


def test_a_served_mapping_role_maps_the_table(tmp_path: Path) -> None:
    """Positive control: the same service answering yields a mapping, not a refusal."""
    reply = _mapping_reply([(0, FieldRole.BOOKED_DATE), (1, FieldRole.NOTES), (2, FieldRole.MOVEMENT_AMOUNT)])
    with _service(reply):
        outcome = resolve_column_roles(_table(), mapper=_mapper(tmp_path))

    assert isinstance(outcome, ColumnRoleProposal)
    assert outcome.roles == (FieldRole.BOOKED_DATE, FieldRole.NOTES, FieldRole.MOVEMENT_AMOUNT)


# -- Supply-nature proposal ------------------------------------------------------


@pytest.mark.parametrize("code", _LOOKUP_REFUSALS, ids=lambda code: code.value)
def test_a_refused_proposal_lookup_is_reported_on_the_proposal(tmp_path: Path, code: ModelRunRefusalCode) -> None:
    with _service('{"supply_nature": "services", "reason": "software"}', lookup_refusal=code) as service:
        proposal = _proposer(tmp_path).propose(_DESCRIPTIONS)

    assert proposal.nature is None
    assert proposal.declined is False
    _assert_refusal(proposal.reader_unavailable, code, ModelRole.SUPPLY_NATURE_PROPOSAL)
    assert service.lookups == [ModelRole.SUPPLY_NATURE_PROPOSAL]
    assert service.runs == []


def test_no_running_service_is_reported_on_the_proposal(tmp_path: Path) -> None:
    proposal = _proposer(tmp_path).propose(_DESCRIPTIONS)

    _assert_refusal(
        proposal.reader_unavailable, ModelRunRefusalCode.SERVICE_UNAVAILABLE, ModelRole.SUPPLY_NATURE_PROPOSAL
    )


def test_a_failed_run_stays_the_clients_error(tmp_path: Path) -> None:
    """A run the agent attempted and failed is not reported as a missing selection."""
    with _service(run_refusal=ModelRunRefusalCode.RUN_FAILED), pytest.raises(LLMProviderError):
        _proposer(tmp_path).propose(_DESCRIPTIONS)


def test_a_served_supply_nature_role_proposes(tmp_path: Path) -> None:
    """Positive control: with the role served the proposal carries a nature and no refusal."""
    with _service('{"supply_nature": "services", "reason": "software licence"}') as service:
        proposal = _proposer(tmp_path).propose(_DESCRIPTIONS)

    assert proposal.nature is SupplyNature.SERVICES
    assert proposal.reader_unavailable is None
    assert len(service.runs) == 1
