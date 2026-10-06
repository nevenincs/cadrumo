"""Encrypted creation receipts and metadata for existing paginated HTTP fixtures."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID, uuid5

from .....application.export.managed_artifact_ports import ArtifactCreationReceipt, ManagedArtifactKind
from .....core.type_guards import is_object_list, is_str_keyed_dict
from ....persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...google.artifact_admission import artifact_mime_type, creation_properties
from ...google.artifact_receipt_store import GoogleArtifactReceiptStore
from ...google.tests.drive_list_server import DriveFilesListEndpoint
from ...google.tests.drive_list_server import drive_files_list_endpoint as _endpoint

_PROFILE = UUID("00a80000-0000-4000-8000-000000000008")
_RECEIPTS: ContextVar[GoogleArtifactReceiptStore | None] = ContextVar("test_drive_creation_receipts", default=None)


def current_drive_receipts() -> GoogleArtifactReceiptStore | None:
    """Return custody from the explicit HTTP-tree fixture, if one is active."""
    return _RECEIPTS.get()


@contextmanager
def drive_files_list_endpoint(
    *, pages: Sequence[Mapping[str, object]], status: int = 200, root_folder_id: str = "drive-root"
) -> Iterator[DriveFilesListEndpoint]:
    """Build acknowledged fixture creations separately from the remote list responses."""
    listed: dict[str, Mapping[str, object]] = {}
    for page in pages:
        rows = page.get("files")
        if is_object_list(rows):
            for row in rows:
                if is_str_keyed_dict(row) and isinstance(row.get("id"), str):
                    listed[str(row["id"])] = row
    kinds = {
        root_folder_id: (ManagedArtifactKind.ROOT, None),
        "vault-id": (ManagedArtifactKind.FOLDER, root_folder_id),
        "namespace-id": (ManagedArtifactKind.FOLDER, "vault-id"),
    }
    for identifier, row in listed.items():
        if identifier not in kinds:
            kind = (
                ManagedArtifactKind.CIPHERTEXT
                if str(row.get("name", "")).endswith(".bin")
                else ManagedArtifactKind.FOLDER
            )
            kinds[identifier] = (kind, "namespace-id" if kind is ManagedArtifactKind.CIPHERTEXT else root_folder_id)
    metadata: dict[str, Mapping[str, object]] = {}
    with (
        TemporaryDirectory(prefix="cadrumo-drive-receipts-") as temporary,
        isolated_runtime_profile(tmp_path=Path(temporary), bucket_id=str(_PROFILE)) as profile,
    ):
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=_PROFILE)
        for identifier, (kind, parent) in kinds.items():
            receipt = ArtifactCreationReceipt(
                profile_id=_PROFILE,
                root_folder_id=root_folder_id,
                artifact_id=identifier,
                parent_id=parent,
                creation_id=uuid5(_PROFILE, identifier),
                kind=kind,
            )
            receipts.record(receipt)
            original = listed.get(identifier, {})
            props = creation_properties(
                profile_id=_PROFILE,
                creation_id=receipt.creation_id,
                kind=kind,
                root_folder_id=None if kind is ManagedArtifactKind.ROOT else root_folder_id,
            )
            raw_props = original.get("appProperties")
            if is_str_keyed_dict(raw_props):
                props.update({key: str(value) for key, value in raw_props.items()})
                if "cadrumo_vault_app" not in raw_props:
                    props.pop("cadrumo_vault_app", None)
            elif original:
                props = {}
            metadata[identifier] = {
                **original,
                "id": identifier,
                "parents": [parent] if parent else ["root"],
                "trashed": False,
                "mimeType": original.get("mimeType", artifact_mime_type(kind)),
                "appProperties": props,
            }
        token = _RECEIPTS.set(receipts)
        try:
            with _endpoint(pages=pages, status=status, metadata=metadata) as endpoint:
                yield endpoint
        finally:
            _RECEIPTS.reset(token)
