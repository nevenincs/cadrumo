"""Canonical local-runtime lifecycle operations for model provisioning."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from time import monotonic
from typing import TYPE_CHECKING, TypedDict, cast

import httpx
from pydantic import BaseModel, Field, model_validator

from ..core import STRICT_FROZEN_CONFIG, AcceleratorKind, ContentionCause
from ..core.config import Settings, load_settings
from ._provisioning_contracts import (
    OLLAMA_PROBE_CACHE_TTL_S,
    OLLAMA_PROBE_TIMEOUT_S,
    OLLAMA_PULL_TIMEOUT_S,
    OLLAMA_READINESS_TIMEOUT_S,
    ProvisioningOutcome,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
    require_provisioning_verdict,
)

if TYPE_CHECKING:
    from .provisioning import HardwareProfile


class RuntimeResident(BaseModel):
    """One model the local runtime reports as currently loaded.

    Sourced from the runtime's own ``/api/ps`` report, which is what makes the
    figure attributable: it is memory held by models *this* runtime loaded, as
    distinct from the device-wide free shortfall NVML measures. The gap between
    the two is peer-process usage.
    """

    model_config = STRICT_FROZEN_CONFIG

    name: str = Field(min_length=1)
    size_bytes: int | None = Field(default=None, ge=0)
    size_vram_bytes: int | None = Field(default=None, ge=0)


def ollama_endpoint(chat_url: str, path: str) -> str:
    """Derive a sibling runtime endpoint (``/api/<path>``) from the configured chat URL."""
    base = chat_url.rsplit("/api/", 1)[0] if "/api/" in chat_url else chat_url.rstrip("/")
    return f"{base}/api/{path}"


#: When each runtime endpoint was last found unreachable, by base URL.
#:
#: Only FAILURE is remembered, and the asymmetry is the point. A successful read
#: is answered live every time, so a resident-model set is never stale and
#: contention is never assessed against a snapshot: the moment the runtime
#: answers, this cache stops participating. What is cached is the answer that
#: does not change and costs the most to obtain -- "nothing is listening there"
#: -- which on a host with no local runtime was being rediscovered once per
#: document at ~0.94s per refused connection.
_UNREACHABLE_SINCE: dict[str, float] = {}


def _read_runtime_json(settings: Settings, path: str) -> object | None:
    url = ollama_endpoint(settings.cadrumo_llm_ollama_chat_url, path)
    base = url.rsplit("/api/", 1)[0]
    failed_at = _UNREACHABLE_SINCE.get(base)
    if failed_at is not None and (monotonic() - failed_at) < OLLAMA_PROBE_CACHE_TTL_S:
        # Identical to what the failed request below returns, minus the wait.
        return None
    try:
        with httpx.Client(timeout=OLLAMA_PROBE_TIMEOUT_S) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        _UNREACHABLE_SINCE[base] = monotonic()
        return None
    _UNREACHABLE_SINCE.pop(base, None)
    return payload


def _resident_from_entry(entry: object) -> RuntimeResident | None:
    if not isinstance(entry, dict):
        return None
    row = cast(dict[str, object], entry)
    name = row.get("name") or row.get("model")
    if not isinstance(name, str) or not name:
        return None
    size = row.get("size")
    size_vram = row.get("size_vram")
    return RuntimeResident(
        name=name,
        size_bytes=int(size) if isinstance(size, int) and size >= 0 else None,
        size_vram_bytes=int(size_vram) if isinstance(size_vram, int) and size_vram >= 0 else None,
    )


def _residents_from_payload(payload: object) -> tuple[RuntimeResident, ...] | None:
    if not isinstance(payload, dict):
        return None
    entries = cast(dict[str, object], payload).get("models")
    if not isinstance(entries, list):
        return None
    residents: list[RuntimeResident] = []
    for entry in cast(list[object], entries):
        resident = _resident_from_entry(entry)
        if resident is None:
            return None
        residents.append(resident)
    return tuple(residents)


def read_runtime_residents(settings: Settings | None = None) -> tuple[RuntimeResident, ...] | None:
    """Read the local runtime's resident model set, or ``None`` when it could not be read.

    A short-timeout ``GET /api/ps``. Loads nothing and runs no inference. The
    ``None`` return is a distinct state from an empty tuple and the two must not
    be collapsed: empty means "measured, nothing is resident", which permits
    attributing a device shortfall to peer processes, while ``None`` means the
    attribution input is missing and
    :func:`assess_model_load_contention` refuses rather than guessing.
    """
    resolved = settings if settings is not None else load_settings()
    return _residents_from_payload(_read_runtime_json(resolved, "ps"))


def cadrumo_selected_models(settings: Settings | None = None) -> frozenset[str]:
    """Return the model identifiers Cadrumo itself selected, the only ones it may unload.

    The boundary of the unload action. A model resident in the local runtime that
    Cadrumo did not select belongs to whoever loaded it, and evicting it would be
    the same overreach as signalling a peer process -- it is reported in the
    contention snapshot and never acted on.
    """
    resolved = settings if settings is not None else load_settings()
    # Every configured role, not a hand-picked pair: a role whose model is left
    # out here is one Cadrumo can load but never release, so the set is the
    # union of the role settings and grows with them.
    return frozenset(
        {
            resolved.cadrumo_llm_ollama_vision_model,
            resolved.cadrumo_llm_ollama_text_model,
            resolved.cadrumo_llm_ollama_mapping_model,
        }
    )


def matches_selected_model(name: str, selected: frozenset[str]) -> bool:
    """Return whether a resident model name is one Cadrumo selected, ignoring the tag suffix."""
    stem = name.split(":", 1)[0]
    return name in selected or any(candidate.split(":", 1)[0] == stem for candidate in selected)


class _ContentionSnapshotBase(TypedDict):
    """The fields every contention verdict shares, splatted into each branch.

    Declared rather than left as an inferred mapping because the branches below
    build the snapshot with ``**base``, and an untyped dict widens every value
    to the union of all of them -- so the splat reads as passing an ``int``
    where a model expects a tuple, and the one thing worth checking here, that
    the shared fields match the model they feed, goes unchecked.
    """

    model: str
    requirement_bytes: int
    safety_margin_bytes: int
    accelerator: AcceleratorKind
    free_vram_bytes: int | None
    free_system_memory_bytes: int | None
    binding_free_bytes: int | None
    residents: tuple[RuntimeResident, ...] | None


class ContentionSnapshot(ProvisioningOutcome):
    """The measured verdict on whether one model load is safe to perform right now.

    Read the fields as three separate claims. ``admitted`` is the decision.
    ``causes`` is :class:`~core.ContentionCause` and says *why* a refusal
    happened, keyed to the condition that applies -- unloading a model Cadrumo
    selected, closing a peer application, or measuring what could not be
    measured. ``residents`` is the attribution evidence: the runtime's own
    loaded set, which is what separates memory Cadrumo can reclaim from memory
    it may only observe.

    Nothing on this model evicts, signals, or otherwise touches a process
    Cadrumo does not own. Pressure caused by a peer is reported and refused,
    never managed.
    """

    model: str = Field(min_length=1)
    requirement_bytes: int = Field(ge=0)
    safety_margin_bytes: int = Field(ge=0)
    accelerator: AcceleratorKind
    free_vram_bytes: int | None = Field(default=None, ge=0)
    free_system_memory_bytes: int | None = Field(default=None, ge=0)
    binding_free_bytes: int | None = Field(default=None, ge=0)
    residents: tuple[RuntimeResident, ...] | None = None
    resident_attributed_bytes: int = Field(default=0, ge=0)
    unloadable_models: tuple[str, ...] = ()
    shortfall_bytes: int | None = Field(default=None, ge=0)
    admitted: bool
    causes: tuple[ContentionCause, ...] = ()

    @model_validator(mode="after")
    def _require_contention_outcome(self) -> ContentionSnapshot:
        require_provisioning_verdict(failed=not self.admitted, verdict=self.precondition_verdict)
        return self

    @property
    def required_bytes(self) -> int:
        """Return the requirement plus the configured safety margin -- the figure actually compared."""
        return self.requirement_bytes + self.safety_margin_bytes


def _attributed_resident_bytes(
    residents: tuple[RuntimeResident, ...],
    *,
    on_device: bool,
    names: frozenset[str] | None = None,
) -> int:
    """Sum resident memory in the binding arena, optionally restricted to named models."""
    total = 0
    for resident in residents:
        if names is not None and resident.name not in names:
            continue
        held = resident.size_vram_bytes if on_device else resident.size_bytes
        total += held or 0
    return total


def _resolve_resident_set(
    residents: tuple[RuntimeResident, ...] | None,
    *,
    residents_measured: bool,
    settings: Settings,
) -> tuple[tuple[RuntimeResident, ...] | None, bool]:
    """Return the runtime's resident set and whether it could actually be read.

    Reads the runtime only when the caller supplied nothing and did not already
    declare the read impossible, so an unreadable set stays distinguishable from
    a measured-empty one.
    """
    if residents is None and residents_measured:
        read = read_runtime_residents(settings)
        return read, read is not None
    return residents, residents_measured and residents is not None


def _shortfall_causes(*, resident_bytes: int, peer_bytes: int) -> tuple[ContentionCause, ...]:
    """Attribute a measured shortfall to the runtime's residents, a peer process, or both."""
    causes: list[ContentionCause] = []
    if resident_bytes > 0:
        causes.append(ContentionCause.RUNTIME_RESIDENT)
    if peer_bytes > 0:
        causes.append(ContentionCause.PEER_PROCESS)
    if not causes:
        # Nothing is resident and nothing is unexplained only when the shortfall
        # is zero, which the admitted branch above already returned; reaching
        # here means the shortfall is entirely outside this runtime.
        causes.append(ContentionCause.PEER_PROCESS)
    return tuple(causes)


def _attributed_shortfall_snapshot(
    base: _ContentionSnapshotBase,
    *,
    model: str,
    resident_set: tuple[RuntimeResident, ...],
    on_device: bool,
    binding_free: int,
    required: int,
    shortfall: int,
    settings: Settings,
) -> ContentionSnapshot:
    """Build the refusal for a measured shortfall whose cause the resident set can attribute."""
    selected = cadrumo_selected_models(settings)
    resident_bytes = _attributed_resident_bytes(resident_set, on_device=on_device)
    unloadable = tuple(resident.name for resident in resident_set if matches_selected_model(resident.name, selected))
    unloadable_bytes = _attributed_resident_bytes(
        resident_set,
        on_device=on_device,
        names=frozenset(unloadable),
    )
    peer_bytes = max(shortfall - resident_bytes, 0)
    return ContentionSnapshot(
        **base,
        resident_attributed_bytes=resident_bytes,
        unloadable_models=unloadable,
        shortfall_bytes=shortfall,
        admitted=False,
        causes=_shortfall_causes(resident_bytes=resident_bytes, peer_bytes=peer_bytes),
        facts={
            "model": model,
            "binding_free_bytes": binding_free,
            "required_bytes": required,
            "shortfall_bytes": shortfall,
            "resident_attributed_bytes": resident_bytes,
            "peer_attributed_bytes": peer_bytes,
            "resident_count": len(resident_set),
            "unloadable_model_count": len(unloadable),
            "unloadable_bytes": unloadable_bytes,
        },
        precondition_verdict=provisioning_no_recovery_verdict(
            ProvisioningPreconditionCondition.LOAD_CAPACITY_AVAILABLE,
            facts={
                "model": model,
                "binding_free_bytes": binding_free,
                "required_bytes": required,
                "shortfall_bytes": shortfall,
                "resident_attributed_bytes": resident_bytes,
                "peer_attributed_bytes": peer_bytes,
                "resident_count": len(resident_set),
                "unloadable_model_count": len(unloadable),
                "unloadable_bytes": unloadable_bytes,
            },
        ),
    )


def assess_model_load_contention(
    model: str,
    requirement_bytes: int,
    *,
    profile: HardwareProfile | None = None,
    residents: tuple[RuntimeResident, ...] | None = None,
    residents_measured: bool = True,
    settings: Settings | None = None,
) -> ContentionSnapshot:
    """Judge whether loading ``model`` is safe right now, failing closed on any unknown.

    **Acting fails closed where reporting fails open.** The free figures, never
    the totals, are compared against the model's declared requirement plus the
    configured safety margin. An unreadable free figure refuses the load: "could
    not tell" is not evidence of headroom, and is precisely the state that
    destroyed running work on the machine this was built for. The only escape is
    the explicit ``cadrumo_llm_contention_check_override`` setting, which admits
    an *unmeasurable* machine and never a *measured* shortfall.

    On a measured shortfall the cause is attributed rather than assumed, because
    the attributions are not interchangeable. Memory held by the runtime's own
    residents is reclaimable through :func:`unload_runtime_model` -- and only for
    the models Cadrumo selected. Memory unexplained by those residents is a peer
    process's, and the refusal says so instead of telling the operator to unload
    something they do not own.

    This function never loads, pulls, evicts, or signals anything. It reads.

    Args:
        model: The model identifier whose load is being judged.
        requirement_bytes: The model's declared memory requirement.
        profile: Measured hardware; probed when omitted.
        residents: The runtime's resident set; read when omitted. ``None``
            together with ``residents_measured`` false means unreadable.
        residents_measured: False when the resident set could not be read.
            Distinguishes an unreadable resident set from a measured-empty one.
        settings: Settings carrying the margin and override; loaded when omitted.

    Returns:
        A :class:`ContentionSnapshot`. This module never raises on absence; the
        dispatch boundary converts a non-admitted snapshot into its typed
        refusal.
    """
    resolved = settings if settings is not None else load_settings()
    margin = resolved.cadrumo_llm_contention_safety_margin_bytes
    from .provisioning import binding_free_bytes, probe_hardware_profile

    hardware = profile if profile is not None else probe_hardware_profile()
    resident_set, residents_known = _resolve_resident_set(
        residents,
        residents_measured=residents_measured,
        settings=resolved,
    )

    kind = hardware.accelerator.kind
    free_vram = hardware.free_vram_bytes
    free_ram = hardware.memory.free_bytes
    on_device = kind is AcceleratorKind.NVIDIA_CUDA
    binding_free = binding_free_bytes(hardware)
    required = requirement_bytes + margin

    base: _ContentionSnapshotBase = {
        "model": model,
        "requirement_bytes": requirement_bytes,
        "safety_margin_bytes": margin,
        "accelerator": kind,
        "free_vram_bytes": free_vram,
        "free_system_memory_bytes": free_ram,
        "binding_free_bytes": binding_free,
        "residents": resident_set,
    }

    if binding_free is None:
        if resolved.cadrumo_llm_contention_check_override:
            return ContentionSnapshot(
                **base,
                admitted=True,
                facts={
                    "model": model,
                    "accelerator_kind": kind.value,
                    "binding_free_measured": False,
                    "contention_check_override": True,
                },
            )
        return ContentionSnapshot(
            **base,
            admitted=False,
            causes=(ContentionCause.UNREADABLE,),
            facts={"model": model, "accelerator_kind": kind.value, "binding_free_measured": False},
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.LOAD_HEADROOM_MEASURABLE,
                facts={"model": model, "accelerator_kind": kind.value, "binding_free_measured": False},
            ),
        )

    if binding_free >= required:
        return ContentionSnapshot(
            **base,
            shortfall_bytes=0,
            admitted=True,
            facts={
                "model": model,
                "binding_free_bytes": binding_free,
                "required_bytes": required,
                "shortfall_bytes": 0,
            },
        )

    shortfall = required - binding_free
    if not residents_known or resident_set is None:
        return ContentionSnapshot(
            **base,
            shortfall_bytes=shortfall,
            admitted=False,
            causes=(ContentionCause.UNREADABLE,),
            facts={
                "model": model,
                "binding_free_bytes": binding_free,
                "required_bytes": required,
                "shortfall_bytes": shortfall,
                "resident_set_readable": False,
            },
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.RESIDENT_SET_READABLE,
                facts={
                    "model": model,
                    "binding_free_bytes": binding_free,
                    "required_bytes": required,
                    "shortfall_bytes": shortfall,
                    "resident_set_readable": False,
                },
            ),
        )

    return _attributed_shortfall_snapshot(
        base,
        model=model,
        resident_set=resident_set,
        on_device=on_device,
        binding_free=binding_free,
        required=required,
        shortfall=shortfall,
        settings=resolved,
    )


class UnloadOutcome(ProvisioningOutcome):
    """The result of an explicit unload of one Cadrumo-selected resident model.

    Never raises and never escalates: a model Cadrumo did not select, or one that
    is not resident, returns ``unloaded`` false with the reason. The action is
    self-scoped by construction -- it asks the local runtime to release a model
    *it* loaded on Cadrumo's behalf, and has no mechanism to affect any other
    process on the device.
    """

    model: str = Field(min_length=1)
    unloaded: bool
    was_resident: bool = False

    @model_validator(mode="after")
    def _require_unload_outcome(self) -> UnloadOutcome:
        require_provisioning_verdict(failed=not self.unloaded, verdict=self.precondition_verdict)
        return self


def unload_runtime_model(
    model: str,
    *,
    residents: tuple[RuntimeResident, ...] | None = None,
    residents_measured: bool = True,
    settings: Settings | None = None,
) -> UnloadOutcome:
    """Release one Cadrumo-selected model from the local runtime, touching nothing else.

    Two guards, in order, and both matter. The model must be one
    :func:`cadrumo_selected_models` names, so Cadrumo cannot evict a model
    another operator or application loaded into the shared runtime. It must then
    be **resident**, which is what keeps this action from becoming a load: the
    runtime's release call would otherwise bring a non-resident model in before
    releasing it, and this module must never cause a model load.

    The release is a zero-keep-alive request carrying no prompt, so the runtime
    drops the model without running inference.

    Args:
        model: The model identifier to release.
        residents: The resident set; read via :func:`read_runtime_residents`
            when omitted.
        residents_measured: False when the resident set could not be read.
        settings: Settings carrying the runtime endpoint; loaded when omitted.

    Returns:
        An :class:`UnloadOutcome` describing what happened and, on refusal, why.
    """
    resolved = settings if settings is not None else load_settings()
    if not matches_selected_model(model, cadrumo_selected_models(resolved)):
        return UnloadOutcome(
            model=model,
            unloaded=False,
            facts={"model": model, "selected_by_cadrumo": False},
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.MODEL_SELECTED_BY_CADRUMO,
                facts={"model": model, "selected_by_cadrumo": False},
            ),
        )
    if residents is None and residents_measured:
        resident_set = read_runtime_residents(resolved)
    else:
        resident_set = residents if residents_measured else None
    if resident_set is None:
        return UnloadOutcome(
            model=model,
            unloaded=False,
            facts={"model": model, "resident_set_readable": False},
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.RESIDENT_SET_READABLE,
                facts={"model": model, "resident_set_readable": False},
            ),
        )
    if not any(matches_selected_model(resident.name, frozenset({model})) for resident in resident_set):
        return UnloadOutcome(
            model=model,
            unloaded=False,
            was_resident=False,
            facts={"model": model, "model_resident": False},
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.MODEL_RESIDENT,
                facts={"model": model, "model_resident": False},
            ),
        )
    url = ollama_endpoint(resolved.cadrumo_llm_ollama_chat_url, "generate")
    try:
        with httpx.Client(timeout=OLLAMA_PROBE_TIMEOUT_S) as client:
            response = client.post(url, json={"model": model, "keep_alive": 0})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return UnloadOutcome(
            model=model,
            unloaded=False,
            was_resident=True,
            facts={"model": model, "runtime_reachable": False, "runtime_error_type": exc.__class__.__name__},
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.RUNTIME_REACHABLE,
                facts={"model": model, "runtime_reachable": False, "runtime_error_type": exc.__class__.__name__},
            ),
        )
    return UnloadOutcome(
        model=model,
        unloaded=True,
        was_resident=True,
        facts={"model": model, "model_resident": True},
    )


class PullProgress(BaseModel):
    """One progress report from an in-flight model fetch.

    ``total_bytes`` is absent early in a pull, before the runtime has resolved
    the manifest, so a renderer must tolerate a percentless report rather than
    computing a ratio against zero.
    """

    model_config = STRICT_FROZEN_CONFIG

    status: str = ""
    completed_bytes: int | None = Field(default=None, ge=0)
    total_bytes: int | None = Field(default=None, ge=0)

    @property
    def percent(self) -> int | None:
        """Return whole-percent progress, or ``None`` when the total is not yet known."""
        if not self.total_bytes or self.completed_bytes is None:
            return None
        return min(100, int(self.completed_bytes * 100 / self.total_bytes))


class PullOutcome(ProvisioningOutcome):
    """The result of an explicit model fetch, including a fetch that never started.

    ``contention`` is populated when the pre-fetch admission check refused, and
    is the reason no bytes moved. Keeping the snapshot rather than flattening it
    to a string is what lets the caller name WHICH cause applied -- unloading a
    resident Cadrumo selected and closing a peer application are different
    instructions and only one of them is ours to offer.
    """

    model: str = Field(min_length=1)
    pulled: bool
    contention: ContentionSnapshot | None = None
    bytes_fetched: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _require_pull_outcome(self) -> PullOutcome:
        require_provisioning_verdict(failed=not self.pulled, verdict=self.precondition_verdict)
        return self


def pull_runtime_model(
    model: str,
    requirement_bytes: int,
    *,
    profile: HardwareProfile | None = None,
    settings: Settings | None = None,
    on_progress: Callable[[PullProgress], None] | None = None,
) -> PullOutcome:
    """Fetch ``model`` into the local runtime, refusing BEFORE any bytes move.

    The admission check runs first and a refusal returns without contacting the
    runtime at all. That ordering is the point of the action: a multi-gigabyte
    download that completes and then cannot be loaded has spent the operator's
    bandwidth to arrive at the refusal it could have been given immediately.

    Never raises, in keeping with every other action here. An unreachable
    runtime is a typed closed outcome -- this function does not
    start a daemon, and nothing on this path pulls implicitly: reaching it at
    all requires an operator to have asked.

    Args:
        model: Runtime identifier to fetch.
        requirement_bytes: The model's declared memory requirement, checked
            against measured headroom before fetching.
        profile: A measured hardware profile; probed when omitted.
        settings: Resolved settings; loaded when omitted.
        on_progress: Called for each progress report the runtime emits. Failures
            in the callback are the caller's to handle; nothing here swallows
            them.

    Returns:
        A :class:`PullOutcome`. ``pulled`` false with ``contention`` populated
        means the fetch was refused before it began.
    """
    resolved = settings if settings is not None else load_settings()
    snapshot = assess_model_load_contention(model, requirement_bytes, profile=profile, settings=resolved)
    if not snapshot.admitted:
        contention_verdict = snapshot.precondition_verdict
        assert contention_verdict is not None
        return PullOutcome(
            model=model,
            pulled=False,
            contention=snapshot,
            facts={
                "model": model,
                "admitted": False,
                "contention_condition": contention_verdict.failed_condition_id,
            },
            precondition_verdict=contention_verdict,
        )

    url = ollama_endpoint(resolved.cadrumo_llm_ollama_chat_url, "pull")
    fetched: int | None = None
    try:
        with (
            httpx.Client(timeout=OLLAMA_PULL_TIMEOUT_S) as client,
            client.stream("POST", url, json={"model": model, "stream": True}) as response,
        ):
            response.raise_for_status()
            for line in response.iter_lines():
                progress = _pull_progress(line)
                if progress is None:
                    continue
                if progress.completed_bytes is not None:
                    fetched = progress.completed_bytes
                if on_progress is not None:
                    on_progress(progress)
    except httpx.HTTPError as exc:
        return PullOutcome(
            model=model,
            pulled=False,
            bytes_fetched=fetched,
            facts={
                "model": model,
                "runtime_reachable": False,
                "runtime_error_type": exc.__class__.__name__,
                "bytes_fetched_known": fetched is not None,
            },
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.RUNTIME_REACHABLE,
                facts={
                    "model": model,
                    "runtime_reachable": False,
                    "runtime_error_type": exc.__class__.__name__,
                    "bytes_fetched_known": fetched is not None,
                },
            ),
        )
    return PullOutcome(
        model=model,
        pulled=True,
        bytes_fetched=fetched,
        facts={"model": model, "runtime_reachable": True, "bytes_fetched_known": fetched is not None},
    )


def _pull_progress(line: str) -> PullProgress | None:
    """Parse one NDJSON progress line, or ``None`` when it carries no report."""
    text = line.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    # CAST-RATIONALE-OLLAMA-PULL-PAYLOAD: json.loads returns Any; isinstance
    # narrows to dict but not its type parameters.
    # nosemgrep: no-cast-in-domain-application
    row = cast(dict[str, object], payload)
    completed = row.get("completed")
    total = row.get("total")
    status = row.get("status")
    return PullProgress(
        status=status if isinstance(status, str) else "",
        completed_bytes=completed if isinstance(completed, int) and completed >= 0 else None,
        total_bytes=total if isinstance(total, int) and total >= 0 else None,
    )


class ReadinessOutcome(ProvisioningOutcome):
    """Whether a model is loaded and actually answering, not merely present.

    ``resident`` and ``answered`` are separate claims on purpose. A model can be
    present on disk and not loaded, or loaded and too slow to be useful, and an
    operator debugging a stalled read needs to know which of the two they have.
    """

    model: str = Field(min_length=1)
    ready: bool
    resident: bool = False
    answered: bool = False
    elapsed_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _require_readiness_outcome(self) -> ReadinessOutcome:
        require_provisioning_verdict(failed=not self.ready, verdict=self.precondition_verdict)
        return self


def verify_model_ready(
    model: str,
    *,
    settings: Settings | None = None,
    timeout_s: float | None = None,
) -> ReadinessOutcome:
    """Confirm ``model`` is resident and answers a trivial prompt within a bound.

    The prompt is deliberately minimal and its CONTENT is irrelevant -- this
    verifies the transport and the load, not the model's quality, so nothing
    here inspects what came back beyond the fact that something did.

    Never raises. An unreachable runtime and a model that is
    absent names the provision verb rather than pulling it, because an implicit
    multi-gigabyte fetch triggered by a verification command is exactly what the
    lifecycle design forbids.
    """
    resolved = settings if settings is not None else load_settings()
    bound = timeout_s if timeout_s is not None else OLLAMA_READINESS_TIMEOUT_S
    residents = read_runtime_residents(resolved)
    if residents is None:
        return ReadinessOutcome(
            model=model,
            ready=False,
            facts={"model": model, "runtime_reachable": False},
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.RUNTIME_REACHABLE,
                facts={"model": model, "runtime_reachable": False},
            ),
        )
    resident = any(matches_selected_model(entry.name, frozenset({model})) for entry in residents)

    url = ollama_endpoint(resolved.cadrumo_llm_ollama_chat_url, "generate")
    started = time.monotonic()
    try:
        with httpx.Client(timeout=bound) as client:
            response = client.post(url, json={"model": model, "prompt": "ok", "stream": False})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        elapsed = int((time.monotonic() - started) * 1000)
        return ReadinessOutcome(
            model=model,
            ready=False,
            resident=resident,
            elapsed_ms=elapsed,
            facts={
                "model": model,
                "model_resident": resident,
                "model_answered": False,
                "elapsed_ms": elapsed,
                "runtime_error_type": exc.__class__.__name__,
            },
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.MODEL_READY,
                facts={
                    "model": model,
                    "model_resident": resident,
                    "model_answered": False,
                    "elapsed_ms": elapsed,
                    "runtime_error_type": exc.__class__.__name__,
                },
            ),
        )
    elapsed = int((time.monotonic() - started) * 1000)
    return ReadinessOutcome(
        model=model,
        ready=True,
        resident=resident,
        answered=True,
        elapsed_ms=elapsed,
        facts={"model": model, "model_resident": resident, "model_answered": True, "elapsed_ms": elapsed},
    )


class InstalledModel(BaseModel):
    """One model the local runtime reports as PRESENT ON DISK, loaded or not.

    Distinct from :class:`RuntimeResident`, and the distinction is the whole
    reason both exist. A resident model is loaded into memory right now; an
    installed model occupies disk whether or not anything ever loads it. Removal
    reclaims disk, so it reads this inventory -- reading the resident set instead
    would report a multi-gigabyte model as absent merely because it is cold.
    """

    model_config = STRICT_FROZEN_CONFIG

    name: str = Field(min_length=1)
    size_bytes: int | None = Field(default=None, ge=0)


def _installed_from_payload(payload: object) -> tuple[InstalledModel, ...] | None:
    if not isinstance(payload, dict):
        return None
    entries = cast(dict[str, object], payload).get("models")
    if not isinstance(entries, list):
        return None
    installed: list[InstalledModel] = []
    for entry in cast(list[object], entries):
        if not isinstance(entry, dict):
            return None
        row = cast(dict[str, object], entry)
        name = row.get("name") or row.get("model")
        if not isinstance(name, str) or not name:
            return None
        size = row.get("size")
        installed.append(
            InstalledModel(
                name=name,
                size_bytes=int(size) if isinstance(size, int) and size >= 0 else None,
            ),
        )
    return tuple(installed)


def read_installed_models(settings: Settings | None = None) -> tuple[InstalledModel, ...] | None:
    """Read the runtime's on-disk model inventory, or ``None`` when it could not be read.

    A short-timeout ``GET /api/tags``. Downloads nothing and loads nothing. As
    with :func:`read_runtime_residents`, ``None`` and the empty tuple are
    different states and must not be collapsed: empty means "measured, no models
    are installed", which is a fact callers may act on, while ``None`` means the
    inventory is unknown and every caller here refuses rather than guessing.

    The reported ``size`` is the runtime's own figure for the bytes that model
    occupies, which is what makes a freed-bytes report a measurement rather than
    an estimate.
    """
    resolved = settings if settings is not None else load_settings()
    return _installed_from_payload(_read_runtime_json(resolved, "tags"))


class RemoveOutcome(ProvisioningOutcome):
    """The result of removing one Cadrumo-selected model from the local runtime's store.

    ``freed_bytes`` is a **measurement, not an estimate**, and is populated only
    when the removal was confirmed against a re-read of the inventory. The figure
    is the runtime's own reported size for that model, so an operator can
    reconcile it against the disk the runtime's store actually gives back. When
    the confirming read fails, the removal may well have succeeded, but no figure
    is reported -- an unreconcilable number is worse than none.

    Never raises. A model Cadrumo did not select, a model that is not installed,
    and an unreadable inventory each return ``removed`` false with the reason.
    """

    model: str = Field(min_length=1)
    removed: bool
    was_installed: bool = False
    freed_bytes: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _require_removal_outcome(self) -> RemoveOutcome:
        require_provisioning_verdict(failed=not self.removed, verdict=self.precondition_verdict)
        return self


def _remove_refusal(
    model: str,
    condition: ProvisioningPreconditionCondition,
    facts: Mapping[str, str | int | bool],
    *,
    was_installed: bool = False,
    freed_bytes: int | None = None,
) -> RemoveOutcome:
    return RemoveOutcome(
        model=model,
        removed=False,
        was_installed=was_installed,
        freed_bytes=freed_bytes,
        facts=facts,
        precondition_verdict=provisioning_no_recovery_verdict(condition, facts=facts),
    )


def _removal_inventory(
    installed: tuple[InstalledModel, ...] | None,
    *,
    installed_measured: bool,
    settings: Settings,
) -> tuple[InstalledModel, ...] | None:
    if installed is None and installed_measured:
        return read_installed_models(settings)
    return installed if installed_measured else None


def _delete_model(entry: InstalledModel, settings: Settings) -> str | None:
    url = ollama_endpoint(settings.cadrumo_llm_ollama_chat_url, "delete")
    try:
        with httpx.Client(timeout=OLLAMA_PROBE_TIMEOUT_S) as client:
            response = client.request("DELETE", url, json={"model": entry.name})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return exc.__class__.__name__
    return None


def _confirm_removal(
    model: str,
    entry: InstalledModel,
    after: tuple[InstalledModel, ...] | None,
) -> RemoveOutcome:
    if after is None:
        facts = {
            "model": model,
            "removal_request_accepted": True,
            "removal_confirmed": False,
            "inventory_reread": False,
        }
        return _remove_refusal(
            model,
            ProvisioningPreconditionCondition.MODEL_REMOVAL_CONFIRMED,
            facts,
            was_installed=True,
        )
    if any(matches_selected_model(row.name, frozenset({model})) for row in after):
        facts = {
            "model": model,
            "removal_request_accepted": True,
            "removal_confirmed": False,
            "model_installed": True,
        }
        return _remove_refusal(
            model,
            ProvisioningPreconditionCondition.MODEL_REMOVAL_CONFIRMED,
            facts,
            was_installed=True,
        )
    return RemoveOutcome(
        model=model,
        removed=True,
        was_installed=True,
        freed_bytes=entry.size_bytes,
        facts={"model": model, "model_installed": False, "removal_confirmed": True},
    )


def remove_runtime_model(
    model: str,
    *,
    installed: tuple[InstalledModel, ...] | None = None,
    installed_measured: bool = True,
    settings: Settings | None = None,
) -> RemoveOutcome:
    """Delete ``model`` from the local runtime's store and report the bytes reclaimed.

    Deletion is delegated to the runtime that owns the store; nothing here
    unlinks a file, walks a directory, or reaches any path Cadrumo manages. That
    boundary is deliberate and load-bearing: the model store is a third-party
    cache, and no encrypted bucket, key material, or secure-storage object is
    reachable from this action by construction.

    The selection guard mirrors :func:`unload_runtime_model` -- Cadrumo removes
    only models :func:`cadrumo_selected_models` names, so a model another
    operator or application pulled into the shared runtime is reported and never
    deleted. Deleting a peer's multi-gigabyte model would be a far more expensive
    overreach than evicting one from memory, since the bytes must be re-fetched.

    The freed figure is measured across the action: the size is read from the
    inventory BEFORE the delete, and reported only after a re-read confirms the
    model is gone.

    Args:
        model: The model identifier to remove.
        installed: The on-disk inventory; read via :func:`read_installed_models`
            when omitted.
        installed_measured: False when the inventory could not be read.
        settings: Settings carrying the runtime endpoint; loaded when omitted.

    Returns:
        A :class:`RemoveOutcome` describing what happened and, on refusal, why.
    """
    resolved = settings if settings is not None else load_settings()
    if not matches_selected_model(model, cadrumo_selected_models(resolved)):
        facts = {"model": model, "selected_by_cadrumo": False}
        return _remove_refusal(model, ProvisioningPreconditionCondition.MODEL_SELECTED_BY_CADRUMO, facts)
    inventory = _removal_inventory(installed, installed_measured=installed_measured, settings=resolved)
    if inventory is None:
        facts = {"model": model, "installed_model_inventory_readable": False}
        return _remove_refusal(model, ProvisioningPreconditionCondition.LOCAL_MODEL_INVENTORY_READABLE, facts)
    entry = next((row for row in inventory if matches_selected_model(row.name, frozenset({model}))), None)
    if entry is None:
        facts = {"model": model, "model_installed": False}
        return _remove_refusal(
            model,
            ProvisioningPreconditionCondition.MODEL_INSTALLED,
            facts,
            freed_bytes=0,
        )
    error_type = _delete_model(entry, resolved)
    if error_type is not None:
        facts = {"model": model, "runtime_reachable": False, "runtime_error_type": error_type}
        return _remove_refusal(
            model,
            ProvisioningPreconditionCondition.RUNTIME_REACHABLE,
            facts,
            was_installed=True,
        )

    # The confirming re-read is what turns the figure into a measurement. A
    # runtime that accepted the request and kept the bytes, or one that became
    # unreachable between the two calls, must not yield a freed-bytes number the
    # operator cannot reconcile against the store.
    after = read_installed_models(resolved)
    return _confirm_removal(model, entry, after)
