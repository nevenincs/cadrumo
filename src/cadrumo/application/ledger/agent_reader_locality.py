"""Where the on-host reader answers, for an execution an agent submitted."""

from __future__ import annotations

from ...core.config import Settings
from ..provisioning_host import runtime_endpoint_is_local
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError


def require_reader_on_this_machine(settings: Settings) -> None:
    """Refuse an agent's read unless the on-host reader answers on this machine's loopback.

    A read is called on-host by the provider it names, and that provider's
    endpoint is a setting that can name another host. A person who points it
    elsewhere chose where their documents go. An agent's read stays on this
    machine or does not run, whichever reader the document's shape would pick.
    Call it before any text or image is handed to a reader.
    """
    try:
        on_this_machine = runtime_endpoint_is_local(settings.cadrumo_llm_ollama_chat_url)
    except ValueError:
        on_this_machine = False
    if not on_this_machine:
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)


__all__ = ["require_reader_on_this_machine"]
