"""Canonical local-runtime reads and load admission for the local AI's consumers.

The native component engine installs the program and pulls the models the
person selected, and the runtime manager runs the server. What is here only
asks that server what it holds and judges whether a load would fit now.
"""

from __future__ import annotations

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
    OLLAMA_PROBE_CACHE_TTL_S,
    OLLAMA_PROBE_TIMEOUT_S,
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


def runtime_model_names_match(left: str, right: str) -> bool:
    """Return whether two runtime model names denote the same tagged model.

    An untagged name means ``:latest`` to the runtime, so ``reader`` and
    ``reader:latest`` match while ``reader:small`` and ``reader:large`` do not --
    a different tag is a different download and a different memory claim. Every
    "is this exact model present or loaded" question uses this comparison.
    """

    def normalised(name: str) -> str:
        return name if ":" in name else f"{name}:latest"

    return normalised(left) == normalised(right)


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
    happened, keyed to the condition that applies -- a model the runtime holds,
    a peer application, or what could not be measured. ``residents`` is the
    attribution evidence: the runtime's own loaded set, which separates memory
    the runtime holds from memory another process holds.

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
) -> int:
    """Sum resident memory in the binding arena."""
    total = 0
    for resident in residents:
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
) -> ContentionSnapshot:
    """Build the refusal for a measured shortfall whose cause the resident set can attribute."""
    resident_bytes = _attributed_resident_bytes(resident_set, on_device=on_device)
    peer_bytes = max(shortfall - resident_bytes, 0)
    return ContentionSnapshot(
        **base,
        resident_attributed_bytes=resident_bytes,
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
    residents is the runtime's, released when it unloads them. Memory unexplained
    by those residents is a peer process's, and the refusal says so.

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
