"""The headroom check at the dispatch choke point.

Distinct from the occupancy bound beside it, and the two are easy to confuse.
Occupancy counts how many loads are already running; this measures whether ONE
load fits right now. Either can refuse while the other would admit, so a gate
for one proves nothing about the other.

The verdict is not computed here and is not computed in the client: it comes
from the single contention authority the doctor surface, the provision verbs and
the batch lane already consult. What these cases prove is the WIRING -- that the
dispatch asks, that it obeys the answer, that it asks while holding its slot,
and that a refusal is never re-sent by the retry policy.

Measurements are injected rather than verdicts. A test that supplied the answer
would exercise none of the comparison, the safety margin or the fail-closed arm,
and would pass against a client that never consulted the authority at all.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import override

import pytest

from ...adapters.outbound.llm._cache import LLMCache
from ...adapters.outbound.llm._run_telemetry import LLMRunTelemetryRecorder
from ...adapters.outbound.llm._usage import UsageRecorder
from ...application.provisioning import (
    AcceleratorDevice,
    AcceleratorReading,
    ContentionSnapshot,
    HardwareProfile,
    RuntimeResident,
    SystemMemoryReading,
    assess_model_load_contention,
    probe_hardware_profile,
    read_runtime_residents,
)
from ...core.config import LLMProvider, override_settings
from ...core.hardware import AcceleratorKind, ContentionCause
from ...core.model_catalogue import model_candidate
from ...tests.fixtures.settings import EnvFileFreeSettings
from ...tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from ..client import LLMClient, LLMRetryPolicy, transport_retry_permitted
from ..errors import LLMContentionError
from ..models import LLMRequest
from ._arena_fixtures import _fresh_arena

__all__ = ["_fresh_arena"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

# A catalogued local model, so the catalogue makes a claim about what it needs.
# The check is deliberately silent about a model it has no requirement for, so a
# case using an uncatalogued id would pass without the check ever running.
_CATALOGUED_MODEL = "qwen3:1.7b"

_GIB = 1024**3


def test_the_model_under_test_still_declares_a_memory_requirement() -> None:
    """Anchor the fixture: a catalogue rename would make every case below vacuous.

    The check returns early for a model the catalogue makes no claim about, so
    if this id stopped resolving, every refusal case would pass by never running
    the check at all -- green, and measuring nothing.
    """
    candidate = model_candidate(_CATALOGUED_MODEL)

    assert candidate is not None, (
        f"{_CATALOGUED_MODEL} left the catalogue; the cases below no longer exercise the check"
    )
    assert candidate.memory_requirement_bytes is not None


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


def _declared_requirement_bytes() -> int:
    """Return the catalogue's memory requirement for the model under test."""
    candidate = model_candidate(_CATALOGUED_MODEL)
    assert candidate is not None
    assert candidate.memory_requirement_bytes is not None
    return candidate.memory_requirement_bytes


def _profile(*, free_vram_bytes: int | None, free_ram_bytes: int) -> HardwareProfile:
    """Build a measured hardware reading with the given free figures."""
    return HardwareProfile(
        memory=SystemMemoryReading(total_bytes=64 * _GIB, free_bytes=free_ram_bytes),
        accelerator=AcceleratorReading(
            kind=AcceleratorKind.NVIDIA_CUDA,
            devices=(
                AcceleratorDevice(
                    index=0,
                    name="probe device",
                    total_vram_bytes=8 * _GIB,
                    free_vram_bytes=free_vram_bytes,
                ),
            ),
        ),
    )


@contextmanager
def _serve_ollama() -> Iterator[tuple[str, list[str]]]:
    """Serve a loopback runtime that answers, recording what reached it."""
    arrivals: list[str] = []

    class _Endpoint(SilentLoopbackHandler):
        @override
        def do_POST(self) -> None:
            read_json_body(self)
            arrivals.append(self.path)
            write_json_response(
                self,
                ollama_chat_reply(" local completion ", model=_CATALOGUED_MODEL),
                status=HTTPStatus.OK,
            )

    with serving_loopback(_Endpoint, path="/api/chat") as endpoint:
        yield endpoint, arrivals


def _client(
    tmp_path: Path,
    *,
    profile: HardwareProfile | None = None,
    residents: tuple[RuntimeResident, ...] | None = None,
    residents_measured: bool = True,
    retry_policy: LLMRetryPolicy | None = None,
) -> LLMClient:
    settings = EnvFileFreeSettings(
        cadrumo_llm_provider=LLMProvider.LOCAL,
        cadrumo_llm_model=_CATALOGUED_MODEL,
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_telemetry_dir=tmp_path / "run-telemetry",
    )
    return LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=settings.cadrumo_llm_cache_dir),
        usage_recorder=UsageRecorder(root_dir=settings.cadrumo_llm_usage_dir),
        run_telemetry_recorder=LLMRunTelemetryRecorder(root_dir=settings.cadrumo_llm_run_telemetry_dir),
        retry_policy=retry_policy or LLMRetryPolicy(max_attempts=1),
        hardware_profile=profile,
        runtime_residents=residents,
        runtime_residents_measured=residents_measured,
    )


def test_a_measured_shortfall_refuses_before_the_runtime_is_touched(tmp_path: Path) -> None:
    """The load does not fit: refused at the dispatch point, nothing sent."""
    starved = _profile(free_vram_bytes=256 * 1024**2, free_ram_bytes=48 * _GIB)
    with _serve_ollama() as (endpoint, arrivals):
        with (
            override_settings(cadrumo_llm_ollama_chat_url=endpoint),
            pytest.raises(LLMContentionError) as refusal,
        ):
            asyncio.run(_client(tmp_path, profile=starved, residents=()).complete(LLMRequest(prompt="hello")))

        # Admission control, not a post-hoc failure: refusing after the runtime
        # began loading would have already spent the memory being protected.
        assert arrivals == []

    # A measured shortfall with a readable, empty resident set is attributed
    # OUTSIDE this runtime -- there is nothing of ours to unload -- and that is
    # a different remediation from an unmeasurable one.
    causes = _causes(refusal.value)
    assert ContentionCause.PEER_PROCESS.value in causes
    assert ContentionCause.UNREADABLE.value not in causes


def test_a_post_quiesce_reading_admits_the_same_request(tmp_path: Path) -> None:
    """The positive control, and the case that separates the two refusal arms.

    Same client, same model, same server -- only the measurement differs. Without
    it, a refusal is indistinguishable from a dispatch that could not have
    succeeded anyway, and on this machine that ambiguity is real rather than
    theoretical: free VRAM sits below the operator threshold and the runtime is
    usually down, so BOTH the shortfall arm and the fail-closed arm hold at once
    and a live refusal proves neither.
    """
    quiesced = _profile(free_vram_bytes=7 * _GIB, free_ram_bytes=48 * _GIB)
    with _serve_ollama() as (endpoint, arrivals), override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        response = asyncio.run(_client(tmp_path, profile=quiesced, residents=()).complete(LLMRequest(prompt="hello")))

    assert response.text == "local completion"
    assert arrivals == ["/api/chat"]


def test_an_unmeasurable_headroom_fails_closed(tmp_path: Path) -> None:
    """ "Could not tell" is not evidence of headroom, and it is a DIFFERENT refusal.

    The accelerator is present but its free figure could not be read, while
    system memory is abundant. Abundant RAM is not the arena the weights load
    into, so the refusal must stand: this is the exact state that destroys
    running work on a machine whose device memory nobody could measure.

    Distinguished by cause rather than by the refusal alone. A gate asserting
    only that something was refused would pass here for the shortfall reason and
    on a starved box for this one, and would never notice if the fail-closed arm
    were removed entirely.
    """
    unmeasurable = _profile(free_vram_bytes=None, free_ram_bytes=48 * _GIB)
    with _serve_ollama() as (endpoint, arrivals):
        with (
            override_settings(cadrumo_llm_ollama_chat_url=endpoint),
            pytest.raises(LLMContentionError) as refusal,
        ):
            asyncio.run(_client(tmp_path, profile=unmeasurable, residents=()).complete(LLMRequest(prompt="hello")))

        assert arrivals == []

    causes = _causes(refusal.value)
    assert ContentionCause.UNREADABLE.value in causes
    assert ContentionCause.PEER_PROCESS.value not in causes, (
        "an unmeasurable reading was attributed to a peer process; the two carry different remediations"
    )


def test_an_unreadable_resident_set_cannot_admit_a_measured_shortfall(tmp_path: Path) -> None:
    """A shortfall the runtime cannot explain is still a shortfall.

    The second fail-closed arm, and the one easier to get wrong: when free
    memory IS measurable and short, an unreadable resident set removes only the
    ATTRIBUTION, never the shortfall. Admitting here because the cause could not
    be determined would be the fail-open inversion of the whole check.
    """
    starved = _profile(free_vram_bytes=256 * 1024**2, free_ram_bytes=48 * _GIB)
    with _serve_ollama() as (endpoint, arrivals):
        with (
            override_settings(cadrumo_llm_ollama_chat_url=endpoint),
            pytest.raises(LLMContentionError) as refusal,
        ):
            asyncio.run(
                _client(tmp_path, profile=starved, residents=None, residents_measured=False).complete(
                    LLMRequest(prompt="hello")
                )
            )

        assert arrivals == []

    assert ContentionCause.UNREADABLE.value in _causes(refusal.value)


def test_an_unmeasurable_headroom_and_a_measured_shortfall_are_not_the_same_refusal(tmp_path: Path) -> None:
    """The discrimination stated directly, since the two arms share an exception type."""
    starved = _profile(free_vram_bytes=256 * 1024**2, free_ram_bytes=48 * _GIB)
    unmeasurable = _profile(free_vram_bytes=None, free_ram_bytes=48 * _GIB)

    with _serve_ollama() as (endpoint, _arrivals), override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        with pytest.raises(LLMContentionError) as shortfall:
            asyncio.run(_client(tmp_path / "a", profile=starved, residents=()).complete(LLMRequest(prompt="hello")))
        with pytest.raises(LLMContentionError) as unreadable:
            asyncio.run(
                _client(tmp_path / "b", profile=unmeasurable, residents=()).complete(LLMRequest(prompt="hello"))
            )

    shortfall_verdict = shortfall.value.terminal_precondition_verdict
    unreadable_verdict = unreadable.value.terminal_precondition_verdict
    assert shortfall_verdict is not None
    assert unreadable_verdict is not None
    assert shortfall_verdict.failed_condition_id == "provisioning.load_capacity.available"
    assert unreadable_verdict.failed_condition_id == "provisioning.load_headroom.measurable"
    assert shortfall_verdict.failed_condition_id != unreadable_verdict.failed_condition_id


def test_a_contention_refusal_is_sent_once_and_never_retried(tmp_path: Path) -> None:
    """The boundary the retry policy must not cross.

    Headroom does not return on a timer, so a refusal inside the retry loop
    would become several refusals while the memory is still held. Proven two
    ways because they can fail independently: the taxonomy must declare it
    non-retryable, AND the check must sit outside the loop, so a retryable
    declaration alone could not re-send it and neither could a generous policy.
    """
    assert transport_retry_permitted(LLMContentionError("no headroom")) is False

    starved = _profile(free_vram_bytes=256 * 1024**2, free_ram_bytes=48 * _GIB)
    generous = LLMRetryPolicy(max_attempts=5, initial_backoff_s=0.01, max_backoff_s=0.02, budget_s=5.0)
    with _serve_ollama() as (endpoint, arrivals):
        with (
            override_settings(cadrumo_llm_ollama_chat_url=endpoint),
            pytest.raises(LLMContentionError),
        ):
            asyncio.run(
                _client(tmp_path, profile=starved, residents=(), retry_policy=generous).complete(
                    LLMRequest(prompt="hello")
                )
            )

        assert arrivals == []


def test_the_refusal_names_the_authority_s_own_causes(tmp_path: Path) -> None:
    """The error carries the authority's typed verdict, model, and causes."""
    resident = RuntimeResident(name=_CATALOGUED_MODEL, size_bytes=2 * _GIB, size_vram_bytes=2 * _GIB)
    starved = _profile(free_vram_bytes=256 * 1024**2, free_ram_bytes=48 * _GIB)
    snapshot = assess_model_load_contention(
        _CATALOGUED_MODEL,
        _declared_requirement_bytes(),
        profile=starved,
        residents=(resident,),
    )

    with (
        _serve_ollama() as (endpoint, _arrivals),
        override_settings(cadrumo_llm_ollama_chat_url=endpoint),
        pytest.raises(LLMContentionError) as refusal,
    ):
        asyncio.run(_client(tmp_path, profile=starved, residents=(resident,)).complete(LLMRequest(prompt="hello")))

    assert snapshot.admitted is False
    assert snapshot.precondition_verdict is not None
    assert refusal.value.terminal_precondition_verdict == snapshot.precondition_verdict
    assert snapshot.causes, "the authority refused without naming a cause, so there is nothing to carry"
    assert refusal.value.context == {
        "model": _CATALOGUED_MODEL,
        "contention_causes": tuple(cause.value for cause in snapshot.causes),
    }


def test_an_off_host_dispatch_is_not_headroom_checked(tmp_path: Path) -> None:
    """A hosted model's weights never touch this machine's memory.

    Asserted through the client's own guard rather than by dispatching at a
    vendor: the point is that the check does not run, and a real cloud call is
    what this repository must never make in a test.
    """
    starved = _profile(free_vram_bytes=0, free_ram_bytes=0)
    client = _client(tmp_path, profile=starved, residents=())

    # Would refuse on-host with these readings; must be silent off-host.
    with pytest.raises(LLMContentionError):
        client._require_load_headroom(LLMProvider.LOCAL, _CATALOGUED_MODEL)
    client._require_load_headroom(LLMProvider.OPENAI, _CATALOGUED_MODEL)


def test_an_uncatalogued_model_is_not_assessed(tmp_path: Path) -> None:
    """The catalogue's claim is the requirement, and there is none for an unknown id.

    Deliberate and worth stating plainly: this is the one direction the check
    does not cover. Inventing a requirement is worse than not checking, because
    an unknown requirement read as zero flows into the authority as the amount
    the model needs and returns ADMITTED on evidence nobody has.
    """
    starved = _profile(free_vram_bytes=0, free_ram_bytes=0)
    client = _client(tmp_path, profile=starved, residents=())

    assert model_candidate("an-operator-chosen-model") is None
    client._require_load_headroom(LLMProvider.LOCAL, "an-operator-chosen-model")


def test_the_dispatch_agrees_with_the_live_authority_on_this_machine(tmp_path: Path) -> None:
    """Live fire: whatever THIS machine measures, the dispatch obeys it.

    Carries the module's own marker rather than an integration one: the probe
    reads this host's memory and accelerator and the runtime on loopback, so it
    reaches no external service.

    Written as agreement with the authority rather than as a hardcoded verdict
    because the verdict is a property of the box. A case asserting "refuses"
    would pass here and fail on a machine with headroom, and a case asserting
    "admits" would do the reverse -- neither would be testing the wiring, which
    is the only thing this layer owns.
    """
    profile = probe_hardware_profile()
    residents = read_runtime_residents()
    requirement = _declared_requirement_bytes()
    expected = assess_model_load_contention(
        _CATALOGUED_MODEL,
        requirement,
        profile=profile,
        residents=residents,
        residents_measured=residents is not None,
    )
    assert isinstance(expected, ContentionSnapshot)

    with _serve_ollama() as (endpoint, arrivals), override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        client = _client(
            tmp_path,
            profile=profile,
            residents=residents,
            residents_measured=residents is not None,
        )
        if expected.admitted:
            response = asyncio.run(client.complete(LLMRequest(prompt="hello")))
            assert response.text == "local completion"
            assert arrivals == ["/api/chat"]
        else:
            with pytest.raises(LLMContentionError):
                asyncio.run(client.complete(LLMRequest(prompt="hello")))
            assert arrivals == []
