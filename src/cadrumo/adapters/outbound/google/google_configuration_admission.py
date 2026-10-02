"""Optional per-request authority admission over Google's canonical transport."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol, cast, override

from ....application.user_profile.google_configuration_operation_ports import (
    GoogleConfigurationAcknowledgement,
    GoogleConfigurationHandoff,
)

if TYPE_CHECKING:
    from google.auth.transport import Request


class GoogleAuthResponse(Protocol):
    """The public google.auth.transport.Response interface returned unchanged."""

    @property
    def status(self) -> int:
        """Return the HTTP response status code."""
        ...

    @property
    def headers(self) -> Mapping[str, str]:
        """Return the response headers."""
        ...

    @property
    def data(self) -> bytes:
        """Return the response body bytes."""
        ...


class _CanonicalRequest(Protocol):
    """The locked requests transport's documented callable boundary."""

    def __call__(
        self,
        url: str,
        method: str = "GET",
        body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | tuple[float, float] | None = 120,
        **kwargs: object,
    ) -> GoogleAuthResponse:
        """Delegate endpoint kwargs and return Google's unchanged response adapter."""
        ...


def admitted_google_auth_request(
    *,
    before_handoff: GoogleConfigurationHandoff | None,
    acknowledged: GoogleConfigurationAcknowledgement | None,
    action: str,
) -> Request:
    """Reuse the actual Google Request, renewing immediately before each HTTP call."""
    from google.auth.transport import Request
    from google.auth.transport.requests import Request as RequestsRequest

    if before_handoff is None and acknowledged is None:
        return RequestsRequest()

    class AdmittedRequest(Request):
        def __init__(self) -> None:
            """Own the actual requests adapter and its unchanged HTTP session."""
            self._delegate = RequestsRequest()
            self.session = self._delegate.session

        @override
        def __call__(
            self,
            url: str,
            method: str = "GET",
            body: bytes | None = None,
            headers: Mapping[str, str] | None = None,
            timeout: float | tuple[float, float] | None = 120,
            **kwargs: object,
        ) -> GoogleAuthResponse:
            """Renew just before Google's own HTTP call and acknowledge its return."""
            if before_handoff is not None:
                before_handoff(action)
            # CAST-RATIONALE-GOOGLE-AUTH-REQUEST: the locked Request forwards
            # these documented parameters to requests.Session.request; its
            # unannotated timeout default otherwise infers only int.
            delegate = cast(_CanonicalRequest, self._delegate)
            response = delegate(url, method=method, body=body, headers=headers, timeout=timeout, **kwargs)
            if acknowledged is not None:
                acknowledged(action)
            return response

    return AdmittedRequest()


__all__ = ["GoogleAuthResponse", "admitted_google_auth_request"]
