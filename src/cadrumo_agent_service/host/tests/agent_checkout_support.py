"""The synced cadrumo-agent checkout and fixed credentials shared by the hosted agent integration tests."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Final

import pytest

from cadrumo_client.contracts.deadline_budget import TimeoutDeadline

from ..controller import AgentGenerations, ResolvedAgentCredentials

CHECKOUT_VARIABLE: Final = "CADRUMO_DEV_AGENT_CHECKOUT"
GENERATIONS: Final = AgentGenerations("synthetic-session", "synthetic-settings")


def agent_checkout() -> Path:
    """Return the synced checkout the environment names, failing the test when it names none."""
    named = os.environ.get(CHECKOUT_VARIABLE)
    if named is None or not named.strip():
        pytest.fail(f"{CHECKOUT_VARIABLE} must name a synced cadrumo-agent checkout", pytrace=False)
    checkout = Path(named)
    if not checkout_interpreter(checkout).is_file():
        pytest.fail(f"{CHECKOUT_VARIABLE} names no synced cadrumo-agent checkout", pytrace=False)
    return checkout


def checkout_interpreter(checkout: Path) -> Path:
    return checkout / ".venv" / "Scripts" / "python.exe"


class FixedCredentials:
    """Credentials with a fresh random bearer each time and the fixed synthetic generations."""

    def resolve_for_agent(self, *, deadline: TimeoutDeadline | None = None) -> ResolvedAgentCredentials:
        return ResolvedAgentCredentials(
            GENERATIONS,
            {},
            gateway_bearer=bytearray(secrets.token_urlsafe(32), "ascii"),
            host_token=bytearray(secrets.token_urlsafe(32), "ascii"),
        )

    def current_generations(self, *, deadline: TimeoutDeadline | None = None) -> AgentGenerations:
        return GENERATIONS
