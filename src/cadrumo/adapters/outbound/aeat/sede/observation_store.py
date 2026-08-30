"""Persistence helpers for read-only filed-declaration observations.

Persists each filed-declaration observation as an
:class:`~adapters.persistence.storage.Envelope` record through
:class:`~adapters.persistence.storage.SecureObjectRepository`, keyed
by declaration identity so a prior filing can be retrieved without re-fetching
it from the sede. Each envelope is classified at
:class:`~adapters.persistence.storage.SensitivityClass` ``FINANCIAL`` and
encrypted under the authenticated bucket session's own key, resolved through
:func:`~adapters.persistence.storage.secure_object_repository_for_active_bucket`.
The store takes no key material and no provider: it holds a taxpayer's filed
declarations, so the session that unwrapped the profile's DEK is the only thing
that may open them.

Artefact bytes are stored under
:data:`adapters.persistence.storage.AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE`
directly through :class:`~adapters.persistence.storage.SecureObjectRepository`
(a raw, digest-keyed blob with no ``Envelope`` wrapper -- out of scope for the
two families below). The two Envelope-wrapped observation families --
:data:`adapters.persistence.storage.AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE`
and
:data:`adapters.persistence.storage.AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE` --
are each a :class:`~adapters.persistence.storage.SecureBoundRepository`
subclass (:class:`FiledDeclaracionObservationRepository`,
:class:`IvaCompensationWalletObservationRepository`): the natural-key
derivation, envelope classification/version gate, and row-identity check
that used to be hand-rolled here (~150 lines, and a row-identity check that
raised its own ``SedeValidationError`` instead of the canonical
``SecureObjectRowIdentityError``) now come from that shared base, with
``_translate_row_identity_error`` preserving this module's domain-specific
error type for the single-row ``load`` path. The base class has no
translation hook for its enumeration path (``iter_records``/``iter_ids``
raise ``SecureObjectRowIdentityError`` directly, unlike ``load``), so
:class:`FiledDeclaracionObservationStore`'s ``list_*`` methods catch and
translate it themselves rather than letting the untyped storage error leak
through this module's boundary.
"""

from __future__ import annotations

import re
from contextlib import nullcontext
from pathlib import Path
from typing import override

from .....core.period import Period
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.hashing import sha256_hex
from .....core.time import now
from .....domain.calculations.registry.authority import bundled_authority
from .....domain.calculations.registry.casilla_membership import undeclared_casilla_ids
from .....domain.calculations.registry.errors import RegistrySnapshotError
from ....persistence.storage import (
    AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE,
    AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE,
    AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE,
    SecureBoundRepository,
    SecureObjectRepository,
    SecureObjectRowIdentityError,
    secure_object_repository_for_active_bucket,
)
from .errors import ExpedienteNotFoundError, SedeValidationError
from .schema import FiledDeclaracionArtefact, FiledDeclaracionObservation, IvaCompensationWalletObservation

_SAFE_SEGMENT_RE = re.compile(r"[^0-9A-Za-z_.-]+")
_ARTEFACT_NAMESPACE = AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE.namespace
_ARTEFACT_CLASSIFICATION = AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE.sensitivity
_ARTEFACT_ENVELOPE_VERSION = AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE.schema_version
_OBSERVATION_NAMESPACE = AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE.namespace
_IVA_WALLET_OBSERVATION_NAMESPACE = AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE.namespace
_STORAGE_REF_PREFIX = "secure-object:financial:"


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


class FiledDeclaracionObservationRepository(SecureBoundRepository[FiledDeclaracionObservation]):
    """Envelope-bound repository for filed-declaration observations.

    Governed by
    :data:`adapters.persistence.storage.AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE`.
    The natural key is the SHA-256 grammar
    :func:`filed_declaracion_observation_object_key` computes from a
    declaration's identity fields; a row whose decrypted payload rebuilds a
    different key surfaces as :class:`~.errors.SedeValidationError` (the
    ``load`` path only -- see the module docstring for why enumeration is
    handled separately).
    """

    namespace = AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE.namespace
    sensitivity = AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE.sensitivity
    schema_version = AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE.schema_version
    payload_type = FiledDeclaracionObservation

    @override
    def extract_identifier(self, payload: FiledDeclaracionObservation) -> str:
        """Return the natural key ``payload`` claims to be filed under."""
        return filed_declaracion_observation_object_key(
            payload.modelo,
            payload.ejercicio,
            payload.period,
            payload.expediente_id,
        )

    @override
    def _translate_row_identity_error(self, error: SecureObjectRowIdentityError) -> Exception:
        """Preserve this module's domain error for a single-row identity mismatch."""
        return SedeValidationError(
            "filed-declaration observation does not belong to the requested row: "
            f"asked for {error.expected_identifier!r}, "
            f"decrypted payload is filed under {error.payload_identifier!r}",
        )


class IvaCompensationWalletObservationRepository(SecureBoundRepository[IvaCompensationWalletObservation]):
    """Envelope-bound repository for read-only IVA compensation-wallet observations.

    Governed by
    :data:`adapters.persistence.storage.AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE`.
    The natural key is the SHA-256 grammar
    :func:`iva_compensation_wallet_observation_object_key` computes from the
    wallet snapshot's identity fields.
    """

    namespace = AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE.namespace
    sensitivity = AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE.sensitivity
    schema_version = AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE.schema_version
    payload_type = IvaCompensationWalletObservation

    @override
    def extract_identifier(self, payload: IvaCompensationWalletObservation) -> str:
        """Return the natural key ``payload`` claims to be filed under."""
        return iva_compensation_wallet_observation_object_key(
            payload.taxpayer_nif,
            payload.target_year,
            payload.target_period,
            payload.captured_at.isoformat(),
        )

    @override
    def _translate_row_identity_error(self, error: SecureObjectRowIdentityError) -> Exception:
        """Preserve this module's domain error for a single-row identity mismatch."""
        return SedeValidationError(
            "IVA wallet observation does not belong to the requested row: "
            f"asked for {error.expected_identifier!r}, "
            f"decrypted payload is filed under {error.payload_identifier!r}",
        )


class FiledDeclaracionObservationStore:
    """Persist captured AEAT filed data through encrypted SQL namespaces.

    The store writes raw captured artefact bytes to
    :data:`adapters.persistence.storage.AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE`
    directly. :class:`FiledDeclaracionObservation` and
    :class:`IvaCompensationWalletObservation` persistence is delegated to
    :class:`FiledDeclaracionObservationRepository` and
    :class:`IvaCompensationWalletObservationRepository` respectively, both
    :class:`~adapters.persistence.storage.SecureBoundRepository` subclasses
    bound to this store's own secure-object backend.
    """

    def __init__(
        self,
        root: Path,
        *,
        objects: SecureObjectRepository | None = None,
    ) -> None:
        """Bind the storage root, and the object repository if one is injected."""
        self._root = Path(root)
        self._objects = objects
        self._observation_repository: FiledDeclaracionObservationRepository | None = None
        self._wallet_repository: IvaCompensationWalletObservationRepository | None = None

    @property
    def _repository(self) -> SecureObjectRepository:
        if self._objects is None:
            self._objects = secure_object_repository_for_active_bucket()
        return self._objects

    @property
    def _observations(self) -> FiledDeclaracionObservationRepository:
        if self._observation_repository is None:
            self._observation_repository = FiledDeclaracionObservationRepository(objects=self._repository)
        return self._observation_repository

    @property
    def _wallet_observations(self) -> IvaCompensationWalletObservationRepository:
        if self._wallet_repository is None:
            self._wallet_repository = IvaCompensationWalletObservationRepository(objects=self._repository)
        return self._wallet_repository

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
        with self._crypto_scope():
            self._observations.save(observation)
        return _logical_path(_OBSERVATION_NAMESPACE, self._observations.extract_identifier(observation))

    def load_observation(self, path: Path) -> FiledDeclaracionObservation:
        """Load and decrypt a :class:`FiledDeclaracionObservation` from the encrypted store.

        The encrypted row is read from
        :data:`adapters.persistence.storage.AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE`.
        """
        object_key = Path(path).name
        with self._crypto_scope():
            observation = self._observations.load(object_key)
        if observation is None:
            raise ExpedienteNotFoundError(f"filed-declaration observation not found: {object_key}")
        return observation

    def list_observations(self) -> tuple[FiledDeclaracionObservation, ...]:
        """Return :class:`FiledDeclaracionObservation` records from the active encrypted backend.

        Rows are scanned from
        :data:`adapters.persistence.storage.AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE`.
        """
        with self._crypto_scope():
            try:
                observations = list(self._observations.iter_records())
            except SecureObjectRowIdentityError as exc:
                raise SedeValidationError(
                    "filed-declaration observation does not derive the row it is stored in; "
                    f"decrypted payload is filed under {exc.expected_identifier!r}",
                ) from exc
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
        with self._crypto_scope():
            self._wallet_observations.save(observation)
        return _logical_path(
            _IVA_WALLET_OBSERVATION_NAMESPACE,
            self._wallet_observations.extract_identifier(observation),
        )

    def load_iva_wallet_observation(self, path: Path) -> IvaCompensationWalletObservation:
        """Load and decrypt an :class:`IvaCompensationWalletObservation` from ``path``.

        The encrypted row is read from
        :data:`adapters.persistence.storage.AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE`.
        """
        object_key = Path(path).name
        with self._crypto_scope():
            observation = self._wallet_observations.load(object_key)
        if observation is None:
            raise ExpedienteNotFoundError(f"IVA wallet observation not found: {object_key}")
        return observation

    def list_iva_wallet_observations(self) -> tuple[IvaCompensationWalletObservation, ...]:
        """Return :class:`IvaCompensationWalletObservation` records from the active encrypted backend.

        Rows are scanned from
        :data:`adapters.persistence.storage.AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE`.
        """
        with self._crypto_scope():
            try:
                observations = list(self._wallet_observations.iter_records())
            except SecureObjectRowIdentityError as exc:
                raise SedeValidationError(
                    "IVA wallet observation does not derive the row it is stored in; "
                    f"decrypted payload is filed under {exc.expected_identifier!r}",
                ) from exc
        return tuple(
            sorted(
                observations,
                key=lambda item: (item.target_year, item.target_period.registry_token, item.captured_at),
            ),
        )

    def _crypto_scope(self):
        return nullcontext()


def _logical_path(namespace: str, object_key: str) -> Path:
    return Path("db://secure_objects") / namespace / object_key


def _validate_observation_casilla_ids(observation: FiledDeclaracionObservation) -> None:
    """Reject filed observations whose casilla rows are not registry ids."""
    if not observation.casillas:
        return
    try:
        snapshot = bundled_authority().snapshot(
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


__all__ = [
    "FiledDeclaracionObservationRepository",
    "FiledDeclaracionObservationStore",
    "IvaCompensationWalletObservationRepository",
    "filed_declaracion_observation_object_key",
    "iva_compensation_wallet_observation_object_key",
]
