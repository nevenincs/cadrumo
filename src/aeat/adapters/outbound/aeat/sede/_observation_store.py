"""Persistence helpers for read-only filed-declaration observations."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

from ....persistence.storage import Envelope, MasterKeyProvider, SensitivityClass
from ....persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ....persistence.storage.sql import SecureObjectRepository
from ._schema import FiledDeclarationArtefact, FiledDeclarationObservation

_SAFE_SEGMENT_RE = re.compile(r"[^0-9A-Za-z_.-]+")
_ARTEFACT_CLASSIFICATION = SensitivityClass.FINANCIAL
_OBSERVATION_CLASSIFICATION = SensitivityClass.FINANCIAL
_OBSERVATION_ENVELOPE_VERSION = 1
_ARTEFACT_NAMESPACE = "aeat.outbound.aeat.sede.filed_declaration.artefacts"
_OBSERVATION_NAMESPACE = "aeat.outbound.aeat.sede.filed_declaration.observations"
_STORAGE_REF_PREFIX = "secure-object:financial:"


class FiledDeclarationObservationStore:
    """Persist captured AEAT filed data through the encrypted SQL backend."""

    def __init__(self, root: Path, *, master_key_provider: MasterKeyProvider | None = None) -> None:
        del root, master_key_provider
        self._objects = SecureObjectRepository()

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
        digest = hashlib.sha256(body).hexdigest()
        if digest != artefact.sha256:
            raise ValueError("filed-declaration artefact SHA-256 does not match its body")
        self._objects.save(
            namespace=_ARTEFACT_NAMESPACE,
            object_key=digest,
            classification=_ARTEFACT_CLASSIFICATION,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=body,
        )
        return artefact.model_copy(update={"storage_ref": _format_storage_ref(digest)})

    def load_artefact(self, storage_ref: str) -> bytes:
        """Return plaintext artefact bytes from an encrypted storage reference."""

        digest = _parse_storage_ref(storage_ref)
        record = self._objects.load(
            _ARTEFACT_NAMESPACE,
            digest,
            expected_class=_ARTEFACT_CLASSIFICATION,
            max_supported_version=1,
        )
        if record is None:
            raise FileNotFoundError(f"filed-declaration artefact not found: {digest}")
        return record.payload

    def persist_observation(self, observation: FiledDeclarationObservation) -> Path:
        """Persist a normalized observation manifest and return its logical object path."""

        object_key = self._observation_key(
            observation.modelo,
            observation.ejercicio,
            observation.period,
            observation.expediente_id,
        )
        envelope = Envelope[FiledDeclarationObservation](
            schema_version=_OBSERVATION_ENVELOPE_VERSION,
            written_at=datetime.now(UTC),
            classification=_OBSERVATION_CLASSIFICATION,
            payload=observation,
        )
        self._objects.save(
            namespace=_OBSERVATION_NAMESPACE,
            object_key=object_key,
            classification=_OBSERVATION_CLASSIFICATION,
            schema_version=_OBSERVATION_ENVELOPE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        return _logical_path(_OBSERVATION_NAMESPACE, object_key)

    def load_observation(self, path: Path) -> FiledDeclarationObservation:
        """Load and decrypt a normalized filed-declaration observation."""

        object_key = Path(path).name
        record = self._objects.load(
            _OBSERVATION_NAMESPACE,
            object_key,
            expected_class=_OBSERVATION_CLASSIFICATION,
            max_supported_version=_OBSERVATION_ENVELOPE_VERSION,
        )
        if record is None:
            raise FileNotFoundError(f"filed-declaration observation not found: {object_key}")
        envelope = Envelope[FiledDeclarationObservation].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not _OBSERVATION_CLASSIFICATION:
            raise ClassificationError(
                f"filed-declaration observation {object_key} has classification {envelope.classification}; "
                f"consumer expected {_OBSERVATION_CLASSIFICATION}",
            )
        if envelope.schema_version > _OBSERVATION_ENVELOPE_VERSION:
            raise EnvelopeVersionError(
                f"filed-declaration observation {object_key} is at version {envelope.schema_version}; "
                f"consumer supports up to {_OBSERVATION_ENVELOPE_VERSION}",
            )
        return envelope.payload

    def _observation_key(
        self,
        modelo: str,
        ejercicio: int,
        period: str,
        expediente_id: str,
    ) -> str:
        key = "\x1f".join(
            (
                _safe_segment(modelo),
                str(ejercicio),
                _safe_segment(period),
                _safe_segment(expediente_id),
            )
        )
        return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _safe_segment(value: str) -> str:
    cleaned = _SAFE_SEGMENT_RE.sub("_", value.strip())
    cleaned = cleaned.strip("._")
    if not cleaned:
        raise ValueError("filed-declaration store path segment is empty")
    return cleaned


def _logical_path(namespace: str, object_key: str) -> Path:
    return Path("db://secure_objects") / namespace / object_key


def _format_storage_ref(digest: str) -> str:
    return f"{_STORAGE_REF_PREFIX}{digest}"


def _parse_storage_ref(storage_ref: str) -> str:
    if not storage_ref.startswith(_STORAGE_REF_PREFIX):
        raise ValueError("filed-declaration artefact storage reference is not financial")
    return storage_ref.removeprefix(_STORAGE_REF_PREFIX)


__all__ = ["FiledDeclarationObservationStore"]
