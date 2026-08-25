"""Explicit real persistence composition for fresh-interpreter test hosts."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager


@contextmanager
def composed_profile_persistence_ports() -> Iterator[None]:
    """Bind the production custody and login-session adapters for one test host."""
    from ..adapters.persistence.storage import build_profile_custody_port, build_profile_login_session_port
    from ..application.user_profile import bind_profile_custody_port, bind_profile_login_session_port

    with ExitStack() as composition:
        composition.enter_context(bind_profile_custody_port(build_profile_custody_port()))
        composition.enter_context(bind_profile_login_session_port(build_profile_login_session_port()))
        yield


__all__ = ["composed_profile_persistence_ports"]
