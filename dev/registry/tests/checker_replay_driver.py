"""Test-owned deterministic checker replay driver."""

from collections.abc import Mapping
from typing import Literal

from cadrumo.domain.calculations.registry.checker_oracle_flow import CheckerDriverMode, CheckerObservation
from cadrumo.domain.calculations.registry.remote_state_guard import RemoteOperation

from .checker_oracle import decode_replay_observation, replay_parse_operation


class CheckerReplayDriver:
    def __init__(self, *, surface_label: str, replay_action: str) -> None:
        self._surface_label = surface_label
        self._replay_action = replay_action

    @property
    def mode(self) -> Literal[CheckerDriverMode.REPLAY]:
        return CheckerDriverMode.REPLAY

    def planned_operations(self, payload: bytes, *, expected: Mapping[str, object]) -> tuple[RemoteOperation, ...]:
        del payload, expected
        return replay_parse_operation(self._replay_action)

    def collect_observation(self, payload: bytes, *, expected: Mapping[str, object]) -> CheckerObservation:
        del expected
        return decode_replay_observation(payload, surface_label=self._surface_label)
