"""Persistence helpers for read-only filed-declaration observations.

Persists each filed-declaration observation as an :class:`Envelope` record
through :class:`SecureObjectRepository`, keyed by declaration identity so a
prior filing can be retrieved without re-fetching it from the sede. Each
envelope is classified at :class:`SensitivityClass` FINANCIAL and encrypted
via the active :class:`MasterKeyProvider`.
"""

from __future__ import annotations

import re
from contextlib import nullcontext
from pathlib import Path

from .....core import Period
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.hashing import sha256_hex
from .....core.time import now
from ....persistence.storage import Envelope, MasterKeyProvider, SensitivityClass
from ....persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ....persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....persistence.storage.sql import SecureObjectRepository
from ._errors import ExpedienteNotFoundError, SedeValidationError
from ._schema import FiledDeclaracionArtefact, FiledDeclaracionObservation, IvaCompensationWalletObservation

_SAFE_SEGMENT_RE = re.compile(r"[^0-9A-Za-z_.-]+")
_ARTEFACT_CLASSIFICATION = SensitivityClass.FINANCIAL
_OBSERVATION_CLASSIFICATION = SensitivityClass.FINANCIAL
_OBSERVATION_ENVELOPE_VERSION = 1
_ARTEFACT_NAMESPACE = "aeat.outbound.aeat.sede.filed_declaration.artefacts"
_OBSERVATION_NAMESPACE = "aeat.outbound.aeat.sede.filed_declaration.observations"
_IVA_WALLET_OBSERVATION_NAMESPACE = "aeat.outbound.aeat.sede.iva_compensation_wallet.observations"
_STORAGE_REF_PREFIX = "secure-object:financial:"


class FiledDeclaracionObservationStore:
    """Persist captured AEAT filed data through the encrypted SQL backend."""

    def __init__(
        self,
        root: Path,
        *,
        master_key_provider: MasterKeyProvider | None = None,
        objects: SecureObjectRepository | None = None,
    ) -> None:
        del master_key_provider
        self._root = Path(root)
        self._objects = objects

    @property
    def _repository(self) -> SecureObjectRepository:
        if self._objects is None:
            self._objects = secure_object_repository_for_active_bucket()
        return self._objects

    def persist_artefact(
        self,
        observation_key: tuple[str, int, Period, str],
        artefact: FiledDeclaracionArtefact,
        body: bytes,
    ) -> FiledDeclaracionArtefact:
        """Persist one captured artefact and return a :class:`FiledDeclaracionArtefact` with its storage reference."""
        if not artefact.storage_ref and not body:
            raise SedeValidationError("cannot persist an empty filed-declaration artefact")
        if body and len(body) != artefact.byte_count:
            raise SedeValidationError("filed-declaration artefact byte count does not match its body")

        del observation_key
        if body and sha256_hex(body) != artefact.sha256:
            raise SedeValidationError("filed-declaration artefact SHA-256 does not match its body")
        digest = sha256_hex(body)
        with self._crypto_scope():
            self._repository.save(
                namespace=_ARTEFACT_NAMESPACE,
                object_key=digest,
                classification=_ARTEFACT_CLASSIFICATION,
                schema_version=1,
                written_at=now(),
                payload=body,
            )
        return artefact.model_copy(update={"storage_ref": _format_storage_ref(digest)})

    def load_artefact(self, storage_ref: str) -> bytes:
        """Return plaintext artefact bytes from an encrypted storage reference."""
        digest = _parse_storage_ref(storage_ref)
        with self._crypto_scope():
            record = self._repository.load(
                _ARTEFACT_NAMESPACE,
                digest,
                expected_class=_ARTEFACT_CLASSIFICATION,
                max_supported_version=1,
            )
        if record is None:
            raise ExpedienteNotFoundError(f"filed-declaration artefact not found: {digest}")
        return record.payload

    def persist_observation(self, observation: FiledDeclaracionObservation) -> Path:
        """Persist a normalized observation manifest and return its logical object path."""
        object_key = self._observation_key(
            observation.modelo,
            observation.ejercicio,
            observation.period,
            observation.expediente_id,
        )
        envelope = Envelope[FiledDeclaracionObservation](
            schema_version=_OBSERVATION_ENVELOPE_VERSION,
            written_at=now(),
            classification=_OBSERVATION_CLASSIFICATION,
            payload=observation,
        )
        with self._crypto_scope():
            self._repository.save(
                namespace=_OBSERVATION_NAMESPACE,
                object_key=object_key,
                classification=_OBSERVATION_CLASSIFICATION,
                schema_version=_OBSERVATION_ENVELOPE_VERSION,
                written_at=envelope.written_at,
                payload=envelope.model_dump_json().encode(_UTF_8_ENCODING),
            )
        return _logical_path(_OBSERVATION_NAMESPACE, object_key)

    def load_observation(self, path: Path) -> FiledDeclaracionObservation:
        """Load and decrypt a :class:`FiledDeclaracionObservation` from the encrypted store."""
        object_key = Path(path).name
        with self._crypto_scope():
            record = self._repository.load(
                _OBSERVATION_NAMESPACE,
                object_key,
                expected_class=_OBSERVATION_CLASSIFICATION,
                max_supported_version=_OBSERVATION_ENVELOPE_VERSION,
            )
        if record is None:
            raise ExpedienteNotFoundError(f"filed-declaration observation not found: {object_key}")
        envelope = Envelope[FiledDeclaracionObservation].model_validate_json(record.payload.decode(_UTF_8_ENCODING))
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

    def list_observations(self) -> tuple[FiledDeclaracionObservation, ...]:
        """Return :class:`FiledDeclaracionObservation` records from the active encrypted backend."""
        observations: list[FiledDeclaracionObservation] = []
        with self._crypto_scope():
            records = self._repository.list_records(
                _OBSERVATION_NAMESPACE,
                expected_class=_OBSERVATION_CLASSIFICATION,
                max_supported_version=_OBSERVATION_ENVELOPE_VERSION,
            )
        for record in records:
            envelope = Envelope[FiledDeclaracionObservation].model_validate_json(record.payload.decode(_UTF_8_ENCODING))
            if envelope.classification is not _OBSERVATION_CLASSIFICATION:
                raise ClassificationError(
                    f"filed-declaration observation {record.object_key!r} has classification "
                    f"{envelope.classification}; consumer expected {_OBSERVATION_CLASSIFICATION}",
                )
            if envelope.schema_version > _OBSERVATION_ENVELOPE_VERSION:
                raise EnvelopeVersionError(
                    f"filed-declaration observation {record.object_key!r} is at version "
                    f"{envelope.schema_version}; consumer supports up to {_OBSERVATION_ENVELOPE_VERSION}",
                )
            observations.append(envelope.payload)
        return tuple(
            sorted(
                observations,
                key=lambda item: (
                    item.modelo,
                    item.ejercicio,
                    item.period.registry_token,
                    item.presented_at,
                    item.expediente_id,
                ),
            ),
        )

    def persist_iva_wallet_observation(self, observation: IvaCompensationWalletObservation) -> Path:
        """Persist a read-only IVA wallet observation and return its logical path."""
        object_key = self._iva_wallet_observation_key(
            observation.taxpayer_nif,
            observation.target_year,
            observation.target_period,
            observation.captured_at.isoformat(),
        )
        envelope = Envelope[IvaCompensationWalletObservation](
            schema_version=_OBSERVATION_ENVELOPE_VERSION,
            written_at=now(),
            classification=_OBSERVATION_CLASSIFICATION,
            payload=observation,
        )
        with self._crypto_scope():
            self._repository.save(
                namespace=_IVA_WALLET_OBSERVATION_NAMESPACE,
                object_key=object_key,
                classification=_OBSERVATION_CLASSIFICATION,
                schema_version=_OBSERVATION_ENVELOPE_VERSION,
                written_at=envelope.written_at,
                payload=envelope.model_dump_json().encode(_UTF_8_ENCODING),
            )
        return _logical_path(_IVA_WALLET_OBSERVATION_NAMESPACE, object_key)

    def load_iva_wallet_observation(self, path: Path) -> IvaCompensationWalletObservation:
        """Load and decrypt an :class:`IvaCompensationWalletObservation` from ``path``."""
        object_key = Path(path).name
        with self._crypto_scope():
            record = self._repository.load(
                _IVA_WALLET_OBSERVATION_NAMESPACE,
                object_key,
                expected_class=_OBSERVATION_CLASSIFICATION,
                max_supported_version=_OBSERVATION_ENVELOPE_VERSION,
            )
        if record is None:
            raise ExpedienteNotFoundError(f"IVA wallet observation not found: {object_key}")
        envelope = Envelope[IvaCompensationWalletObservation].model_validate_json(
            record.payload.decode(_UTF_8_ENCODING),
        )
        if envelope.classification is not _OBSERVATION_CLASSIFICATION:
            raise ClassificationError(
                f"IVA wallet observation {object_key} has classification {envelope.classification}; "
                f"consumer expected {_OBSERVATION_CLASSIFICATION}",
            )
        if envelope.schema_version > _OBSERVATION_ENVELOPE_VERSION:
            raise EnvelopeVersionError(
                f"IVA wallet observation {object_key} is at version {envelope.schema_version}; "
                f"consumer supports up to {_OBSERVATION_ENVELOPE_VERSION}",
            )
        return envelope.payload

    def list_iva_wallet_observations(self) -> tuple[IvaCompensationWalletObservation, ...]:
        """Return :class:`IvaCompensationWalletObservation` records from the active encrypted backend."""
        observations: list[IvaCompensationWalletObservation] = []
        with self._crypto_scope():
            records = self._repository.list_records(
                _IVA_WALLET_OBSERVATION_NAMESPACE,
                expected_class=_OBSERVATION_CLASSIFICATION,
                max_supported_version=_OBSERVATION_ENVELOPE_VERSION,
            )
        for record in records:
            envelope = Envelope[IvaCompensationWalletObservation].model_validate_json(
                record.payload.decode(_UTF_8_ENCODING),
            )
            if envelope.classification is not _OBSERVATION_CLASSIFICATION:
                raise ClassificationError(
                    f"IVA wallet observation {record.object_key!r} has classification {envelope.classification}; "
                    f"consumer expected {_OBSERVATION_CLASSIFICATION}",
                )
            if envelope.schema_version > _OBSERVATION_ENVELOPE_VERSION:
                raise EnvelopeVersionError(
                    f"IVA wallet observation {record.object_key!r} is at version {envelope.schema_version}; "
                    f"consumer supports up to {_OBSERVATION_ENVELOPE_VERSION}",
                )
            observations.append(envelope.payload)
        return tuple(
            sorted(
                observations,
                key=lambda item: (item.target_year, item.target_period.registry_token, item.captured_at),
            ),
        )

    def _observation_key(
        self,
        modelo: str,
        ejercicio: int,
        period: Period,
        expediente_id: str,
    ) -> str:
        key = "\x1f".join(
            (
                _safe_segment(modelo),
                str(ejercicio),
                _safe_segment(period.registry_token),
                _safe_segment(expediente_id),
            ),
        )
        return sha256_hex(key.encode(_UTF_8_ENCODING))

    def _crypto_scope(self):
        return nullcontext()

    def _iva_wallet_observation_key(
        self,
        taxpayer_nif: str,
        target_year: int,
        target_period: Period,
        captured_at: str,
    ) -> str:
        key = "\x1f".join(
            (
                _safe_segment(taxpayer_nif),
                str(target_year),
                _safe_segment(target_period.registry_token),
                captured_at,
            ),
        )
        return sha256_hex(key.encode(_UTF_8_ENCODING))


def _safe_segment(value: str) -> str:
    cleaned = _SAFE_SEGMENT_RE.sub("_", value.strip())
    cleaned = cleaned.strip("._")
    if not cleaned:
        raise SedeValidationError("filed-declaration store path segment is empty")
    return cleaned


def _logical_path(namespace: str, object_key: str) -> Path:
    return Path("db://secure_objects") / namespace / object_key


def _format_storage_ref(digest: str) -> str:
    return f"{_STORAGE_REF_PREFIX}{digest}"


def _parse_storage_ref(storage_ref: str) -> str:
    if not storage_ref.startswith(_STORAGE_REF_PREFIX):
        raise SedeValidationError("filed-declaration artefact storage reference is not financial")
    return storage_ref.removeprefix(_STORAGE_REF_PREFIX)


__all__ = ["FiledDeclaracionObservationStore"]
