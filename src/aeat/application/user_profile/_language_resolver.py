"""Active-profile output-language resolver wiring for ``core.i18n``.

The ``core`` layer must not import application modules, so it resolves
the active profile's ``preferences.output_language`` preference through
a registered callback (see
:func:`aeat.core.i18n.register_profile_language_resolver`).

This module owns the application-side resolver and registers it as a
module-import side-effect. Importing it is cheap — every heavyweight
import (workflow persistence, orchestration) is deferred inside the
resolver body so registration cannot trigger an import cascade.
"""

from __future__ import annotations

from ...core.i18n import register_profile_language_resolver


def resolve_active_profile_output_language() -> str | None:
    """Return the active profile's ``preferences.output_language`` fact.

    Performs a pure read of workflow state — no mutation, no bucket
    events — and returns ``None`` when there is no active profile or no
    language fact, so the caller falls back to the settings default.
    """
    from ...adapters.persistence.storage import has_active_bucket_session

    if not has_active_bucket_session():
        return None

    from ..workflow._persistence import workflow_state_repository
    from ._orchestration import fact_value

    record = workflow_state_repository().load().active_profile_record()
    if record is None:
        return None
    return fact_value(record, "preferences.output_language")


def register_language_resolver() -> None:
    """Register :func:`resolve_active_profile_output_language` with ``core.i18n``.

    Replaces the prior module-import side-effect registration: callers
    now invoke this function from a known initialiser (the
    :mod:`aeat.application.user_profile` package import) so the
    registration point is explicit and greppable rather than hidden in
    a noqa-protected import line.
    """
    register_profile_language_resolver(resolve_active_profile_output_language)
