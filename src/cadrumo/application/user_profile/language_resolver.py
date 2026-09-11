"""Resolve the active profile's preferred output language for ``core.i18n``.

The ``core`` layer remains independent of application modules. It resolves the
active profile's ``preferences.output_language`` preference through a registered
callback. Each executable host explicitly calls :func:`register_language_resolver`
when it composes profile persistence. That function registers
:func:`resolve_active_profile_output_language` with
:func:`cadrumo.core.i18n.register_profile_language_resolver`.
"""

from __future__ import annotations

from ...core.i18n.render import register_profile_language_resolver
from ...core.logging import get_logger
from ...core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from .custody_ports import (
    clear_profile_output_language_hint,
    read_profile_output_language_hint,
    write_profile_output_language_hint,
)
from .login_session_port import profile_current_bucket_session

_logger = get_logger(__name__)

__all__ = [
    "mirror_profile_output_language_hint",
    "register_language_resolver",
    "resolve_active_profile_output_language",
    "resolve_active_profile_output_language_hint",
    "resolve_profile_output_language_hint",
]


def resolve_active_profile_output_language() -> str | None:
    """Return the active profile's ``preferences.output_language`` fact.

    Performs a pure read of workflow state — no mutation, no bucket
    events — and returns ``None`` when there is no active profile or no
    language fact, so the caller falls back to the settings default.
    When no bucket session is currently bound, reads the bucket-local
    non-secret language hint instead of the encrypted profile envelope.
    """
    if profile_current_bucket_session() is None:
        return resolve_active_profile_output_language_hint()

    from ..workflow.persistence import workflow_state_repository
    from .projections import record_to_path_values

    record = workflow_state_repository().load().active_profile_record()
    if record is None:
        return None
    return record_to_path_values(record).get(PROFILE_OUTPUT_LANGUAGE_PATH)


def resolve_active_profile_output_language_hint() -> str | None:
    """Return the active bucket's last-known output-language hint, if present."""
    try:
        from ...core.bucket_pointer import resolve_active_bucket_id

        bucket_id = resolve_active_bucket_id()
        if bucket_id is None:
            return None
        return resolve_profile_output_language_hint(bucket_id)
    except Exception:
        return None


def resolve_profile_output_language_hint(bucket_id: str) -> str | None:
    """Return a named bucket's last-known output-language hint, if present."""
    try:
        from ...core.config import load_settings

        trimmed = bucket_id.strip()
        if not trimmed:
            return None
        return read_profile_output_language_hint(
            storage_root=load_settings().cadrumo_local_storage_root,
            bucket_id=trimmed,
        )
    except Exception:
        return None


def register_language_resolver() -> None:
    """Register :func:`resolve_active_profile_output_language` with ``core.i18n``.

    Executable hosts invoke this alongside custody and login-session composition,
    keeping registration explicit and greppable rather than hiding it in a
    package-import side effect.
    """
    register_profile_language_resolver(resolve_active_profile_output_language)


def mirror_profile_output_language_hint(bucket_id: str, language: str | None) -> None:
    """Mirror a profile's language preference into its non-secret bucket hint.

    The hint answers one question the encrypted preference cannot: which
    language to speak BEFORE the profile is unlocked.
    :func:`resolve_active_profile_output_language` falls back to it whenever no
    bucket session is bound, and the reader fails soft on absence -- so while
    nothing wrote the hint, that fallback always returned ``None`` and every
    pre-login surface silently took the settings default, however deliberately
    the operator had chosen a language during setup.

    Clearing the preference clears the hint, so the two cannot disagree about
    an absence. Failure is swallowed for the same reason the read is: this
    mirrors a convenience, and a hint that could not be written must not fail
    the fact write that owns the real value.
    """
    try:
        from ...core.config import load_settings

        trimmed = bucket_id.strip()
        if not trimmed:
            return
        storage_root = load_settings().cadrumo_local_storage_root
        if language is None or not str(language).strip():
            clear_profile_output_language_hint(storage_root=storage_root, bucket_id=trimmed)
            return
        write_profile_output_language_hint(
            storage_root=storage_root,
            bucket_id=trimmed,
            language=language,
        )
    except Exception:
        _logger.debug("could not mirror the output-language hint", exc_info=True)
