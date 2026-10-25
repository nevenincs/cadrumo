"""The headroom check at the dispatch choke point.

Distinct from the occupancy bound beside it, and the two are easy to confuse.
Occupancy counts how many loads are already running; this measures whether ONE
load fits right now. Either can refuse while the other would admit, so a gate
for one proves nothing about the other.

The verdict is not computed here and is not computed in the client: it comes
from the single contention authority the doctor surface, the provision verbs and
the batch lane already consult. What these cases prove is the WIRING -- that the
dispatch asks with the size the lane's catalogue entry states, that it obeys the
answer, that it asks while holding its slot, and that a refusal is never re-sent
by the retry policy.

Measurements are injected rather than verdicts. A test that supplied the answer
would exercise none of the comparison, the safety margin or the fail-closed arm,
and would pass against a client that never consulted the authority at all. The
agent service behind the model-run port is a recording stand-in, so "nothing
was run" is an observation of the service rather than an inference.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from cadrumo_client.contracts.model_runs import ModelRunBody, ModelRunLane

from .....application.provisioning import HardwareProfile, probe_hardware_profile
from .....application.provisioning_runtime import (
    ContentionSnapshot,
    RuntimeResident,
    assess_model_load_contention,
    read_runtime_residents,
)
from .....core.hardware import ContentionCause
from .....core.model_catalogue import ModelRole
from .....tests.fixtures.settings import EnvFileFreeSettings
from ....persistence.llm.cache import LLMCache
from ....persistence.llm.run_records import LLMRunRecorder
from ....persistence.llm.usage import UsageRecorder
from ..client import LLMClient, LLMRetryPolicy, _on_host_inference_arena, transport_retry_permitted
from ..errors import LLMContentionError
from ..models import LLMRequest
from ._arena_fixtures import _fresh_arena
from .load_headroom_support import measured_hardware_profile
from .model_run_support import DEFAULT_LANE, ON_HOST_LANE, serving_agent

__all__ = ["_fresh_arena"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_GIB = 1024**3

# A synthetic catalogue size: the figure the lane's entry states for its model.
_SIZE_BYTES = 2 * _GIB

_SIZED_LANE = ON_HOST_LANE.model_copy(update={"size_bytes": _SIZE_BYTES})
"""An on-host lane whose catalogue entry states the model's size."""


def _causes(refusal: LLMContentionError) -> tuple[str, ...]:
    """Return the refusal's declared causes from structured context."""
    context = refusal.context or {}
    causes = context.get("contention_causes")
    assert isinstance(causes, tuple)
    typed_causes: list[str] = []
    for cause in causes:
        assert isinstance(cause, str)
        typed_causes.append(cause)
    return tuple(typed_causes)


def _profile(*, free_vram_bytes: int | None, free_ram_bytes: int) -> HardwareProfile:
    """Build a measured hardware reading with the given free figures."""
    return measured_hardware_profile(
        free_vram_bytes=free_vram_bytes,
        free_ram_bytes=free_ram_bytes,
        total_vram_bytes=8 * _GIB,
        total_ram_bytes=64 * _GIB,
    )


_STARVED = _profile(free_vram_bytes=256 * 1024**2, free_ram_bytes=48 * _GIB)
_QUIESCED = _profile(free_vram_bytes=7 * _GIB, free_ram_bytes=48 * _GIB)
_UNMEASURABLE = _profile(free_vram_bytes=None, free_ram_bytes=48 * _GIB)


def _client(
    tmp_path: Path,
    *,
    profile: HardwareProfile | None = None,
    residents: tuple[RuntimeResident, ...] | None = None,
    residents_measured: bool = True,
    retry_policy: LLMRetryPolicy | None = None,
) -> LLMClient:
    settings = EnvFileFreeSettings(
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_record_dir=tmp_path / "run-record",
    )
    return LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=settings.cadrumo_llm_cache_dir),
        usage_recorder=UsageRecorder(root_dir=settings.cadrumo_llm_usage_dir),
        run_record_recorder=LLMRunRecorder(root_dir=settings.cadrumo_llm_run_record_dir),
        retry_policy=retry_policy or LLMRetryPolicy(max_attempts=1),
        hardware_profile=profile,
        runtime_residents=residents,
        runtime_residents_measured=residents_measured,
    )


def _request() -> LLMRequest:
    return LLMRequest(prompt="hello", model_role=ModelRole.TEXT_EXTRACTION)


def test_a_measured_shortfall_refuses_before_the_run_is_sent(tmp_path: Path) -> None:
    """The load does not fit: refused at the dispatch point, nothing run."""
    with serving_agent(lane=_SIZED_LANE) as service, pytest.raises(LLMContentionError) as refusal:
        asyncio.run(_client(tmp_path, profile=_STARVED, residents=()).complete(_request()))

    # Admission control, not a post-hoc failure: refusing after the runtime
    # began loading would have already spent the memory being protected.
    assert service.runs == []

    # A measured shortfall with a readable, empty resident set is attributed
    # OUTSIDE this runtime -- there is nothing of ours to unload -- and that is
    # a different remediation from an unmeasurable one.
    causes = _causes(refusal.value)
    assert ContentionCause.PEER_PROCESS.value in causes
    assert ContentionCause.UNREADABLE.value not in causes


def test_a_post_quiesce_reading_admits_the_same_request(tmp_path: Path) -> None:
    """The positive control, and the case that separates the two refusal arms.

    Same client, same lane, same service -- only the measurement differs.
    Without it, a refusal is indistinguishable from a dispatch that could not
    have succeeded anyway.
    """
    with serving_agent(lane=_SIZED_LANE, replies=("agent completion",)) as service:
        response = asyncio.run(_client(tmp_path, profile=_QUIESCED, residents=()).complete(_request()))

    assert response.text == "agent completion"
    assert len(service.runs) == 1


def test_an_unmeasurable_headroom_fails_closed(tmp_path: Path) -> None:
    """ "Could not tell" is not evidence of headroom, and it is a DIFFERENT refusal.

    The accelerator is present but its free figure could not be read, while
    system memory is abundant. Abundant RAM is not the arena the weights load
    into, so the refusal must stand.

    Distinguished by cause rather than by the refusal alone. A gate asserting
    only that something was refused would pass here for the shortfall reason and
    on a starved box for this one, and would never notice if the fail-closed arm
    were removed entirely.
    """
    with serving_agent(lane=_SIZED_LANE) as service, pytest.raises(LLMContentionError) as refusal:
        asyncio.run(_client(tmp_path, profile=_UNMEASURABLE, residents=()).complete(_request()))

    assert service.runs == []
    causes = _causes(refusal.value)
    assert ContentionCause.UNREADABLE.value in causes
    assert ContentionCause.PEER_PROCESS.value not in causes, (
        "an unmeasurable reading was attributed to a peer process; the two carry different remediations"
    )


def test_an_unreadable_resident_set_cannot_admit_a_measured_shortfall(tmp_path: Path) -> None:
    """A shortfall the runtime cannot explain is still a shortfall.

    When free memory IS measurable and short, an unreadable resident set removes
    only the ATTRIBUTION, never the shortfall. Admitting here because the cause
    could not be determined would be the fail-open inversion of the whole check.
    """
    with serving_agent(lane=_SIZED_LANE) as service, pytest.raises(LLMContentionError) as refusal:
        asyncio.run(_client(tmp_path, profile=_STARVED, residents=None, residents_measured=False).complete(_request()))

    assert service.runs == []
    assert ContentionCause.UNREADABLE.value in _causes(refusal.value)


def test_an_unmeasurable_headroom_and_a_measured_shortfall_are_not_the_same_refusal(tmp_path: Path) -> None:
    """The discrimination stated directly, since the two arms share an exception type."""
    with serving_agent(lane=_SIZED_LANE):
        with pytest.raises(LLMContentionError) as shortfall:
            asyncio.run(_client(tmp_path / "a", profile=_STARVED, residents=()).complete(_request()))
        with pytest.raises(LLMContentionError) as unreadable:
            asyncio.run(_client(tmp_path / "b", profile=_UNMEASURABLE, residents=()).complete(_request()))

    shortfall_verdict = shortfall.value.terminal_precondition_verdict
    unreadable_verdict = unreadable.value.terminal_precondition_verdict
    assert shortfall_verdict is not None
    assert unreadable_verdict is not None
    assert shortfall_verdict.failed_condition_id == "provisioning.load_capacity.available"
    assert unreadable_verdict.failed_condition_id == "provisioning.load_headroom.measurable"


def test_a_contention_refusal_is_sent_once_and_never_retried(tmp_path: Path) -> None:
    """The boundary the retry policy must not cross.

    Headroom does not return on a timer, so a refusal inside the retry loop
    would become several refusals while the memory is still held. Proven two
    ways because they can fail independently: the taxonomy must declare it
    non-retryable, AND the check must sit outside the loop.
    """
    assert transport_retry_permitted(LLMContentionError("no headroom")) is False

    generous = LLMRetryPolicy(max_attempts=5, initial_backoff_s=0.01, max_backoff_s=0.02, budget_s=5.0)
    with serving_agent(lane=_SIZED_LANE) as service, pytest.raises(LLMContentionError):
        asyncio.run(_client(tmp_path, profile=_STARVED, residents=(), retry_policy=generous).complete(_request()))

    assert service.lookups == [ModelRole.TEXT_EXTRACTION]
    assert service.runs == []


def test_the_refusal_names_the_authority_s_own_causes_and_the_catalogue_size(tmp_path: Path) -> None:
    """The error carries the authority's verdict for the lane's model at its catalogue size."""
    resident = RuntimeResident(name=_SIZED_LANE.model, size_bytes=_GIB, size_vram_bytes=_GIB)
    snapshot = assess_model_load_contention(
        _SIZED_LANE.model,
        _SIZE_BYTES,
        profile=_STARVED,
        residents=(resident,),
    )

    with serving_agent(lane=_SIZED_LANE), pytest.raises(LLMContentionError) as refusal:
        asyncio.run(_client(tmp_path, profile=_STARVED, residents=(resident,)).complete(_request()))

    assert snapshot.admitted is False
    assert snapshot.precondition_verdict is not None
    assert refusal.value.terminal_precondition_verdict == snapshot.precondition_verdict
    assert snapshot.causes, "the authority refused without naming a cause, so there is nothing to carry"
    assert refusal.value.context == {
        "model": _SIZED_LANE.model,
        "contention_causes": tuple(cause.value for cause in snapshot.causes),
    }


def test_an_off_host_lane_is_not_headroom_checked(tmp_path: Path) -> None:
    """A hosted model's weights never touch this machine's memory.

    Asserted through the client's own guard on the same stated size, so the
    lane's ``reads_off_host`` flag is the only difference between the refusal
    and the silence.
    """
    starved = _profile(free_vram_bytes=0, free_ram_bytes=0)
    client = _client(tmp_path, profile=starved, residents=())
    off_host = DEFAULT_LANE.model_copy(update={"size_bytes": _SIZE_BYTES})

    with pytest.raises(LLMContentionError):
        client._require_load_headroom(_SIZED_LANE)
    client._require_load_headroom(off_host)


@pytest.mark.parametrize("size_bytes", [None, 0])
def test_an_unknown_size_skips_the_memory_check_and_still_takes_the_slot(
    tmp_path: Path, size_bytes: int | None
) -> None:
    """The catalogue's size is the requirement, and an entry that states none makes no claim.

    Inventing a requirement is worse than not checking, because an unknown
    requirement read as zero flows into the authority as the amount the model
    needs and returns ADMITTED on evidence nobody has. The memory check is
    skipped; the occupancy bound is not, because the load still happens here.
    """
    unknown = ON_HOST_LANE.model_copy(update={"size_bytes": size_bytes})
    starved = _profile(free_vram_bytes=0, free_ram_bytes=0)
    client = _client(tmp_path, profile=starved, residents=())
    held_during_run: list[int] = []

    def answer(body: ModelRunBody) -> str:
        del body
        held_during_run.append(_on_host_inference_arena(client.settings).held)
        return "agent completion"

    with serving_agent(lane=unknown, answer=answer) as service:
        response = asyncio.run(client.complete(_request()))

    assert response.text == "agent completion"
    assert len(service.runs) == 1
    assert held_during_run == [1], "an on-host run of unknown size must still hold an inference slot"


def _assert_agrees(client: LLMClient, lane: ModelRunLane, expected: ContentionSnapshot) -> None:
    with serving_agent(lane=lane, replies=("agent completion",)) as service:
        if expected.admitted:
            response = asyncio.run(client.complete(_request()))
            assert response.text == "agent completion"
            assert len(service.runs) == 1
        else:
            with pytest.raises(LLMContentionError):
                asyncio.run(client.complete(_request()))
            assert service.runs == []


def test_the_dispatch_agrees_with_the_live_authority_on_this_machine(tmp_path: Path) -> None:
    """Live fire: whatever THIS machine measures, the dispatch obeys it.

    Carries the module's own marker rather than an integration one: the probe
    reads this host's memory and accelerator and the runtime on loopback, so it
    reaches no external service.

    Written as agreement with the authority rather than as a hardcoded verdict
    because the verdict is a property of the box.
    """
    profile = probe_hardware_profile()
    residents = read_runtime_residents()
    expected = assess_model_load_contention(
        _SIZED_LANE.model,
        _SIZE_BYTES,
        profile=profile,
        residents=residents,
        residents_measured=residents is not None,
    )
    client = _client(tmp_path, profile=profile, residents=residents, residents_measured=residents is not None)

    _assert_agrees(client, _SIZED_LANE, expected)
