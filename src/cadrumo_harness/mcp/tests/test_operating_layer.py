"""The operating layer as the MCP server serves it: the harness_load floor, its resources and their limits.

Every call goes through the real server over the SDK's in-memory transport. The
expected documents are read straight from the shipped harness tree, so a server
that served stale, partial or other text fails here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from mcp import MCPError
from mcp.types import INVALID_PARAMS, INVALID_REQUEST, TextContent, TextResourceContents

from ..._skill_metadata import parse_skill_metadata
from ...resources import harness_root
from ..main import main
from ..protocol_contract import SIGN_IN_REMEDY
from ..runtime_adapter import RuntimeMcpAdapter
from ..server import build_server
from .admitted_lease import admitted_adapter
from .session import connected_server_and_client_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_UTF_8 = "utf-8"
_SKILL = "cadrumo-preparar-modelo-130"
_RULE = "cadrumo-operator-grounding"


def _shipped_skills() -> dict[str, str]:
    """Every shipped SKILL.md by its directory name, read from the tree itself."""
    root = harness_root().joinpath("skills")
    return {
        child.name: child.joinpath("SKILL.md").read_text(encoding=_UTF_8)
        for child in root.iterdir()
        if child.is_dir() and child.joinpath("SKILL.md").is_file()
    }


def _shipped_rules() -> dict[str, str]:
    """Every shipped operating rule by its file name without .md, read from the tree itself."""
    return {
        child.name.removesuffix(".md"): child.read_text(encoding=_UTF_8)
        for child in harness_root().joinpath("rules").iterdir()
        if child.is_file() and child.name.endswith(".md")
    }


@pytest.mark.anyio
async def test_harness_load_returns_every_rule_and_every_skill_with_its_applies_when() -> None:
    adapter = admitted_adapter()
    try:
        async with connected_server_and_client_session(build_server(adapter)) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            loaded = await client.call_tool("harness_load", {})
    finally:
        await adapter.close()

    schema = tools["harness_load"].input_schema
    assert schema["required"] == []
    assert schema["properties"] == {"skill": {"type": "string"}}
    annotations = tools["harness_load"].annotations
    assert annotations is not None and annotations.read_only_hint is True and annotations.open_world_hint is False

    assert loaded.is_error is False
    document = loaded.structured_content
    assert document is not None
    assert document["outcome"] == "loaded"
    rules = _shipped_rules()
    for name, text in rules.items():
        assert text.strip() in document["rules"], name
    assert len(document["rules"]) == len("\n\n".join(text.rstrip() for text in rules.values()))
    # The floor does not carry a skill's document unless one is named.
    assert "skill" not in document

    shipped = _shipped_skills()
    assert [entry["name"] for entry in document["skills"]] == sorted(shipped)
    for entry in document["skills"]:
        metadata = parse_skill_metadata(shipped[entry["name"]])
        assert entry["resource"] == f"cadrumo://skill/{entry['name']}"
        assert entry["description"] == metadata.description
        assert metadata.applies_when is not None
        assert entry["applies_when"] == metadata.applies_when.model_dump(mode="json")
    # The text block repeats the same document for a client that reads no structured content.
    text_block = loaded.content[0]
    assert isinstance(text_block, TextContent)
    assert json.loads(text_block.text) == document


@pytest.mark.anyio
async def test_harness_load_with_a_skill_name_returns_that_skill_document() -> None:
    adapter = admitted_adapter()
    try:
        async with connected_server_and_client_session(build_server(adapter)) as client:
            loaded = await client.call_tool("harness_load", {"skill": _SKILL})
    finally:
        await adapter.close()

    assert loaded.is_error is False
    document = loaded.structured_content
    assert document is not None
    assert document["skill"] == {
        "name": _SKILL,
        "resource": f"cadrumo://skill/{_SKILL}",
        "text": _shipped_skills()[_SKILL],
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("arguments", "code"),
    [
        ({"skill": "cadrumo-preparar-modelo-999"}, "unknown_skill"),
        # A rule is not a skill, and a path is not a name.
        ({"skill": _RULE}, "unknown_skill"),
        ({"skill": f"../{_SKILL}"}, "unknown_skill"),
        ({"skill": 130}, "invalid_request"),
        ({"persona": "verifier"}, "invalid_request"),
    ],
)
async def test_harness_load_refuses_a_skill_it_does_not_ship(arguments: dict[str, object], code: str) -> None:
    adapter = admitted_adapter()
    try:
        async with connected_server_and_client_session(build_server(adapter)) as client:
            refused = await client.call_tool("harness_load", arguments)
    finally:
        await adapter.close()

    assert refused.is_error is True
    assert refused.structured_content == {"outcome": "refused", "code": code}


@pytest.mark.anyio
async def test_resources_list_and_read_every_skill_and_rule_as_shipped() -> None:
    adapter = admitted_adapter()
    try:
        async with connected_server_and_client_session(build_server(adapter)) as client:
            templates = (await client.list_resource_templates()).resource_templates
            listed = (await client.list_resources()).resources
            skill = await client.read_resource(f"cadrumo://skill/{_SKILL}")
            rule = await client.read_resource(f"cadrumo://rule/{_RULE}")
    finally:
        await adapter.close()

    assert [template.uri_template for template in templates] == ["cadrumo://skill/{name}", "cadrumo://rule/{name}"]
    shipped_skills, shipped_rules = _shipped_skills(), _shipped_rules()
    assert [resource.uri for resource in listed] == [
        *(f"cadrumo://skill/{name}" for name in sorted(shipped_skills)),
        *(f"cadrumo://rule/{name}" for name in sorted(shipped_rules)),
    ]
    assert all(resource.mime_type == "text/markdown" for resource in listed)
    by_uri = {resource.uri: resource for resource in listed}
    applies_when = parse_skill_metadata(shipped_skills[_SKILL]).applies_when
    assert applies_when is not None
    assert by_uri[f"cadrumo://skill/{_SKILL}"].meta == {"applies_when": applies_when.model_dump(mode="json")}
    assert by_uri[f"cadrumo://rule/{_RULE}"].meta is None

    assert all(isinstance(content, TextResourceContents) for content in (*skill.contents, *rule.contents))
    assert [
        (content.uri, content.mime_type, content.text)
        for content in skill.contents
        if isinstance(content, TextResourceContents)
    ] == [(f"cadrumo://skill/{_SKILL}", "text/markdown", shipped_skills[_SKILL])]
    assert [(content.uri, content.text) for content in rule.contents if isinstance(content, TextResourceContents)] == [
        (f"cadrumo://rule/{_RULE}", shipped_rules[_RULE])
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "uri",
    [
        "cadrumo://skill/cadrumo-preparar-modelo-999",
        f"cadrumo://skill/{_RULE}",
        f"cadrumo://rule/{_SKILL}",
        # No persona ships, so the server serves none.
        "cadrumo://persona/verifier",
        f"cadrumo://skill/{_SKILL}/reference/casillas.md",
        "cadrumo://corpus/ley-58-2003:art-27.2",
    ],
)
async def test_reading_a_resource_the_harness_does_not_ship_is_refused(uri: str) -> None:
    adapter = admitted_adapter()
    try:
        async with connected_server_and_client_session(build_server(adapter)) as client:
            with pytest.raises(MCPError) as refused:
                await client.read_resource(uri)
    finally:
        await adapter.close()

    assert refused.value.code == INVALID_PARAMS
    assert refused.value.data == {"outcome": "refused", "code": "unknown_resource", "uri": uri}


@pytest.mark.anyio
async def test_without_a_session_the_floor_and_every_resource_request_are_refused_alike() -> None:
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    expected = {"outcome": "refused", "code": "authentication_required", "remedy": SIGN_IN_REMEDY}
    try:
        async with connected_server_and_client_session(build_server(adapter)) as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            loaded = await client.call_tool("harness_load", {})
            refusals: list[MCPError] = []
            for request in (
                client.list_resource_templates,
                client.list_resources,
                lambda: client.read_resource(f"cadrumo://rule/{_RULE}"),
            ):
                with pytest.raises(MCPError) as refused:
                    await request()
                refusals.append(refused.value)
        assert adapter.client is None and adapter.admission is None
    finally:
        await adapter.close()

    # The tool list is advertised before admission; what the floor holds is not.
    assert "harness_load" in names
    assert loaded.is_error is True
    assert loaded.structured_content == expected
    assert [(error.code, error.data) for error in refusals] == [(INVALID_REQUEST, expected)] * 3


@pytest.mark.anyio
async def test_serving_the_operating_layer_writes_no_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    adapter = admitted_adapter()
    try:
        async with connected_server_and_client_session(build_server(adapter)) as client:
            tools = (await client.list_tools()).tools
            await client.call_tool("harness_load", {"skill": _SKILL})
            await client.list_resources()
            await client.read_resource(f"cadrumo://skill/{_SKILL}")
    finally:
        await adapter.close()

    # Materialisation is the person's launch option, never a tool: nothing a client asks writes a file.
    assert list(tmp_path.iterdir()) == []
    assert not {tool.name for tool in tools} & {"materialise", "materialise_workspace", "workspace"}


def _launch(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    """Run the console script's own entry function with this launch's arguments."""
    monkeypatch.setattr(sys, "argv", ["cadrumo-mcp", *arguments])
    # The entry point sets this for its process; the test process gets it back afterwards.
    monkeypatch.setenv("PYDANTIC_DISABLE_PLUGINS", "__all__")
    main()


def test_the_entry_point_materialises_a_workspace_only_when_its_launch_asks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace = tmp_path / "workspace"
    _launch(monkeypatch, "--materialise-workspace", str(workspace))

    manifest = json.loads(capsys.readouterr().out)
    shipped_skills, shipped_rules = _shipped_skills(), _shipped_rules()
    assert manifest["output_path"] == str(workspace)
    assert manifest["skills_written"] == len(shipped_skills)
    assert manifest["rules_written"] == len(shipped_rules)
    for name, text in shipped_skills.items():
        assert (workspace / ".claude" / "skills" / name / "SKILL.md").read_text(encoding=_UTF_8) == text
    for name, text in shipped_rules.items():
        assert (workspace / ".claude" / "rules" / f"{name}.md").read_text(encoding=_UTF_8) == text
    memory = (workspace / "CLAUDE.md").read_text(encoding=_UTF_8)
    assert all(f"@.claude/rules/{name}.md" in memory for name in shipped_rules)


@pytest.mark.parametrize("serving", [("--profile-id", str(uuid4())), ("--surface", "full")])
def test_materialising_refuses_to_combine_with_serving_and_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    serving: tuple[str, str],
) -> None:
    workspace = tmp_path / "workspace"
    with pytest.raises(SystemExit) as refused:
        _launch(monkeypatch, "--materialise-workspace", str(workspace), *serving)

    assert refused.value.code == 2
    assert "--materialise-workspace writes files and serves nothing" in capsys.readouterr().err
    assert not workspace.exists()
