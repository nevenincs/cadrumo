"""Explicit real persistence composition for fresh-interpreter test hosts."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import ExitStack, contextmanager


@contextmanager
def composed_profile_persistence_ports() -> Generator[None]:
    """Bind the production custody and login-session adapters for one test host."""
    from ..adapters.persistence.storage.profile_custody import build_profile_custody_port
    from ..adapters.persistence.storage.profile_login_session import build_profile_login_session_port
    from ..application.user_profile.custody_ports import bind_profile_custody_port
    from ..application.user_profile.language_resolver import register_language_resolver
    from ..application.user_profile.login_session_port import bind_profile_login_session_port

    with ExitStack() as composition:
        composition.enter_context(bind_profile_custody_port(build_profile_custody_port()))
        composition.enter_context(bind_profile_login_session_port(build_profile_login_session_port()))
        register_language_resolver()
        yield


__all__ = ["composed_profile_persistence_ports"]
