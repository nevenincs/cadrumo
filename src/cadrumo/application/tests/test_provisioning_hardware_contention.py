"""Real-behavior tests for the hardware profile and the live contention snapshot.

Two seams keep these tests honest without a single mock. Hardware figures arrive
as injected :class:`~application.provisioning.SystemMemoryReading` /
:class:`~application.provisioning.AcceleratorReading` **measurements** through
the probe's own arguments, so every branch runs the production model
construction and the production comparison logic -- nothing about this host's
actual GPU state (which changes minute to minute under an agent fleet) can reach
the assertions. Runtime interaction runs against a real
:class:`~http.server.ThreadingHTTPServer` speaking the runtime's wire shape, so
the ``/api/ps`` read and the unload request exercise real HTTP through real
``httpx``.

Every refusal case carries a positive control asserting the permit case passes
through the same call, so a refusal cannot pass for the wrong reason.
"""

from __future__ import annotations

from http import HTTPStatus
from queue import Queue
from typing import ClassVar, override

import pytest

from ...core import AcceleratorKind, ContentionCause
from ...core.model_catalogue import ModelRole
from ...core.config import override_settings
from ...tests.loopback_llm import (
    SilentLoopbackHandler,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from ..provisioning import (
    AcceleratorDevice,
    AcceleratorReading,
    HardwareProfile,
    RuntimeResident,
    SystemMemoryReading,
    assess_model_load_contention,
    cadrumo_selected_models,
    probe_hardware_profile,
    probe_local_inference_hardware,
    pull_runtime_model,
    read_runtime_residents,
    read_system_memory,
    select_model_for_role,
    unload_runtime_model,
    verify_model_ready,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

GIB = 1024**3


# ---------------------------------------------------------------------------
# Injected-measurement helpers
# ---------------------------------------------------------------------------


def _profile(
    *,
    kind: AcceleratorKind,
    devices: tuple[AcceleratorDevice, ...] = (),
    total_ram: int | None = 32 * GIB,
    free_ram: int | None = 16 * GIB,
) -> HardwareProfile:
    """Compose a profile from injected measurements, never from this host."""
    return probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=total_ram, free_bytes=free_ram),
        accelerator=AcceleratorReading(kind=kind, devices=devices),
    )


def _device(index: int, *, total: int | None, free: int | None) -> AcceleratorDevice:
    return AcceleratorDevice(index=index, name=f"card-{index}", total_vram_bytes=total, free_vram_bytes=free)


# ---------------------------------------------------------------------------
# the hardware profile
# ---------------------------------------------------------------------------


def test_live_system_memory_reading_returns_a_typed_pair() -> None:
    """The live platform reader answers a typed reading with non-negative or absent figures."""
    reading = read_system_memory()
    assert isinstance(reading, SystemMemoryReading)
    for value in (reading.total_bytes, reading.free_bytes):
        assert value is None or value >= 0
    if reading.total_bytes is not None and reading.free_bytes is not None:
        assert reading.free_bytes <= reading.total_bytes


def test_total_vram_sums_devices_but_free_vram_takes_the_largest_single_device() -> None:
    """Totals aggregate for reporting; free VRAM never sums, because a model loads onto one device."""
    profile = _profile(
        kind=AcceleratorKind.NVIDIA_CUDA,
        devices=(_device(0, total=8 * GIB, free=3 * GIB), _device(1, total=8 * GIB, free=2 * GIB)),
    )
    assert profile.total_vram_bytes == 16 * GIB
    # The defect this asserts against: 3 + 2 = 5 GiB is capacity no allocation
    # can reach, and admitting a 4 GiB model on it is the overflow.
    assert profile.free_vram_bytes == 3 * GIB


def test_total_vram_is_unreadable_when_any_device_total_is_unreadable() -> None:
    """A partially readable device set yields no total, rather than a silently short one."""
    profile = _profile(
        kind=AcceleratorKind.NVIDIA_CUDA,
        devices=(_device(0, total=8 * GIB, free=3 * GIB), _device(1, total=None, free=None)),
    )
    assert profile.total_vram_bytes is None
    # The readable device still bounds what can be acted on.
    assert profile.free_vram_bytes == 3 * GIB


def test_free_vram_is_none_when_no_device_reports_a_free_figure() -> None:
    """An enumerated but unreadable device set reports unknown, never zero and never plenty."""
    profile = _profile(kind=AcceleratorKind.NVIDIA_CUDA, devices=(_device(0, total=None, free=None),))
    assert profile.free_vram_bytes is None


def test_absent_accelerator_reports_no_vram_on_either_axis() -> None:
    """A measured-zero-device machine carries no VRAM figures at all."""
    profile = _profile(kind=AcceleratorKind.NONE)
    assert profile.total_vram_bytes is None
    assert profile.free_vram_bytes is None


@pytest.mark.parametrize(
    "kind",
    [AcceleratorKind.NONE, AcceleratorKind.NVIDIA_CUDA, AcceleratorKind.UNKNOWN],
)
def test_diagnostic_row_stays_available_on_every_accelerator_kind(kind: AcceleratorKind) -> None:
    """Reporting fails OPEN: no accelerator kind turns the diagnostic row into a shortfall."""
    status = probe_local_inference_hardware(_profile(kind=kind))
    assert status.service == "local-inference-hardware"
    assert status.available is True


def test_diagnostic_row_renders_unreadable_figures_as_unverified() -> None:
    """Unknown is shown as unverified on the row, never as a number and never as a refusal."""
    status = probe_local_inference_hardware(
        _profile(kind=AcceleratorKind.UNKNOWN, total_ram=None, free_ram=None),
    )
    assert status.available is True
    assert status.facts["accelerator_kind"] == "unknown"
    assert status.precondition_verdict is None


def test_diagnostic_row_renders_measured_figures_as_numbers() -> None:
    """Positive control for the row: a fully measured machine shows figures, not unverified."""
    status = probe_local_inference_hardware(
        _profile(kind=AcceleratorKind.NVIDIA_CUDA, devices=(_device(0, total=16 * GIB, free=4 * GIB),)),
    )
    assert status.facts["accelerator_kind"] == "nvidia_cuda"
    assert status.facts["total_vram_bytes"] == 16 * GIB
    assert status.facts["free_vram_bytes"] == 4 * GIB
    assert status.precondition_verdict is None


# ---------------------------------------------------------------------------
# acting fails closed where reporting fails open
# ---------------------------------------------------------------------------


def test_unreadable_accelerator_refuses_the_load() -> None:
    """The fail-closed core: an unmeasurable machine must not be admitted."""
    snapshot = assess_model_load_contention(
        "qwen2.5vl:3b",
        3 * GIB,
        profile=_profile(kind=AcceleratorKind.UNKNOWN),
        residents=(),
        settings=None,
    )
    assert snapshot.admitted is False
    assert snapshot.causes == (ContentionCause.UNREADABLE,)
    assert snapshot.precondition_verdict is not None
    assert snapshot.precondition_verdict.failed_condition_id == "provisioning.load_headroom.measurable"


def test_measured_headroom_admits_the_load() -> None:
    """Positive control for the refusal above: the same call admits on measured headroom."""
    snapshot = assess_model_load_contention(
        "qwen2.5vl:3b",
        3 * GIB,
        profile=_profile(
            kind=AcceleratorKind.NVIDIA_CUDA,
            devices=(_device(0, total=16 * GIB, free=12 * GIB),),
        ),
        residents=(),
    )
    assert snapshot.admitted is True
    assert snapshot.causes == ()
    assert snapshot.shortfall_bytes == 0


def test_readable_accelerator_with_unreadable_free_figure_refuses() -> None:
    """A present-but-unreadable device is unknown headroom, which refuses."""
    snapshot = assess_model_load_contention(
        "qwen2.5vl:3b",
        3 * GIB,
        profile=_profile(kind=AcceleratorKind.NVIDIA_CUDA, devices=(_device(0, total=16 * GIB, free=None),)),
        residents=(),
    )
    assert snapshot.admitted is False
    assert snapshot.causes == (ContentionCause.UNREADABLE,)


def test_cpu_only_machine_is_judged_against_free_system_memory() -> None:
    """A measured-zero-device machine binds on RAM, and both directions are exercised."""
    admitted = assess_model_load_contention(
        "qwen2.5:3b",
        2 * GIB,
        profile=_profile(kind=AcceleratorKind.NONE, free_ram=16 * GIB),
        residents=(),
    )
    assert admitted.admitted is True
    assert admitted.binding_free_bytes == 16 * GIB

    refused = assess_model_load_contention(
        "qwen2.5:3b",
        2 * GIB,
        profile=_profile(kind=AcceleratorKind.NONE, free_ram=1 * GIB),
        residents=(),
    )
    assert refused.admitted is False


def test_cpu_only_machine_with_unreadable_free_memory_refuses() -> None:
    """Even a measured-zero-device machine refuses when its free RAM is unknown."""
    snapshot = assess_model_load_contention(
        "qwen2.5:3b",
        2 * GIB,
        profile=_profile(kind=AcceleratorKind.NONE, free_ram=None),
        residents=(),
    )
    assert snapshot.admitted is False
    assert snapshot.causes == (ContentionCause.UNREADABLE,)


def test_the_safety_margin_is_part_of_the_compared_figure() -> None:
    """A load that fits the requirement but not the margin is refused, and lowering the margin admits it."""
    profile = _profile(kind=AcceleratorKind.NVIDIA_CUDA, devices=(_device(0, total=16 * GIB, free=3 * GIB),))
    with override_settings(cadrumo_llm_contention_safety_margin_bytes=GIB):
        refused = assess_model_load_contention("m", 3 * GIB, profile=profile, residents=())
    assert refused.admitted is False
    assert refused.required_bytes == 4 * GIB

    with override_settings(cadrumo_llm_contention_safety_margin_bytes=0):
        admitted = assess_model_load_contention("m", 3 * GIB, profile=profile, residents=())
    assert admitted.admitted is True


def test_the_override_admits_an_unmeasurable_machine_but_never_a_measured_shortfall() -> None:
    """The escape hatch is scoped to 'could not tell', not to 'measured, and it does not fit'."""
    with override_settings(cadrumo_llm_contention_check_override=True):
        unmeasurable = assess_model_load_contention(
            "m",
            3 * GIB,
            profile=_profile(kind=AcceleratorKind.UNKNOWN),
            residents=(),
        )
        measured_shortfall = assess_model_load_contention(
            "m",
            3 * GIB,
            profile=_profile(
                kind=AcceleratorKind.NVIDIA_CUDA,
                devices=(_device(0, total=16 * GIB, free=1 * GIB),),
            ),
            residents=(),
        )
    assert unmeasurable.admitted is True
    assert measured_shortfall.admitted is False


# ---------------------------------------------------------------------------
# attribution: our residents versus a peer process
# ---------------------------------------------------------------------------


def test_shortfall_explained_by_our_residents_names_the_unload_remediation() -> None:
    """Memory our runtime holds is reclaimable, and the refusal says to unload it."""
    with override_settings(
        cadrumo_llm_ollama_vision_model="qwen2.5vl:3b",
        cadrumo_llm_contention_safety_margin_bytes=0,
    ):
        snapshot = assess_model_load_contention(
            "qwen2.5vl:7b",
            8 * GIB,
            profile=_profile(
                kind=AcceleratorKind.NVIDIA_CUDA,
                devices=(_device(0, total=16 * GIB, free=4 * GIB),),
            ),
            residents=(RuntimeResident(name="qwen2.5vl:3b", size_bytes=5 * GIB, size_vram_bytes=5 * GIB),),
        )
    assert snapshot.admitted is False
    assert snapshot.causes == (ContentionCause.RUNTIME_RESIDENT,)
    assert snapshot.unloadable_models == ("qwen2.5vl:3b",)
    assert snapshot.facts["unloadable_model_count"] == 1
    assert snapshot.precondition_verdict is not None


def test_shortfall_unexplained_by_residents_is_attributed_to_a_peer_process() -> None:
    """Memory nothing of ours holds is a peer's, and the refusal must not say 'unload'."""
    with override_settings(cadrumo_llm_contention_safety_margin_bytes=0):
        snapshot = assess_model_load_contention(
            "qwen2.5vl:7b",
            8 * GIB,
            profile=_profile(
                kind=AcceleratorKind.NVIDIA_CUDA,
                devices=(_device(0, total=16 * GIB, free=4 * GIB),),
            ),
            residents=(),
        )
    assert snapshot.admitted is False
    assert snapshot.causes == (ContentionCause.PEER_PROCESS,)
    assert snapshot.unloadable_models == ()
    peer_attributed_bytes = snapshot.facts["peer_attributed_bytes"]
    assert isinstance(peer_attributed_bytes, int)
    assert peer_attributed_bytes > 0
    assert snapshot.precondition_verdict is not None


def test_a_partially_explained_shortfall_names_both_causes_and_both_remediations() -> None:
    """Residents that help but do not cover it must not read as a complete remedy."""
    with override_settings(
        cadrumo_llm_ollama_vision_model="qwen2.5vl:3b",
        cadrumo_llm_contention_safety_margin_bytes=0,
    ):
        snapshot = assess_model_load_contention(
            "qwen2.5vl:7b",
            10 * GIB,
            profile=_profile(
                kind=AcceleratorKind.NVIDIA_CUDA,
                devices=(_device(0, total=16 * GIB, free=2 * GIB),),
            ),
            residents=(RuntimeResident(name="qwen2.5vl:3b", size_bytes=3 * GIB, size_vram_bytes=3 * GIB),),
        )
    assert snapshot.admitted is False
    assert snapshot.causes == (ContentionCause.RUNTIME_RESIDENT, ContentionCause.PEER_PROCESS)
    assert snapshot.resident_attributed_bytes == 3 * GIB
    assert snapshot.facts["unloadable_model_count"] == 1
    peer_attributed_bytes = snapshot.facts["peer_attributed_bytes"]
    assert isinstance(peer_attributed_bytes, int)
    assert peer_attributed_bytes > 0


def test_a_resident_cadrumo_did_not_select_is_reported_but_never_offered_for_unload() -> None:
    """The runtime holding it does not make it ours to evict."""
    with override_settings(
        cadrumo_llm_ollama_vision_model="qwen2.5vl:3b",
        cadrumo_llm_ollama_text_model="qwen2.5:3b",
        cadrumo_llm_contention_safety_margin_bytes=0,
    ):
        snapshot = assess_model_load_contention(
            "qwen2.5vl:7b",
            8 * GIB,
            profile=_profile(
                kind=AcceleratorKind.NVIDIA_CUDA,
                devices=(_device(0, total=16 * GIB, free=4 * GIB),),
            ),
            residents=(RuntimeResident(name="llama3:70b", size_bytes=5 * GIB, size_vram_bytes=5 * GIB),),
        )
    assert snapshot.causes == (ContentionCause.RUNTIME_RESIDENT,)
    assert snapshot.unloadable_models == ()
    assert snapshot.facts["resident_count"] == 1
    assert snapshot.facts["unloadable_model_count"] == 0
    assert snapshot.precondition_verdict is not None


def test_an_unreadable_resident_set_refuses_even_though_the_shortfall_is_measured() -> None:
    """A measured shortfall with no attribution input refuses rather than blaming a peer."""
    with override_settings(cadrumo_llm_contention_safety_margin_bytes=0):
        snapshot = assess_model_load_contention(
            "qwen2.5vl:7b",
            8 * GIB,
            profile=_profile(
                kind=AcceleratorKind.NVIDIA_CUDA,
                devices=(_device(0, total=16 * GIB, free=4 * GIB),),
            ),
            residents=None,
            residents_measured=False,
        )
    assert snapshot.admitted is False
    assert snapshot.causes == (ContentionCause.UNREADABLE,)
    assert snapshot.shortfall_bytes == 4 * GIB


def test_the_motivating_machine_state_refuses() -> None:
    """The live case this was built for: a 16 GiB card with under 4 GiB free must refuse a 7B load."""
    with override_settings(cadrumo_llm_contention_safety_margin_bytes=GIB):
        snapshot = assess_model_load_contention(
            "qwen2.5vl:7b",
            6 * GIB,
            profile=_profile(
                kind=AcceleratorKind.NVIDIA_CUDA,
                devices=(_device(0, total=16 * GIB, free=3 * GIB + GIB // 2),),
                free_ram=48 * GIB,
            ),
            residents=(),
        )
    assert snapshot.admitted is False
    # Ample free RAM must not launder a device shortfall.
    assert snapshot.free_system_memory_bytes == 48 * GIB


# ---------------------------------------------------------------------------
# the runtime read and the unload action, over real HTTP
# ---------------------------------------------------------------------------


class _RuntimeLoopbackHandler(SilentLoopbackHandler):
    """A real local endpoint speaking the model runtime's ``/api/ps`` and release wire shape.

    ``/api/ps`` reports RESIDENCY -- what is loaded on the device right now --
    which is a management fact rather than an inference reply, so the bodies
    stay local here while the plumbing is shared.
    """

    residents: ClassVar[list[dict[str, object]]] = []
    events: ClassVar[Queue[dict[str, object]]]

    @override
    def do_GET(self) -> None:
        self.events.put({"method": "GET", "path": self.path})
        write_json_response(self, {"models": list(self.residents)}, status=HTTPStatus.OK)

    @override
    def do_POST(self) -> None:
        self.events.put({"method": "POST", "path": self.path, "body": dict(read_json_body(self))})
        write_json_response(self, {"done": True}, status=HTTPStatus.OK)


@pytest.fixture
def runtime() -> object:
    """Serve a real runtime endpoint on a loopback port and yield its chat URL and event queue."""
    events: Queue[dict[str, object]] = Queue()
    _RuntimeLoopbackHandler.events = events
    _RuntimeLoopbackHandler.residents = []
    with serving_loopback(_RuntimeLoopbackHandler, path="/api/chat") as chat_url:
        yield (chat_url, events)


def test_resident_set_is_read_from_the_runtime_ps_endpoint(runtime: tuple[str, Queue[dict[str, object]]]) -> None:
    """The read hits ``/api/ps`` and parses the runtime's own attribution figures."""
    chat_url, events = runtime
    _RuntimeLoopbackHandler.residents = [{"name": "qwen2.5vl:3b", "size": 4 * GIB, "size_vram": 3 * GIB}]
    with override_settings(cadrumo_llm_ollama_chat_url=chat_url):
        residents = read_runtime_residents()
    assert residents == (RuntimeResident(name="qwen2.5vl:3b", size_bytes=4 * GIB, size_vram_bytes=3 * GIB),)
    assert events.get(timeout=5) == {"method": "GET", "path": "/api/ps"}


def test_an_unreachable_runtime_reads_as_unmeasured_not_as_empty() -> None:
    """``None`` and ``()`` are different states and the unreachable case must yield ``None``."""
    with override_settings(cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat"):
        assert read_runtime_residents() is None


def test_unload_releases_a_selected_resident_with_a_zero_keep_alive_and_no_prompt(
    runtime: tuple[str, Queue[dict[str, object]]],
) -> None:
    """The release must carry no prompt, so it can never become a load."""
    chat_url, events = runtime
    with override_settings(
        cadrumo_llm_ollama_chat_url=chat_url,
        cadrumo_llm_ollama_vision_model="qwen2.5vl:3b",
    ):
        outcome = unload_runtime_model(
            "qwen2.5vl:3b",
            residents=(RuntimeResident(name="qwen2.5vl:3b", size_bytes=4 * GIB, size_vram_bytes=3 * GIB),),
        )
    assert outcome.unloaded is True
    assert outcome.was_resident is True
    posted = events.get(timeout=5)
    assert posted["method"] == "POST"
    assert posted["body"] == {"model": "qwen2.5vl:3b", "keep_alive": 0}
    body = posted["body"]
    assert isinstance(body, dict)
    assert "prompt" not in body


def test_a_selection_with_no_declared_requirement_declines_to_be_assessed() -> None:
    """An unknown memory requirement must not be assessed as zero.

    Zero is not a neutral placeholder on this path: it reaches
    ``assess_model_load_contention`` as the amount the model needs, so the
    check reports the load ADMITTED against a figure nobody supplied. Three
    call sites derived this guard independently and each missed this fourth
    case, which is why the accessor owns it.

    Mutation that must trip this: return ``(runtime_id, requirement or 0)``.
    """
    selection = select_model_for_role(ModelRole.VISION_TRANSCRIPTION)
    assert selection.candidate is not None, "this host catalogues no vision candidate; the case below is vacuous"
    # Positive control: fully declared, the load is assessable.
    assert selection.assessable_load is not None

    stripped = selection.model_copy(
        update={"candidate": selection.candidate.model_copy(update={"memory_requirement_bytes": None})},
    )

    assert stripped.assessable_load is None, (
        "a candidate declaring no memory requirement must not yield an assessable load; "
        "assessing it would report admitted on evidence nobody has"
    )


def test_unload_refuses_a_model_cadrumo_did_not_select_and_sends_nothing(
    runtime: tuple[str, Queue[dict[str, object]]],
) -> None:
    """Cadrumo never touches what it did not load -- and the guard is proven by silence on the wire."""
    chat_url, events = runtime
    with override_settings(
        cadrumo_llm_ollama_chat_url=chat_url,
        cadrumo_llm_ollama_vision_model="qwen2.5vl:3b",
        cadrumo_llm_ollama_text_model="qwen2.5:3b",
    ):
        outcome = unload_runtime_model(
            "llama3:70b",
            residents=(RuntimeResident(name="llama3:70b", size_bytes=40 * GIB, size_vram_bytes=40 * GIB),),
        )
    assert outcome.unloaded is False
    assert outcome.facts["selected_by_cadrumo"] is False
    assert outcome.precondition_verdict is not None
    assert events.empty(), "a refused unload must not reach the runtime at all"


def test_unload_of_a_non_resident_model_is_a_no_op_and_never_loads_it(
    runtime: tuple[str, Queue[dict[str, object]]],
) -> None:
    """The residency guard is what stops the release call from bringing a model in."""
    chat_url, events = runtime
    with override_settings(
        cadrumo_llm_ollama_chat_url=chat_url,
        cadrumo_llm_ollama_vision_model="qwen2.5vl:3b",
    ):
        outcome = unload_runtime_model("qwen2.5vl:3b", residents=())
    assert outcome.unloaded is False
    assert outcome.was_resident is False
    assert events.empty(), "a non-resident release must not reach the runtime at all"


def test_unload_with_an_unreadable_resident_set_does_nothing(
    runtime: tuple[str, Queue[dict[str, object]]],
) -> None:
    """Unknown residency is not permission to act."""
    chat_url, events = runtime
    with override_settings(
        cadrumo_llm_ollama_chat_url=chat_url,
        cadrumo_llm_ollama_vision_model="qwen2.5vl:3b",
    ):
        outcome = unload_runtime_model("qwen2.5vl:3b", residents=None, residents_measured=False)
    assert outcome.unloaded is False
    assert events.empty()


def test_selected_models_are_exactly_the_configured_roles() -> None:
    """The unload boundary is the configured selection, nothing wider and nothing missed.

    Every role gets a distinct value so an omitted role is visible: a set built
    from only two of the three would still match if the third shared a default
    with one of them, which is exactly the state the shipped defaults are in.
    """
    with override_settings(
        cadrumo_llm_ollama_vision_model="vision-model",
        cadrumo_llm_ollama_text_model="text-model",
        cadrumo_llm_ollama_mapping_model="mapping-model",
    ):
        assert cadrumo_selected_models() == frozenset({"vision-model", "text-model", "mapping-model"})


# ---------------------------------------------------------------------------
# the pull and readiness actions, over real HTTP
# ---------------------------------------------------------------------------


def _roomy_profile() -> HardwareProfile:
    """A machine with headroom to spare, so admission is not the thing under test."""
    return _profile(
        kind=AcceleratorKind.NVIDIA_CUDA,
        devices=(_device(0, total=24 * GIB, free=20 * GIB),),
        total_ram=64 * GIB,
        free_ram=48 * GIB,
    )


def _starved_profile() -> HardwareProfile:
    """A machine measurably short of the requirement, with the shortfall attributable."""
    return _profile(
        kind=AcceleratorKind.NVIDIA_CUDA,
        devices=(_device(0, total=16 * GIB, free=1 * GIB),),
        total_ram=64 * GIB,
        free_ram=48 * GIB,
    )


def _paths(events: Queue[dict[str, object]]) -> list[str]:
    """Drain every request the runtime stub actually received, in order."""
    seen: list[str] = []
    while not events.empty():
        seen.append(str(events.get_nowait()["path"]))
    return seen


def test_a_refused_pull_never_issues_the_fetch(runtime: tuple[str, Queue[dict[str, object]]]) -> None:
    """The admission check runs BEFORE the fetch, and this is the whole point of the action.

    Asserted on the REQUESTS the runtime received rather than on the outcome,
    because an outcome saying ``pulled=False`` is satisfied equally by a pull
    that ran, downloaded gigabytes, and then failed. The claim here is the one
    that matters to an operator's bandwidth: ``/api/pull`` was never called.

    The queue is not empty and must not be asserted so: attributing a shortfall
    requires reading the runtime's resident set, so ``/api/ps`` is expected and
    is part of the check rather than part of the fetch. An earlier version of
    this case asserted an empty queue and failed against correct code.
    """
    chat_url, events = runtime
    with override_settings(cadrumo_llm_ollama_chat_url=chat_url):
        outcome = pull_runtime_model("huge-model:70b", 40 * GIB, profile=_starved_profile())

    assert outcome.pulled is False
    assert outcome.contention is not None
    assert outcome.contention.admitted is False
    assert "/api/pull" not in _paths(events), "a refused pull must not have issued the fetch"


def test_an_admitted_pull_does_issue_the_fetch(runtime: tuple[str, Queue[dict[str, object]]]) -> None:
    """Positive control for the case above.

    Without this, a ``pull_runtime_model`` that refused unconditionally -- or
    that never issued a request under any circumstances -- would satisfy the
    never-fetches assertion and look correct.
    """
    chat_url, events = runtime
    with override_settings(cadrumo_llm_ollama_chat_url=chat_url):
        outcome = pull_runtime_model("small-model:1b", 1 * GIB, profile=_roomy_profile())

    assert outcome.pulled is True
    assert "/api/pull" in _paths(events)


def test_a_pull_against_an_unreachable_runtime_refuses_naming_the_daemon_command() -> None:
    """An unreachable runtime is an instructive refusal, never a spawn.

    Driven against a REAL closed loopback port rather than a patched client, so
    the refusal is produced by an actual failed connection. Port 1 is reserved
    and never listening.
    """
    with override_settings(cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat"):
        outcome = pull_runtime_model("small-model:1b", 1 * GIB, profile=_roomy_profile())

    assert outcome.pulled is False
    assert outcome.contention is None, "this is a transport failure, not an admission refusal"
    assert outcome.facts["runtime_reachable"] is False
    assert outcome.precondition_verdict is not None


def test_a_readiness_check_against_an_unreachable_runtime_refuses_naming_the_daemon_command() -> None:
    """Same boundary on the verify path, and the same real closed port."""
    with override_settings(cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat"):
        outcome = verify_model_ready("small-model:1b")

    assert outcome.ready is False
    assert outcome.answered is False
    assert outcome.facts["runtime_reachable"] is False
    assert outcome.precondition_verdict is not None


def test_a_readiness_check_reports_ready_when_the_runtime_answers(
    runtime: tuple[str, Queue[dict[str, object]]],
) -> None:
    """Positive control for both refusal cases above.

    A verify that reported unready unconditionally would satisfy every refusal
    assertion in this file. This is what distinguishes "refuses correctly" from
    "refuses always".
    """
    chat_url, events = runtime
    _RuntimeLoopbackHandler.residents = [{"name": "small-model:1b", "size": 1 * GIB, "size_vram": 1 * GIB}]
    with override_settings(cadrumo_llm_ollama_chat_url=chat_url):
        outcome = verify_model_ready("small-model:1b")

    assert outcome.ready is True
    assert outcome.answered is True
    assert outcome.resident is True
    assert outcome.elapsed_ms is not None
    assert events.get(timeout=5)["path"] == "/api/ps"
    assert events.get(timeout=5)["path"] == "/api/generate"
