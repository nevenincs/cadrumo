"""``WhoamiIdentity.readiness`` carries the canonical profile-health taxonomy.

``ActiveProfileHealth.status`` is a closed ``ProfileHealthStatus`` literal, but
the MCP identity block redeclared it as an arbitrary non-empty string. The
projection always copies the health verdict, so the widening was invisible in
normal operation — yet a directly constructed or client-deserialized identity
could carry a readiness outside the taxonomy, and this block is precisely what
an agent reconciles before a mutating command. An unrecognised readiness is a
value the recovery logic has no branch for.

Each refusal is paired with the valid value it accepts, so a contract that
started refusing everything is distinguishable from one refusing the right
thing.
"""

from __future__ import annotations

import typing

import pytest
from pydantic import ValidationError

from cadrumo.application.workflow import ActiveProfileHealth, ProfileHealthStatus

from .._harness_tools import HarnessFloorPayload, WhoamiIdentity

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DECLARED_STATUSES = typing.cast(tuple[ProfileHealthStatus, ...], typing.get_args(ProfileHealthStatus))


@pytest.mark.parametrize("bad", ["bogus", "", "READY", "ready ", "unknown_status"])
def test_readiness_outside_the_taxonomy_is_refused(bad: str) -> None:
    with pytest.raises(ValidationError):
        WhoamiIdentity.model_validate({"readiness": bad})


@pytest.mark.parametrize("status", _DECLARED_STATUSES)
def test_every_declared_health_status_is_accepted(status: ProfileHealthStatus) -> None:
    """The identity block must admit exactly the taxonomy, not a subset of it.

    A degraded-pointer status is as legitimate a readiness as ``ready``: the
    whoami tool exists to report those cases.
    """
    assert WhoamiIdentity(readiness=status).readiness == status  # type: ignore[arg-type]


def test_the_taxonomy_is_the_health_projections_own() -> None:
    """The two contracts are one declaration, not two lists that could drift."""
    for status in _DECLARED_STATUSES:
        health = ActiveProfileHealth(active_profile=None, source="none", status=status)
        assert WhoamiIdentity(readiness=health.status).readiness == health.status

    with pytest.raises(ValidationError):
        ActiveProfileHealth.model_validate({"active_profile": None, "source": "none", "status": "bogus"})


def test_readiness_stays_required() -> None:
    """Narrowing the type must not silently give the field a default."""
    with pytest.raises(ValidationError):
        WhoamiIdentity.model_validate({})


def test_client_deserialization_refuses_a_widened_readiness() -> None:
    """A payload rebuilt from a client's JSON carries the same contract."""
    valid = WhoamiIdentity(readiness="ready", active_profile="Erika", precondition_action=None)
    assert WhoamiIdentity.model_validate_json(valid.model_dump_json()) == valid

    widened = valid.model_dump()
    widened["readiness"] = "bogus"
    with pytest.raises(ValidationError):
        WhoamiIdentity.model_validate(widened)


def test_the_nested_floor_identity_inherits_the_contract() -> None:
    """The floor tool embeds the identity block, so it cannot be a second shape."""
    floor = HarnessFloorPayload(
        off_host_consent="consent",
        operator_rules="rules",
        identity=WhoamiIdentity(readiness="ready"),
    )
    assert floor.identity is not None
    assert floor.identity.readiness == "ready"

    with pytest.raises(ValidationError):
        HarnessFloorPayload.model_validate(
            {
                "off_host_consent": "consent",
                "operator_rules": "rules",
                "identity": {"readiness": "bogus"},
            },
        )
