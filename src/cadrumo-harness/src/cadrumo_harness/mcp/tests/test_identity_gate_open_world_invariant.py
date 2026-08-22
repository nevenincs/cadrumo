"""No AEAT-reaching command may bypass the identity gate.

The gate lets a call proceed without identity confirmation when it is
``read_only and not open_world``. The second half is currently a no-op — no
exposed command is both — and that is exactly why it needs pinning rather than
trusting.

The invariant holds today by ACCIDENT. ``read_only`` derives from the family's
mutability, and every AEAT-reaching verb sits in a family that also mutates, so
all 32 classify non-read-only and stay gated. Nothing about that is a decision;
it is a side effect of the derivation being family-grained. Declaring reads per
command — which is a live proposal — would flip those verbs to ``read_only`` and,
without the ``open_world`` term, silently drop identity confirmation from every
one of them.

Why that matters more than "it is only a read": a live ``pull`` fetches taxpayer
data from AEAT under a certificate. Reading the WRONG taxpayer mutates nothing
locally and is still a confidentiality breach, and the wrong figures then feed
every downstream calculation. `sensitive-financial-data-secure-storage-only` treats the AEAT boundary
as the load-bearing one, and this is the gate that asks "which taxpayer?" before
a verb crosses it.

So this file exists to make a future reclassification RED here rather than
quietly un-gate 32 commands.
"""

from __future__ import annotations

import pytest

from .._command_policy import command_policy
from .._identity_gate import identity_gate_refusal
from .._tools import build_tool_descriptors

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


def test_no_exposed_command_is_both_read_only_and_open_world() -> None:
    """The invariant the gate's ``and not open_world`` term defends.

    A command reaching this state would bypass identity confirmation on an AEAT
    fetch. It is zero today; this fails the moment a reclassification makes it
    otherwise, which is the entire point of the term.
    """
    offenders = sorted(
        key
        for key in _exposed_keys()
        if command_policy(key).read_only and command_policy(key).open_world
    )

    assert offenders == [], (
        "these commands reach AEAT yet classify read_only, so they would skip the identity gate: "
        f"{offenders}. Either they do not belong in an open-world family, or the gate's predicate "
        "needs revisiting before they ship."
    )


def test_every_aeat_reaching_command_is_still_gated() -> None:
    """The positive half: the population the term protects is real and non-empty.

    Without this, the invariant above is satisfiable by there being no
    open-world commands at all, and would keep passing if the whole live surface
    were removed or stopped classifying as open-world.
    """
    open_world = [key for key in _exposed_keys() if command_policy(key).open_world]

    assert len(open_world) > 10, f"expected the live AEAT surface, found {len(open_world)}"
    assert all(not command_policy(key).read_only for key in open_world)


def test_an_unidentified_open_world_call_is_refused() -> None:
    """End to end through the real decision function, not the predicate alone."""
    open_world = [
        key for key in _exposed_keys() if command_policy(key).open_world and key.startswith("app.live.")
    ]
    assert open_world, "no app.live command found to exercise the gate"

    for key in open_world[:5]:
        refusal = identity_gate_refusal(key, state=_UnconfirmedSession())  # type: ignore[arg-type]
        assert refusal, f"{key} reaches AEAT and was allowed without an identity read"


def test_a_local_read_is_still_allowed_unidentified() -> None:
    """The control: the change must not have gated ordinary local reads.

    Without this, refusing everything would satisfy every assertion above.
    """
    local_reads = [
        key
        for key in _exposed_keys()
        if command_policy(key).read_only and not command_policy(key).open_world
    ]
    assert local_reads, "no local read-only command found"

    for key in local_reads[:5]:
        assert identity_gate_refusal(key, state=_UnconfirmedSession()) is None, key  # type: ignore[arg-type]
