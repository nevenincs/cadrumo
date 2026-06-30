"""Typed ``--json`` payload for ``aeat app agent materialise``.

The materialiser writes the shipped operator harness (rules, personas, skills)
into an operator-chosen directory. The result is a strict
:class:`~aeat.entrypoints.cli._schemas.OutputSchema` mirroring the application
:class:`~aeat.agent.WorkspaceManifest`, surfaced through
:class:`~aeat.entrypoints.cli._schemas.SchemaEnvelope`.
"""

from __future__ import annotations

from pydantic import Field

from ._schemas import OutputSchema, register_schema


@register_schema("agent")
class AgentWorkspaceResult(OutputSchema):
    """JSON result of materialising an operator workspace.

    Mirrors :class:`~aeat.agent.WorkspaceManifest`: the output path and the count
    of rules, personas, and skills written from the shipped harness data.
    """

    output_path: str = Field(min_length=1)
    rules_written: int = Field(ge=0)
    personas_written: int = Field(ge=0)
    skills_written: int = Field(ge=0)
