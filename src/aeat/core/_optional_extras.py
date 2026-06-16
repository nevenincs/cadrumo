"""Capability-gated optional package extras and their import guard.

The shipped package is lean: a bare ``pip install aeat`` omits the optional
integration stacks (Google export, the live-AEAT browser, the Anthropic-API LLM
provider). Each maps to a ``[project.optional-dependencies]`` extra and is
imported lazily, so the core CLI builds and runs without it.

This module is the single source of truth for those extras. It lives in ``core``
— the innermost layer — so an adapter can guard its own external-library import
without importing the application layer, and the doctor (application) can probe
the same registry. :func:`require_optional_extra` is the seam every feature
boundary calls before its lazy import so a missing extra becomes one instructive
:class:`MissingOptionalExtraError` naming ``pip install aeat[<extra>]`` instead of
a raw deep-stack ``ModuleNotFoundError``.
"""

from __future__ import annotations

import importlib.util

from pydantic import BaseModel, Field

from ._models import STRICT_FROZEN_CONFIG

__all__ = [
    "ANTHROPIC_EXTRA",
    "BROWSER_EXTRA",
    "GOOGLE_EXTRA",
    "OPTIONAL_EXTRAS",
    "MissingOptionalExtraError",
    "OptionalExtra",
    "optional_extra_available",
    "require_optional_extra",
]


class OptionalExtra(BaseModel):
    """A capability-gated optional package extra and how to probe/install it."""

    model_config = STRICT_FROZEN_CONFIG

    extra: str = Field(min_length=1)
    import_name: str = Field(min_length=1)
    feature: str = Field(min_length=1)

    @property
    def install_hint(self) -> str:
        """The exact command that installs this extra."""
        return f"pip install aeat[{self.extra}]"


# The capability-mapped optional extras declared in
# ``[project.optional-dependencies]``. Each adapter family guards its own entry
# with the matching constant; the doctor enumerates the tuple.
GOOGLE_EXTRA = OptionalExtra(extra="google", import_name="googleapiclient", feature="Google Drive / Sheets export")
BROWSER_EXTRA = OptionalExtra(extra="browser", import_name="playwright", feature="live AEAT browser automation")
ANTHROPIC_EXTRA = OptionalExtra(extra="anthropic", import_name="anthropic", feature="the Anthropic-API LLM provider")

OPTIONAL_EXTRAS: tuple[OptionalExtra, ...] = (GOOGLE_EXTRA, BROWSER_EXTRA, ANTHROPIC_EXTRA)


class MissingOptionalExtraError(ImportError):
    """Raised when a feature is reached but its optional extra is not installed.

    Subclasses :class:`ImportError` so an adapter that already catches import
    failures keeps working, while carrying the structured :attr:`extra` and a
    ready-to-print :attr:`install_hint` for the feature's own error handler.
    """

    def __init__(self, extra: OptionalExtra) -> None:
        self.extra = extra
        self.install_hint = extra.install_hint
        super().__init__(
            f"{extra.feature} requires the optional '{extra.extra}' extra. Install it with: {extra.install_hint}",
            name=extra.import_name,
        )


def optional_extra_available(extra: OptionalExtra) -> bool:
    """Return whether ``extra``'s package is importable, without importing it.

    A spec-only check (:func:`importlib.util.find_spec`) — no side effects, no
    heavy module load. Never raises: a missing parent package resolves to
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
    """
    if not optional_extra_available(extra):
        raise MissingOptionalExtraError(extra)
