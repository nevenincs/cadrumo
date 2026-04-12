"""Prompt rendering helpers."""

from __future__ import annotations

from collections.abc import Mapping

from aeat.llm._errors import LLMConfigError
from aeat.llm._models import PromptDefinition


def render_prompt(definition: PromptDefinition, values: Mapping[str, str]) -> str:
    """Render a prompt definition using string formatting."""

    try:
        return definition.template.format_map(values)
    except KeyError as exc:  # pragma: no cover - defensive error path
        msg = f"Prompt {definition.id!r} requires missing template variable {exc.args[0]!r}"
        raise LLMConfigError(msg) from exc
