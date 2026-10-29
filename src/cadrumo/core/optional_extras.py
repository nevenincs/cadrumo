"""Capability-gated optional package extras and their import guard.

The shipped package is lean: it omits the optional integration stacks (Google
export and the live-AEAT browser). Each maps to a
``[project.optional-dependencies]`` extra and is
imported lazily, so the core CLI builds and runs without it.

This module is the single source of truth for those extras. It lives in ``core``
— the innermost layer — so an adapter can guard its own external-library import
without importing the application layer. :func:`require_optional_extra`
is the seam every feature boundary calls before its lazy import so a missing
extra becomes one :class:`MissingOptionalExtraError` naming the feature that
needs it instead of a raw deep-stack ``ModuleNotFoundError``.

These records describe package availability only. They do not decide whether an
operator has opted into Google export or browser automation;
that consent surface is represented separately by :class:`~core.capabilities.ServiceCapability`.
"""

from __future__ import annotations

import importlib.util

from pydantic import BaseModel, Field

from .errors.hierarchy import CoreError
from .models import STRICT_FROZEN_CONFIG

__all__ = [
    "BROWSER_EXTRA",
    "GOOGLE_EXTRA",
    "OFX_EXTRA",
    "OPTIONAL_EXTRAS",
    "PDF_EXTRA",
    "MissingOptionalExtraError",
    "OptionalExtra",
    "optional_extra_available",
    "optional_extra_for_module",
    "require_optional_extra",
]


class OptionalExtra(BaseModel):
    """A capability-gated optional package extra.

    Attributes:
        extra: The ``[project.optional-dependencies]`` key.
        import_name: Importable package/module name the import guard looks for.
        feature: Human-readable feature label used in refusals.
    """

    model_config = STRICT_FROZEN_CONFIG

    extra: str = Field(min_length=1)
    import_name: str = Field(min_length=1)
    feature: str = Field(min_length=1)


# The capability-mapped optional extras declared in
# ``[project.optional-dependencies]``. Each adapter family guards its own entry
# with the matching constant.
GOOGLE_EXTRA = OptionalExtra(extra="google", import_name="googleapiclient", feature="Google Drive / Sheets export")
BROWSER_EXTRA = OptionalExtra(extra="browser", import_name="playwright", feature="live AEAT browser automation")
# ``ofxtools`` is GPL-3.0-only; gating it behind an extra keeps the CORE
# dependency closure free of strong copyleft.
OFX_EXTRA = OptionalExtra(extra="ofx", import_name="ofxtools", feature="OFX/QFX bank-statement import")
# The calculation-summary PDF writer. ``reportlab`` is exclusive to the extra:
# no core distribution requires it, so its spec is present exactly when the
# extra is installed. Reading and verifying a summary needs no extra -- that
# path runs on the core ``pikepdf``, ``pypdfium2`` and ``cryptography``.
PDF_EXTRA = OptionalExtra(extra="pdf", import_name="reportlab", feature="the calculation-summary PDF")

OPTIONAL_EXTRAS: tuple[OptionalExtra, ...] = (
    GOOGLE_EXTRA,
    BROWSER_EXTRA,
    OFX_EXTRA,
    PDF_EXTRA,
)


class MissingOptionalExtraError(CoreError):
    """Raised when a feature is reached but its optional extra is not installed.

    Descends from :class:`~core.errors.hierarchy.CoreError` so the project-wide
    :class:`~core.errors.hierarchy.CadrumoError` boundary sees the refusal. Feature
    guards raise this exception only when the operator reaches the guarded boundary.

    The operator-facing text is the registered error code's own translation
    key, so this refusal renders through the same catalogue every other
    registered error does. The context carries the extra's machine identity
    AND its feature label, because the key names both: an operator told only
    that "an internal application error occurred" cannot tell which capability
    is missing, let alone install it.

    Attributes:
        extra: Optional-extra registry record that failed the spec-only probe.
    """

    def __init__(self, extra: OptionalExtra) -> None:
        """Initialize the error from the missing optional-extra registry record."""
        self.extra = extra
        super().__init__(
            translated_message=type(self).code.message_key,
            context={
                "extra": extra.extra,
                "feature": extra.feature,
                "import_name": extra.import_name,
                "importable": False,
            },
        )
        self.name = extra.import_name
        self.path = None


def optional_extra_available(extra: OptionalExtra) -> bool:
    """Return whether ``extra``'s package is importable, without importing it.

    A spec-only check (:func:`importlib.util.find_spec`) — no side effects, no
    heavy module load. Never raises: a missing parent package resolves to
    ``False``. This helper intentionally does not call
    :func:`require_optional_extra`, which owns the feature-boundary refusal.

    Args:
        extra: The :class:`OptionalExtra` registry record to look for.

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
