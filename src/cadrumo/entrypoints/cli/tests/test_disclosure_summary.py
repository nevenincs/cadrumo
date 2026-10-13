"""A status counts the session's disclosures, and every frontend pages the same full list.

Against a running runtime with a synthetic encrypted profile, the person's
signed-in session discloses hundreds of projections. The status reply carries
their count and a count per category, not the list, so it stays within what an
agent client reads. The full list is read by page, and the command line, the
terminal interface's pager and MCP's status tool each read every entry exactly
once and agree on the count, the summary and the pages. A person's session
names its own connection as the destination of what it discloses, so the
frontends' lists differ in that destination alone. The adapter, the installed
clients, the command line, the native transport, the runtime, the session
authority, the profile worker and the profile's custody are real; the native
login, the keychain and the wall clock are ports held by the test.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import (
    DISCLOSURE_PAGE_ENTRIES,
    DisclosurePage,
    DisclosurePageRequest,
)
from cadrumo.application.user_profile.disclosure_paging import DisclosurePager
from cadrumo.core.config import override_settings
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter

from ...runtime.tests.stored_sign_in_runtime import stored_sign_in_runtime
from .command_line_rendering import command_result

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_STATUS_REPLY_LIMIT = 16_000
"""Characters a status reply may take; the full list it replaced took about 125,000."""

type _Page = dict[str, Any]


def _cli_page(profile_id: str, offset: int) -> _Page:
    """Run the command once, signed in with the password on its own channel as a person at a terminal is."""
    reported = command_result(
        "--profile",
        profile_id,
        "--profile-secrets-stdin",
        "config",
        "profile",
        "disclosures",
        "--offset",
        str(offset),
        stdin=json.dumps({"profile_passphrase": PROFILE_INPUT}),
        reveal_identifiers=True,
    )
    page = reported["page"]
    assert isinstance(page, dict)
    # The command's count and summary are those of the list its page belongs to.
    assert reported["disclosure_count"] == page["total"]
    assert reported["disclosure_summary"] == page["disclosure_summary"]
    assert reported["disclosure_digest"] == page["disclosure_digest"]
    return page


def _cli_pages(profile_id: str) -> list[_Page]:
    pages = [_cli_page(profile_id, 0)]
    while pages[-1]["next_offset"] is not None:
        pages.append(_cli_page(profile_id, pages[-1]["next_offset"]))
    return pages


def _shape(pages: list[_Page]) -> tuple[list[tuple[str, str]], set[str]]:
    """Split a frontend's entries into what they disclose, in order, and the destinations they name."""
    entries = [item for page in pages for item in page["entries"]]
    return [(item["category"], item["projection_id"]) for item in entries], {item["destination_id"] for item in entries}


def _summary(disclosed: list[tuple[str, str]]) -> list[dict[str, Any]]:
    counts = Counter(category for category, _projection in disclosed)
    return [{"category": category, "count": counts[category]} for category in sorted(counts)]


def _json(page: DisclosurePage) -> _Page:
    return page.model_dump(mode="json")


@pytest.mark.anyio
async def test_every_frontend_counts_and_pages_the_same_disclosures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        profile_id = str(runtime.profile_id)
        adapter = RuntimeMcpAdapter(profile_id=None, client=None, resumes_sign_in=True)
        terminal = await open_installed_runtime_client(
            profile_id=runtime.profile_id, frontend=OperationFrontendProjection.TUI
        )
        try:
            with override_settings(cadrumo_active_profile=profile_id):
                status = await adapter.call("status", {})
                counted = status["status"]["effective_scope"]
                mcp_pages: list[_Page] = []
                request: dict[str, Any] = {"offset": 0, "expected_digest": counted["disclosure_digest"]}
                while True:
                    reply = await adapter.call("status", {"disclosures": request})
                    mcp_pages.append(reply["disclosure_page"])
                    if mcp_pages[-1]["next_offset"] is None:
                        break
                    request = {**request, "offset": mcp_pages[-1]["next_offset"]}
                stale = await adapter.call("status", {"disclosures": {"offset": 1, "expected_digest": "0" * 64}})
                past_the_end = await adapter.call(
                    "status",
                    {
                        "disclosures": {
                            "offset": counted["disclosure_count"],
                            "expected_digest": counted["disclosure_digest"],
                        }
                    },
                )
                cli_pages = await asyncio.to_thread(_cli_pages, profile_id)

            await asyncio.to_thread(terminal.resume_receipt, timeout=120)
            scope = (await asyncio.to_thread(terminal.status)).status.effective_scope
            pager = DisclosurePager(terminal)
            terminal_pages = [await asyncio.to_thread(pager.next_page, scope.disclosure_digest)]
            while terminal_pages[-1].next_offset is not None:
                terminal_pages.append(await asyncio.to_thread(pager.next_page, scope.disclosure_digest))
            # After the last page the pager begins the list again.
            again = await asyncio.to_thread(pager.next_page, scope.disclosure_digest)
            unpinned = await asyncio.to_thread(terminal.disclosure_page, DisclosurePageRequest())
        finally:
            await asyncio.to_thread(terminal.close)
            await adapter.close()

    count = counted["disclosure_count"]
    status_size = len(json.dumps(status))
    mcp_disclosed, mcp_destinations = _shape(mcp_pages)
    cli_disclosed, cli_destinations = _shape(cli_pages)
    terminal_disclosed, terminal_destinations = _shape([_json(page) for page in terminal_pages])

    # The status reply is bounded: it counts the disclosures and lists none of them.
    assert status_size < _STATUS_REPLY_LIMIT, status_size
    assert "disclosures" not in counted
    assert count > 2 * DISCLOSURE_PAGE_ENTRIES, "the synthetic profile must span several pages"
    assert counted["disclosure_summary"] == _summary(mcp_disclosed)
    assert sum(item["count"] for item in counted["disclosure_summary"]) == count

    # Every frontend reads every entry once, in pages of at most the bound, ending where the count says.
    for disclosed in (mcp_disclosed, cli_disclosed, terminal_disclosed):
        assert len(disclosed) == len(set(disclosed)) == count
    assert len(mcp_pages) == len(cli_pages) == len(terminal_pages) == -(-count // DISCLOSURE_PAGE_ENTRIES)
    assert all(len(page["entries"]) <= DISCLOSURE_PAGE_ENTRIES for page in mcp_pages)
    assert {page["disclosure_digest"] for page in mcp_pages} == {counted["disclosure_digest"]}
    assert again.offset == 0 and again.entries == terminal_pages[0].entries
    assert unpinned == terminal_pages[0]

    # The three frontends agree on the count, the summary and the pages, entry for entry.
    assert scope.disclosure_count == count
    assert [item.model_dump(mode="json") for item in scope.disclosure_summary] == counted["disclosure_summary"]
    assert [page["disclosure_summary"] for page in cli_pages] == [counted["disclosure_summary"]] * len(cli_pages)
    assert cli_disclosed == mcp_disclosed
    assert terminal_disclosed == mcp_disclosed
    offsets = [page["offset"] for page in mcp_pages]
    assert [page["offset"] for page in cli_pages] == offsets == [page.offset for page in terminal_pages]
    # Each session names its own connection as the one destination of everything it discloses.
    assert len(mcp_destinations) == 1 and len(terminal_destinations) == 1
    assert mcp_destinations != terminal_destinations
    assert all(len({item["destination_id"] for item in page["entries"]}) == 1 for page in cli_pages)
    assert not cli_destinations & (mcp_destinations | terminal_destinations)

    # A continuation of a list that is not the one counted, or past its end, is refused.
    assert stale["outcome"] == "refused" and stale["code"] == "operation_unavailable", stale
    assert past_the_end["outcome"] == "refused" and past_the_end["code"] == "operation_unavailable", past_the_end
