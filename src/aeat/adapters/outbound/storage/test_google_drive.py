"""Tests for `GoogleDriveProvider`.

A `_FakeDriveService` mirrors the parts of the Drive v3 Resource
interface the provider actually consumes (`.files().list/create/
update/get/delete/get_media`). Every request is recorded so tests can
assert on the exact API call sequence the provider produces.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest

from aeat.adapters.outbound.storage import (
    ProviderKind,
    StorageIntegrityError,
    StorageNotFoundError,
    StoragePermissionError,
    StorageProvider,
    StorageValidationError,
)
from aeat.adapters.outbound.storage._google_drive import GoogleDriveProvider

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def _sha256(payload: bytes) -> str:
    return f"sha256-{hashlib.sha256(payload).hexdigest()}"


@dataclass
class _FakeRequest:
    """One-shot Drive API request; `execute()` returns a pre-built response."""

    response: object
    raise_exc: Exception | None = None

    def execute(self) -> object:
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.response


@dataclass
class _FakeFile:
    file_id: str
    name: str
    parents: list[str]
    payload: bytes
    app_properties: dict[str, str]
    mime_type: str = "application/octet-stream"
    trashed: bool = False

    def to_entry(self) -> dict[str, Any]:
        return {
            "id": self.file_id,
            "name": self.name,
            "size": str(len(self.payload)),
            "md5Checksum": hashlib.md5(self.payload, usedforsecurity=False).hexdigest(),
            "modifiedTime": "2026-05-14T10:00:00Z",
            "appProperties": dict(self.app_properties),
            "mimeType": self.mime_type,
            "trashed": self.trashed,
        }


@dataclass
class _FakeDriveService:
    """Minimal Drive Resource-shaped fake.

    Holds an in-memory map of every file the provider has interacted
    with. Each method records the call into `self.calls` for
    assertions, then returns a `_FakeRequest` whose `execute()` yields
    the response.
    """

    files_by_id: dict[str, _FakeFile] = field(default_factory=dict)
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    raise_on: dict[str, Exception] = field(default_factory=dict)

    def files(self) -> _FakeDriveFiles:
        return _FakeDriveFiles(self)


@dataclass
class _FakeDriveFiles:
    parent: _FakeDriveService

    def list(self, **kwargs: Any) -> _FakeRequest:
        self.parent.calls.append(("list", dict(kwargs)))
        if "list" in self.parent.raise_on:
            return _FakeRequest(response=None, raise_exc=self.parent.raise_on["list"])
        query = str(kwargs.get("q", ""))
        files = list(self.parent.files_by_id.values())
        # Tiny query interpreter — handles the three patterns the
        # provider emits: parent-in, name-equals, name-contains, mime,
        # trashed-false.
        matches: list[_FakeFile] = []
        for entry in files:
            if entry.trashed:
                continue
            if " in parents" in query:
                parent_id = query.split("'", 2)[1]
                if parent_id not in entry.parents:
                    continue
            if "name='" in query:
                target = query.split("name='", 1)[1].split("'", 1)[0]
                if entry.name != target:
                    continue
            if "name contains '" in query:
                fragment = query.split("name contains '", 1)[1].split("'", 1)[0]
                if fragment not in entry.name:
                    continue
            if (
                "mimeType='application/vnd.google-apps.folder'" in query
                and entry.mime_type != "application/vnd.google-apps.folder"
            ):
                continue
            matches.append(entry)
        return _FakeRequest(response={"files": [m.to_entry() for m in matches]})

    def create(self, **kwargs: Any) -> _FakeRequest:
        self.parent.calls.append(("create", dict(kwargs)))
        if "create" in self.parent.raise_on:
            return _FakeRequest(response=None, raise_exc=self.parent.raise_on["create"])
        body = kwargs["body"]
        media_body = kwargs.get("media_body")
        payload: bytes = b""
        if media_body is not None:
            payload = media_body._fd.getvalue() if hasattr(media_body, "_fd") else b""
        new_id = f"drive-{uuid.uuid4().hex[:12]}"
        entry = _FakeFile(
            file_id=new_id,
            name=str(body["name"]),
            parents=list(body.get("parents", [])),
            payload=payload,
            app_properties=dict(body.get("appProperties", {})),
            mime_type=str(body.get("mimeType", "application/octet-stream")),
        )
        self.parent.files_by_id[new_id] = entry
        return _FakeRequest(response=entry.to_entry())

    def update(self, **kwargs: Any) -> _FakeRequest:
        self.parent.calls.append(("update", dict(kwargs)))
        file_id = str(kwargs["fileId"])
        body = kwargs.get("body", {})
        media_body = kwargs.get("media_body")
        entry = self.parent.files_by_id[file_id]
        if "name" in body:
            entry.name = str(body["name"])
        if "appProperties" in body:
            entry.app_properties = dict(body["appProperties"])
        if media_body is not None and hasattr(media_body, "_fd"):
            entry.payload = media_body._fd.getvalue()
        return _FakeRequest(response=entry.to_entry())

    def get(self, **kwargs: Any) -> _FakeRequest:
        self.parent.calls.append(("get", dict(kwargs)))
        if "get" in self.parent.raise_on:
            return _FakeRequest(response=None, raise_exc=self.parent.raise_on["get"])
        file_id = str(kwargs["fileId"])
        entry = self.parent.files_by_id.get(file_id)
        if entry is None:
            return _FakeRequest(response=None, raise_exc=_HttpError(404))
        return _FakeRequest(response=entry.to_entry())

    def delete(self, **kwargs: Any) -> _FakeRequest:
        self.parent.calls.append(("delete", dict(kwargs)))
        file_id = str(kwargs["fileId"])
        if file_id in self.parent.files_by_id:
            del self.parent.files_by_id[file_id]
        return _FakeRequest(response={})

    def get_media(self, **kwargs: Any) -> _FakeRequest:
        self.parent.calls.append(("get_media", dict(kwargs)))
        file_id = str(kwargs["fileId"])
        entry = self.parent.files_by_id.get(file_id)
        if entry is None:
            return _FakeRequest(response=None, raise_exc=_HttpError(404))
        return _FakeRequest(response=entry.payload)


class _HttpError(Exception):
    """Drive HttpError-shaped stand-in for tests.

    Real `googleapiclient.errors.HttpError` carries `resp.status`; the
    provider's `_translate_http_error` reads that path.
    """

    def __init__(self, status: int, detail: str = "fake http error") -> None:
        super().__init__(detail)
        self.resp = type("_FakeResp", (), {"status": status})()


def _provider(service: _FakeDriveService, *, root_folder_id: str = "root-folder-id") -> GoogleDriveProvider:
    return GoogleDriveProvider(
        credentials=object(),
        root_folder_id=root_folder_id,
        service_factory=lambda creds: service,
    )


def test_drive_provider_satisfies_runtime_protocol() -> None:
    provider = _provider(_FakeDriveService())
    assert isinstance(provider, StorageProvider)


def test_init_rejects_blank_root_folder_id() -> None:
    with pytest.raises(StorageValidationError):
        GoogleDriveProvider(credentials=object(), root_folder_id="   ")


def test_put_creates_vault_and_namespace_folders_then_uploads(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FakeDriveService()
    # Pre-seed: nothing — the provider creates `aeat-vault/` + `ledger_transaction/` lazily.
    provider = _provider(service)

    # Stub out `_build_media_body` so we do not require googleapiclient.
    captured_payload: dict[str, bytes] = {}

    def fake_media(payload: bytes) -> Any:
        captured_payload["bytes"] = payload
        stub = type("_FakeMedia", (), {"_fd": type("_FD", (), {"getvalue": lambda self: payload})()})()
        return stub

    monkeypatch.setattr("aeat.adapters.outbound.storage._google_drive._build_media_body", fake_media)

    metadata = provider.put(
        "ledger_transaction",
        "abcdef0123456789",
        b"payload-1",
        content_hash=_sha256(b"payload-1"),
        label="payroll",
    )
    assert metadata.namespace == "ledger_transaction"
    assert metadata.object_key_hmac == "abcdef0123456789"
    assert metadata.byte_length == 9
    actions = [call[0] for call in service.calls]
    # Expected sequence: list (vault present?) → create (vault) → list (ns present?) → create (ns) → list (existing file?) → create (file)
    assert actions == ["list", "create", "list", "create", "list", "create"]
    assert captured_payload["bytes"] == b"payload-1"


def test_put_reuses_existing_vault_and_namespace_folders(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FakeDriveService(
        files_by_id={
            "vault-id": _FakeFile(
                file_id="vault-id",
                name="aeat-vault",
                parents=["root-folder-id"],
                payload=b"",
                app_properties={},
                mime_type="application/vnd.google-apps.folder",
            ),
            "ns-id": _FakeFile(
                file_id="ns-id",
                name="ledger_transaction",
                parents=["vault-id"],
                payload=b"",
                app_properties={},
                mime_type="application/vnd.google-apps.folder",
            ),
        }
    )
    provider = _provider(service)
    monkeypatch.setattr(
        "aeat.adapters.outbound.storage._google_drive._build_media_body",
        lambda payload: type("_FakeMedia", (), {"_fd": type("_FD", (), {"getvalue": lambda self: payload})()})(),
    )

    metadata = provider.put(
        "ledger_transaction",
        "abcdef0123456789",
        b"hello",
        content_hash=_sha256(b"hello"),
        label="x",
    )
    actions = [call[0] for call in service.calls]
    # Vault + namespace already exist → only list-list-list-create.
    assert actions == ["list", "list", "list", "create"]
    assert metadata.byte_length == 5


def test_get_round_trips_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FakeDriveService(
        files_by_id={
            "vault-id": _FakeFile("vault-id", "aeat-vault", ["root-folder-id"], b"", {}, "application/vnd.google-apps.folder"),
            "ns-id": _FakeFile("ns-id", "ledger_transaction", ["vault-id"], b"", {}, "application/vnd.google-apps.folder"),
            "obj-id": _FakeFile(
                file_id="obj-id",
                name="abcdef01--label.bin",
                parents=["ns-id"],
                payload=b"hello-drive",
                app_properties={"object_key_hmac": "abcdef0123456789", "content_hash": _sha256(b"hello-drive")},
            ),
        }
    )
    provider = _provider(service)
    monkeypatch.setattr(
        "aeat.adapters.outbound.storage._google_drive._build_media_body",
        lambda payload: type("_FakeMedia", (), {})(),
    )

    payload, metadata = provider.get("ledger_transaction", "abcdef0123456789")
    assert payload == b"hello-drive"
    assert metadata.object_key_hmac == "abcdef0123456789"


def test_get_raises_storage_not_found_when_namespace_missing() -> None:
    service = _FakeDriveService(
        files_by_id={
            "vault-id": _FakeFile("vault-id", "aeat-vault", ["root-folder-id"], b"", {}, "application/vnd.google-apps.folder"),
        }
    )
    provider = _provider(service)
    with pytest.raises(StorageNotFoundError):
        provider.get("ledger_transaction", "abcdef0123456789")


def test_get_raises_integrity_error_on_hash_mismatch() -> None:
    service = _FakeDriveService(
        files_by_id={
            "vault-id": _FakeFile("vault-id", "aeat-vault", ["root-folder-id"], b"", {}, "application/vnd.google-apps.folder"),
            "ns-id": _FakeFile("ns-id", "ledger_transaction", ["vault-id"], b"", {}, "application/vnd.google-apps.folder"),
            "obj-id": _FakeFile(
                file_id="obj-id",
                name="abcdef01--label.bin",
                parents=["ns-id"],
                payload=b"genuine",
                app_properties={"object_key_hmac": "abcdef0123456789", "content_hash": _sha256(b"different")},
            ),
        }
    )
    provider = _provider(service)
    with pytest.raises(StorageIntegrityError):
        provider.get("ledger_transaction", "abcdef0123456789")


def test_delete_returns_true_when_file_existed() -> None:
    service = _FakeDriveService(
        files_by_id={
            "vault-id": _FakeFile("vault-id", "aeat-vault", ["root-folder-id"], b"", {}, "application/vnd.google-apps.folder"),
            "ns-id": _FakeFile("ns-id", "ledger_transaction", ["vault-id"], b"", {}, "application/vnd.google-apps.folder"),
            "obj-id": _FakeFile(
                file_id="obj-id",
                name="abcdef01--x.bin",
                parents=["ns-id"],
                payload=b"x",
                app_properties={"object_key_hmac": "abcdef0123456789"},
            ),
        }
    )
    provider = _provider(service)
    assert provider.delete("ledger_transaction", "abcdef0123456789") is True
    assert "obj-id" not in service.files_by_id


def test_delete_returns_false_when_file_absent() -> None:
    service = _FakeDriveService(
        files_by_id={
            "vault-id": _FakeFile("vault-id", "aeat-vault", ["root-folder-id"], b"", {}, "application/vnd.google-apps.folder"),
            "ns-id": _FakeFile("ns-id", "ledger_transaction", ["vault-id"], b"", {}, "application/vnd.google-apps.folder"),
        }
    )
    provider = _provider(service)
    assert provider.delete("ledger_transaction", "abcdef0123456789") is False


def test_iter_namespaces_yields_folders_under_vault() -> None:
    service = _FakeDriveService(
        files_by_id={
            "vault-id": _FakeFile("vault-id", "aeat-vault", ["root-folder-id"], b"", {}, "application/vnd.google-apps.folder"),
            "ns-a": _FakeFile("ns-a", "alpha", ["vault-id"], b"", {}, "application/vnd.google-apps.folder"),
            "ns-b": _FakeFile("ns-b", "beta", ["vault-id"], b"", {}, "application/vnd.google-apps.folder"),
            "file-x": _FakeFile("file-x", "stray.bin", ["vault-id"], b"x", {}, "application/octet-stream"),
        }
    )
    provider = _provider(service)
    namespaces = sorted(provider.iter_namespaces())
    assert namespaces == ["alpha", "beta"]


def test_iter_objects_yields_metadata() -> None:
    service = _FakeDriveService(
        files_by_id={
            "vault-id": _FakeFile("vault-id", "aeat-vault", ["root-folder-id"], b"", {}, "application/vnd.google-apps.folder"),
            "ns-id": _FakeFile("ns-id", "ledger_transaction", ["vault-id"], b"", {}, "application/vnd.google-apps.folder"),
            "obj-1": _FakeFile(
                file_id="obj-1",
                name="aaaaaaaa--first.bin",
                parents=["ns-id"],
                payload=b"a",
                app_properties={"object_key_hmac": "aaaaaaaa00000001"},
            ),
            "obj-2": _FakeFile(
                file_id="obj-2",
                name="bbbbbbbb--second.bin",
                parents=["ns-id"],
                payload=b"bb",
                app_properties={"object_key_hmac": "bbbbbbbb00000002"},
            ),
        }
    )
    provider = _provider(service)
    objects = list(provider.iter_objects("ledger_transaction"))
    assert len(objects) == 2
    keys = sorted(obj.object_key_hmac for obj in objects)
    assert keys == ["aaaaaaaa00000001", "bbbbbbbb00000002"]


def test_iter_objects_raises_for_missing_namespace() -> None:
    service = _FakeDriveService(
        files_by_id={
            "vault-id": _FakeFile("vault-id", "aeat-vault", ["root-folder-id"], b"", {}, "application/vnd.google-apps.folder"),
        }
    )
    provider = _provider(service)
    with pytest.raises(StorageNotFoundError):
        list(provider.iter_objects("never_seen"))


def test_probe_returns_root_folder_absent_when_get_404s() -> None:
    service = _FakeDriveService()
    provider = _provider(service)
    report = provider.probe()
    assert report.provider_kind == ProviderKind.GOOGLE_DRIVE
    assert report.reachable is True
    assert report.writable is False
    assert report.root_folder_present is False


def test_probe_returns_writable_true_when_full_round_trip_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FakeDriveService(
        files_by_id={
            "root-folder-id": _FakeFile(
                file_id="root-folder-id",
                name="ParentFolder",
                parents=[],
                payload=b"",
                app_properties={},
                mime_type="application/vnd.google-apps.folder",
            ),
        }
    )
    provider = _provider(service)
    monkeypatch.setattr(
        "aeat.adapters.outbound.storage._google_drive._build_media_body",
        lambda payload: type("_FakeMedia", (), {"_fd": type("_FD", (), {"getvalue": lambda self: payload})()})(),
    )
    report = provider.probe()
    assert report.reachable is True
    assert report.writable is True
    assert report.root_folder_present is True


def test_probe_read_only_skips_sentinel_round_trip() -> None:
    service = _FakeDriveService(
        files_by_id={
            "root-folder-id": _FakeFile(
                file_id="root-folder-id",
                name="ParentFolder",
                parents=[],
                payload=b"",
                app_properties={},
                mime_type="application/vnd.google-apps.folder",
            ),
        }
    )
    provider = _provider(service)
    report = provider.probe(read_only=True)
    assert report.read_only is True
    assert report.writable is False
    assert report.root_folder_present is True
    # No create-call (sentinel skipped).
    assert all(call[0] != "create" for call in service.calls)


def test_translate_http_error_maps_403_to_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FakeDriveService(
        files_by_id={
            "vault-id": _FakeFile("vault-id", "aeat-vault", ["root-folder-id"], b"", {}, "application/vnd.google-apps.folder"),
            "ns-id": _FakeFile("ns-id", "ledger_transaction", ["vault-id"], b"", {}, "application/vnd.google-apps.folder"),
        },
        raise_on={"create": _HttpError(403, "permission denied")},
    )
    provider = _provider(service)
    monkeypatch.setattr(
        "aeat.adapters.outbound.storage._google_drive._build_media_body",
        lambda payload: type("_FakeMedia", (), {"_fd": type("_FD", (), {"getvalue": lambda self: payload})()})(),
    )
    with pytest.raises(StoragePermissionError):
        provider.put(
            "ledger_transaction",
            "abcdef0123456789",
            b"x",
            content_hash=_sha256(b"x"),
            label="x",
        )


def test_put_rejects_blank_namespace() -> None:
    provider = _provider(_FakeDriveService())
    with pytest.raises(StorageValidationError):
        provider.put("", "abcdef0123456789", b"x", content_hash="sha256-x", label="x")
