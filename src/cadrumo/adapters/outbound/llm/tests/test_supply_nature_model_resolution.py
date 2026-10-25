"""The supply-nature proposer sends to the model the reader probe checks.

Both resolve the role through one selection, so an operator's model setting
names the model the probe looks for in the runtime's inventory and the model a
proposal is sent to. A named model is honoured without the headroom bar, so
this host's free memory cannot decide the result.
"""

from __future__ import annotations

import pytest

from .....application.tests.role_model_support import configured_role_model
from .....core.model_catalogue import ModelRole, candidates_for_role, default_model_runtime_id
from .....tests.fixtures.settings import EnvFileFreeSettings
from ..supply_nature_proposal import SupplyNatureProposer

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_ROLE = ModelRole.SUPPLY_NATURE_PROPOSAL


def test_the_proposer_sends_to_the_named_model_the_probe_checks() -> None:
    named = next(
        candidate.runtime_id
        for candidate in candidates_for_role(_ROLE)
        if candidate.runtime_id != default_model_runtime_id(_ROLE)
    )
    settings = EnvFileFreeSettings(cadrumo_llm_ollama_supply_nature_model=named)

    proposer = SupplyNatureProposer(settings=settings)

    assert configured_role_model(_ROLE, settings) == named
    assert named in proposer.decided_by
