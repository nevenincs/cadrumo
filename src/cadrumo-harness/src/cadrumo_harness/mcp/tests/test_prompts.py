"""Guided-workflow prompts embed the shipped skills and orient the session.

Proves the guided-workflow prompt channel: the catalogue is exactly the shipped
skills plus the orientation entry, every skill prompt embeds its ``SKILL.md``
verbatim as a resource, the orientation prompt embeds the operator rules, and an
unknown prompt name maps to a clean protocol error. The SDK-independent
``_prompts.py`` surface is asserted directly; the server-side ``list``/``get``
wiring is asserted through the real built ``Server`` - built with an empty
descriptor set so the prompt handlers are exercised without transiting the CLI
tool-descriptor import chain. When the harness distribution's MCP runtime is absent, the
SDK-dependent build is asserted to fail at the optional-dependency boundary
instead - never a skip.
"""

from __future__ import annotations

import importlib.util
from typing import Any, cast

import anyio
import pytest

from cadrumo.core import accepted_filing_period_codes, accepted_filing_period_patterns

from ... import iter_skill_documents, operator_rules_text
from .._completions import complete_prompt_argument
from .._prompts import (
    ORIENTATION_PROMPT_NAME,
    PromptNotFoundError,
    build_prompt_catalogue,
    prompt_document,
)
from ._session import connected_server_and_client_session as connect

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_UTF_8 = "utf-8"
_SDK_PRESENT = importlib.util.find_spec("mcp") is not None
_PERIOD_COMPLETIONS = tuple(str(value) for value in accepted_filing_period_codes())


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
        assert document.embedded[0].uri == f"cadrumo://skill/{name}"
        assert document.embedded[0].mime_type == "text/markdown"


def test_orientation_prompt_embeds_the_operator_rules() -> None:
    document = prompt_document(ORIENTATION_PROMPT_NAME)
    assert document.brief_text.strip()
    assert ORIENTATION_PROMPT_NAME == "cadrumo-empezar"
    assert document.prompt.title == "Empezar con el asistente Cadrumo"
    assert "operate Cadrumo" in document.brief_text
    assert "aeat console" not in document.brief_text.casefold()
    embedded_texts = [item.text for item in document.embedded]
    assert operator_rules_text() in embedded_texts
    assert document.embedded[0].uri == "cadrumo://rule/cadrumo-operating-rules"


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

    from mcp.types import PromptReference

    # An empty descriptor set exercises the prompt handlers without building the
    # CLI tool descriptors (the prompt channel is independent of the tool surface).
    server = cast("Any", build_server(()))
    skill_texts = _shipped_skill_texts()

    async def _drive() -> None:
        async with connect(server) as session:
            listed = (await session.list_prompts()).prompts
            assert {prompt.name for prompt in listed} == {entry.name for entry in build_prompt_catalogue()}
            workflow = next(prompt for prompt in listed if prompt.name != ORIENTATION_PROMPT_NAME)
            period_argument = next(argument for argument in workflow.arguments or [] if argument.name == "period")
            assert (period_argument.description or "").startswith("The AEAT period code.")
            assert all(pattern in (period_argument.description or "") for pattern in accepted_filing_period_patterns())
            assert "ANUAL" not in (period_argument.description or "")

            completion = (
                await session.complete(
                    ref=PromptReference(type="ref/prompt", name=workflow.name),
                    argument={"name": "period", "value": ""},
                )
            ).completion
            assert tuple(completion.values) == _PERIOD_COMPLETIONS

            result = await session.get_prompt("cadrumo-preparar-modelo-130")
        assert result.messages[0].content.type == "text"
        assert result.messages[0].content.text.strip()
        resource_message = result.messages[1]
        assert resource_message.content.type == "resource"
        assert str(resource_message.content.resource.uri) == "cadrumo://skill/cadrumo-preparar-modelo-130"
        assert resource_message.content.resource.mime_type == "text/markdown"
        assert hasattr(resource_message.content.resource, "text")
        assert resource_message.content.resource.text == skill_texts["cadrumo-preparar-modelo-130"]

    anyio.run(_drive)


def test_server_get_prompt_orientation_embeds_the_rules() -> None:
    from .._server import build_server

    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(())
        return

    server = cast("Any", build_server(()))

    async def _drive() -> None:
        async with connect(server) as session:
            result = await session.get_prompt(ORIENTATION_PROMPT_NAME)
        embedded = [
            resource.text
            for message in result.messages
            if message.content.type == "resource" and hasattr(resource := message.content.resource, "text")
        ]
        assert operator_rules_text() in embedded

    anyio.run(_drive)


def test_server_get_prompt_unknown_name_is_a_protocol_error() -> None:
    from .._server import build_server

    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(())
        return

    from mcp.types import GetPromptRequestParams

    # The registered handler itself is asserted directly here (not through a real
    # client session): the contract under test is that the SDK-independent
    # ``PromptNotFoundError`` translates to a raw ``ValueError`` at the handler
    # boundary (the shape a JSON-RPC dispatch turns into a clean protocol error
    # for the client) - a call-site detail the dispatcher, not this test, is
    # responsible for wrapping. The handler ignores its context argument entirely
    # (see ``_on_get_prompt``), so no real session is needed to invoke it.
    server = cast("Any", build_server(()))
    entry = server.get_request_handler("prompts/get")
    assert entry is not None

    async def _drive() -> None:
        with pytest.raises(ValueError, match="no-such-workflow"):
            await entry.handler(cast("Any", None), GetPromptRequestParams(name="no-such-workflow"))

    anyio.run(_drive)


def test_workflow_prompts_declare_typed_arguments_orientation_does_not() -> None:
    # Guided workflows accept filing_year + period; orientation takes none.
    catalogue = {entry.name: entry for entry in build_prompt_catalogue()}
    orientation = catalogue[ORIENTATION_PROMPT_NAME]
    assert orientation.arguments == ()
    workflow = next(entry for name, entry in catalogue.items() if name != ORIENTATION_PROMPT_NAME)
    arg_names = {argument.name for argument in workflow.arguments}
    assert arg_names == {"filing_year", "period"}
    assert all(argument.required is False for argument in workflow.arguments)
    period_argument = next(argument for argument in workflow.arguments if argument.name == "period")
    assert all(pattern in period_argument.description for pattern in accepted_filing_period_patterns())
    assert "ANUAL" not in period_argument.description


def test_prompt_get_substitutes_the_supplied_scope_into_the_brief() -> None:
    workflow_name = next(entry.name for entry in build_prompt_catalogue() if entry.name != ORIENTATION_PROMPT_NAME)
    document = prompt_document(workflow_name, {"filing_year": "2026", "period": "3T"})
    assert "filing year 2026" in document.brief_text
    assert "period 3T" in document.brief_text
    assert "taxpayer files with AEAT themselves" in document.brief_text
    # No arguments -> no scope line appended.
    bare = prompt_document(workflow_name, None)
    assert "Scope for this run" not in bare.brief_text


def test_completions_serve_period_and_year_values_by_prefix() -> None:
    assert complete_prompt_argument("period", "") == _PERIOD_COMPLETIONS
    assert complete_prompt_argument("period", "3") == ("3P", "3T")
    zero_prefix = complete_prompt_argument("period", "0")
    assert "0A" in zero_prefix
    assert all(value.startswith("0") for value in zero_prefix)
    assert complete_prompt_argument("period", "an") == ()
    years = complete_prompt_argument("filing_year", "202")
    assert "2026" in years
    assert all(value.startswith("202") for value in years)
    # An unknown argument yields no candidates.
    assert complete_prompt_argument("nonsense", "x") == ()
