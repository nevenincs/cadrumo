"""The supply-nature proposer runs on its own role's selection, under the read's consent.

The proposer names no model and no provider. It asks the agent service for the
supply-nature role, and because line descriptions are document content, a lane
that reads off-host needs the per-invocation consent token while a lane that
stays on this computer needs none. The production client and agent adapter run
for real against a recording stand-in for the service.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.model_roles import ModelRole
from .....domain.iva.supply_nature import SupplyNature
from .....tests.fixtures.settings import EnvFileFreeSettings
from ..client import LLMClient
from ..consent import EvidenceConsentToken
from ..supply_nature_proposal import SupplyNatureProposer
from .model_run_support import ON_HOST_LANE, serving_agent

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_DESCRIPTIONS = ("Licencia anual de software", "Soporte remoto")
_REPLY = '{"supply_nature": "services", "reason": "software licence"}'
_TOKEN = EvidenceConsentToken(surface="runtime:ledger.evidence.extract", evidence_content_address="e" * 64)


def _proposer(tmp_path: Path, *, consent_token: EvidenceConsentToken | None = None) -> SupplyNatureProposer:
    settings = EnvFileFreeSettings(cadrumo_storage_root=tmp_path)
    return SupplyNatureProposer(client=LLMClient(settings=settings), settings=settings, consent_token=consent_token)


def test_the_proposer_asks_the_service_for_its_own_role(tmp_path: Path) -> None:
    with serving_agent(replies=(_REPLY,), lane=ON_HOST_LANE) as service:
        proposer = _proposer(tmp_path)
        proposal = proposer.propose(_DESCRIPTIONS)

    assert proposal.nature is SupplyNature.SERVICES
    assert service.lookups == [ModelRole.SUPPLY_NATURE_PROPOSAL]
    header, body = service.runs[0]
    assert header.role == ModelRole.SUPPLY_NATURE_PROPOSAL.value
    assert header.consent is None, "a lane that stays on this computer binds no consent"
    assert body.temperature == 0.0
    assert proposer.decided_by == "llm:agent-supply-nature-proposal:configured"


def test_an_off_host_lane_without_consent_is_reported_and_nothing_is_sent(tmp_path: Path) -> None:
    with serving_agent(replies=(_REPLY,)) as service:
        proposal = _proposer(tmp_path).propose(_DESCRIPTIONS)

    assert proposal.nature is None
    assert proposal.reader_unavailable is not None
    assert proposal.reader_unavailable.failed_condition_id == "llm.evidence.off_host_dispatch_permitted"
    assert service.runs == []


def test_an_off_host_lane_with_consent_binds_it_to_the_run(tmp_path: Path) -> None:
    with serving_agent(replies=(_REPLY,)) as service:
        proposal = _proposer(tmp_path, consent_token=_TOKEN).propose(_DESCRIPTIONS)

    assert proposal.nature is SupplyNature.SERVICES
    header, _body = service.runs[0]
    assert header.consent is not None
