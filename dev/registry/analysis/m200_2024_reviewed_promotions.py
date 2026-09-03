"""Closed receipt boundary for reviewed M200/2024 candidate promotions.

One reconciliation invocation can be expensive because every authority compiler
must independently examine the pinned design, manual, legal catalogue, semantic
map, and restored-candidate audit.  ``M200ReviewedPromotionSnapshot`` is the
explicit, invocation-owned evidence snapshot: it builds that audit once, then
compiles every closed receipt once.  It is deliberately not a module cache.
Callers that do not supply it receive a fresh snapshot for that call.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cadrumo.core.hashing import sha256_hex
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .m200_2024_blocker_adjudication import build_worklist
from .m200_2024_blocker_adjudications import (
    CompiledM200BlockerAuthority,
    compile_m200_2024_blocker_authority,
)
from .m200_2024_blocker_adjudications import (
    verify_canonical_declarations as verify_blocker_canonical_declarations,
)
from .m200_2024_template_adjudications import (
    CompiledM200Same2024TemplateAuthority,
    compile_m200_2024_same_template_authority,
)
from .m200_2024_template_adjudications import (
    verify_canonical_declarations as verify_template_canonical_declarations,
)
from .m200_2024_unique_adjudications import (
    CompiledM200UniqueAuthority,
    compile_m200_2024_unique_authority,
)
from .m200_2024_unique_adjudications import (
    verify_canonical_declarations as verify_unique_canonical_declarations,
)
from .m200_restored_semantic_audit import RestoredSemanticAudit, audit_bundled_restorations

_SNAPSHOT_ISSUER = object()


@dataclass(frozen=True, slots=True)
class M200ReviewedPromotionSnapshot:
    """Immutable receipts compiled from one explicit restored-audit snapshot."""

    audits: tuple[RestoredSemanticAudit, ...]
    template_authority: CompiledM200Same2024TemplateAuthority
    blocker_authority: CompiledM200BlockerAuthority
    unique_authority: CompiledM200UniqueAuthority
    receipt_sha256: str
    _issuer: object


def build_m200_2024_reviewed_promotion_snapshot() -> M200ReviewedPromotionSnapshot:
    """Compile every reviewed cohort once against one fresh evidence snapshot."""
    audits = audit_bundled_restorations()
    template_authority = compile_m200_2024_same_template_authority(audits=audits)
    blocker_authority = compile_m200_2024_blocker_authority(
        audits=audits,
        worklist=build_worklist(audits=audits),
        same_template_authority=template_authority,
    )
    unique_authority = compile_m200_2024_unique_authority(audits=audits)
    return M200ReviewedPromotionSnapshot(
        audits=audits,
        template_authority=template_authority,
        blocker_authority=blocker_authority,
        unique_authority=unique_authority,
        receipt_sha256=_receipt_sha256(template_authority, blocker_authority, unique_authority),
        _issuer=_SNAPSHOT_ISSUER,
    )


def verified_promoted_candidate_ids(
    *,
    casillas_root: Path | None = None,
) -> frozenset[str]:
    """Compile and return only receipt- and byte-verified candidates.

    This public boundary always constructs a fresh source-bound snapshot; it
    cannot accept a caller-built receipt.  Private same-invocation consumers
    use ``_verified_promoted_candidate_ids`` to avoid replay.
    """
    return _verified_promoted_candidate_ids(
        build_m200_2024_reviewed_promotion_snapshot(),
        casillas_root=casillas_root,
    )


def _verified_promoted_candidate_ids(
    evidence: M200ReviewedPromotionSnapshot,
    *,
    casillas_root: Path | None = None,
) -> frozenset[str]:
    """Verify an issuer-bound snapshot created within the active invocation."""
    candidates = _receipt_candidate_ids(evidence)
    verify_template_canonical_declarations(evidence.template_authority, casillas_root=casillas_root)
    verify_blocker_canonical_declarations(evidence.blocker_authority, casillas_root=casillas_root)
    verify_unique_canonical_declarations(evidence.unique_authority, casillas_root=casillas_root)
    return candidates


def _receipt_candidate_ids(evidence: M200ReviewedPromotionSnapshot) -> frozenset[str]:
    """Return the closed receipt union before its caller selects a byte tree.

    A transaction that is repairing one reviewed cohort cannot demand that the
    live bytes already equal that cohort.  It still needs all three compiler
    receipts to be issuer-bound, exhaustive, and disjoint before staging, and
    then verifies each cohort against the appropriate candidate tree.
    """
    _require_issued_snapshot(evidence)
    template = frozenset(item.casilla_id for item in evidence.template_authority.adjudications)
    blocker = frozenset(item.casilla_id for item in evidence.blocker_authority.adjudications)
    unique = frozenset(item.casilla_id for item in evidence.unique_authority.adjudications)
    if template & blocker or template & unique or blocker & unique:
        raise RegistryValidationError("M200/2024 reviewed promotion cohorts overlap")
    return template | blocker | unique


def _receipt_sha256(
    template: CompiledM200Same2024TemplateAuthority,
    blocker: CompiledM200BlockerAuthority,
    unique: CompiledM200UniqueAuthority,
) -> str:
    """Bind an issued snapshot to all immutable compiler receipt fields."""
    return sha256_hex(repr((template, blocker, unique)).encode("utf-8"))


def _require_issued_snapshot(snapshot: M200ReviewedPromotionSnapshot) -> None:
    """Refuse a hand-built or receipt-mutated cache injection before use."""
    if snapshot._issuer is not _SNAPSHOT_ISSUER or snapshot.receipt_sha256 != _receipt_sha256(
        snapshot.template_authority,
        snapshot.blocker_authority,
        snapshot.unique_authority,
    ):
        raise RegistryValidationError("M200/2024 reviewed promotion snapshot provenance drifted")
