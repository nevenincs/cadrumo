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


@dataclass(frozen=True, slots=True)
class M200ReviewedPromotionSnapshot:
    """Immutable receipts compiled from one explicit restored-audit snapshot."""

    audits: tuple[RestoredSemanticAudit, ...]
    template_authority: CompiledM200Same2024TemplateAuthority
    blocker_authority: CompiledM200BlockerAuthority
    unique_authority: CompiledM200UniqueAuthority


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
    )


def verified_promoted_candidate_ids(
    *,
    casillas_root: Path | None = None,
    snapshot: M200ReviewedPromotionSnapshot | None = None,
) -> frozenset[str]:
    """Return only receipt- and byte-verified candidates from one snapshot.

    The optional snapshot is intentionally caller-owned and short lived.  No
    process-global result is retained, so a later invocation always recompiles
    from current source and evidence.  Canonical declaration bytes are checked
    on every use, including isolated rebind trees.
    """
    evidence = build_m200_2024_reviewed_promotion_snapshot() if snapshot is None else snapshot
    template = frozenset(item.casilla_id for item in evidence.template_authority.adjudications)
    blocker = frozenset(item.casilla_id for item in evidence.blocker_authority.adjudications)
    unique = frozenset(item.casilla_id for item in evidence.unique_authority.adjudications)
    if template & blocker or template & unique or blocker & unique:
        raise RegistryValidationError("M200/2024 reviewed promotion cohorts overlap")
    verify_template_canonical_declarations(evidence.template_authority, casillas_root=casillas_root)
    verify_blocker_canonical_declarations(evidence.blocker_authority, casillas_root=casillas_root)
    verify_unique_canonical_declarations(evidence.unique_authority, casillas_root=casillas_root)
    return template | blocker | unique
