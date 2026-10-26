"""Desktop-shaped profile requests through real native IPC and the profile worker."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from threading import Event
from typing import Any

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo_client.transport.installed_client import open_installed_client
from cadrumo_runtime.host.session_hold_operations import OperationRelay
from cadrumo_runtime.host.tests.stored_sign_in_runtime import stored_sign_in_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="native Windows worker"),
    pytest.mark.usefixtures("authority_operation"),
]


def _document(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return value


@pytest.mark.asyncio
async def test_desktop_profile_read_write_invalidation_and_stale_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch, signed_in=False) as runtime:
        client = await open_installed_client(profile_id=runtime.profile_id, frontend=OperationFrontendProjection.TUI)
        await asyncio.to_thread(client.login_password, bytearray(PROFILE_INPUT.encode()), timeout=120)
        advanced, changed = Event(), Event()
        client.subscribe_operation_changes(advanced.set)
        client.subscribe_profile_record_changes(changed.set)
        relay = OperationRelay(client)
        profile = str(runtime.profile_id)

        def run(definition: str, payload: dict[str, object]) -> dict[str, Any]:
            submitted = relay.handle(
                "operation_submit",
                {"definition_id": definition, "subject_ref": f"profile:{profile}", "payload": payload},
            )
            operation = submitted["operation_id"]
            deadline = time.monotonic() + 90
            while True:
                advanced.clear()
                observed = relay.handle("operation_observe", {"operation_id": operation, "after_cursor": 0})
                projection = _document(_document(observed["observation"])["projection"])
                if projection["lifecycle"] == "terminal":
                    if projection["terminal_condition"] != "succeeded":
                        return {"refused": projection["terminal_condition"], "effect": projection["effect"]}
                    result = relay.handle("operation_result", {"operation_id": operation})
                    return _document(_document(result["document"])["projection"])
                assert advanced.wait(max(0, deadline - time.monotonic())), "operation progress push missing"

        def overview() -> tuple[dict[str, Any], list[dict[str, Any]], int]:
            payload: dict[str, object] = {
                "profile_id": profile,
                "page_kind": "overview",
                "cursor": 0,
                "limit": 128,
                "output_language": "en",
            }
            items: list[dict[str, Any]] = []
            pages = 0
            while True:
                page = run("user-profile.view", payload)
                assert page["outcome"] == "page"
                pages += 1
                items.extend(page["items"])
                if page["next_cursor"] is None:
                    return page, items, pages
                payload.update(
                    cursor=page["next_cursor"],
                    expected_revision=page["record_revision"],
                    expected_content_digest=page["content_digest"],
                )

        try:
            started = time.perf_counter()
            before, fields, pages = await asyncio.to_thread(overview)
            read_ms = (time.perf_counter() - started) * 1000
            assert any(item.get("kind") == "field" and item["field"]["path"] == "identity.tax_id" for item in fields)
            assert not changed.is_set(), "read-only views must not invalidate themselves"
            payload = {
                "profile_id": profile,
                "expected_revision": before["record_revision"],
                "expected_content_digest": before["content_digest"],
                "path": "identity.tax_id",
                "value": "X1234567L",
            }
            started = time.perf_counter()
            saved = await asyncio.to_thread(run, "user-profile.field-mutation", payload)
            assert saved["profile_id"] == profile
            assert await asyncio.to_thread(changed.wait, 10), "settled write did not cue the desktop"
            after, items, _ = await asyncio.to_thread(overview)
            save_ms = (time.perf_counter() - started) * 1000
            assert after["record_revision"] > before["record_revision"]
            assert any(
                item.get("kind") == "field"
                and item["field"]["path"] == "identity.tax_id"
                and item["field"]["value"] == "X1234567L"
                for item in items
            )
            started = time.perf_counter()
            auth = await asyncio.to_thread(run, "auth.local-read", {"profile_id": profile, "kind": "sync_readiness"})
            readiness_ms = (time.perf_counter() - started) * 1000
            assert auth["profile_id"] == profile
            readiness = auth["sync_readiness"]
            assert not readiness["ready"]
            requirements = {item["field"]: item for item in readiness["requirements"]}
            assert requirements["identity.tax_id"]["satisfied"], "use the saved NIE instead of asking again"
            assert not requirements["auth.provider"]["satisfied"]
            assert all("value" not in item for item in readiness["requirements"])
            started = time.perf_counter()
            prepared = await asyncio.to_thread(run, "user-profile.censo-prepare", {"profile_id": profile})
            prepare_ms = (time.perf_counter() - started) * 1000
            assert prepared["operation_request"]["baseline"]["profile_id"] == profile
            assert prepared["operation_request"]["baseline"]["record_revision"] == after["record_revision"]
            assert len(prepared["effective_fields"]) == 3
            stale = await asyncio.to_thread(run, "user-profile.field-mutation", {**payload, "value": "Y1234567X"})
            assert stale.get("refused") in {"refused", "failed"}, stale
            # The existing executor conservatively settles exceptions after its
            # effect fence as unknown. The desktop must preserve that outcome;
            # a fresh canonical read, not the exception, proves what is stored.
            assert stale["effect"] in {"none", "unknown"}
            checked, checked_items, _ = await asyncio.to_thread(overview)
            assert checked["record_revision"] == after["record_revision"]
            assert any(
                item.get("kind") == "field"
                and item["field"]["path"] == "identity.tax_id"
                and item["field"]["value"] == "X1234567L"
                for item in checked_items
            )
            print(
                json.dumps(
                    {
                        "benchmark": "desktop_profile_relay",
                        "overview_pages": pages,
                        "read_ms": round(read_ms, 2),
                        "save_and_readback_ms": round(save_ms, 2),
                        "censo_readiness_ms": round(readiness_ms, 2),
                        "censo_prepare_ms": round(prepare_ms, 2),
                    }
                )
            )
        finally:
            await asyncio.to_thread(client.close)
