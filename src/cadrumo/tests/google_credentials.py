"""Google credentials stand-ins for tests that must never reach the network.

Many Google adapter tests exercise a path that refuses before any credential
is used -- a blank identifier, an unreachable scope, a link the ``drive.file``
scope cannot see -- or they inject a transport-only service seam and so build
no client at all. Those tests still have to pass *something* for the
``credentials`` parameter.

Passing a bare ``object()`` types as ``object`` and proves nothing: if the code
under test ever did reach for the credential it would raise
``AttributeError`` from somewhere unrelated, and a reader cannot tell whether
the argument is deliberately unused or merely untyped. The stand-in here is a
genuine :class:`~google.auth.credentials.Credentials` subclass, so it satisfies
the real parameter type, and its one abstract method fails loudly with a
message naming what happened.

Lives in the shared test-support package rather than beside one suite because
the same need appears in three layers at once -- the Google outbound adapters,
the storage provider adapters, and the calc-sheets application service.
"""

from __future__ import annotations

from typing import Never, override

from google.auth.credentials import Credentials


class UnusedGoogleCredentials(Credentials):
    """Credentials the code under test is expected never to use.

    Any refresh is a test failure rather than a network call: reaching this
    method means the path under test tried to authenticate when the test
    asserted it would refuse, or would use an injected service, first.
    """

    @override
    def refresh(self, request: object) -> Never:
        message = "the path under test must not authenticate, but refreshed these credentials"
        raise AssertionError(message)


def unused_google_credentials() -> Credentials:
    """Return credentials that satisfy the parameter type and refuse any use."""
    return UnusedGoogleCredentials()


__all__ = ["UnusedGoogleCredentials", "unused_google_credentials"]
