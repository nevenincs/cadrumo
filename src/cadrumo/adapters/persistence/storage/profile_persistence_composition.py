"""The one composition of the ports a profile-bound host must bind together.

Custody, the login session, workflow persistence and the language resolver are
one unit. A host that binds some and not the rest can open a capsule it cannot
then read a record through, and application code says so by refusing rather
than assuming: an unbound port raises ``InternalInvariantError`` instead of
reporting an absent profile. Discharging that obligation is the host's job, and
this module is where every host discharges it.

Four hosts enter this scope -- the shipped frontend composition root, the MCP
server's own root, the pytest session fixture, and the docs-sequence runner --
and each used to restate the wiring. The copies had already drifted over which
ports belong to the set, which is the failure mode this module removes: a port
added here reaches all of them in the same change.

It lives beside the adapters it builds rather than in either process root
because the MCP distribution is an outer root in its own right and does not
import the CLI entrypoint, and because a test host must not have to reach into
a ``tests`` package for shipped wiring. Importing this module pulls only the
persistence tree, which is what entering the scope pulls in anyway.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ....application.user_profile.custody_ports import ProfileCustodyPort


@contextmanager
def composed_profile_persistence_ports() -> Generator[ProfileCustodyPort]:
    """Bind the profile-persistence ports for one host scope, and unbind after.

    The yielded custody port is the one that was bound, so a caller holding on
    to it does not build a second instance.
    """
    from ....application.user_profile.custody_ports import bind_profile_custody_port
    from ....application.user_profile.language_resolver import register_language_resolver
    from ....application.user_profile.login_session_port import bind_profile_login_session_port
    from ....application.workflow.persistence import bind_workflow_persistence_port
    from ..workflow import build_workflow_persistence_port
    from .profile_custody import build_profile_custody_port
    from .profile_login_session import build_profile_login_session_port

    profile_custody = build_profile_custody_port()
    with ExitStack() as composition:
        composition.enter_context(bind_profile_custody_port(profile_custody))
        composition.enter_context(bind_profile_login_session_port(build_profile_login_session_port()))
        composition.enter_context(bind_workflow_persistence_port(build_workflow_persistence_port()))
        register_language_resolver()
        yield profile_custody


__all__ = ["composed_profile_persistence_ports"]
