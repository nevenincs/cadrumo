"""Where the on-host reader answers, for an execution an agent submitted."""

from __future__ import annotations

from ...core.config import Settings
from ...core.loopback_endpoint import endpoint_is_loopback
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError


def require_reader_on_this_machine(settings: Settings) -> None:
    """Refuse an agent's read unless the on-host reader answers on this machine's loopback.

    A read is called on-host by the provider it names, and that provider's
    endpoint is a setting that can name another host. A person who points it
    elsewhere chose where their documents go. An agent's read stays on this
    machine or does not run, whichever reader the document's shape would pick.
    Call it before any text or image is handed to a reader, and build the
    reader from these same settings: the local reader sends a loopback request
    to the endpoint it was given, without a proxy and without following a
    redirect.
    """
    if not endpoint_is_loopback(settings.cadrumo_llm_ollama_chat_url):
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)


__all__ = ["require_reader_on_this_machine"]
