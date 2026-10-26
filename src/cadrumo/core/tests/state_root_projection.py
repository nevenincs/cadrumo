"""Finite storage-root projection for cross-substrate fixtures."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from ..config_state_root import StateRootInputs, _mode_evidence, platform_user_data_root
from ..models import STRICT_FROZEN_CONFIG
from ..storage_environment import storage_root_for


class StateRootResolution(BaseModel):
    """Resolved application-data anchor and default storage root."""

    model_config = STRICT_FROZEN_CONFIG
    platform_user_data_root: Path
    storage_root: Path


def resolve_state_root(inputs: StateRootInputs) -> StateRootResolution:
    """Resolve the relative-path anchor and the storage root from one set of inputs."""
    evidence = _mode_evidence(inputs)
    return StateRootResolution(
        platform_user_data_root=platform_user_data_root(inputs),
        storage_root=storage_root_for(inputs.environ, evidence, sys_platform=inputs.platform),
    )
