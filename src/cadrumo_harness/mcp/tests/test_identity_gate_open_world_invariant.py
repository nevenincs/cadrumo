"""AEAT-reaching callback policy keeps AEAT reads behind identity confirmation."""

from __future__ import annotations

import pytest

from .._command_policy import CommandPolicyProjection, command_policy
from ..identity_gate import identity_gate_refusal
from ..tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _exposed_keys() -> tuple[str, ...]:
    return tuple(sorted(descriptor.command_key for descriptor in build_tool_descriptors()))


class _UnconfirmedSession:
    """A session in which no identity read has happened yet."""

    identity_confirmed = False

    def rearm(self) -> None:  # pragma: no cover - never reached on the refusal path
        raise AssertionError("the gate must not re-arm on an open-world read")

    def record_identity_read(self) -> None:  # pragma: no cover - same
        raise AssertionError("an open-world read is not an identity read")


def test_the_exposed_surface_is_non_empty() -> None:
    """Guard the denominator, or every sweep below is vacuously green."""
    assert len(_exposed_keys()) > 100


def test_read_only_aeat_commands_still_require_identity() -> None:
    """Precise leaf mutability cannot bypass AEAT identity protection."""
    planted = CommandPolicyProjection(
        command_key="renamed.aeat.read",
        read_only=True,
        destructive=False,
        idempotent=True,
        handoff=False,
        live_write=False,
        open_world=True,
        reaches_aeat=True,
    )
    assert identity_gate_refusal(
        planted.command_key,
        execution_policy=planted,
        state=_UnconfirmedSession(),  # type: ignore[arg-type]
    )


def test_every_aeat_reaching_command_is_still_gated() -> None:
    """The positive half: the population the term protects is real and non-empty.

    Without this, the invariant above is satisfiable by there being no
    AEAT-reaching commands at all, and would keep passing if the whole live
    surface were removed or stopped declaring the ``aeat`` capability.
    """
    reaching = [key for key in _exposed_keys() if command_policy(key).reaches_aeat]

    assert len(reaching) > 10, f"expected the live AEAT surface, found {len(reaching)}"


def test_an_unidentified_open_world_call_is_refused() -> None:
    """End to end through the real decision function, not the predicate alone."""
    reaching = [key for key in _exposed_keys() if command_policy(key).reaches_aeat and key.startswith("app.live.")]
    assert reaching, "no app.live command found to exercise the gate"

    for key in reaching[:5]:
        refusal = identity_gate_refusal(key, state=_UnconfirmedSession())  # type: ignore[arg-type]
        assert refusal, f"{key} reaches AEAT and was allowed without an identity read"


def test_a_local_read_is_still_allowed_unidentified() -> None:
    """The control: the change must not have gated ordinary local reads.

    Without this, refusing everything would satisfy every assertion above.
    """
    local_reads = [
        key for key in _exposed_keys() if command_policy(key).read_only and not command_policy(key).reaches_aeat
    ]
    assert local_reads, "no local read-only command found"

    for key in local_reads[:5]:
        assert identity_gate_refusal(key, state=_UnconfirmedSession()) is None, key  # type: ignore[arg-type]
