"""Real-behavior tests for the hardware profile and the live contention snapshot.

Two seams keep these tests honest without a single mock. Hardware figures arrive
as injected :class:`~application.provisioning.SystemMemoryReading` /
:class:`~application.provisioning.AcceleratorReading` **measurements** through
the probe's own arguments, so every branch runs the production model
construction and the production comparison logic -- nothing about this host's
actual GPU state (which changes minute to minute under an automation fleet) can reach
the assertions. Runtime interaction runs against a real
:class:`~http.server.ThreadingHTTPServer` speaking the runtime's wire shape, so
the ``/api/ps`` read exercises real HTTP through real ``httpx``.

Every refusal case carries a positive control asserting the permit case passes
through the same call, so a refusal cannot pass for the wrong reason.
"""

from __future__ import annotations

from http import HTTPStatus
from queue import Queue
from typing import ClassVar, override

import pytest

from ...core.config import override_settings
from ...core.hardware import AcceleratorKind, ContentionCause
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
    SystemMemoryReading,
    probe_hardware_profile,
    probe_local_inference_hardware,
    read_system_memory,
)
from ..provisioning_runtime import (
    RuntimeResident,
    assess_model_load_contention,
    read_runtime_residents,
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
        "synthetic-resident:small",
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
        "synthetic-resident:small",
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
        "synthetic-resident:small",
        3 * GIB,
        profile=_profile(kind=AcceleratorKind.NVIDIA_CUDA, devices=(_device(0, total=16 * GIB, free=None),)),
        residents=(),
    )
    assert snapshot.admitted is False
    assert snapshot.causes == (ContentionCause.UNREADABLE,)


def test_cpu_only_machine_is_judged_against_free_system_memory() -> None:
    """A measured-zero-device machine binds on RAM, and both directions are exercised."""
    admitted = assess_model_load_contention(
        "synthetic-text:small",
        2 * GIB,
        profile=_profile(kind=AcceleratorKind.NONE, free_ram=16 * GIB),
        residents=(),
    )
    assert admitted.admitted is True
    assert admitted.binding_free_bytes == 16 * GIB

    refused = assess_model_load_contention(
        "synthetic-text:small",
        2 * GIB,
        profile=_profile(kind=AcceleratorKind.NONE, free_ram=1 * GIB),
        residents=(),
    )
    assert refused.admitted is False


def test_cpu_only_machine_with_unreadable_free_memory_refuses() -> None:
    """Even a measured-zero-device machine refuses when its free RAM is unknown."""
    snapshot = assess_model_load_contention(
        "synthetic-text:small",
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


def test_shortfall_explained_by_the_runtime_residents_is_attributed_to_them() -> None:
    """Memory the runtime holds is attributed to its residents, not to a peer."""
    with override_settings(
        cadrumo_llm_contention_safety_margin_bytes=0,
    ):
        snapshot = assess_model_load_contention(
            "synthetic-load:large",
            8 * GIB,
            profile=_profile(
                kind=AcceleratorKind.NVIDIA_CUDA,
                devices=(_device(0, total=16 * GIB, free=4 * GIB),),
            ),
            residents=(RuntimeResident(name="synthetic-resident:small", size_bytes=5 * GIB, size_vram_bytes=5 * GIB),),
        )
    assert snapshot.admitted is False
    assert snapshot.causes == (ContentionCause.RUNTIME_RESIDENT,)
    assert snapshot.precondition_verdict is not None


def test_shortfall_unexplained_by_residents_is_attributed_to_a_peer_process() -> None:
    """Memory no resident holds is a peer's."""
    with override_settings(cadrumo_llm_contention_safety_margin_bytes=0):
        snapshot = assess_model_load_contention(
            "synthetic-load:large",
            8 * GIB,
            profile=_profile(
                kind=AcceleratorKind.NVIDIA_CUDA,
                devices=(_device(0, total=16 * GIB, free=4 * GIB),),
            ),
            residents=(),
        )
    assert snapshot.admitted is False
    assert snapshot.causes == (ContentionCause.PEER_PROCESS,)
    peer_attributed_bytes = snapshot.facts["peer_attributed_bytes"]
    assert isinstance(peer_attributed_bytes, int)
    assert peer_attributed_bytes > 0
    assert snapshot.precondition_verdict is not None


def test_a_partially_explained_shortfall_names_both_causes_and_both_remediations() -> None:
    """Residents that help but do not cover it must not read as a complete remedy."""
    with override_settings(
        cadrumo_llm_contention_safety_margin_bytes=0,
    ):
        snapshot = assess_model_load_contention(
            "synthetic-load:large",
            10 * GIB,
            profile=_profile(
                kind=AcceleratorKind.NVIDIA_CUDA,
                devices=(_device(0, total=16 * GIB, free=2 * GIB),),
            ),
            residents=(RuntimeResident(name="synthetic-resident:small", size_bytes=3 * GIB, size_vram_bytes=3 * GIB),),
        )
    assert snapshot.admitted is False
    assert snapshot.causes == (ContentionCause.RUNTIME_RESIDENT, ContentionCause.PEER_PROCESS)
    assert snapshot.resident_attributed_bytes == 3 * GIB
    peer_attributed_bytes = snapshot.facts["peer_attributed_bytes"]
    assert isinstance(peer_attributed_bytes, int)
    assert peer_attributed_bytes > 0


def test_an_unreadable_resident_set_refuses_even_though_the_shortfall_is_measured() -> None:
    """A measured shortfall with no attribution input refuses rather than blaming a peer."""
    with override_settings(cadrumo_llm_contention_safety_margin_bytes=0):
        snapshot = assess_model_load_contention(
            "synthetic-load:large",
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
            "synthetic-load:large",
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
# the runtime read, over real HTTP
# ---------------------------------------------------------------------------


class _RuntimeLoopbackHandler(SilentLoopbackHandler):
    """A real local endpoint speaking the model runtime's ``/api/ps`` and release wire shape.

    ``/api/ps`` reports RESIDENCY -- what is loaded on the device right now --
    which is a management fact rather than an inference reply, so the bodies
    stay local here while the plumbing is shared.
    """

    residents: ClassVar[list[dict[str, object]]] = []
    installed: ClassVar[list[dict[str, object]]] = []
    events: ClassVar[Queue[dict[str, object]]]

    @override
    def do_GET(self) -> None:
        self.events.put({"method": "GET", "path": self.path})
        inventory = self.installed if self.path == "/api/tags" else self.residents
        write_json_response(self, {"models": list(inventory)}, status=HTTPStatus.OK)

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
    _RuntimeLoopbackHandler.installed = []
    with serving_loopback(_RuntimeLoopbackHandler, path="/api/chat") as chat_url:
        yield (chat_url, events)


def test_resident_set_is_read_from_the_runtime_ps_endpoint(runtime: tuple[str, Queue[dict[str, object]]]) -> None:
    """The read hits ``/api/ps`` and parses the runtime's own attribution figures."""
    chat_url, events = runtime
    _RuntimeLoopbackHandler.residents = [{"name": "synthetic-resident:small", "size": 4 * GIB, "size_vram": 3 * GIB}]
    with override_settings(cadrumo_llm_ollama_chat_url=chat_url):
        residents = read_runtime_residents()
    assert residents == (RuntimeResident(name="synthetic-resident:small", size_bytes=4 * GIB, size_vram_bytes=3 * GIB),)
    assert events.get_nowait() == {"method": "GET", "path": "/api/ps"}


def test_an_unreachable_runtime_reads_as_unmeasured_not_as_empty() -> None:
    """``None`` and ``()`` are different states and the unreachable case must yield ``None``."""
    with override_settings(cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat"):
        assert read_runtime_residents() is None
