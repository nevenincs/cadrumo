"""Persistence helpers for read-only filed-declaration observations.

Persists each filed-declaration observation as an
:class:`~adapters.persistence.storage.Envelope` record through
:class:`~adapters.persistence.storage.SecureObjectRepository`, keyed
by declaration identity so a prior filing can be retrieved without re-fetching
it from the sede. Each envelope is classified at
:class:`~adapters.persistence.storage.SensitivityClass` ``FINANCIAL`` and
encrypted via the active
:class:`~adapters.persistence.storage.MasterKeyProvider`.

Artefact bytes are stored under
:data:`adapters.persistence.storage.AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE`;
filed-declaration observation envelopes are stored under
:data:`adapters.persistence.storage.AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE`;
IVA wallet observation envelopes are stored under
:data:`adapters.persistence.storage.AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE`.
Those namespace definitions provide the schema version, key grammar, profile
scope, and full-custody disposition for each row family.
"""

from __future__ import annotations

import re
from contextlib import nullcontext
from pathlib import Path

from .....core import Period
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.hashing import sha256_hex
from .....core.resources import resources
from .....core.time import now
from .....domain.calculations.registry import RegistrySnapshotError, undeclared_casilla_ids
from ....persistence.storage import (
    AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE,
    AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE,
    AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE,
    ClassificationError,
    Envelope,
    EnvelopeVersionError,
    MasterKeyProvider,
    SecureObjectRepository,
    inner_envelope_version_is_current,
    secure_object_repository_for_active_bucket,
)
from ....persistence.storage.crypto import secure_object_key_digest
from ._errors import ExpedienteNotFoundError, SedeValidationError
from ._schema import FiledDeclaracionArtefact, FiledDeclaracionObservation, IvaCompensationWalletObservation

_SAFE_SEGMENT_RE = re.compile(r"[^0-9A-Za-z_.-]+")
_ARTEFACT_NAMESPACE = AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE.namespace
_ARTEFACT_CLASSIFICATION = AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE.sensitivity
_ARTEFACT_ENVELOPE_VERSION = AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE.schema_version
_OBSERVATION_NAMESPACE = AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE.namespace
_OBSERVATION_CLASSIFICATION = AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE.sensitivity
_OBSERVATION_ENVELOPE_VERSION = AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE.schema_version
_IVA_WALLET_OBSERVATION_NAMESPACE = AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE.namespace
_IVA_WALLET_CLASSIFICATION = AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE.sensitivity
_IVA_WALLET_ENVELOPE_VERSION = AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE.schema_version
_STORAGE_REF_PREFIX = "secure-object:financial:"


class FiledDeclaracionObservationStore:
    """Persist captured AEAT filed data through encrypted SQL namespaces.

    The store writes raw captured artefact bytes to
    :data:`adapters.persistence.storage.AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE`.
    It wraps :class:`FiledDeclaracionObservation` and
    :class:`IvaCompensationWalletObservation` payloads in
    :class:`~adapters.persistence.storage.Envelope` records before writing
    them to their dedicated FINANCIAL namespaces through
    :class:`~adapters.persistence.storage.SecureObjectRepository`.
    """

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
        """Persist one captured artefact and return its :class:`FiledDeclaracionArtefact` storage reference.

        Artefact bytes are stored under
        :data:`adapters.persistence.storage.AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE`
        using the body SHA-256 as the natural object key.
        """
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
                schema_version=_ARTEFACT_ENVELOPE_VERSION,
                written_at=now(),
                payload=body,
            )
        return artefact.model_copy(update={"storage_ref": _format_storage_ref(digest)})

    def load_artefact(self, storage_ref: str) -> bytes:
        """Return plaintext artefact bytes from an encrypted storage reference.

        The reference resolves into
        :data:`adapters.persistence.storage.AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE`.

        The returned bytes are re-hashed and compared with the requested
        digest. A content address is a claim ABOUT bytes, and a claim nothing
        re-checks is only a lookup key: :meth:`persist_artefact` verifies the
        digest on the way in, but the row could be overwritten afterwards
        under the same key, and the read then returned content that did not
        match the reference it was asked for. Decrypting proves custody of the
        bucket key; it says nothing about whether these are the bytes the
        reference names.

        This is AEAT filing evidence, so a silent substitution is the failure
        that matters: the artefact is what a taxpayer would produce to defend
        a filed figure, and bytes that do not hash to their own reference
        cannot do that whatever they contain.

        Raises:
            ExpedienteNotFoundError: When no artefact is stored under the
                reference.
            SedeValidationError: When the stored bytes do not hash to the
                requested digest.
        """
        digest = _parse_storage_ref(storage_ref)
        with self._crypto_scope():
            record = self._repository.load(
                _ARTEFACT_NAMESPACE,
                digest,
                expected_class=_ARTEFACT_CLASSIFICATION,
                max_supported_version=_ARTEFACT_ENVELOPE_VERSION,
            )
        if record is None:
            raise ExpedienteNotFoundError(f"filed-declaration artefact not found: {digest}")
        actual = sha256_hex(record.payload)
        if actual != digest:
            raise SedeValidationError(
                "filed-declaration artefact does not match its content address: "
                f"requested {digest}, stored bytes hash to {actual}",
            )
        return record.payload

    def persist_observation(self, observation: FiledDeclaracionObservation) -> Path:
        """Persist a normalized observation manifest and return its logical object path.

        The envelope row is stored under
        :data:`adapters.persistence.storage.AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE`.
        """
        _validate_observation_casilla_ids(observation)
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
        """Load and decrypt a :class:`FiledDeclaracionObservation` from the encrypted store.

        The encrypted row is read from
        :data:`adapters.persistence.storage.AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE`.
        """
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
        if not inner_envelope_version_is_current(envelope.schema_version, _OBSERVATION_ENVELOPE_VERSION):
            raise EnvelopeVersionError(
                f"filed-declaration observation {object_key} is at version {envelope.schema_version}; "
                f"consumer supports up to {_OBSERVATION_ENVELOPE_VERSION}",
            )
        _assert_payload_is_the_requested_row(
            self._key_of_observation(envelope.payload),
            object_key,
            "filed-declaration observation",
        )
        return envelope.payload

    def list_observations(self) -> tuple[FiledDeclaracionObservation, ...]:
        """Return :class:`FiledDeclaracionObservation` records from the active encrypted backend.

        Rows are scanned from
        :data:`adapters.persistence.storage.AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE`.
        """
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
            if not inner_envelope_version_is_current(envelope.schema_version, _OBSERVATION_ENVELOPE_VERSION):
                raise EnvelopeVersionError(
                    f"filed-declaration observation {record.object_key!r} is at version "
                    f"{envelope.schema_version}; consumer supports up to {_OBSERVATION_ENVELOPE_VERSION}",
                )
            _assert_payload_is_its_own_row(
                self._key_of_observation(envelope.payload),
                record.object_key,
                "filed-declaration observation",
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
        """Persist a read-only IVA wallet observation and return its logical path.

        The envelope row is stored under
        :data:`adapters.persistence.storage.AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE`.
        """
        object_key = self._iva_wallet_observation_key(
            observation.taxpayer_nif,
            observation.target_year,
            observation.target_period,
            observation.captured_at.isoformat(),
        )
        envelope = Envelope[IvaCompensationWalletObservation](
            schema_version=_IVA_WALLET_ENVELOPE_VERSION,
            written_at=now(),
            classification=_IVA_WALLET_CLASSIFICATION,
            payload=observation,
        )
        with self._crypto_scope():
            self._repository.save(
                namespace=_IVA_WALLET_OBSERVATION_NAMESPACE,
                object_key=object_key,
                classification=_IVA_WALLET_CLASSIFICATION,
                schema_version=_IVA_WALLET_ENVELOPE_VERSION,
                written_at=envelope.written_at,
                payload=envelope.model_dump_json().encode(_UTF_8_ENCODING),
            )
        return _logical_path(_IVA_WALLET_OBSERVATION_NAMESPACE, object_key)

    def load_iva_wallet_observation(self, path: Path) -> IvaCompensationWalletObservation:
        """Load and decrypt an :class:`IvaCompensationWalletObservation` from ``path``.

        The encrypted row is read from
        :data:`adapters.persistence.storage.AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE`.
        """
        object_key = Path(path).name
        with self._crypto_scope():
            record = self._repository.load(
                _IVA_WALLET_OBSERVATION_NAMESPACE,
                object_key,
                expected_class=_IVA_WALLET_CLASSIFICATION,
                max_supported_version=_IVA_WALLET_ENVELOPE_VERSION,
            )
        if record is None:
            raise ExpedienteNotFoundError(f"IVA wallet observation not found: {object_key}")
        envelope = Envelope[IvaCompensationWalletObservation].model_validate_json(
            record.payload.decode(_UTF_8_ENCODING),
        )
        if envelope.classification is not _IVA_WALLET_CLASSIFICATION:
            raise ClassificationError(
                f"IVA wallet observation {object_key} has classification {envelope.classification}; "
                f"consumer expected {_IVA_WALLET_CLASSIFICATION}",
            )
        if not inner_envelope_version_is_current(envelope.schema_version, _IVA_WALLET_ENVELOPE_VERSION):
            raise EnvelopeVersionError(
                f"IVA wallet observation {object_key} is at version {envelope.schema_version}; "
                f"consumer supports up to {_IVA_WALLET_ENVELOPE_VERSION}",
            )
        _assert_payload_is_the_requested_row(
            self._key_of_iva_wallet_observation(envelope.payload),
            object_key,
            "IVA wallet observation",
        )
        return envelope.payload

    def list_iva_wallet_observations(self) -> tuple[IvaCompensationWalletObservation, ...]:
        """Return :class:`IvaCompensationWalletObservation` records from the active encrypted backend.

        Rows are scanned from
        :data:`adapters.persistence.storage.AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE`.
        """
        observations: list[IvaCompensationWalletObservation] = []
        with self._crypto_scope():
            records = self._repository.list_records(
                _IVA_WALLET_OBSERVATION_NAMESPACE,
                expected_class=_IVA_WALLET_CLASSIFICATION,
                max_supported_version=_IVA_WALLET_ENVELOPE_VERSION,
            )
        for record in records:
            envelope = Envelope[IvaCompensationWalletObservation].model_validate_json(
                record.payload.decode(_UTF_8_ENCODING),
            )
            if envelope.classification is not _IVA_WALLET_CLASSIFICATION:
                raise ClassificationError(
                    f"IVA wallet observation {record.object_key!r} has classification {envelope.classification}; "
                    f"consumer expected {_IVA_WALLET_CLASSIFICATION}",
                )
            if not inner_envelope_version_is_current(envelope.schema_version, _IVA_WALLET_ENVELOPE_VERSION):
                raise EnvelopeVersionError(
                    f"IVA wallet observation {record.object_key!r} is at version {envelope.schema_version}; "
                    f"consumer supports up to {_IVA_WALLET_ENVELOPE_VERSION}",
                )
            _assert_payload_is_its_own_row(
                self._key_of_iva_wallet_observation(envelope.payload),
                record.object_key,
                "IVA wallet observation",
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
        return filed_declaracion_observation_object_key(modelo, ejercicio, period, expediente_id)

    def _key_of_observation(self, observation: FiledDeclaracionObservation) -> str:
        """Return the natural key a decrypted filed observation claims to be filed under."""
        return self._observation_key(
            observation.modelo,
            observation.ejercicio,
            observation.period,
            observation.expediente_id,
        )

    def _key_of_iva_wallet_observation(self, observation: IvaCompensationWalletObservation) -> str:
        """Return the natural key a decrypted wallet observation claims to be filed under."""
        return self._iva_wallet_observation_key(
            observation.taxpayer_nif,
            observation.target_year,
            observation.target_period,
            observation.captured_at.isoformat(),
        )

    def _crypto_scope(self):
        return nullcontext()

    def _iva_wallet_observation_key(
        self,
        taxpayer_nif: str,
        target_year: int,
        target_period: Period,
        captured_at: str,
    ) -> str:
        return iva_compensation_wallet_observation_object_key(
            taxpayer_nif,
            target_year,
            target_period,
            captured_at,
        )


def _assert_payload_is_the_requested_row(derived_key: str, requested_key: str, subject: str) -> None:
    """Refuse a decrypted payload whose own identity is not the row asked for.

    Both observation families derive their natural key from identity fields
    the payload itself carries, but nothing re-derived it after decryption:
    ``load_*`` validated only the envelope's class and version, so a valid
    payload re-encrypted under another row's key was returned as that row.
    Custody consumers would then associate filing evidence with the wrong
    declaration, or a wallet balance with the wrong period — with no error
    anywhere, because every layer beneath answered correctly about the row it
    was handed.

    Raises:
        SedeValidationError: When the payload belongs to a different row.
    """
    if derived_key != requested_key:
        raise SedeValidationError(
            f"{subject} does not belong to the requested row: "
            f"asked for {requested_key!r}, decrypted payload is filed under {derived_key!r}",
        )


def _assert_payload_is_its_own_row(derived_key: str, stored_key: bytes, subject: str) -> None:
    """Refuse an enumerated payload whose identity does not derive its stored row.

    The enumeration counterpart of :func:`_assert_payload_is_the_requested_row`.
    Listing has no requested key to compare against, so the comparison is made
    against the row's stored key digest — the same digest the write path
    produced from the natural key. Without it, a substituted row is carried
    into every consumer that enumerates instead of looking up, which is the
    wider of the two doors.

    Raises:
        SedeValidationError: When the payload does not derive its own row key.
    """
    if secure_object_key_digest(derived_key) != stored_key:
        raise SedeValidationError(
            f"{subject} does not derive the row it is stored in; decrypted payload is filed under {derived_key!r}",
        )


def filed_declaracion_observation_object_key(
    modelo: str,
    ejercicio: int,
    period: Period,
    expediente_id: str,
) -> str:
    """Return the secure-object natural key for a filed-declaration observation.

    The key is the hash grammar declared by
    :data:`adapters.persistence.storage.AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE`.
    """
    key = "\x1f".join(
        (
            _safe_segment(modelo),
            str(ejercicio),
            _safe_segment(period.registry_token),
            _safe_segment(expediente_id),
        ),
    )
    return sha256_hex(key.encode(_UTF_8_ENCODING))


def iva_compensation_wallet_observation_object_key(
    taxpayer_nif: str,
    target_year: int,
    target_period: Period,
    captured_at: str,
) -> str:
    """Return the secure-object natural key for an IVA-wallet observation.

    The key is the hash grammar declared by
    :data:`adapters.persistence.storage.AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE`.
    """
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


def _validate_observation_casilla_ids(observation: FiledDeclaracionObservation) -> None:
    """Reject filed observations whose casilla rows are not registry ids."""
    if not observation.casillas:
        return
    try:
        snapshot = resources().modelos.authority.snapshot(
            observation.modelo,
            filing_year=observation.ejercicio,
            period=observation.period.registry_token,
        )
    except RegistrySnapshotError as exc:
        raise SedeValidationError(
            "filed-declaration observation casilla ids cannot be validated because "
            f"registry has no snapshot for modelo {observation.modelo!r} "
            f"{observation.ejercicio} {observation.period.registry_token!r}",
        ) from exc
    invalid = undeclared_casilla_ids(snapshot.revision, (casilla.casilla_id for casilla in observation.casillas))
    if invalid:
        raise SedeValidationError(
            "filed-declaration observations must use canonical casilla.id values declared by "
            f"registry:{observation.modelo}:{snapshot.revision.id}; invalid casilla ids: {invalid!r}",
        )


def _format_storage_ref(digest: str) -> str:
    return f"{_STORAGE_REF_PREFIX}{digest}"


def _parse_storage_ref(storage_ref: str) -> str:
    if not storage_ref.startswith(_STORAGE_REF_PREFIX):
        raise SedeValidationError("filed-declaration artefact storage reference is not financial")
    return storage_ref.removeprefix(_STORAGE_REF_PREFIX)


__all__ = ["FiledDeclaracionObservationStore"]
