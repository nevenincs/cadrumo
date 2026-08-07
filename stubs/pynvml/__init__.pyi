"""Minimal typing surface for the NVML bindings the accelerator probe calls.

``nvidia-ml-py`` ships no ``py.typed`` and has no ``types-*`` distribution, so it
joins the hand-written stubs beside it rather than an unresolved-import
allowance -- the project keeps that allowance empty on purpose.

Scoped to the seven symbols the probe uses. A stub that guessed at the rest of
NVML would assert shapes nobody here has checked against the real library, and a
wrong shape in a stub is worse than an absent one: it type-checks.

``nvmlDeviceGetName`` is annotated as returning ``bytes | str`` because the
binding has returned both across versions, and the caller decodes defensively
for exactly that reason.
"""

from typing import Protocol

class NVMLError(Exception):
    """Base error the bindings raise for every NVML failure."""

class _MemoryInfo(Protocol):
    """The memory triple ``nvmlDeviceGetMemoryInfo`` returns.

    Typed as a protocol rather than a class because the caller reads only
    ``total`` and ``free`` and coerces both through ``int()``; binding it to a
    concrete type would over-specify a structure this codebase never inspects.
    """

    @property
    def total(self) -> int: ...
    @property
    def free(self) -> int: ...

class _Device(Protocol):
    """Opaque device handle. The caller passes it back and never inspects it."""

def nvmlInit() -> None: ...  # noqa: N802 - the binding's own casing
def nvmlShutdown() -> None: ...  # noqa: N802 - the binding's own casing
def nvmlDeviceGetCount() -> int: ...  # noqa: N802 - the binding's own casing
def nvmlDeviceGetHandleByIndex(index: int, /) -> _Device: ...  # noqa: N802 - the binding's own casing
def nvmlDeviceGetName(handle: _Device, /) -> bytes | str: ...  # noqa: N802 - the binding's own casing
def nvmlDeviceGetMemoryInfo(handle: _Device, /) -> _MemoryInfo: ...  # noqa: N802 - the binding's own casing
