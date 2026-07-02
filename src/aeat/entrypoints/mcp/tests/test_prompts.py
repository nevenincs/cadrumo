"""Guided-workflow prompts embed the shipped skills and orient the session.

Proves the guided-workflow prompt channel (decision record R4): the catalogue is exactly the shipped
skills plus the orientation entry, every skill prompt embeds its ``SKILL.md``
verbatim as a resource, the orientation prompt embeds the operator rules, and an
unknown prompt name maps to a clean protocol error. The SDK-independent
``_prompts.py`` surface is asserted directly; the server-side ``list``/``get``
wiring is asserted through the real built ``Server`` - built with an empty
descriptor set so the prompt handlers are exercised without transiting the CLI
tool-descriptor import chain. When the ``aeat[agent]`` extra is absent, the
SDK-dependent build is asserted to fail at the optional-dependency boundary
instead - never a skip.
"""

from __future__ import annotations

import importlib.util
from typing import Any, cast

import anyio
import pytest

from ....agent import iter_skill_documents, operator_rules_text
from .._prompts import (
    ORIENTATION_PROMPT_NAME,
    PromptNotFoundError,
    build_prompt_catalogue,
    prompt_document,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_UTF_8 = "utf-8"
_SDK_PRESENT = importlib.util.find_spec("mcp") is not None


def _shipped_skill_texts() -> dict[str, str]:
    texts: dict[str, str] = {}
    for document in iter_skill_documents():
        name = str(document).replace("\\", "/").split("/")[-2]
        texts[name] = document.read_text(encoding=_UTF_8)
    return texts


# --- catalogue + document (SDK-independent) -----------------------------------


def test_catalogue_is_the_shipped_skills_plus_orientation() -> None:
    catalogue = build_prompt_catalogue()
    names = [entry.name for entry in catalogue]
    skill_names = set(_shipped_skill_texts())
    assert ORIENTATION_PROMPT_NAME in names
    assert set(names) - {ORIENTATION_PROMPT_NAME} == skill_names
    assert len(catalogue) == len(skill_names) + 1


def test_each_skill_prompt_embeds_its_skill_document_verbatim() -> None:
    skill_texts = _shipped_skill_texts()
    for name, text in skill_texts.items():
        document = prompt_document(name)
        assert document.brief_text.strip()
        embedded_texts = [item.text for item in document.embedded]
        assert text in embedded_texts
        assert document.embedded[0].uri == f"aeat://skill/{name}"
        assert document.embedded[0].mime_type == "text/markdown"


def test_orientation_prompt_embeds_the_operator_rules() -> None:
    document = prompt_document(ORIENTATION_PROMPT_NAME)
    assert document.brief_text.strip()
    embedded_texts = [item.text for item in document.embedded]
    assert operator_rules_text() in embedded_texts


def test_unknown_prompt_name_raises_prompt_not_found() -> None:
    with pytest.raises(PromptNotFoundError):
        prompt_document("no-such-workflow")


# --- server list/get wiring (SDK-gated, empty descriptors, never skipped) ------


def test_server_lists_and_serves_every_prompt() -> None:
    from .._server import build_server

    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(())
        return

    from mcp.types import GetPromptRequest, GetPromptRequestParams, ListPromptsRequest

    # An empty descriptor set exercises the prompt handlers without building the
    # CLI tool descriptors (the prompt channel is independent of the tool surface).
    server = cast("Any", build_server(()))
    handlers = server.request_handlers
    skill_texts = _shipped_skill_texts()

    async def _drive() -> None:
        listed = (await handlers[ListPromptsRequest](ListPromptsRequest(method="prompts/list"))).root.prompts
        assert {prompt.name for prompt in listed} == {entry.name for entry in build_prompt_catalogue()}

        request = GetPromptRequest(
            method="prompts/get",
            params=GetPromptRequestParams(name="preparar-modelo-130"),
        )
        result = (await handlers[GetPromptRequest](request)).root
        assert result.messages[0].content.type == "text"
        assert result.messages[0].content.text.strip()
        resource_message = result.messages[1]
        assert resource_message.content.type == "resource"
        assert str(resource_message.content.resource.uri) == "aeat://skill/preparar-modelo-130"
        assert resource_message.content.resource.mimeType == "text/markdown"
        assert resource_message.content.resource.text == skill_texts["preparar-modelo-130"]

    anyio.run(_drive)


def test_server_get_prompt_orientation_embeds_the_rules() -> None:
    from .._server import build_server

    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(())
        return

    from mcp.types import GetPromptRequest, GetPromptRequestParams

    server = cast("Any", build_server(()))
    handlers = server.request_handlers

    async def _drive() -> None:
        request = GetPromptRequest(
            method="prompts/get",
            params=GetPromptRequestParams(name=ORIENTATION_PROMPT_NAME),
        )
        result = (await handlers[GetPromptRequest](request)).root
        embedded = [message.content.resource.text for message in result.messages if message.content.type == "resource"]
        assert operator_rules_text() in embedded

    anyio.run(_drive)


def test_server_get_prompt_unknown_name_is_a_protocol_error() -> None:
    from .._server import build_server

    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(())
        return

    from mcp.types import GetPromptRequest, GetPromptRequestParams

    server = cast("Any", build_server(()))
    handlers = server.request_handlers

    async def _drive() -> None:
        request = GetPromptRequest(
            method="prompts/get",
            params=GetPromptRequestParams(name="no-such-workflow"),
        )
        with pytest.raises(ValueError, match="no-such-workflow"):
            await handlers[GetPromptRequest](request)

    anyio.run(_drive)
