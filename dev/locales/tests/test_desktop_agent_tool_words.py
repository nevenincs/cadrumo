"""Every tool the agent can call has a label and a description in every locale the window shows."""

from __future__ import annotations

import pytest

from cadrumo_mcp.mcp.protocol_contract import MCP_TOOL_CATALOGUE

from ..desktop_agent_tool_keys import (
    AGENT_OWN_TOOLS,
    AGENT_TOOL_FAMILIES,
    AGENT_TOOL_KEY_PREFIX,
    AGENT_TOOL_KEYS,
    AGENT_TOOL_WORD_PARTS,
    CADRUMO_MCP_SERVER,
    CADRUMO_MCP_TOOLS,
)
from ..desktop_chrome import DESKTOP_CHROME_FAMILIES, DESKTOP_CHROME_KEYS, DESKTOP_LOCALES, desktop_chrome_strings

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_declared_cadrumo_tools_are_the_ones_the_mcp_service_declares() -> None:
    assert sorted(CADRUMO_MCP_TOOLS) == sorted(name for name, _description, _schema in MCP_TOOL_CATALOGUE)


def test_every_declared_tool_has_a_label_and_a_description_key() -> None:
    expected = {
        f"{AGENT_TOOL_KEY_PREFIX}{server}.{name}.{part}"
        for server, names in ((CADRUMO_MCP_SERVER, CADRUMO_MCP_TOOLS), ("cadrumo_agent_tools", AGENT_OWN_TOOLS))
        for name in names
        for part in AGENT_TOOL_WORD_PARTS
    }
    assert expected == AGENT_TOOL_KEYS
    assert expected <= DESKTOP_CHROME_KEYS
    assert dict(AGENT_TOOL_FAMILIES).items() <= DESKTOP_CHROME_FAMILIES.items()


def test_every_tool_key_is_authored_in_every_locale_the_window_shows() -> None:
    strings = desktop_chrome_strings(keys=AGENT_TOOL_KEYS)
    assert set(strings) == set(DESKTOP_LOCALES)
    for locale, words in strings.items():
        assert set(words) == AGENT_TOOL_KEYS, locale
        assert all(text.strip() for text in words.values()), locale


def test_a_tool_is_worded_differently_in_each_locale_it_translates() -> None:
    strings = desktop_chrome_strings(keys=AGENT_TOOL_KEYS)
    label = f"{AGENT_TOOL_KEY_PREFIX}{CADRUMO_MCP_SERVER}.execute.label"
    assert len({strings[locale][label] for locale in DESKTOP_LOCALES}) == len(DESKTOP_LOCALES)
