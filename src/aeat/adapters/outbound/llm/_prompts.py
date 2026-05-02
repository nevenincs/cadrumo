"""Prompt rendering helpers.

Renders :class:`aeat.adapters.outbound.llm.PromptDefinition` templates
against caller-supplied substitution mappings using Python's
:meth:`str.format_map` semantics. Missing template variables surface as a
typed :exc:`aeat.adapters.outbound.llm.LLMConfigError` rather than a bare
:exc:`KeyError` so consumers always handle prompt-shape failures through
the substrate's error envelope.
"""

from __future__ import annotations

from collections.abc import Mapping

from ._errors import LLMConfigError
from ._models import PromptDefinition


def render_prompt(definition: PromptDefinition, values: Mapping[str, str]) -> str:
    """Render a prompt definition using string formatting.

    Substitutes ``{...}`` placeholders in :attr:`PromptDefinition.template`
    with values from ``values`` via :meth:`str.format_map`.

    Args:
        definition: The registered :class:`PromptDefinition` to render.
        values: Mapping of template variable names to substitution values.

    Returns:
        The rendered prompt text.

    Raises:
        LLMConfigError: When ``values`` does not provide every template
            variable referenced by ``definition.template``.
    """

    try:
        return definition.template.format_map(values)
    except KeyError as exc:  # pragma: no cover - defensive error path
        msg = f"Prompt {definition.id!r} requires missing template variable {exc.args[0]!r}"
        raise LLMConfigError(msg) from exc
