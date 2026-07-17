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

from ._models import STRICT_FROZEN_CONFIG
from .errors import CoreError

__all__ = [
    "ANTHROPIC_EXTRA",
    "BROWSER_EXTRA",
    "GOOGLE_EXTRA",
    "OFX_EXTRA",
    "OPTIONAL_EXTRAS",
    "MissingOptionalExtraError",
    "OptionalExtra",
    "optional_extra_available",
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

    @property
    def install_hint(self) -> str:
        """Return the exact package-install command for this extra.

        This is a dependency remediation hint, not a runtime provisioning command
        such as ``playwright install chromium``.
        """
        return f"pip install cadrumo[{self.extra}]"


# The capability-mapped optional extras declared in
# ``[project.optional-dependencies]``. Each adapter family guards its own entry
# with the matching constant; the doctor enumerates the tuple.
GOOGLE_EXTRA = OptionalExtra(extra="google", import_name="googleapiclient", feature="Google Drive / Sheets export")
BROWSER_EXTRA = OptionalExtra(extra="browser", import_name="playwright", feature="live AEAT browser automation")
ANTHROPIC_EXTRA = OptionalExtra(extra="anthropic", import_name="anthropic", feature="the Anthropic-API LLM provider")
# ``ofxtools`` is GPL-3.0-only; gating it behind an extra keeps the CORE
# dependency closure free of strong copyleft.
OFX_EXTRA = OptionalExtra(extra="ofx", import_name="ofxtools", feature="OFX/QFX bank-statement import")

OPTIONAL_EXTRAS: tuple[OptionalExtra, ...] = (GOOGLE_EXTRA, BROWSER_EXTRA, ANTHROPIC_EXTRA, OFX_EXTRA)


class MissingOptionalExtraError(CoreError, ImportError):
    """Raised when a feature is reached but its optional extra is not installed.

    Descends from :class:`~core.errors.CoreError` so the project-wide
    :class:`~core.errors.CadrumoError` boundary sees the refusal, and from
    :class:`ImportError` so adapters that already catch import failures keep
    working. Application probes report the same missing package as a
    :class:`application.provisioning.DependencyStatus`; feature guards raise
    this exception only when the operator reaches the guarded boundary.

    Attributes:
        extra: Optional-extra registry record that failed the spec-only probe.
        install_hint: Exact ``pip install cadrumo[<extra>]`` remediation command.
    """

    def __init__(self, extra: OptionalExtra) -> None:
        self.extra = extra
        self.install_hint = extra.install_hint
        message = f"{extra.feature} requires the optional '{extra.extra}' extra. Install it with: {extra.install_hint}"
        super().__init__(
            message,
            context={"extra": extra.extra, "import_name": extra.import_name, "feature": extra.feature},
            suggestion=extra.install_hint,
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
