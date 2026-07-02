"""Typed ``--json`` payload for ``aeat app agent materialise``.

The materialiser writes the shipped operator harness (rules, personas, skills)
into an operator-chosen directory. The result is a strict
:class:`OutputSchema` mirroring the application
:class:`WorkspaceManifest`, surfaced through :class:`SchemaEnvelope`.
"""

from __future__ import annotations

from pydantic import Field

from ._schemas import OutputSchema, register_schema


@register_schema("agent")
class AgentWorkspaceResult(OutputSchema):
    """JSON result of materialising an operator workspace.

    Mirrors :class:`WorkspaceManifest`: the output path and the count of rules,
    personas, and skills written from the shipped harness data.
    """

    output_path: str = Field(min_length=1)
    rules_written: int = Field(ge=0)
    personas_written: int = Field(ge=0)
    skills_written: int = Field(ge=0)
