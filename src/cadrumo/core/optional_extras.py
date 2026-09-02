"""Capability-gated optional package extras and their import guard.

The shipped package is lean: a bare ``pip install cadrumo`` omits the optional
integration stacks (Google export, the live-AEAT browser, the Anthropic-API LLM
provider). Each maps to a ``[project.optional-dependencies]`` extra and is
imported lazily, so the core CLI builds and runs without it.

This module is the single source of truth for those extras. It lives in ``core``
— the innermost layer — so an adapter can guard its own external-library import
without importing the application layer, and the application doctor can probe the
same :data:`OPTIONAL_EXTRAS` registry through
:func:`application.provisioning.probe_optional_extra`. :func:`require_optional_extra`
is the seam every feature boundary calls before its lazy import so a missing
extra becomes one instructive :class:`MissingOptionalExtraError` naming
``pip install cadrumo[<extra>]`` instead of a raw deep-stack
``ModuleNotFoundError``.

These records describe package availability only. They do not decide whether an
operator has opted into Google export, browser automation, or hosted LLM usage;
that consent surface is represented separately by :class:`~core.ServiceCapability`.
"""

from __future__ import annotations

import importlib.util

from pydantic import BaseModel, Field

from .errors.hierarchy import CoreError
from .models import STRICT_FROZEN_CONFIG

__all__ = [
    "ANTHROPIC_EXTRA",
    "BROWSER_EXTRA",
    "GOOGLE_EXTRA",
    "LLM_EXTRA",
    "OFX_EXTRA",
    "OPTIONAL_EXTRAS",
    "MissingOptionalExtraError",
    "OptionalExtra",
    "optional_extra_available",
    "optional_extra_for_module",
    "require_optional_extra",
]


class OptionalExtra(BaseModel):
    """A capability-gated optional package extra and how to probe/install it.

    Attributes:
        extra: The ``[project.optional-dependencies]`` key.
        import_name: Importable package/module name used by the spec-only probe.
        feature: Human-readable feature label used in refusals and doctor rows.
    """

    model_config = STRICT_FROZEN_CONFIG

    extra: str = Field(min_length=1)
    import_name: str = Field(min_length=1)
    feature: str = Field(min_length=1)


# The capability-mapped optional extras declared in
# ``[project.optional-dependencies]``. Each adapter family guards its own entry
# with the matching constant; the doctor enumerates the tuple.
GOOGLE_EXTRA = OptionalExtra(extra="google", import_name="googleapiclient", feature="Google Drive / Sheets export")
BROWSER_EXTRA = OptionalExtra(extra="browser", import_name="playwright", feature="live AEAT browser automation")
ANTHROPIC_EXTRA = OptionalExtra(extra="anthropic", import_name="anthropic", feature="the Anthropic-API LLM provider")
# ``ofxtools`` is GPL-3.0-only; gating it behind an extra keeps the CORE
# dependency closure free of strong copyleft.
OFX_EXTRA = OptionalExtra(extra="ofx", import_name="ofxtools", feature="OFX/QFX bank-statement import")
# Local-inference document reading (the gated ``cadrumo.llm`` subpackage).
# Registered here rather than hand-rolled outside the classifier like the
# ``agent`` extra, so the doctor enumerates it and one refusal shape covers
# every inference boundary.
#
# **The probe target must be EXCLUSIVE to the extra, and that is why it is
# ``pynvml`` rather than ``PIL``.** A probe answers one question: is the extra
# installed. Pillow cannot answer it, because Pillow is also an unconditional
# base dependency (declared directly, since ``pypdfium2``'s ``to_pil()`` relies
# on it) -- so ``find_spec("PIL")`` succeeds in every core install,
# :func:`optional_extra_available` is permanently true, and every
# :func:`require_optional_extra` call below it is a no-op that reports the
# boundary healthy while it fails open. ``pynvml`` is supplied by
# ``nvidia-ml-py``, which the ``llm`` extra declares and the core closure does
# not, so its spec is present exactly when the extra is installed. This is a
# spec-only probe, so it needs no NVIDIA hardware and no NVML runtime: the
# accelerator reader handles an absent driver on its own terms.
LLM_EXTRA = OptionalExtra(extra="llm", import_name="pynvml", feature="local-inference document reading")

OPTIONAL_EXTRAS: tuple[OptionalExtra, ...] = (GOOGLE_EXTRA, BROWSER_EXTRA, ANTHROPIC_EXTRA, OFX_EXTRA, LLM_EXTRA)


class MissingOptionalExtraError(CoreError, ImportError):
    """Raised when a feature is reached but its optional extra is not installed.

    Descends from :class:`~core.errors.CoreError` so the project-wide
    :class:`~core.errors.CadrumoError` boundary sees the refusal, and from
    :class:`ImportError` so adapters that already catch import failures keep
    working. Application probes report the same missing package as a
    :class:`application.provisioning.DependencyStatus`; feature guards raise
    this exception only when the operator reaches the guarded boundary.

    Carries the extra's machine identity and nothing else. The operator-facing
    text is the registered error code's own translation key, so this refusal
    renders through the same catalogue every other registered error does, and
    the recovery is resolved downstream from the facts rather than rendered
    here as an install command.

    Attributes:
        extra: Optional-extra registry record that failed the spec-only probe.
    """

    def __init__(self, extra: OptionalExtra) -> None:
        """Initialize the error from the missing optional-extra registry record."""
        self.extra = extra
        super().__init__(
            translated_message=type(self).code.message_key,
            context={"extra": extra.extra, "import_name": extra.import_name, "importable": False},
        )
        self.name = extra.import_name
        self.path = None


def optional_extra_available(extra: OptionalExtra) -> bool:
    """Return whether ``extra``'s package is importable, without importing it.

    A spec-only check (:func:`importlib.util.find_spec`) — no side effects, no
    heavy module load. Never raises: a missing parent package resolves to
    ``False``. This helper intentionally does not call
    :func:`require_optional_extra`; probes should report dependency status, not
    raise feature-boundary refusals.

    Args:
        extra: The :class:`OptionalExtra` registry record to probe.

    Returns:
        ``True`` when ``extra.import_name`` has an import spec; otherwise
        ``False``.
    """
    try:
        return importlib.util.find_spec(extra.import_name) is not None
    except ModuleNotFoundError:
        return False


def optional_extra_for_module(module_name: str) -> OptionalExtra | None:
    """Return the registered extra that owns ``module_name``, or ``None``.

    Answers the classification question "is this missing module a capability
    package the operator may legitimately not have installed?" against
    :data:`OPTIONAL_EXTRAS` — the declared inventory of optionally-absent
    packages. Any module outside that inventory is a required dependency (or a
    first-party module), so its absence is a broken installation rather than a
    configuration choice.

    Matching is on the top-level package so a failed deep import
    (``playwright.async_api``) attributes to its owning extra. The match is
    deliberately one-way: a ``ModuleNotFoundError`` raised from *inside* an
    installed optional package names that package's own missing dependency, does
    not match the registry, and is therefore classified as a real failure.

    Args:
        module_name: The dotted module name that failed to import.

    Returns:
        The owning :class:`OptionalExtra`, or ``None`` when ``module_name``
        belongs to no registered extra.
    """
    root = module_name.split(".", 1)[0]
    if not root:
        return None
    return next((extra for extra in OPTIONAL_EXTRAS if extra.import_name.split(".", 1)[0] == root), None)


def require_optional_extra(extra: OptionalExtra) -> None:
    """Raise :class:`MissingOptionalExtraError` when ``extra`` is absent; a no-op when present.

    Call this at a feature boundary, immediately before the lazy import of the
    extra's package, so a missing extra becomes a single actionable message
    instead of a raw deep-stack ``ModuleNotFoundError``.

    Args:
        extra: The :class:`OptionalExtra` required by the feature boundary.

    Raises:
        MissingOptionalExtraError: If ``extra.import_name`` is not importable.
    """
    if not optional_extra_available(extra):
        raise MissingOptionalExtraError(extra)
