"""Draft approval persistence and stale-detection helpers."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from ..financial.categories import CATEGORY_PROFILES_2025, CategoryProfile, SpendingCategory
from ..financial.transactions import Transaction, TransactionCatalogue, load_transactions
from ..formulas import FiscalPeriod, MissingRulesetError, Quarter, get_registry
from ..models import ModeloCode
from ._errors import FilingDraftError
from ._protocols import CasillaSchemaProvider
from ._schema import (
    FilingApprovalBasis,
    FilingDraft,
    FilingDraftStatus,
)
from ._validator import derive_validation_status

_PERIOD_RE = re.compile(r"^(?P<year>\d{4})(?:Q(?P<quarter>[1-4]))?$")
_DEFAULT_TRANSACTION_CATALOGUE_FILENAME = "transactions.json"
_REVIEW_STATUSES = frozenset(
    {
        FilingDraftStatus.APPROVED,
        FilingDraftStatus.APPROVAL_STALE,
    }
)


class FilingApprovalStaleReason(StrEnum):
    """Stable reason codes surfaced when an approval becomes stale."""

    APPROVAL_BASIS_VERSION_CHANGED = "APPROVAL_BASIS_VERSION_CHANGED"
    DRAFT_PAYLOAD_CHANGED = "DRAFT_PAYLOAD_CHANGED"
    DRAFT_REVIEW_CHANGED = "DRAFT_REVIEW_CHANGED"
    TRANSACTION_CATALOGUE_CHANGED = "TRANSACTION_CATALOGUE_CHANGED"
    CATEGORY_PROFILES_CHANGED = "CATEGORY_PROFILES_CHANGED"
    SCHEMA_FORMULA_CHANGED = "SCHEMA_FORMULA_CHANGED"


def compute_current_approval_basis(
    draft: FilingDraft,
    *,
    schema_provider: CasillaSchemaProvider,
    transaction_catalogue: TransactionCatalogue | None = None,
    category_profiles: Mapping[SpendingCategory, CategoryProfile] | None = None,
    transaction_catalogue_path: Path | None = None,
) -> FilingApprovalBasis:
    """Return the approval-basis digests for the current upstream state."""

    catalogue = transaction_catalogue or _load_transaction_catalogue(transaction_catalogue_path)
    profiles = category_profiles or CATEGORY_PROFILES_2025
    return FilingApprovalBasis(
        draft_payload_fingerprint=draft.draft_id,
        draft_review_fingerprint=_draft_review_fingerprint(draft),
        transaction_catalogue_fingerprint=_transaction_catalogue_fingerprint(catalogue),
        category_profiles_fingerprint=_category_profiles_fingerprint(profiles),
        schema_formula_fingerprint=_schema_formula_fingerprint(
            draft,
            schema_provider=schema_provider,
        ),
    )


def compute_review_checksum(approval_basis: FilingApprovalBasis) -> str:
    """Return the canonical checksum for ``approval_basis``."""

    return _sha256_payload(approval_basis.model_dump(mode="json"))


def approval_stale_reasons(
    draft: FilingDraft,
    *,
    schema_provider: CasillaSchemaProvider,
    transaction_catalogue: TransactionCatalogue | None = None,
    category_profiles: Mapping[SpendingCategory, CategoryProfile] | None = None,
    transaction_catalogue_path: Path | None = None,
) -> tuple[FilingApprovalStaleReason, ...]:
    """Return the ordered stale reasons for ``draft``.

    The return value is empty when the draft has no approval metadata or when
    its stored approval basis still matches the freshly recomputed basis.
    """

    if draft.approval_basis is None:
        return ()

    current_basis = compute_current_approval_basis(
        draft,
        schema_provider=schema_provider,
        transaction_catalogue=transaction_catalogue,
        category_profiles=category_profiles,
        transaction_catalogue_path=transaction_catalogue_path,
    )
    reasons: list[FilingApprovalStaleReason] = []
    stored_basis = draft.approval_basis
    if stored_basis.version != current_basis.version:
        reasons.append(FilingApprovalStaleReason.APPROVAL_BASIS_VERSION_CHANGED)
    if stored_basis.draft_payload_fingerprint != current_basis.draft_payload_fingerprint:
        reasons.append(FilingApprovalStaleReason.DRAFT_PAYLOAD_CHANGED)
    if stored_basis.draft_review_fingerprint != current_basis.draft_review_fingerprint:
        reasons.append(FilingApprovalStaleReason.DRAFT_REVIEW_CHANGED)
    if stored_basis.transaction_catalogue_fingerprint != current_basis.transaction_catalogue_fingerprint:
        reasons.append(FilingApprovalStaleReason.TRANSACTION_CATALOGUE_CHANGED)
    if stored_basis.category_profiles_fingerprint != current_basis.category_profiles_fingerprint:
        reasons.append(FilingApprovalStaleReason.CATEGORY_PROFILES_CHANGED)
    if stored_basis.schema_formula_fingerprint != current_basis.schema_formula_fingerprint:
        reasons.append(FilingApprovalStaleReason.SCHEMA_FORMULA_CHANGED)
    return tuple(reasons)


def approve_draft(
    draft: FilingDraft,
    *,
    approved_by: str,
    schema_provider: CasillaSchemaProvider,
    transaction_catalogue: TransactionCatalogue | None = None,
    category_profiles: Mapping[SpendingCategory, CategoryProfile] | None = None,
    approved_at: datetime | None = None,
    transaction_catalogue_path: Path | None = None,
) -> FilingDraft:
    """Persist approval metadata on ``draft`` and promote it to ``APPROVED``."""

    normalized_approver = approved_by.strip()
    if not normalized_approver:
        raise FilingDraftError("approved_by must not be blank")

    if derive_validation_status(draft.findings) is not FilingDraftStatus.READY_TO_SUBMIT:
        raise FilingDraftError("only READY_TO_SUBMIT drafts may be approved")

    timestamp = approved_at or datetime.now(tz=UTC)
    approval_basis = compute_current_approval_basis(
        draft,
        schema_provider=schema_provider,
        transaction_catalogue=transaction_catalogue,
        category_profiles=category_profiles,
        transaction_catalogue_path=transaction_catalogue_path,
    )
    return draft.model_copy(
        update={
            "status": FilingDraftStatus.APPROVED,
            "approved_at": timestamp,
            "approved_by": normalized_approver,
            "approval_basis": approval_basis,
            "review_checksum": compute_review_checksum(approval_basis),
            "updated_at": timestamp,
        }
    )


def unapprove_draft(
    draft: FilingDraft,
    *,
    unapproved_at: datetime | None = None,
) -> FilingDraft:
    """Remove approval metadata and restore the machine validation status."""

    timestamp = unapproved_at or datetime.now(tz=UTC)
    return draft.model_copy(
        update={
            "status": derive_validation_status(draft.findings),
            "approved_at": None,
            "approved_by": None,
            "approval_basis": None,
            "review_checksum": None,
            "updated_at": timestamp,
        }
    )


def refresh_review_status(
    draft: FilingDraft,
    *,
    schema_provider: CasillaSchemaProvider,
    transaction_catalogue: TransactionCatalogue | None = None,
    category_profiles: Mapping[SpendingCategory, CategoryProfile] | None = None,
    refreshed_at: datetime | None = None,
    transaction_catalogue_path: Path | None = None,
) -> FilingDraft:
    """Return ``draft`` with its approval status synchronized to current state."""

    timestamp = refreshed_at or datetime.now(tz=UTC)
    if draft.status not in _REVIEW_STATUSES:
        cleared = _review_metadata_reset()
        if any(getattr(draft, key) != value for key, value in cleared.items()):
            cleared["updated_at"] = timestamp
            return draft.model_copy(update=cleared)
        return draft

    if (
        draft.approval_basis is None
        or draft.approved_at is None
        or draft.approved_by is None
        or draft.review_checksum is None
    ):
        cleared: dict[str, object] = _review_metadata_reset()
        cleared["status"] = derive_validation_status(draft.findings)
        if any(getattr(draft, key) != value for key, value in cleared.items()):
            cleared["updated_at"] = timestamp
            return draft.model_copy(update=cleared)
        return draft

    reasons = approval_stale_reasons(
        draft,
        schema_provider=schema_provider,
        transaction_catalogue=transaction_catalogue,
        category_profiles=category_profiles,
        transaction_catalogue_path=transaction_catalogue_path,
    )
    next_status = FilingDraftStatus.APPROVAL_STALE if reasons else FilingDraftStatus.APPROVED
    if draft.status is next_status:
        return draft
    return draft.model_copy(
        update={
            "status": next_status,
            "updated_at": timestamp,
        }
    )


def describe_stale_reason(reason: FilingApprovalStaleReason) -> str:
    """Return a short user-facing explanation for ``reason``."""

    match reason:
        case FilingApprovalStaleReason.APPROVAL_BASIS_VERSION_CHANGED:
            return "approval basis version changed"
        case FilingApprovalStaleReason.DRAFT_PAYLOAD_CHANGED:
            return "draft payload changed"
        case FilingApprovalStaleReason.DRAFT_REVIEW_CHANGED:
            return "draft validation surface changed"
        case FilingApprovalStaleReason.TRANSACTION_CATALOGUE_CHANGED:
            return "transaction catalogue changed"
        case FilingApprovalStaleReason.CATEGORY_PROFILES_CHANGED:
            return "category profiles changed"
        case FilingApprovalStaleReason.SCHEMA_FORMULA_CHANGED:
            return "schema or formula provenance changed"
    return reason.value.lower().replace("_", " ")


def _review_metadata_reset() -> dict[str, object]:
    return {
        "approved_at": None,
        "approved_by": None,
        "approval_basis": None,
        "review_checksum": None,
    }


def _load_transaction_catalogue(path: Path | None) -> TransactionCatalogue:
    if path is None:
        from ..config import load_settings

        path = load_settings().aeat_financial_txs_dir.resolve() / _DEFAULT_TRANSACTION_CATALOGUE_FILENAME
    if not path.exists():
        return TransactionCatalogue()
    return load_transactions(path)


def _draft_review_fingerprint(draft: FilingDraft) -> str:
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
    payload = [
        _normalize_transaction(transaction)
        for transaction in sorted(catalogue.values(), key=lambda item: item.transaction_id)
    ]
    return _sha256_payload(payload)


def _normalize_transaction(transaction: Transaction) -> dict[str, str | None]:
    return {
        "business_classification": transaction.business_classification.value,
        "business_pct": _canonical_decimal(transaction.business_pct),
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
    draft: FilingDraft,
    *,
    schema_provider: CasillaSchemaProvider,
) -> str:
    collection = schema_provider.get_collection(draft.modelo)
    payload = {
        "current_schema_version": collection.schema_version,
        "draft_schema_version": draft.schema_version,
        "ruleset_id": _resolve_ruleset_id(draft.modelo, draft.period),
    }
    return _sha256_payload(payload)


def _resolve_ruleset_id(modelo: str, period: str) -> str:
    fiscal_period = _parse_fiscal_period(period)
    if fiscal_period is None:
        return "unresolved-period"
    try:
        modelo_code = ModeloCode(modelo)
    except ValueError:
        return "unregistered-modelo"
    registry = get_registry()
    try:
        return registry.resolve(modelo=modelo_code, period=fiscal_period).ruleset_id
    except MissingRulesetError:
        return "no-ruleset"
    except Exception:
        return "unresolved-ruleset"


def _parse_fiscal_period(period: str) -> FiscalPeriod | None:
    match = _PERIOD_RE.fullmatch(period)
    if match is None:
        return None
    quarter_raw = match.group("quarter")
    quarter = Quarter(f"Q{quarter_raw}") if quarter_raw is not None else None
    return FiscalPeriod(year=int(match.group("year")), quarter=quarter)


def _sha256_payload(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    if value.is_zero():
        return "0"
    return format(value.normalize(), "f")
