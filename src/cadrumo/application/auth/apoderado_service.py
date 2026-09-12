"""Apoderado application service.

Operator verbs:

``status``
    Read-only summary of the active apoderado configuration.
``configure``
    Set ``--represented-nif NIF --scope SCOPE`` (repeated).
``clear``
    Retire the apoderado configuration for the active bucket.
``check``
    Live verification of the stored apoderamiento against the AEAT
    sede. The live-read path is not wired, so this verb refuses with
    :class:`ApoderadoLiveCheckUnavailableError`; use ``status`` for the
    offline configuration read.

Configuration is persisted per-bucket through the application-owned
configuration repository capability. The repository implementation is responsible
for encryption and storage; the service never writes plaintext to disk. Live
mutation of AEAT-side apoderamiento state (registrar, ampliar, revocar, confirmar,
renunciar, presentar-en-representacion) is permanently refused at this boundary;
the service has no verb that would write to AEAT.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from ...core.config import Settings
from ...core.errors.hierarchy import CadrumoError
from ...core.identity.bucket import BucketId, canonical_bucket_id
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.clock import now
from ...domain.auth.apoderamientos.catalogue import ApoderamientosCatalogue, load_default_catalogue, parse_scope_tokens
from .apoderado_repository import ApoderadoConfigurationRepository, ApoderadoConfigurationRepositoryFactory
from .apoderado_text import ApoderadoNotes


class ApoderadoConfigurationNotSetError(CadrumoError):
    """Raised when status or check runs without a configured apoderado."""


class ApoderadoRepresentedNifInvalidError(CadrumoError):
    """Raised when ``configure`` receives an invalid represented-party tax id.

    Both the flag-driven and the paged-flow transports commit through
    :meth:`ApoderadoService.configure`, which validates the represented
    party's identifier through the canonical
    :func:`cadrumo.domain.calculations.registry.tax_id_runtime.validate_runtime_identity`
    authority. The raised
    error carries NO raw identifier in its context -- the value is
    identity-sensitive and must never leak into a diagnostic.
    """


class ApoderadoLiveCheckUnavailableError(CadrumoError):
    """Raised when the live-read path is not yet wired or AEAT contact fails."""


class ApoderadoConfigurationIdentityError(CadrumoError):
    """Raised when a stored configuration does not belong to the key it sits under.

    The persisted record key IS the bucket binding for this record: nothing else
    in the row asserts ownership. A configuration for bucket B placed under
    bucket A's key would otherwise be returned by ``status(bucket_id=A)`` and
    projected with B's represented tax identifier -- an identity-bearing
    cross-bucket leak that the key-only boundary cannot otherwise detect.

    The error carries no represented identifier: that value is
    identity-sensitive and must never reach a diagnostic.
    """


RepresentedNif = Annotated[str, StringConstraints(min_length=1, max_length=16)]
"""The tax identifier of the party an apoderamiento represents.

The LENGTH bound only. Whether the value is a well-formed Spanish tax
identifier is checked by the apoderamiento flow, through
:func:`cadrumo.domain.calculations.registry.tax_id_runtime.validate_runtime_identity`,
and is deliberately not
attached here: the two identity validators in ``core.identity`` currently
disagree about one CIF leader class, so typing this field with the canonical
:data:`~cadrumo.domain.calculations.registry.tax_id_format.SubjectTaxId` alias would silently move it from
the flow's policy to the opposite one. The length is uncontested and was
written out at four sites; it is declared once here until that ruling lands.
"""


class ApoderadoConfiguration(BaseModel):
    """Persisted apoderado configuration for one bucket."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    represented_nif: RepresentedNif
    granted_scopes: tuple[str, ...] = Field(default_factory=tuple)
    catalogue_version: str = Field(min_length=1)
    configured_at: datetime
    notes: ApoderadoNotes = ""


class ApoderadoStatus(BaseModel):
    """Read-only status surface returned by ``apoderado status``."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    configured: bool
    represented_nif: str | None = Field(default=None)
    granted_scopes: tuple[str, ...] = Field(default_factory=tuple)
    catalogue_version: str | None = Field(default=None)
    configured_at: datetime | None = Field(default=None)


class ApoderadoService:
    """Local apoderado configuration management.

    Live AEAT mutation is permanently refused at this boundary. ``check``
    performs read-only verification only; the actual remote contact is
    a sealed extension point.
    """

    def __init__(
        self,
        *,
        repository_factory: ApoderadoConfigurationRepositoryFactory,
        settings: Settings | None = None,
        catalogue: ApoderamientosCatalogue | None = None,
    ) -> None:
        """Bind the repository factory, settings, and authoritative catalogue."""
        # `load_settings()` honours `override_settings`; bare `Settings()`
        # bypasses the context-var.
        from ...core.config import load_settings as _load_settings

        self._settings = settings or _load_settings()
        self._catalogue = catalogue or load_default_catalogue()
        self._repository_factory = repository_factory
        # Build repositories lazily per requested bucket so catalogue-only
        # verbs never touch storage and a long-lived service cannot route
        # bucket B's apoderado NIF into bucket A's database.
        self._repository_instances: dict[str, ApoderadoConfigurationRepository] = {}

    def _repository_for(self, bucket_id: str) -> ApoderadoConfigurationRepository:
        canonical_id = canonical_bucket_id(bucket_id)
        repository = self._repository_instances.get(canonical_id)
        if repository is None:
            repository = self._repository_factory(bucket_id=canonical_id, settings=self._settings)
            self._repository_instances[canonical_id] = repository
        return repository

    @property
    def catalogue(self) -> ApoderamientosCatalogue:
        """Return the AEAT apoderamiento scope :class:`ApoderamientosCatalogue` in use by this service."""
        return self._catalogue

    def status(self, *, bucket_id: str) -> ApoderadoStatus:
        """Return the current :class:`ApoderadoStatus` for ``bucket_id``.

        Reads the persisted :class:`ApoderadoConfiguration` (if any) and
        projects it into a read-only status record. Does not contact AEAT.

        Args:
            bucket_id: The profile bucket's UUIDv4 identifier.
        """
        normalised_bucket_id = canonical_bucket_id(bucket_id)
        config = self._repository_for(normalised_bucket_id).load()
        if config is None:
            return ApoderadoStatus(bucket_id=normalised_bucket_id, configured=False)
        return ApoderadoStatus(
            bucket_id=normalised_bucket_id,
            configured=True,
            represented_nif=config.represented_nif,
            granted_scopes=config.granted_scopes,
            catalogue_version=config.catalogue_version,
            configured_at=config.configured_at,
        )

    def configure(
        self,
        *,
        bucket_id: str,
        represented_nif: str,
        scope_tokens: tuple[str, ...],
        notes: str = "",
    ) -> ApoderadoConfiguration:
        """Persist apoderado config and return the resulting :class:`ApoderadoConfiguration`.

        Validates the represented party's tax identifier through the
        authority-aware
        :func:`cadrumo.domain.calculations.registry.tax_id_runtime.validate_runtime_identity`
        (the single validation law both the flag path and the paged flow
        commit through), then validates and dedups scopes against the
        catalogue.

        :raises ApoderadoRepresentedNifInvalidError: When ``represented_nif``
            is not a valid NIF, NIE, or CIF.
        """
        from ...core.identity.documents import IdentityError
        from ...domain.calculations.registry.tax_id_runtime import validate_runtime_identity

        try:
            validate_runtime_identity(represented_nif)
        except IdentityError as exc:
            raise ApoderadoRepresentedNifInvalidError(
                translated_message="errors.refused.refused_apoderado_invalid_represented_nif",
            ) from exc
        granted = parse_scope_tokens(scope_tokens, self._catalogue)
        config = ApoderadoConfiguration(
            bucket_id=canonical_bucket_id(bucket_id),
            represented_nif=represented_nif,
            granted_scopes=granted,
            catalogue_version=self._catalogue.catalogue_version,
            configured_at=now(),
            notes=notes,
        )
        self._repository_for(config.bucket_id).save(config)
        return config

    def clear(self, *, bucket_id: str) -> bool:
        """Retire the configuration. Returns True iff a record was removed."""
        normalised_bucket_id = canonical_bucket_id(bucket_id)
        return self._repository_for(normalised_bucket_id).delete()

    def check(self, *, bucket_id: str) -> ApoderadoStatus:
        """Read-only live verification (sealed pending live-read wiring).

        ``check`` is the live-verification verb: it would contact the
        AEAT sede to confirm the stored apoderamiento is still granted.
        That live-read path is not wired (live AEAT reads are refused at
        this boundary per the safety gate), so ``check`` raises
        :class:`ApoderadoLiveCheckUnavailableError` unconditionally rather
        than silently re-reading stored configuration and presenting it as
        a live result. Use ``status`` for the offline configuration read.

        Returns the live :class:`ApoderadoStatus` once the live-read path is
        wired; until then it raises.

        :raises ApoderadoLiveCheckUnavailableError: always, until the
            live-read path is wired.
        """
        raise ApoderadoLiveCheckUnavailableError


__all__ = [
    "ApoderadoConfiguration",
    "ApoderadoConfigurationIdentityError",
    "ApoderadoConfigurationNotSetError",
    "ApoderadoLiveCheckUnavailableError",
    "ApoderadoRepresentedNifInvalidError",
    "ApoderadoService",
    "ApoderadoStatus",
]
