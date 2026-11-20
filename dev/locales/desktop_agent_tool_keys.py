"""The words the desktop shows for the tools the agent calls.

The agent serves each call with the identity of its tool: the server that owns
it and its name there. The shell words a tool by those two names, so a tool
gained is declared here with its words.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

#: The tool server of Cadrumo's deterministic MCP service, and the names of its
#: tools. The service's own declaration is the source of this list, and a test
#: holds the two equal.
CADRUMO_MCP_SERVER: Final[str] = "cadrumo"
CADRUMO_MCP_TOOLS: Final[tuple[str, ...]] = (
    "status",
    "authority",
    "corpus_search",
    "views",
    "search",
    "describe",
    "execute",
    "observe",
    "result",
    "result_page",
    "review",
    "respond",
    "control",
)

#: The tool server of the agent's own tools, and their names. This mirrors the
#: names cadrumo-agent serves for them; the agent is not importable here.
AGENT_OWN_SERVER: Final[str] = "cadrumo_agent_tools"
AGENT_OWN_TOOLS: Final[tuple[str, ...]] = (
    "read_file",
    "write_file",
    "run_program",
    "load_skill",
    "read_conversation_history",
    "search_previous_conversations",
    "read_attachment",
    "list_attachments",
    "web_search",
    "read_web_source",
    "resolve_output_path",
    "run_subagent",
)

#: Every server whose tools the shell words, with the names of its tools.
AGENT_TOOLS_BY_SERVER: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {CADRUMO_MCP_SERVER: CADRUMO_MCP_TOOLS, AGENT_OWN_SERVER: AGENT_OWN_TOOLS}
)

AGENT_TOOL_KEY_PREFIX: Final[str] = "desktop.agent.tool."
AGENT_TOOL_WORD_PARTS: Final[tuple[str, ...]] = ("label", "description")

#: The family of words a tool has, as ``prefix -> members``.
AGENT_TOOL_FAMILIES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        AGENT_TOOL_KEY_PREFIX: tuple(
            f"{server}.{name}.{part}"
            for server, names in AGENT_TOOLS_BY_SERVER.items()
            for name in names
            for part in AGENT_TOOL_WORD_PARTS
        )
    }
)

#: Every tool key the desktop words, each family member spelled out.
AGENT_TOOL_KEYS: Final[frozenset[str]] = frozenset(
    f"{prefix}{member}" for prefix, members in AGENT_TOOL_FAMILIES.items() for member in members
)
