"""Draft approval persistence and stale-detection helpers.

Provides the :func:`approve_draft` / :func:`unapprove_draft` /
:func:`refresh_review_status` lifecycle on top of
:class:`aeat.domain.filing.ModeloDraft`, plus the deterministic
fingerprint pipeline that lets :func:`approval_stale_reasons` detect
when an APPROVED draft has been invalidated by upstream changes.

The :func:`compute_current_approval_basis` helper accepts an optional
:class:`TransactionCatalogueRepository` override; when omitted, it
loads the :class:`TransactionCatalogue` from the encrypted
secure-object backend.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum

from ...core.hashing import sha256_hex as _sha256_hex
from ...core.i18n import tr
from ...core.logging import get_logger
from ...core.time import now
from ...domain._identifiers import canonical_decimal_string
from ...domain.categories import CategoryProfile, SpendingCategory, resolve_category_profiles
from ...domain.filing import (
    CasillaSchemaProvider,
    ModeloApprovalBasis,
    ModeloDraft,
    ModeloDraftError,
    ModeloValidator,
    derive_validation_status,
)
from ...domain.submission._protocols import ModeloDraftStatus
from ...domain.transactions import Transaction, TransactionCatalogue

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
            :class:`aeat.domain.filing.ModeloApprovalBasis` schema
            version has been bumped since approval.
        DRAFT_PAYLOAD_CHANGED: The draft's payload fingerprint
            (``draft_id``) no longer matches the stored basis.
        DRAFT_REVIEW_CHANGED: The draft's validation findings or
            machine status changed since approval.
        TRANSACTION_CATALOGUE_CHANGED: Upstream classified
            transactions have been updated since approval.
        CATEGORY_PROFILES_CHANGED: The fiscal category profile catalog
            has been edited since approval.
        SCHEMA_FORMULA_CHANGED: The registry-backed casilla schema or formula set
            has changed since approval.
    """

    APPROVAL_BASIS_VERSION_CHANGED = "BASE_APROBACION_VERSION_CAMBIADA"
    DRAFT_PAYLOAD_CHANGED = "BORRADOR_CONTENIDO_CAMBIADO"
    DRAFT_REVIEW_CHANGED = "BORRADOR_REVISION_CAMBIADA"
    TRANSACTION_CATALOGUE_CHANGED = "CATALOGO_TRANSACCIONES_CAMBIADO"
    CATEGORY_PROFILES_CHANGED = "PERFILES_CATEGORIA_CAMBIADOS"
    SCHEMA_FORMULA_CHANGED = "ESQUEMA_FORMULA_CAMBIADO"


def compute_current_approval_basis(
    draft: ModeloDraft,
    *,
    bucket_id: str,
    schema_provider: CasillaSchemaProvider,
    transaction_catalogue: TransactionCatalogue | None = None,
    category_profiles: Mapping[SpendingCategory, CategoryProfile] | None = None,
) -> ModeloApprovalBasis:
    """Return the :class:`ModeloApprovalBasis` digests for the current upstream state.

    Args:
        draft: The :class:`aeat.domain.filing.ModeloDraft` whose basis
            is being computed.
        bucket_id: Stable bucket identifier; used to load the persisted
            transaction catalogue when no override is supplied.
        schema_provider: The active
            :class:`aeat.domain.filing.CasillaSchemaProvider`.
        transaction_catalogue: Optional :class:`TransactionCatalogue` override.
            When ``None``, the catalogue is loaded from the encrypted
            SecureObjectRepository.
        category_profiles: Optional override of the active category
            profile map. Defaults to the bundled 2025 registry.

    Returns:
        A freshly computed :class:`ModeloApprovalBasis`.
    """
    catalogue = transaction_catalogue if transaction_catalogue is not None else _load_transaction_catalogue(bucket_id)
    profiles = category_profiles if category_profiles is not None else resolve_category_profiles(2025)
    return ModeloApprovalBasis(
        draft_payload_fingerprint=draft.draft_id,
        draft_review_fingerprint=_draft_review_fingerprint(draft),
        transaction_catalogue_fingerprint=_transaction_catalogue_fingerprint(catalogue),
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
    return _sha256_payload(approval_basis.model_dump(mode="json"))


def approval_stale_reasons(
    draft: ModeloDraft,
    *,
    bucket_id: str,
    schema_provider: CasillaSchemaProvider,
    transaction_catalogue: TransactionCatalogue | None = None,
    category_profiles: Mapping[SpendingCategory, CategoryProfile] | None = None,
) -> tuple[ModeloApprovalStaleReason, ...]:
    """Return the ordered stale reasons for ``draft``.

    The return value is empty when the draft has no approval metadata
    or when its stored approval basis still matches the freshly
    recomputed basis.

    Args:
        draft: The :class:`aeat.domain.filing.ModeloDraft` to inspect.
        bucket_id: Stable bucket identifier; forwarded to
            :func:`compute_current_approval_basis`.
        schema_provider: The active
            :class:`aeat.domain.filing.CasillaSchemaProvider`.
        transaction_catalogue: Optional :class:`TransactionCatalogue` override.
        category_profiles: Optional category profile map override.

    Returns:
        Tuple of :class:`ModeloApprovalStaleReason` values in
        evaluation order; empty when the basis is fresh.
    """
    if draft.approval_basis is None:
        return ()

    current_basis = compute_current_approval_basis(
        draft,
        bucket_id=bucket_id,
        schema_provider=schema_provider,
        transaction_catalogue=transaction_catalogue,
        category_profiles=category_profiles,
    )
    reasons: list[ModeloApprovalStaleReason] = []
    stored_basis = draft.approval_basis
    if stored_basis.version != current_basis.version:
        reasons.append(ModeloApprovalStaleReason.APPROVAL_BASIS_VERSION_CHANGED)
    if stored_basis.draft_payload_fingerprint != current_basis.draft_payload_fingerprint:
        reasons.append(ModeloApprovalStaleReason.DRAFT_PAYLOAD_CHANGED)
    if stored_basis.draft_review_fingerprint != current_basis.draft_review_fingerprint:
        reasons.append(ModeloApprovalStaleReason.DRAFT_REVIEW_CHANGED)
    if stored_basis.transaction_catalogue_fingerprint != current_basis.transaction_catalogue_fingerprint:
        reasons.append(ModeloApprovalStaleReason.TRANSACTION_CATALOGUE_CHANGED)
    if stored_basis.category_profiles_fingerprint != current_basis.category_profiles_fingerprint:
        reasons.append(ModeloApprovalStaleReason.CATEGORY_PROFILES_CHANGED)
    if stored_basis.schema_formula_fingerprint != current_basis.schema_formula_fingerprint:
        reasons.append(ModeloApprovalStaleReason.SCHEMA_FORMULA_CHANGED)
    return tuple(reasons)


def approve_draft(
    draft: ModeloDraft,
    *,
    bucket_id: str,
    approved_by: str,
    schema_provider: CasillaSchemaProvider,
    transaction_catalogue: TransactionCatalogue | None = None,
    category_profiles: Mapping[SpendingCategory, CategoryProfile] | None = None,
    approved_at: datetime | None = None,
) -> ModeloDraft:
    """Stamp approval metadata on ``draft`` and promote it to ``APPROVED``.

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
            :class:`aeat.domain.filing.CasillaSchemaProvider`.
        transaction_catalogue: Optional catalogue override.
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
    category_profiles: Mapping[SpendingCategory, CategoryProfile] | None = None,
    refreshed_at: datetime | None = None,
) -> ModeloDraft:
    """Return ``draft`` with its approval status synchronised to current state.

    Downstream-status drafts (submitted / acknowledged / rejected /
    amended / cancelled) get any leftover approval metadata cleared
    so historical state cannot pretend to be current. APPROVED drafts
    transition to :attr:`ModeloDraftStatus.APROBACION_CADUCADA` when
    :func:`approval_stale_reasons` returns a non-empty tuple.

    Args:
        draft: The draft to refresh.
        bucket_id: Stable bucket identifier; forwarded to
            :func:`approval_stale_reasons`.
        schema_provider: The active
            :class:`aeat.domain.filing.CasillaSchemaProvider`.
        transaction_catalogue: Optional :class:`TransactionCatalogue` override used
            when computing the approval basis fingerprint.
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
    """Return a short user-facing English explanation for ``reason``.

    Args:
        reason: The :class:`ModeloApprovalStaleReason` to describe.

    Returns:
        A localized phrase suitable for inline UI display.
    """
    match reason:
        case ModeloApprovalStaleReason.APPROVAL_BASIS_VERSION_CHANGED:
            return tr("application.filing.review.stale_reasons.approval_basis_version_changed")
        case ModeloApprovalStaleReason.DRAFT_PAYLOAD_CHANGED:
            return tr("application.filing.review.stale_reasons.draft_payload_changed")
        case ModeloApprovalStaleReason.DRAFT_REVIEW_CHANGED:
            return tr("application.filing.review.stale_reasons.draft_review_changed")
        case ModeloApprovalStaleReason.TRANSACTION_CATALOGUE_CHANGED:
            return tr("application.filing.review.stale_reasons.transaction_catalogue_changed")
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
        f"draft does not match the registry review surface: {codes!r}",
        translated_message="application.filing.review.errors.registry_review_mismatch",
        context={"codes": ", ".join(codes)},
    )


def _load_transaction_catalogue(bucket_id: str) -> TransactionCatalogue:
    """Load the transaction catalogue from the secure backend."""
    from ...domain.transactions import TransactionCatalogueRepository

    return TransactionCatalogueRepository(bucket_id=bucket_id).load()


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
    return _sha256_payload(payload)


def _transaction_catalogue_fingerprint(catalogue: TransactionCatalogue) -> str:
    hasher = hashlib.sha256()
    hasher.update(b"[")
    for index, transaction in enumerate(sorted(catalogue.values(), key=lambda item: item.transaction_id)):
        if index > 0:
            hasher.update(b",")
        hasher.update(_canonical_json_bytes(_normalize_transaction(transaction)))
    hasher.update(b"]")
    return hasher.hexdigest()


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
    return _sha256_payload(payload)


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
                "formula_inputs": list(casilla.formula_inputs),
                "id": casilla.id,
                "required": casilla.required,
                "value_type": casilla.value_type,
            }
            for casilla in collection.all()
        ],
    }
    return _sha256_payload(payload)


def _sha256_payload(payload: object) -> str:
    return _sha256_hex(_canonical_json_bytes(payload))


def _canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
