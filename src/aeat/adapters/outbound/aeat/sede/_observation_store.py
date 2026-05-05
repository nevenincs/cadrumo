"""Persistence helpers for read-only filed-declaration observations."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

from ....persistence.storage import (
    BlobReference,
    EncryptedBlobStore,
    Envelope,
    MasterKeyProvider,
    SensitivityClass,
    get_master_key_provider,
    load_encrypted_envelope,
    save_encrypted_envelope,
)
from ._schema import FiledDeclarationArtefact, FiledDeclarationObservation

_SAFE_SEGMENT_RE = re.compile(r"[^0-9A-Za-z_.-]+")
_ARTEFACT_CLASSIFICATION = SensitivityClass.FINANCIAL
_OBSERVATION_CLASSIFICATION = SensitivityClass.FINANCIAL
_OBSERVATION_ENVELOPE_VERSION = 1
_OBSERVATION_HKDF_CONTEXT = b"aeat.sede.filed-declaration-observation.v1"
_STORAGE_REF_PREFIX = "blob:financial:"


class FiledDeclarationObservationStore:
    """Persist captured AEAT filed data through the encrypted storage substrate."""

    def __init__(self, root: Path, *, master_key_provider: MasterKeyProvider | None = None) -> None:
        self.root = Path(root)
        self._master_key_provider = master_key_provider
        self._blob_store = EncryptedBlobStore(
            root_dir=self.root,
            master_key_provider=master_key_provider,
        )

    def persist_artefact(
        self,
        observation_key: tuple[str, int, str, str],
        artefact: FiledDeclarationArtefact,
        body: bytes,
    ) -> FiledDeclarationArtefact:
        """Persist one captured artefact and return metadata with its storage reference."""

        if not body:
            raise ValueError("cannot persist an empty filed-declaration artefact")
        if len(body) != artefact.byte_count:
            raise ValueError("filed-declaration artefact byte count does not match its body")

        del observation_key
        reference = self._blob_store.put(
            body,
            classification=_ARTEFACT_CLASSIFICATION,
            content_type=artefact.content_type,
        )
        if reference.sha256_plaintext_hex != artefact.sha256:
            raise ValueError("filed-declaration artefact SHA-256 does not match its body")
        return artefact.model_copy(update={"storage_ref": _format_storage_ref(reference)})

    def load_artefact(self, storage_ref: str) -> bytes:
        """Return plaintext artefact bytes from an encrypted storage reference."""

        return self._blob_store.get(_parse_storage_ref(storage_ref))

    def persist_observation(self, observation: FiledDeclarationObservation) -> Path:
        """Persist a normalized observation manifest as ciphertext and return its path."""

        folder = self._observation_dir(
            observation.modelo,
            observation.ejercicio,
            observation.period,
            observation.expediente_id,
        )
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "observation.envelope.json"
        envelope = Envelope[FiledDeclarationObservation](
            schema_version=_OBSERVATION_ENVELOPE_VERSION,
            written_at=datetime.now(UTC),
            classification=_OBSERVATION_CLASSIFICATION,
            payload=observation,
        )
        save_encrypted_envelope(
            envelope,
            path,
            master_key_provider=self._master_key(),
            hkdf_context=_OBSERVATION_HKDF_CONTEXT,
        )
        return path

    def load_observation(self, path: Path) -> FiledDeclarationObservation:
        """Load and decrypt a normalized filed-declaration observation."""

        envelope = load_encrypted_envelope(
            Path(path),
            Envelope[FiledDeclarationObservation],
            expected_class=_OBSERVATION_CLASSIFICATION,
            master_key_provider=self._master_key(),
            hkdf_context=_OBSERVATION_HKDF_CONTEXT,
            max_supported_version=_OBSERVATION_ENVELOPE_VERSION,
        )
        return envelope.payload

    def _master_key(self) -> MasterKeyProvider:
        return self._master_key_provider or get_master_key_provider()

    def _observation_dir(
        self,
        modelo: str,
        ejercicio: int,
        period: str,
        expediente_id: str,
    ) -> Path:
        key = "\x1f".join(
            (
                _safe_segment(modelo),
                str(ejercicio),
                _safe_segment(period),
                _safe_segment(expediente_id),
            )
        )
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.root / "observations" / digest[:2] / digest


def _safe_segment(value: str) -> str:
    cleaned = _SAFE_SEGMENT_RE.sub("_", value.strip())
    cleaned = cleaned.strip("._")
    if not cleaned:
        raise ValueError("filed-declaration store path segment is empty")
    return cleaned


def _format_storage_ref(reference: BlobReference) -> str:
    if reference.classification is not _ARTEFACT_CLASSIFICATION:
        raise ValueError("filed-declaration artefacts must be stored as financial data")
    return f"{_STORAGE_REF_PREFIX}{reference.sha256_plaintext_hex}"


def _parse_storage_ref(storage_ref: str) -> BlobReference:
    if not storage_ref.startswith(_STORAGE_REF_PREFIX):
        raise ValueError("filed-declaration artefact storage reference is not financial")
    return BlobReference(
        sha256_plaintext_hex=storage_ref.removeprefix(_STORAGE_REF_PREFIX),
        classification=_ARTEFACT_CLASSIFICATION,
    )


__all__ = ["FiledDeclarationObservationStore"]
