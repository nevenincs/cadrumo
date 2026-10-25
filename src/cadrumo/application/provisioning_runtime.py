"""Canonical local-runtime reads and model loads for the local AI's consumers.

The native component engine installs the program and pulls every role's
model, and the runtime manager runs the server. What is here only asks that
server what it holds and has it load or unload a model it already holds.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from time import monotonic
from typing import TYPE_CHECKING, TypedDict

import httpx
from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ..core.config import Settings, load_settings
from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.hardware import AcceleratorKind, ContentionCause
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.type_guards import is_object_dict, is_object_list
from .provisioning_contracts import (
    OLLAMA_LOAD_KEEP_ALIVE,
    OLLAMA_PROBE_CACHE_TTL_S,
    OLLAMA_PROBE_TIMEOUT_S,
    OLLAMA_READINESS_TIMEOUT_S,
    ProvisioningFactValue,
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


def _resident_from_entry(row: object) -> RuntimeResident | None:
    if not is_object_dict(row):
        return None
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
    if not is_object_dict(payload):
        return None
    entries = payload.get("models")
    if not is_object_list(entries):
        return None
    residents: list[RuntimeResident] = []
    for entry in entries:
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
            resolved.cadrumo_llm_ollama_supply_nature_model,
        }
    )


def runtime_model_names_match(left: str, right: str) -> bool:
    """Return whether two runtime model names denote the same tagged model.

    An untagged name means ``:latest`` to the runtime, so ``qwen3`` and
    ``qwen3:latest`` match while ``qwen3:1.7b`` and ``qwen3:8b`` do not -- a
    different size is a different download and a different memory claim. Every
    "is this exact model present or loaded" question uses this comparison.
    """

    def normalised(name: str) -> str:
        return name if ":" in name else f"{name}:latest"

    return normalised(left) == normalised(right)


def matches_selected_model(name: str, selected: frozenset[str]) -> bool:
    """Return whether a model name belongs to a family Cadrumo selected, ignoring the tag suffix.

    Family-level on purpose: it bounds which models Cadrumo may unload or
    remove and which residents count as reclaimable, so a differently sized
    variant of a selected model stays within Cadrumo's reach. It never answers
    whether one exact model is present; :func:`runtime_model_names_match` does.
    """
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
    ``causes`` is :class:`~core.hardware.ContentionCause` and says *why* a refusal
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
    requirement_bytes: NonNegativeInt
    safety_margin_bytes: NonNegativeInt
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
    @pydantic_validation_boundary
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
    @pydantic_validation_boundary
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
    if not any(runtime_model_names_match(model, resident.name) for resident in resident_set):
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


class LoadOutcome(ProvisioningOutcome):
    """The result of an explicit load of one pulled model into the runtime's memory.

    ``already_loaded`` marks a model that was resident before the request, so
    nothing was sent. ``contention`` is populated when the admission check
    refused, and is the reason nothing was loaded.
    """

    model: str = Field(min_length=1)
    loaded: bool
    already_loaded: bool = False
    contention: ContentionSnapshot | None = None
    elapsed_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_load_outcome(self) -> LoadOutcome:
        require_provisioning_verdict(failed=not self.loaded, verdict=self.precondition_verdict)
        return self


def _load_refusal(
    model: str,
    condition: ProvisioningPreconditionCondition,
    facts: Mapping[str, ProvisioningFactValue],
    *,
    elapsed_ms: int | None = None,
) -> LoadOutcome:
    return LoadOutcome(
        model=model,
        loaded=False,
        elapsed_ms=elapsed_ms,
        facts=facts,
        precondition_verdict=provisioning_no_recovery_verdict(condition, facts=facts),
    )


def _is_resident(model: str, residents: tuple[RuntimeResident, ...]) -> bool:
    return any(runtime_model_names_match(model, entry.name) for entry in residents)


def _load_preflight(
    model: str,
    requirement_bytes: int,
    *,
    profile: HardwareProfile | None,
    settings: Settings,
) -> LoadOutcome | None:
    residents = read_runtime_residents(settings)
    if residents is None:
        return _load_refusal(
            model, ProvisioningPreconditionCondition.RUNTIME_REACHABLE, {"model": model, "runtime_reachable": False}
        )
    if _is_resident(model, residents):
        return LoadOutcome(
            model=model,
            loaded=True,
            already_loaded=True,
            facts={"model": model, "model_resident": True, "already_loaded": True},
        )
    inventory = read_installed_models(settings)
    if inventory is None:
        return _load_refusal(
            model,
            ProvisioningPreconditionCondition.LOCAL_MODEL_INVENTORY_READABLE,
            {"model": model, "installed_model_inventory_readable": False},
        )
    if not any(runtime_model_names_match(model, entry.name) for entry in inventory):
        return _load_refusal(
            model, ProvisioningPreconditionCondition.MODEL_INSTALLED, {"model": model, "model_installed": False}
        )
    snapshot = assess_model_load_contention(
        model, requirement_bytes, profile=profile, residents=residents, settings=settings
    )
    if snapshot.admitted:
        return None
    verdict = snapshot.precondition_verdict
    if verdict is None:
        raise ValueError("a refused model-load contention snapshot must carry its precondition verdict")
    return LoadOutcome(
        model=model,
        loaded=False,
        contention=snapshot,
        facts={"model": model, "admitted": False, "contention_condition": verdict.failed_condition_id},
        precondition_verdict=verdict,
    )


def _request_runtime_load(model: str, settings: Settings) -> tuple[str | None, int]:
    url = ollama_endpoint(settings.cadrumo_llm_ollama_chat_url, "generate")
    started = time.monotonic()
    try:
        with httpx.Client(timeout=OLLAMA_READINESS_TIMEOUT_S) as client:
            response = client.post(url, json={"model": model, "keep_alive": OLLAMA_LOAD_KEEP_ALIVE, "stream": False})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return exc.__class__.__name__, int((time.monotonic() - started) * 1000)
    return None, int((time.monotonic() - started) * 1000)


def _load_request_outcome(model: str, settings: Settings) -> LoadOutcome:
    error_type, elapsed = _request_runtime_load(model, settings)
    if error_type is not None:
        return _load_refusal(
            model,
            ProvisioningPreconditionCondition.MODEL_LOADED,
            {
                "model": model,
                "model_loaded": False,
                "elapsed_ms": elapsed,
                "runtime_error_type": error_type,
            },
            elapsed_ms=elapsed,
        )
    after = read_runtime_residents(settings)
    if after is None or not _is_resident(model, after):
        return _load_refusal(
            model,
            ProvisioningPreconditionCondition.MODEL_LOADED,
            {"model": model, "model_loaded": False, "elapsed_ms": elapsed, "resident_set_readable": after is not None},
            elapsed_ms=elapsed,
        )
    return LoadOutcome(
        model=model,
        loaded=True,
        elapsed_ms=elapsed,
        facts={"model": model, "model_resident": True, "elapsed_ms": elapsed},
    )


def load_runtime_model(
    model: str,
    requirement_bytes: int,
    *,
    profile: HardwareProfile | None = None,
    settings: Settings | None = None,
) -> LoadOutcome:
    """Load a pulled ``model`` into the runtime's memory so the first read does not pay the cold start.

    Idempotent: a model that is already resident is reported loaded and
    nothing is sent. A model that is not on disk is refused rather than
    fetched, because a load must never become an implicit download. The
    admission check runs before the load, exactly as it does before a pull,
    and the result is confirmed against a re-read of the resident set.

    The request carries no prompt, so the runtime loads the model without
    running inference, and a keep-alive long enough to outlast the gap between
    an operator's load and their first read. Loading leaves the weights
    unchanged, so a remembered fitness verdict stays valid.

    Returns:
        A :class:`LoadOutcome`. Never raises.
    """
    resolved = settings if settings is not None else load_settings()
    preflight = _load_preflight(model, requirement_bytes, profile=profile, settings=resolved)
    if preflight is not None:
        return preflight
    return _load_request_outcome(model, resolved)


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
    @pydantic_validation_boundary
    def _require_readiness_outcome(self) -> ReadinessOutcome:
        require_provisioning_verdict(failed=not self.ready, verdict=self.precondition_verdict)
        return self


def load_and_verify_model(
    model: str,
    *,
    settings: Settings | None = None,
    timeout_s: float | None = None,
) -> ReadinessOutcome:
    """Load ``model`` when it is not resident, and confirm it answers a trivial prompt within a bound.

    This loads: the one-token prompt brings a model that is on disk but not in
    memory into memory, with the same keep-alive as an explicit load, so a
    verification leaves the model resident exactly as long as a load would.
    A caller that must not load without admission checks it first.

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
    resident = any(runtime_model_names_match(model, entry.name) for entry in residents)
    if not resident:
        # A generate call against an absent model is refused by the runtime
        # anyway; asking the inventory first names the actual gap -- a pull --
        # instead of reporting a load failure.
        inventory = read_installed_models(resolved)
        if inventory is not None and not any(runtime_model_names_match(model, entry.name) for entry in inventory):
            return ReadinessOutcome(
                model=model,
                ready=False,
                facts={"model": model, "model_installed": False},
                precondition_verdict=provisioning_no_recovery_verdict(
                    ProvisioningPreconditionCondition.MODEL_INSTALLED,
                    facts={"model": model, "model_installed": False},
                ),
            )

    url = ollama_endpoint(resolved.cadrumo_llm_ollama_chat_url, "generate")
    started = time.monotonic()
    try:
        with httpx.Client(timeout=bound) as client:
            # One token proves the load and the transport; an unbounded reply
            # from a reasoning model measures its verbosity instead.
            response = client.post(
                url,
                json={
                    "model": model,
                    "prompt": "ok",
                    "stream": False,
                    "keep_alive": OLLAMA_LOAD_KEEP_ALIVE,
                    "options": {"num_predict": 1},
                },
            )
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
    installed model occupies disk whether or not anything ever loads it, so a
    question about what is installed reads this inventory -- reading the resident
    set instead would report a multi-gigabyte model as absent merely because it
    is cold.
    """

    model_config = STRICT_FROZEN_CONFIG

    name: str = Field(min_length=1)
    size_bytes: int | None = Field(default=None, ge=0)
    digest: str | None = Field(default=None, min_length=1)
    """The runtime's content digest for the pulled weights; changes when a pull replaces them."""


def _installed_model_from_entry(row: object) -> InstalledModel | None:
    if not is_object_dict(row):
        return None
    name = row.get("name") or row.get("model")
    if not isinstance(name, str) or not name:
        return None
    size = row.get("size")
    digest = row.get("digest")
    return InstalledModel(
        name=name,
        size_bytes=int(size) if isinstance(size, int) and size >= 0 else None,
        digest=digest if isinstance(digest, str) and digest else None,
    )


def _installed_models_from_entries(entries: list[object]) -> tuple[InstalledModel, ...] | None:
    installed: list[InstalledModel] = []
    for row in entries:
        model = _installed_model_from_entry(row)
        if model is None:
            return None
        installed.append(model)
    return tuple(installed)


def _installed_from_payload(payload: object) -> tuple[InstalledModel, ...] | None:
    if not is_object_dict(payload):
        return None
    entries = payload.get("models")
    if not is_object_list(entries):
        return None
    return _installed_models_from_entries(entries)


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
