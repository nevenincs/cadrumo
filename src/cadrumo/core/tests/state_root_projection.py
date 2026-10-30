"""Finite storage-root projection for cross-substrate fixtures."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from ..config_state_root import StateRootInputs
from ..models import STRICT_FROZEN_CONFIG
from ..storage_environment import storage_root_for


class StateRootResolution(BaseModel):
    """The storage root one set of inputs resolves to."""

    model_config = STRICT_FROZEN_CONFIG
    storage_root: Path


def resolve_state_root(inputs: StateRootInputs) -> StateRootResolution:
    """Resolve the storage root from one set of inputs."""
    return StateRootResolution(storage_root=storage_root_for(inputs.environ, sys_platform=inputs.platform))
