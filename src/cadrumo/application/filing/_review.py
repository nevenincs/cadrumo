"""Draft approval persistence and stale-detection helpers.

Provides the :func:`approve_draft` / :func:`unapprove_draft` /
:func:`refresh_review_status` lifecycle on top of
:class:`domain.filing.ModeloDraft` and
:class:`domain.submission.ModeloDraftStatus`, plus the deterministic
:class:`domain.filing.ModeloApprovalBasis` fingerprint pipeline that lets
:func:`approval_stale_reasons` detect when a
:attr:`~domain.submission.ModeloDraftStatus.APROBADO` draft has been
invalidated by upstream changes.

The :func:`compute_current_approval_basis` helper accepts optional
:class:`domain.transactions.TransactionCatalogue` and category-profile
overrides. When the catalogue override is omitted, it loads the
:class:`~domain.transactions.TransactionCatalogue` from the encrypted
secure-object backend through
:class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository`.

See Also:
    :func:`application.filing.build_runtime_schema_provider`
        Builds the registry-backed schema provider whose casilla and formula
        surface participates in the approval basis.
    :func:`application.review.drafts_pending`
        Emits stale filing approvals as high-severity review queue items.
    :class:`domain.filing.ModeloApprovalBasis`
        Persisted digest bundle compared during stale detection.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Final, Protocol

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...core.hashing import content_hash_hex
from ...core.i18n import tr
from ...core.logging import get_logger
from ...core.time import now
from ...domain.calculations.registry.bindings import RegistryModeloObservation
from ...domain.categories import CategoryProfile, SpendingCategory, resolve_category_profiles
from ...domain.filing import (
    CasillaSchemaProvider,
    ModeloApprovalBasis,
    ModeloDraft,
    ModeloDraftError,
    ModeloValidator,
    derive_validation_status,
)
from ...domain.identifiers import canonical_decimal_string
from ...domain.invoices import InvoiceCatalogue
from ...domain.submission import ModeloDraftStatus
from ...domain.transactions import Transaction, TransactionCatalogue
from ...domain.user_profile.errors import ProfileNotFoundError
from ..user_profile.profile_record_repository import ProfileRecordRepository
from ..user_profile.projections import record_to_path_values


class _StoredPriorObservation(Protocol):
    """Structural shape of one persisted prior-filing observation payload.

    Matches the observation repository's stored envelope structurally so the
    fingerprint helper can project it without importing that repository's private
    envelope type. ``captured_at`` is deliberately absent from this shape — it is
    the volatile field the digest must ignore.
    """

    @property
    def observation(self) -> RegistryModeloObservation: ...
    @property
    def source_kind(self) -> str: ...
    @property
    def member_nif(self) -> str | None: ...
    @property
    def stamped_revision_id(self) -> str: ...


_logger = get_logger(__name__)
_REVIEW_STATUSES = frozenset(
    {
        ModeloDraftStatus.APROBADO,
        ModeloDraftStatus.APROBACION_CADUCADA,
    },
)
_DOWNSTREAM_STATUSES = frozenset(
    {
        ModeloDraftStatus.PRESENTADA,
        ModeloDraftStatus.ACEPTADA,
        ModeloDraftStatus.RECHAZADA,
        ModeloDraftStatus.ENMENDADO,
        ModeloDraftStatus.ANULADO,
    },
)


class ModeloApprovalStaleReason(StrEnum):
    """Stable reason codes surfaced when a draft approval becomes stale.

    Attributes:
        APPROVAL_BASIS_VERSION_CHANGED: The
            :class:`domain.filing.ModeloApprovalBasis` schema
            version has been bumped since approval.
        DRAFT_PAYLOAD_CHANGED: The draft's payload fingerprint
            (``draft_id``) no longer matches the stored basis.
        DRAFT_REVIEW_CHANGED: The draft's validation findings or
            machine status changed since approval.
        TRANSACTION_CATALOGUE_CHANGED: Upstream classified
            transactions have been updated since approval.
        INVOICE_CATALOGUE_CHANGED: Upstream issued/received invoices
            (a calculation source resolved through the source mesh)
            have been updated since approval.
        PRIOR_FILING_OBSERVATIONS_CHANGED: Prior filed observations in the
            bucket (the previous_filing carry and relation fold-in source)
            have been updated since approval.
        PROFILE_ACTIVITY_CHANGED: The taxpayer profile facts that scope
            relation resolution (activity-start date, m111 no-retenciones
            attestations, declared income categories) have changed since
            approval.
        CATEGORY_PROFILES_CHANGED: The fiscal category profile catalog
            has been edited since approval.
        SCHEMA_FORMULA_CHANGED: The registry-backed casilla schema or formula set
            has changed since approval.
        REVIEW_CHECKSUM_MISMATCH: The stored ``review_checksum`` is not the
            checksum of the stored basis. Unlike every other reason here, this
            does not mean an upstream source moved -- it means the persisted
            approval metadata is internally inconsistent, so the aggregate
            claim over the basis is false and the approval cannot be trusted
            even when every basis field still matches.
    """

    APPROVAL_BASIS_VERSION_CHANGED = "BASE_APROBACION_VERSION_CAMBIADA"
    DRAFT_PAYLOAD_CHANGED = "BORRADOR_CONTENIDO_CAMBIADO"
    DRAFT_REVIEW_CHANGED = "BORRADOR_REVISION_CAMBIADA"
    TRANSACTION_CATALOGUE_CHANGED = "CATALOGO_TRANSACCIONES_CAMBIADO"
    INVOICE_CATALOGUE_CHANGED = "CATALOGO_FACTURAS_CAMBIADO"
    PRIOR_FILING_OBSERVATIONS_CHANGED = "OBSERVACIONES_DECLARACIONES_ANTERIORES_CAMBIADAS"
    PROFILE_ACTIVITY_CHANGED = "ACTIVIDAD_PERFIL_CAMBIADA"
    CATEGORY_PROFILES_CHANGED = "PERFILES_CATEGORIA_CAMBIADOS"
    SCHEMA_FORMULA_CHANGED = "ESQUEMA_FORMULA_CAMBIADO"
    REVIEW_CHECKSUM_MISMATCH = "SUMA_VERIFICACION_REVISION_NO_COINCIDE"


def compute_current_approval_basis(
    draft: ModeloDraft,
    *,
    bucket_id: str,
    schema_provider: CasillaSchemaProvider,
    transaction_catalogue: TransactionCatalogue | None = None,
    invoice_catalogue: InvoiceCatalogue | None = None,
    prior_filing_observations_fingerprint: str | None = None,
    profile_activity_fingerprint: str | None = None,
    category_profiles: Mapping[SpendingCategory, CategoryProfile] | None = None,
) -> ModeloApprovalBasis:
    """Return the :class:`ModeloApprovalBasis` digests for current upstream state.

    The basis hashes the draft identity and validation surface, the supplied or
    persisted :class:`TransactionCatalogue`, the supplied or persisted
    :class:`~domain.invoices.InvoiceCatalogue` (a calculation source
    resolved through the source mesh), the bucket's prior filed observations (the
    ``previous_filing`` carry and relation fold-in source), the bucket's taxpayer
    profile facts that scope relation resolution, the supplied or bundled
    :class:`~domain.categories.CategoryProfile` mapping, and the active
    registry schema/formula surface exposed by ``schema_provider``.

    The invoice-catalogue, prior-filing-observations, and profile-activity digests
    make an ``APROBADO`` draft stale when its upstream invoices, prior filed
    values, or relation-scoping profile facts change, closing the gap left by
    fingerprinting only the ledger transaction catalogue. Like the transaction
    catalogue they are self-loaded from ``bucket_id`` so stale detection is
    reproducible at refresh time without running the source mesh in the review
    layer.

    Args:
        draft: The :class:`domain.filing.ModeloDraft` whose basis
            is being computed.
        bucket_id: Stable bucket identifier; used to load the persisted
            transaction and invoice catalogues and prior observations when no
            override is supplied.
        schema_provider: The active
            :class:`domain.filing.CasillaSchemaProvider`.
        transaction_catalogue: Optional :class:`TransactionCatalogue` override.
            When ``None``, the catalogue is loaded from the encrypted
            :class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository`.
        invoice_catalogue: Optional :class:`~domain.invoices.InvoiceCatalogue`
            override. When ``None``, the catalogue is loaded from the encrypted
            :class:`~adapters.persistence.profile.invoices.InvoiceCatalogueRepository`.
        prior_filing_observations_fingerprint: Optional precomputed prior-filing
            digest. When ``None``, the digest is self-loaded from the bucket's
            :class:`~application.calculations.CalculationObservationRepository`.
            A precomputed override (typically
            :func:`empty_prior_filing_observations_fingerprint`) lets a caller
            skip the bucket self-load for a deterministic basis without exposing
            the private stored-observation envelope type or routing to a
            non-active bucket.
        profile_activity_fingerprint: Optional precomputed taxpayer-profile
            digest. When ``None``, the digest is self-loaded from the bucket's
            :class:`~application.user_profile.CommittedProfileRepository`. A precomputed
            override (typically :func:`empty_profile_activity_fingerprint`) lets a
            caller skip the bucket self-load for a deterministic basis.
        category_profiles: Optional override of the active category
            profile map. Defaults to the bundled 2025 registry.

    Returns:
        A freshly computed :class:`ModeloApprovalBasis`.
    """
    catalogue = transaction_catalogue if transaction_catalogue is not None else _load_transaction_catalogue(bucket_id)
    invoices = invoice_catalogue if invoice_catalogue is not None else _load_invoice_catalogue(bucket_id)
    prior_observations_fingerprint = (
        prior_filing_observations_fingerprint
        if prior_filing_observations_fingerprint is not None
        else _load_prior_filing_observations_fingerprint(bucket_id)
    )
    profile_fingerprint = (
        profile_activity_fingerprint
        if profile_activity_fingerprint is not None
        else _load_profile_activity_fingerprint(bucket_id)
    )
    profiles = category_profiles if category_profiles is not None else resolve_category_profiles(2025)
    return ModeloApprovalBasis(
        draft_payload_fingerprint=draft.draft_id,
        draft_review_fingerprint=_draft_review_fingerprint(draft),
        transaction_catalogue_fingerprint=_transaction_catalogue_fingerprint(catalogue),
        invoice_catalogue_fingerprint=_invoice_catalogue_fingerprint(invoices),
        prior_filing_observations_fingerprint=prior_observations_fingerprint,
        profile_activity_fingerprint=profile_fingerprint,
        category_profiles_fingerprint=_category_profiles_fingerprint(profiles),
        schema_formula_fingerprint=_schema_formula_fingerprint(
            draft,
            schema_provider=schema_provider,
        ),
    )


def compute_review_checksum(approval_basis: ModeloApprovalBasis) -> str:
    """Return the canonical SHA-256 hex checksum for ``approval_basis``.

    Args:
        approval_basis: The basis to hash.

    Returns:
        Lowercase hex SHA-256 of the basis's canonical JSON dump.
    """
    return content_hash_hex(approval_basis.model_dump(mode="json"))


#: Every approval-basis axis, paired with the stale reason a change to it
#: raises, in the order the reasons are reported. Declared as data rather than a
#: comparison chain so the correspondence is readable in one place, and reached
#: through an accessor rather than a field-name string so that renaming a basis
#: field breaks the type check instead of silently comparing nothing.
#:
#: A basis field with no row here stops invalidating approvals silently, which is
#: the failure mode to watch when the basis gains an axis: enrol it here in the
#: same change that declares it.
_APPROVAL_BASIS_STALE_REASONS: Final[
    tuple[tuple[Callable[[ModeloApprovalBasis], object], ModeloApprovalStaleReason], ...]
] = (
    (lambda basis: basis.version, ModeloApprovalStaleReason.APPROVAL_BASIS_VERSION_CHANGED),
    (lambda basis: basis.draft_payload_fingerprint, ModeloApprovalStaleReason.DRAFT_PAYLOAD_CHANGED),
    (lambda basis: basis.draft_review_fingerprint, ModeloApprovalStaleReason.DRAFT_REVIEW_CHANGED),
    (
        lambda basis: basis.transaction_catalogue_fingerprint,
        ModeloApprovalStaleReason.TRANSACTION_CATALOGUE_CHANGED,
    ),
    (lambda basis: basis.invoice_catalogue_fingerprint, ModeloApprovalStaleReason.INVOICE_CATALOGUE_CHANGED),
    (
        lambda basis: basis.prior_filing_observations_fingerprint,
        ModeloApprovalStaleReason.PRIOR_FILING_OBSERVATIONS_CHANGED,
    ),
    (lambda basis: basis.profile_activity_fingerprint, ModeloApprovalStaleReason.PROFILE_ACTIVITY_CHANGED),
    (lambda basis: basis.category_profiles_fingerprint, ModeloApprovalStaleReason.CATEGORY_PROFILES_CHANGED),
    (lambda basis: basis.schema_formula_fingerprint, ModeloApprovalStaleReason.SCHEMA_FORMULA_CHANGED),
)


def approval_stale_reasons(
    draft: ModeloDraft,
    *,
    bucket_id: str,
    schema_provider: CasillaSchemaProvider,
    transaction_catalogue: TransactionCatalogue | None = None,
    invoice_catalogue: InvoiceCatalogue | None = None,
    prior_filing_observations_fingerprint: str | None = None,
    profile_activity_fingerprint: str | None = None,
    category_profiles: Mapping[SpendingCategory, CategoryProfile] | None = None,
) -> tuple[ModeloApprovalStaleReason, ...]:
    """Return the ordered stale reasons for ``draft``.

    The return value is empty when the draft has no approval metadata
    or when its stored approval basis still matches the freshly
    recomputed basis.

    Args:
        draft: The :class:`domain.filing.ModeloDraft` to inspect.
        bucket_id: Stable bucket identifier; forwarded to
            :func:`compute_current_approval_basis`.
        schema_provider: The active
            :class:`domain.filing.CasillaSchemaProvider`.
        transaction_catalogue: Optional :class:`TransactionCatalogue` override.
        invoice_catalogue: Optional :class:`~domain.invoices.InvoiceCatalogue`
            override; forwarded to :func:`compute_current_approval_basis`.
        prior_filing_observations_fingerprint: Optional precomputed prior-filing
            digest override; forwarded to :func:`compute_current_approval_basis`.
        profile_activity_fingerprint: Optional precomputed taxpayer-profile
            digest override; forwarded to :func:`compute_current_approval_basis`.
        category_profiles: Optional category profile map override.

    Returns:
        Tuple of :class:`ModeloApprovalStaleReason` values in
        evaluation order; empty when the basis is fresh.
    """
    if draft.approval_basis is None:
        return ()

    stored_basis = draft.approval_basis
    # The checksum is an aggregate claim OVER the basis, so it is verified
    # against the basis itself before any field-by-field comparison. Checking
    # only that it is present (which is all refresh_review_status did) let a
    # persisted draft keep APROBADO with a replaced checksum while every basis
    # field still matched -- the tamper survived the reload unchallenged.
    if draft.review_checksum is not None and draft.review_checksum != compute_review_checksum(stored_basis):
        return (ModeloApprovalStaleReason.REVIEW_CHECKSUM_MISMATCH,)

    current_basis = compute_current_approval_basis(
        draft,
        bucket_id=bucket_id,
        schema_provider=schema_provider,
        transaction_catalogue=transaction_catalogue,
        invoice_catalogue=invoice_catalogue,
        prior_filing_observations_fingerprint=prior_filing_observations_fingerprint,
        profile_activity_fingerprint=profile_activity_fingerprint,
        category_profiles=category_profiles,
    )
    return tuple(reason for axis, reason in _APPROVAL_BASIS_STALE_REASONS if axis(stored_basis) != axis(current_basis))


def approve_draft(
    draft: ModeloDraft,
    *,
    bucket_id: str,
    approved_by: str,
    schema_provider: CasillaSchemaProvider,
    transaction_catalogue: TransactionCatalogue | None = None,
    invoice_catalogue: InvoiceCatalogue | None = None,
    prior_filing_observations_fingerprint: str | None = None,
    profile_activity_fingerprint: str | None = None,
    category_profiles: Mapping[SpendingCategory, CategoryProfile] | None = None,
    approved_at: datetime | None = None,
) -> ModeloDraft:
    """Stamp approval metadata on ``draft`` and promote it to ``APROBADO``.

    Args:
        draft: The :class:`ModeloDraft` to approve. Must be
            :attr:`ModeloDraftStatus.LISTO_PARA_PRESENTAR`. The optional
            ``transaction_catalogue`` is a :class:`TransactionCatalogue`
            consulted when computing the approval basis fingerprint; when
            ``None`` it is loaded from the repository.
        bucket_id: Stable bucket identifier; forwarded to
            :func:`compute_current_approval_basis`.
        approved_by: Operator identifier; rejected when blank after
            stripping.
        schema_provider: The active
            :class:`domain.filing.CasillaSchemaProvider`.
        transaction_catalogue: Optional catalogue override.
        invoice_catalogue: Optional :class:`~domain.invoices.InvoiceCatalogue`
            override; forwarded to :func:`compute_current_approval_basis`.
        prior_filing_observations_fingerprint: Optional precomputed prior-filing
            digest override; forwarded to :func:`compute_current_approval_basis`.
        profile_activity_fingerprint: Optional precomputed taxpayer-profile
            digest override; forwarded to :func:`compute_current_approval_basis`.
        category_profiles: Optional category profile map override.
        approved_at: Optional timestamp; defaults to the canonical clock helper.

    Returns:
        A new :class:`ModeloDraft` with approval metadata populated.

    Raises:
        ModeloDraftError: When ``approved_by`` is blank or the draft is
            not in :attr:`ModeloDraftStatus.LISTO_PARA_PRESENTAR`.
    """
    normalized_approver = approved_by.strip()
    if not normalized_approver:
        raise ModeloDraftError(
            translated_message="application.filing.review.errors.approved_by_blank",
        )

    if derive_validation_status(draft.findings) is not ModeloDraftStatus.LISTO_PARA_PRESENTAR:
        raise ModeloDraftError(
            translated_message="application.filing.review.errors.draft_not_ready",
        )
    _require_registry_review_alignment(draft, schema_provider=schema_provider)

    timestamp = approved_at or now()
    approval_basis = compute_current_approval_basis(
        draft,
        bucket_id=bucket_id,
        schema_provider=schema_provider,
        transaction_catalogue=transaction_catalogue,
        invoice_catalogue=invoice_catalogue,
        prior_filing_observations_fingerprint=prior_filing_observations_fingerprint,
        profile_activity_fingerprint=profile_activity_fingerprint,
        category_profiles=category_profiles,
    )
    updated = draft.model_copy(
        update={
            "status": ModeloDraftStatus.APROBADO,
            "approved_at": timestamp,
            "approved_by": normalized_approver,
            "approval_basis": approval_basis,
            "review_checksum": compute_review_checksum(approval_basis),
            "updated_at": timestamp,
        },
    )
    _logger.info(
        "draft approved draft_id=%s modelo=%s period=%s approved_by=%s",
        draft.draft_id,
        draft.modelo,
        draft.period,
        normalized_approver,
    )
    return updated


def unapprove_draft(
    draft: ModeloDraft,
    *,
    unapproved_at: datetime | None = None,
) -> ModeloDraft:
    """Remove approval metadata and restore the machine validation status.

    Args:
        draft: The draft to revert.
        unapproved_at: Optional timestamp; defaults to
            the canonical clock helper.

    Returns:
        A new :class:`ModeloDraft` with approval metadata cleared and
        ``status`` set to the validation status derived from
        :attr:`ModeloDraft.findings`.
    """
    timestamp = unapproved_at or now()
    updated = draft.model_copy(
        update={
            "status": derive_validation_status(draft.findings),
            "approved_at": None,
            "approved_by": None,
            "approval_basis": None,
            "review_checksum": None,
            "updated_at": timestamp,
        },
    )
    _logger.info("draft unapproved draft_id=%s modelo=%s period=%s", draft.draft_id, draft.modelo, draft.period)
    return updated


def refresh_review_status(
    draft: ModeloDraft,
    *,
    bucket_id: str,
    schema_provider: CasillaSchemaProvider,
    transaction_catalogue: TransactionCatalogue | None = None,
    invoice_catalogue: InvoiceCatalogue | None = None,
    prior_filing_observations_fingerprint: str | None = None,
    profile_activity_fingerprint: str | None = None,
    category_profiles: Mapping[SpendingCategory, CategoryProfile] | None = None,
    refreshed_at: datetime | None = None,
) -> ModeloDraft:
    """Return ``draft`` with its approval status synchronised to current state.

    Downstream-status drafts (submitted / acknowledged / rejected /
    amended / cancelled) get any leftover approval metadata cleared
    so historical state cannot pretend to be current. ``APROBADO`` drafts
    transition to :attr:`ModeloDraftStatus.APROBACION_CADUCADA` when
    :func:`approval_stale_reasons` returns a non-empty tuple.

    Args:
        draft: The draft to refresh.
        bucket_id: Stable bucket identifier; forwarded to
            :func:`approval_stale_reasons`.
        schema_provider: The active
            :class:`domain.filing.CasillaSchemaProvider`.
        transaction_catalogue: Optional :class:`TransactionCatalogue` override used
            when computing the approval basis fingerprint.
        invoice_catalogue: Optional :class:`~domain.invoices.InvoiceCatalogue`
            override; forwarded to :func:`approval_stale_reasons`.
        prior_filing_observations_fingerprint: Optional precomputed prior-filing
            digest override; forwarded to :func:`approval_stale_reasons`.
        profile_activity_fingerprint: Optional precomputed taxpayer-profile
            digest override; forwarded to :func:`approval_stale_reasons`.
        category_profiles: Optional category profile map override.
        refreshed_at: Optional timestamp; defaults to
            the canonical clock helper.

    Returns:
        Either ``draft`` unchanged (when no transition was needed) or a
        new :class:`ModeloDraft` with the appropriate status update.
    """
    timestamp = refreshed_at or now()
    has_review_metadata = _has_review_metadata(draft)
    if draft.status in _DOWNSTREAM_STATUSES:
        cleared = _review_metadata_reset()
        if any(getattr(draft, key) != value for key, value in cleared.items()):
            cleared["updated_at"] = timestamp
            _logger.debug(
                "refresh: cleared stale approval metadata for downstream draft draft_id=%s status=%s",
                draft.draft_id,
                draft.status.value,
            )
            return draft.model_copy(update=cleared)
        return draft
    if draft.status not in _REVIEW_STATUSES and not has_review_metadata:
        return draft

    if (
        draft.approval_basis is None
        or draft.approved_at is None
        or draft.approved_by is None
        or draft.review_checksum is None
    ):
        incomplete_reset = _review_metadata_reset()
        incomplete_reset["status"] = derive_validation_status(draft.findings)
        if any(getattr(draft, key) != value for key, value in incomplete_reset.items()):
            incomplete_reset["updated_at"] = timestamp
            _logger.warning(
                "refresh: incomplete approval metadata cleared draft_id=%s modelo=%s period=%s",
                draft.draft_id,
                draft.modelo,
                draft.period,
            )
            return draft.model_copy(update=incomplete_reset)
        return draft

    reasons = approval_stale_reasons(
        draft,
        bucket_id=bucket_id,
        schema_provider=schema_provider,
        transaction_catalogue=transaction_catalogue,
        invoice_catalogue=invoice_catalogue,
        prior_filing_observations_fingerprint=prior_filing_observations_fingerprint,
        profile_activity_fingerprint=profile_activity_fingerprint,
        category_profiles=category_profiles,
    )
    next_status = ModeloDraftStatus.APROBACION_CADUCADA if reasons else ModeloDraftStatus.APROBADO
    if draft.status is next_status:
        _logger.debug(
            "refresh: no transition needed draft_id=%s status=%s",
            draft.draft_id,
            draft.status.value,
        )
        return draft
    if next_status is ModeloDraftStatus.APROBACION_CADUCADA:
        _logger.warning(
            "draft approval marked stale draft_id=%s modelo=%s period=%s reasons=%s",
            draft.draft_id,
            draft.modelo,
            draft.period,
            [r.value for r in reasons],
        )
    return draft.model_copy(
        update={
            "status": next_status,
            "updated_at": timestamp,
        },
    )


def describe_stale_reason(reason: ModeloApprovalStaleReason) -> str:
    """Return a short localized explanation for ``reason``.

    Args:
        reason: The :class:`ModeloApprovalStaleReason` to describe.

    Returns:
        A localized phrase suitable for inline UI display.
    """
    match reason:
        case ModeloApprovalStaleReason.REVIEW_CHECKSUM_MISMATCH:
            return tr("application.filing.review.stale_reasons.review_checksum_mismatch")
        case ModeloApprovalStaleReason.APPROVAL_BASIS_VERSION_CHANGED:
            return tr("application.filing.review.stale_reasons.approval_basis_version_changed")
        case ModeloApprovalStaleReason.DRAFT_PAYLOAD_CHANGED:
            return tr("application.filing.review.stale_reasons.draft_payload_changed")
        case ModeloApprovalStaleReason.DRAFT_REVIEW_CHANGED:
            return tr("application.filing.review.stale_reasons.draft_review_changed")
        case ModeloApprovalStaleReason.TRANSACTION_CATALOGUE_CHANGED:
            return tr("application.filing.review.stale_reasons.transaction_catalogue_changed")
        case ModeloApprovalStaleReason.INVOICE_CATALOGUE_CHANGED:
            return tr("application.filing.review.stale_reasons.invoice_catalogue_changed")
        case ModeloApprovalStaleReason.PRIOR_FILING_OBSERVATIONS_CHANGED:
            return tr("application.filing.review.stale_reasons.prior_filing_observations_changed")
        case ModeloApprovalStaleReason.PROFILE_ACTIVITY_CHANGED:
            return tr("application.filing.review.stale_reasons.profile_activity_changed")
        case ModeloApprovalStaleReason.CATEGORY_PROFILES_CHANGED:
            return tr("application.filing.review.stale_reasons.category_profiles_changed")
        case ModeloApprovalStaleReason.SCHEMA_FORMULA_CHANGED:
            return tr("application.filing.review.stale_reasons.schema_formula_changed")
    return tr("application.filing.review.stale_reasons.unknown", reason=reason.value.lower().replace("_", " "))


def _review_metadata_reset() -> dict[str, object]:
    # Legitimate internal boundary: returns a partial-update dict consumed by
    # ModeloDraft.model_copy(update=...) and mutated by callers before use.
    # dict[str, object] is required here; Mapping would prevent the mutation.
    return {
        "approved_at": None,
        "approved_by": None,
        "approval_basis": None,
        "review_checksum": None,
    }


def _has_review_metadata(draft: ModeloDraft) -> bool:
    return any(
        value is not None
        for value in (
            draft.approved_at,
            draft.approved_by,
            draft.approval_basis,
            draft.review_checksum,
        )
    )


def _require_registry_review_alignment(
    draft: ModeloDraft,
    *,
    schema_provider: CasillaSchemaProvider,
) -> None:
    findings = ModeloValidator(schema_provider=schema_provider).validate(draft)
    if derive_validation_status(findings) is ModeloDraftStatus.LISTO_PARA_PRESENTAR:
        return
    codes = tuple(finding.code for finding in findings)
    raise ModeloDraftError(
        translated_message="application.filing.review.errors.registry_review_mismatch",
        context={
            "modelo": draft.modelo,
            "finding_count": len(codes),
            "codes": codes,
        },
    )


def _load_transaction_catalogue(bucket_id: str) -> TransactionCatalogue:
    """Load the transaction catalogue from the secure backend."""
    from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository

    return TransactionCatalogueRepository(bucket_id=bucket_id).load()


def _load_invoice_catalogue(bucket_id: str) -> InvoiceCatalogue:
    """Load the bucket's invoice catalogue from the secure backend."""
    return InvoiceCatalogueRepository(bucket_id=bucket_id).load()


def _load_prior_filing_observations_fingerprint(bucket_id: str) -> str:
    """Digest the bucket's stored prior-filing observations from the secure backend.

    Self-loads the bucket-scoped
    :class:`~application.calculations.CalculationObservationRepository` and
    fingerprints every persisted observation. This is the ``previous_filing``
    carry and relation fold-in SOURCE store, so the digest changes whenever a
    prior filed value in the bucket changes — reproducibly, from ``bucket_id``
    alone, without running the source mesh or resolving any relation.
    """
    from ..calculations import CalculationObservationRepository

    return _prior_filing_observations_fingerprint(CalculationObservationRepository(bucket_id=bucket_id).iter_records())


def _prior_filing_observations_fingerprint(payloads: Iterable[_StoredPriorObservation]) -> str:
    """Order-independent digest over a set of stored observation payloads.

    Each payload is projected to a STABLE shape that captures the calculation-
    relevant identity and value of the filed observation — the source modelo,
    filing year, period token, source kind, grupo-member NIF, the stamped
    registry revision, and every casilla id/value — and deliberately EXCLUDES the
    volatile ``captured_at`` timestamp so re-saving identical data does not
    over-invalidate an approval. Consumes the repository's ``iter_records()``
    stream structurally (the stored envelope type is private to the observation
    repository); an empty stream yields the stable empty-set digest.
    """
    projected = sorted(_normalize_prior_filing_observation(payload) for payload in payloads)
    return content_hash_hex(projected)


def _normalize_prior_filing_observation(payload: _StoredPriorObservation) -> list[object]:
    observation = payload.observation
    casilla_values = sorted(
        [
            entry.casilla_id,
            entry.value_kind,
            canonical_decimal_string(entry.value) if isinstance(entry.value, Decimal) else entry.value,
        ]
        for entry in observation.observations
    )
    return [
        str(observation.modelo),
        str(observation.filing_year),
        str(observation.period),
        payload.source_kind,
        payload.member_nif or "",
        payload.stamped_revision_id,
        casilla_values,
    ]


def empty_prior_filing_observations_fingerprint() -> str:
    """Return the digest of an empty prior-filing observation set.

    A caller passes this to :func:`compute_current_approval_basis` /
    :func:`approve_draft` to stamp a deterministic prior-filing digest without a
    bucket self-load (e.g. a test approving against a non-active/sentinel bucket
    with no prior observations), mirroring the empty-``InvoiceCatalogue`` override
    the invoice fingerprint accepts.
    """
    return _prior_filing_observations_fingerprint(())


def _load_profile_activity_fingerprint(bucket_id: str) -> str:
    """Digest the bucket's taxpayer profile facts from the secure backend.

    Self-loads the bucket-scoped :class:`~application.user_profile.CommittedProfileRepository`
    and fingerprints the wizard-free canonical projection
    (:func:`~application.user_profile.record_to_path_values`) — the SAME projection
    the relation resolver reads to scope relation resolution (activity-start date,
    m111 no-retenciones attestations, declared income categories). So the digest
    changes whenever a relation-scoping profile fact changes — reproducibly, from
    ``bucket_id`` alone, without running the source mesh. An absent profile yields
    the stable empty-projection digest.
    """
    try:
        record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return _profile_activity_fingerprint(None)
    return _profile_activity_fingerprint(record_to_path_values(record))


def _profile_activity_fingerprint(path_values: Mapping[str, str] | None) -> str:
    """Order-independent digest of the wizard-free taxpayer-profile projection.

    Hashes the canonical ``path -> value`` projection (every profile fact rendered
    to text) in sort-canonical order, so the digest is stable across re-serialisation
    and changes on any profile-fact edit. This is the wizard-free calc-relevant view
    by construction, so it carries no volatile persistence field to exclude. ``None``
    (no profile for the bucket) yields the stable empty-projection digest.
    """
    payload = sorted((path_values or {}).items())
    return content_hash_hex(payload)


def empty_profile_activity_fingerprint() -> str:
    """Return the digest of an absent taxpayer profile.

    A caller passes this to :func:`compute_current_approval_basis` /
    :func:`approve_draft` to stamp a deterministic profile digest without a bucket
    self-load (e.g. a test approving against a non-active/sentinel bucket with no
    profile), mirroring the empty overrides the other source fingerprints accept.
    """
    return _profile_activity_fingerprint(None)


def _draft_review_fingerprint(draft: ModeloDraft) -> str:
    payload = {
        "validation_status": derive_validation_status(draft.findings).value,
        "findings": [
            {
                "casilla_id": finding.casilla_id,
                "code": finding.code,
                "message": finding.message,
                "references_rules": list(finding.references_rules),
                "severity": finding.severity.value,
            }
            for finding in sorted(
                draft.findings,
                key=lambda item: (
                    item.casilla_id or "",
                    item.severity.value,
                    item.code,
                ),
            )
        ],
    }
    return content_hash_hex(payload)


def _transaction_catalogue_fingerprint(catalogue: TransactionCatalogue) -> str:
    payload = [
        _normalize_transaction(transaction)
        for transaction in sorted(catalogue.values(), key=lambda item: item.transaction_id)
    ]
    return content_hash_hex(payload)


def _invoice_catalogue_fingerprint(catalogue: InvoiceCatalogue) -> str:
    """Order-independent digest of the bucket's invoice catalogue.

    Each :class:`~domain.invoices.Invoice` is a frozen record with no
    volatile timestamp fields, so a canonical JSON dump of every invoice (sorted
    by ``invoice_id``) captures the full calculation-relevant content and changes
    whenever any invoice is added, removed, or edited. An empty catalogue yields a
    stable empty-list digest. Mirrors :func:`_transaction_catalogue_fingerprint`.
    """
    payload = [
        invoice.model_dump(mode="json") for invoice in sorted(catalogue.values(), key=lambda item: item.invoice_id)
    ]
    return content_hash_hex(payload)


def _normalize_transaction(transaction: Transaction) -> dict[str, str | None]:
    return {
        "business_classification": transaction.business_classification.value,
        "business_pct": (
            canonical_decimal_string(transaction.business_pct) if transaction.business_pct is not None else None
        ),
        "category_id": transaction.category_id,
        "direction": transaction.direction.value,
        "invoice_id": transaction.invoice_id,
        "transaction_id": transaction.transaction_id,
    }


def _category_profiles_fingerprint(profiles: Mapping[SpendingCategory, CategoryProfile]) -> str:
    payload = [
        {
            "category": category.value,
            "profile": profiles[category].model_dump(mode="json"),
        }
        for category in sorted(profiles, key=lambda item: item.value)
    ]
    return content_hash_hex(payload)


def _schema_formula_fingerprint(
    draft: ModeloDraft,
    *,
    schema_provider: CasillaSchemaProvider,
) -> str:
    collection = schema_provider.get_collection(draft.modelo)
    payload = {
        "current_schema_version": collection.schema_version,
        "draft_schema_version": draft.schema_version,
        "casillas": [
            {
                "formula_input_casilla_ids": list(casilla.formula_input_casilla_ids),
                "casilla_id": casilla.casilla_id,
                "required": casilla.required,
                "value_type": casilla.value_type,
            }
            for casilla in collection.all()
        ],
    }
    return content_hash_hex(payload)
