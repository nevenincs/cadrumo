"""Stub for the `InstalledAppFlow` surface this project drives.

`google-auth-oauthlib` ships no `py.typed`, so every call through the installed
-app OAuth flow resolved as partially unknown, including the credentials the
flow returns. Only the members this project calls are declared; the parameter
lists mirror the runtime signatures (`InstalledAppFlow.from_client_config`,
`Flow.run_local_server`) rather than widening to `**kwargs`.
"""

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

class OAuthCredentials(Protocol):
    """The credential members the installed-app flow hands back.

    `google.oauth2.credentials.Credentials` ships `py.typed` but leaves these
    attributes unannotated, so reading them through the concrete class yields
    an unknown type. This declares the surface the flow's callers actually use.
    """

    refresh_token: str | None
    token_uri: str | None
    scopes: Sequence[str] | None
    id_token: str | None

class Flow:
    credentials: OAuthCredentials
    def run_local_server(
        self,
        host: str = ...,
        bind_addr: str | None = ...,
        port: int = ...,
        authorization_prompt_message: str | None = ...,
        success_message: str = ...,
        open_browser: bool = ...,
        redirect_uri_trailing_slash: bool = ...,
        timeout_seconds: float | None = ...,
        token_audience: str | None = ...,
        browser: str | None = ...,
        **kwargs: Any,
    ) -> OAuthCredentials: ...

class InstalledAppFlow(Flow):
    @classmethod
    def from_client_config(
        cls,
        client_config: Mapping[str, Any],
        scopes: Sequence[str] | None,
        **kwargs: Any,
    ) -> InstalledAppFlow: ...
