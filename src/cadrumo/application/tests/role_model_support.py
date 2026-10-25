"""Shared support resolving the model id an on-host reader for a role loads."""

from __future__ import annotations

from ...core.config import Settings, load_settings
from ...core.model_catalogue import ModelRole
from ..local_reader import select_role_model


def configured_role_model(role: ModelRole, settings: Settings | None = None) -> str | None:
    """Return the runtime model id the on-host reader for ``role`` actually loads.

    The two document readers load their settings as written. The column mapper
    and the supply-nature proposer resolve through :func:`select_role_model`,
    so this returns whatever that selection names -- the operator's setting
    when it differs from the shipped default, otherwise the catalogue's pick
    for this machine, whatever its free memory says this moment -- or ``None``
    when no catalogued model can serve the role.
    """
    resolved = settings if settings is not None else load_settings()
    selection = select_role_model(role, resolved)
    if role is ModelRole.VISION_TRANSCRIPTION:
        return resolved.cadrumo_llm_ollama_vision_model
    if role is ModelRole.TEXT_EXTRACTION:
        return resolved.cadrumo_llm_ollama_text_model
    return selection.capacity_runtime_id
