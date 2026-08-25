"""The operating layer reaches a client through the floor tool and resources.

Proves that the ``harness.load`` floor tool returns the shipped operator
rules and the active persona verbatim (the tools-only floor), and the
``cadrumo://`` resource surface enumerates exactly the shipped skills, rules, and
personas, resolves each to its verbatim ``text/markdown`` document, and refuses
an unknown URI cleanly. The SDK-independent surface is asserted directly; the
server wiring and capability negotiation are asserted through the real built
``Server``. When the harness distribution's MCP runtime is absent, the SDK-dependent build
is asserted to fail at the optional-dependency boundary instead - the same
graceful-degradation contract ``test_sdk_adaptation`` follows, never a skip.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import anyio
import pytest

from cadrumo.adapters.persistence.storage import master_key
from cadrumo.adapters.persistence.storage.custody import (
    load_committed_profile_password_material,
    unlock_profile_custody,
)
from cadrumo.application.user_profile import (
    profile_bind_bucket_session,
    register_profile_with_credentials,
)
from cadrumo.tests.profile_persistence import composed_profile_persistence_ports

from ... import iter_operator_rules, iter_personas, iter_skill_documents, operator_rules_text
from .._harness_tools import (
    HARNESS_LOAD_TOOL,
    WHOAMI_TOOL,
    WhoamiIdentity,
    build_harness_floor_payload,
    build_whoami_identity,
    render_harness_floor_text,
    render_whoami_identity_text,
)
from .._persona_scope import AgentPersona
from .._resources import (
    HarnessResourceKind,
    HarnessResourceNotFoundError,
    list_harness_resource_templates,
    list_harness_resources,
    read_harness_resource,
    resource_uri,
)
from .._tools import build_tool_descriptors
from ._profile import PROFILE_PASSPHRASE, READY_PROFILE_FACTS, verify_recovery_handover
from ._session import connected_server_and_client_session as connect

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_UTF_8 = "utf-8"
_SDK_PRESENT = importlib.util.find_spec("mcp") is not None


@contextmanager
def _authenticated_current_profile(*, profile_id: str, passphrase: str, storage_root: Path) -> Iterator[None]:
    """Bind one real current custody session after authenticating its envelope."""
    material = load_committed_profile_password_material(UUID(profile_id), root=storage_root)
    unlocked = unlock_profile_custody(material.envelope, passphrase, sentinel=material.sentinel)
    instant = datetime.now(UTC)
    # `profile_bucket_session_open_resumed` was removed with the session-resume
    # forwards; the product repointed its own callers to this class method in the
    # same commit, so the harness follows the same door rather than a shim.
    session = master_key.BucketSession.open_resumed(
        bucket_id=profile_id,
        dek=unlocked.dek,
        idle_minutes=15,
        opened_at=instant,
        idle_deadline=instant + timedelta(minutes=15),
        absolute_deadline=instant + timedelta(hours=4),
        storage_root=storage_root,
    )
    profile_bind_bucket_session(session)
    try:
        yield
    finally:
        master_key.close_active_bucket_session()


def _shipped_skill_names() -> set[str]:
    names: set[str] = set()
    for document in iter_skill_documents():
        parts = str(document).replace("\\", "/").split("/")
        names.add(parts[-2])
    return names


def _shipped_rule_stems() -> set[str]:
    return {document.name.removesuffix(".md") for document in iter_operator_rules()}


def _shipped_persona_stems() -> set[str]:
    return {document.name.removesuffix(".md") for document in iter_personas()}


def _shipped_persona_text(stem: str) -> str:
    for document in iter_personas():
        if document.name == f"{stem}.md":
            return document.read_text(encoding=_UTF_8)
    raise AssertionError(f"no shipped persona {stem!r}")


# --- floor tool payload (SDK-independent) -------------------------------------


def test_floor_payload_without_persona_is_the_shipped_rules_verbatim() -> None:
    payload = build_harness_floor_payload(persona=None)
    assert payload.operator_rules == operator_rules_text()
    assert payload.active_persona is None


def test_floor_payload_with_persona_carries_that_persona_document_verbatim() -> None:
    payload = build_harness_floor_payload(persona=AgentPersona.VERIFIER)
    assert payload.operator_rules == operator_rules_text()
    assert payload.active_persona is not None
    assert payload.active_persona.name == "cadrumo-verifier"
    assert payload.active_persona.text == _shipped_persona_text("cadrumo-verifier")


def test_floor_text_embeds_both_the_rules_and_the_active_persona() -> None:
    payload = build_harness_floor_payload(persona=AgentPersona.RECONCILER)
    text = render_harness_floor_text(payload)
    assert operator_rules_text() in text
    assert _shipped_persona_text("cadrumo-reconciler") in text


def test_floor_payload_carries_the_off_host_consent_disclosure() -> None:
    # The off-host privacy disclosure rides on every floor load, for every
    # persona and the un-personified session, so it can never be skipped.
    from .._harness_tools import off_host_consent_text

    for persona in (None, AgentPersona.VERIFIER, AgentPersona.MODELO_PREPARER):
        payload = build_harness_floor_payload(persona=persona)
        assert payload.off_host_consent == off_host_consent_text()
        assert payload.off_host_consent.strip()
        # The disclosure names the off-host provider (localized, so assert the
        # brand token present across every locale rather than English prose).
        assert "LLM" in payload.off_host_consent


def test_floor_text_surfaces_the_consent_before_the_operating_rules() -> None:
    # The disclosure must be read FIRST — before any off-host-visible interaction —
    # so it precedes the operating-rules heading in the rendered floor text.
    payload = build_harness_floor_payload(persona=None)
    text = render_harness_floor_text(payload)
    consent_at = text.find(payload.off_host_consent)
    rules_at = text.find("# aeat operator operating rules")
    assert consent_at != -1
    assert rules_at != -1
    assert consent_at < rules_at


# --- resource enumeration + read (SDK-independent) ----------------------------


def test_resources_enumerate_exactly_the_shipped_documents() -> None:
    refs = list_harness_resources()
    by_kind: dict[HarnessResourceKind, set[str]] = {kind: set() for kind in HarnessResourceKind}
    for ref in refs:
        by_kind[ref.kind].add(ref.name)
    assert by_kind[HarnessResourceKind.SKILL] == _shipped_skill_names()
    assert by_kind[HarnessResourceKind.RULE] == _shipped_rule_stems()
    assert by_kind[HarnessResourceKind.PERSONA] == _shipped_persona_stems()


def test_every_advertised_resource_uri_resolves_as_markdown() -> None:
    for ref in list_harness_resources():
        content = read_harness_resource(ref.uri)
        assert content.ref.uri == ref.uri
        assert content.ref.mime_type == "text/markdown"
        assert content.text.strip()


def test_a_skill_a_rule_and_a_persona_resolve_verbatim() -> None:
    skill = read_harness_resource(resource_uri(HarnessResourceKind.SKILL, "cadrumo-preparar-modelo-130"))
    persona = read_harness_resource(resource_uri(HarnessResourceKind.PERSONA, "cadrumo-verifier"))
    assert persona.text == _shipped_persona_text("cadrumo-verifier")
    # The skill body is the shipped SKILL.md frontmatter + prose.
    assert skill.text.startswith("---")
    assert "name: cadrumo-preparar-modelo-130" in skill.text


def test_templates_declare_the_three_kinds() -> None:
    templates = {template.kind: template.uri_template for template in list_harness_resource_templates()}
    assert templates[HarnessResourceKind.SKILL] == "cadrumo://skill/{name}"
    assert templates[HarnessResourceKind.RULE] == "cadrumo://rule/{name}"
    assert templates[HarnessResourceKind.PERSONA] == "cadrumo://persona/{name}"


@pytest.mark.parametrize(
    "uri",
    ["cadrumo://skill/does-not-exist", "cadrumo://bogus/x", "http://elsewhere/y", "cadrumo://persona/"],
)
def test_unknown_or_malformed_uri_refuses_cleanly(uri: str) -> None:
    with pytest.raises(HarnessResourceNotFoundError):
        read_harness_resource(uri)


# --- server wiring + capability negotiation (SDK-gated, never skipped) ---------


def test_floor_tool_and_resources_are_wired_into_the_built_server() -> None:
    from .._server import build_server

    descriptors = build_tool_descriptors()
    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(descriptors)
        return

    server = cast("Any", build_server(descriptors, persona=AgentPersona.VERIFIER))

    async def _drive() -> None:
        from mcp.types import TextResourceContents

        async with connect(server) as session:
            tools = (await session.list_tools()).tools
            assert HARNESS_LOAD_TOOL in {tool.name for tool in tools}

            resources = (await session.list_resources()).resources
            assert {str(resource.uri) for resource in resources} == {ref.uri for ref in list_harness_resources()}

            templates = (await session.list_resource_templates()).resource_templates
            assert {template.uri_template for template in templates} == {
                template.uri_template for template in list_harness_resource_templates()
            }

            contents = (
                await session.read_resource(resource_uri(HarnessResourceKind.PERSONA, "cadrumo-verifier"))
            ).contents
            content = contents[0]
            assert isinstance(content, TextResourceContents)
            assert content.mime_type == "text/markdown"
            assert content.text == _shipped_persona_text("cadrumo-verifier")

    anyio.run(_drive)


def test_floor_tool_call_returns_the_active_persona_payload() -> None:
    from .._server import build_server

    descriptors = build_tool_descriptors()
    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(descriptors)
        return

    server = cast("Any", build_server(descriptors, persona=AgentPersona.VERIFIER))

    async def _drive() -> None:
        from mcp.types import TextContent

        async with connect(server) as session:
            result = await session.call_tool(HARNESS_LOAD_TOOL, {})
        assert result.is_error is False
        assert result.structured_content is not None
        assert result.structured_content["operator_rules"] == operator_rules_text()
        assert result.structured_content["active_persona"]["text"] == _shipped_persona_text("cadrumo-verifier")
        content = result.content[0]
        assert isinstance(content, TextContent)
        assert operator_rules_text() in content.text

    anyio.run(_drive)


# --- whoami identity tool --------------------------------------------------


def test_whoami_identity_resolves_the_active_profile_label(tmp_path: Any) -> None:
    """The identity probe reads an explicitly authenticated current capsule."""
    from cadrumo.tests.secure_sql import isolated_profile_storage_root

    with (
        isolated_profile_storage_root(tmp_path=tmp_path) as storage_root,
        composed_profile_persistence_ports(),
    ):
        outcome = register_profile_with_credentials(
            recovery_handover=verify_recovery_handover,
            label="Erika",
            passphrase=PROFILE_PASSPHRASE,
            facts=READY_PROFILE_FACTS,
        )
        with _authenticated_current_profile(
            profile_id=outcome.profile_id,
            passphrase=PROFILE_PASSPHRASE,
            storage_root=storage_root,
        ):
            identity = build_whoami_identity()

    assert identity.active_profile == "Erika"
    assert identity.active_profile != outcome.profile_id
    assert identity.readiness  # a non-empty health status
    assert isinstance(identity.tax_id_present, bool)


def test_whoami_identity_is_null_when_no_profile_is_active(tmp_path: Any) -> None:
    from cadrumo.tests.secure_sql import isolated_profile_storage_root

    with isolated_profile_storage_root(tmp_path=tmp_path):
        identity = build_whoami_identity()

    assert identity.active_profile is None
    assert identity.tax_id_present is False
    assert identity.readiness == "none"
    assert identity.precondition_action is not None
    assert identity.precondition_action.action is not None
    assert identity.precondition_action.action.action_id == "operator.profile.create"
    assert identity.precondition_action.missing_argument_names == ("profile_name",)


def test_render_whoami_identity_names_the_label_and_readiness() -> None:
    text = render_whoami_identity_text(
        WhoamiIdentity(
            active_profile="Erika",
            tax_id_present=True,
            readiness="ready",
            precondition_action=None,
        ),
    )
    assert "Erika" in text
    assert "ready" in text
    assert "yes" in text  # tax id on file


def test_whoami_is_always_advertised_and_never_persona_scoped_away() -> None:
    # whoami is a console tool like search/execute: advertised on every session,
    # in CORE and FULL, with no persona and under a restrictive persona — the
    # identity assertion must never be scoped away.
    from .._server import build_server
    from .._surface import SurfaceMode

    descriptors = build_tool_descriptors()
    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(descriptors)
        return

    async def _advertised(persona: AgentPersona | None, mode: SurfaceMode) -> set[str]:
        server = cast("Any", build_server(descriptors, persona=persona, surface_mode=mode))
        async with connect(server) as session:
            tools = (await session.list_tools()).tools
        return {tool.name for tool in tools}

    async def _drive() -> None:
        for persona in (None, AgentPersona.VERIFIER):
            for mode in (SurfaceMode.CORE, SurfaceMode.FULL):
                assert WHOAMI_TOOL in await _advertised(persona, mode)

    anyio.run(_drive)


def test_whoami_tool_call_returns_the_active_profile_label(tmp_path: Any) -> None:
    from cadrumo.tests.secure_sql import isolated_profile_storage_root

    from .._server import build_server

    descriptors = build_tool_descriptors()
    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(descriptors)
        return

    with (
        isolated_profile_storage_root(tmp_path=tmp_path) as storage_root,
        composed_profile_persistence_ports(),
    ):
        outcome = register_profile_with_credentials(
            recovery_handover=verify_recovery_handover,
            label="Erika",
            passphrase=PROFILE_PASSPHRASE,
            facts=READY_PROFILE_FACTS,
        )
        with _authenticated_current_profile(
            profile_id=outcome.profile_id,
            passphrase=PROFILE_PASSPHRASE,
            storage_root=storage_root,
        ):
            server = cast("Any", build_server(descriptors, persona=None))

            async def _drive() -> None:
                from mcp.types import TextContent

                async with connect(server) as session:
                    result = await session.call_tool(WHOAMI_TOOL, {})
                assert result.is_error is False
                assert result.structured_content is not None
                assert result.structured_content["active_profile"] == "Erika"
                assert result.structured_content["active_profile"] != outcome.profile_id
                content = result.content[0]
                assert isinstance(content, TextContent)
                assert "Erika" in content.text

            anyio.run(_drive)


def test_floor_response_carries_the_active_identity_block(tmp_path: Any) -> None:
    from cadrumo.tests.secure_sql import isolated_profile_storage_root

    from .._server import build_server

    descriptors = build_tool_descriptors()
    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(descriptors)
        return

    with (
        isolated_profile_storage_root(tmp_path=tmp_path) as storage_root,
        composed_profile_persistence_ports(),
    ):
        outcome = register_profile_with_credentials(
            recovery_handover=verify_recovery_handover,
            label="Erika",
            passphrase=PROFILE_PASSPHRASE,
            facts=READY_PROFILE_FACTS,
        )
        with _authenticated_current_profile(
            profile_id=outcome.profile_id,
            passphrase=PROFILE_PASSPHRASE,
            storage_root=storage_root,
        ):
            server = cast("Any", build_server(descriptors, persona=None))

            async def _drive() -> None:
                async with connect(server) as session:
                    result = await session.call_tool(HARNESS_LOAD_TOOL, {})
                assert result.is_error is False
                assert result.structured_content is not None
                assert result.structured_content["identity"]["active_profile"] == "Erika"

            anyio.run(_drive)


def test_server_negotiates_prompts_and_resources_capabilities() -> None:
    from .._server import build_server

    descriptors = build_tool_descriptors()
    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(descriptors)
        return

    server = cast("Any", build_server(descriptors))
    capabilities = server.get_capabilities(
        notification_options=_notification_options(),
        experimental_capabilities={},
    )
    assert capabilities.tools is not None
    assert capabilities.resources is not None
    assert capabilities.prompts is not None


def _notification_options() -> object:
    from mcp.server.lowlevel.server import NotificationOptions

    return NotificationOptions()
