"""Closed receipt boundary for reviewed M200/2024 candidate promotions."""

from __future__ import annotations

from pathlib import Path

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .m200_2024_blocker_adjudications import (
    compile_m200_2024_blocker_authority,
    promoted_candidate_ids as blocker_promoted_candidate_ids,
)
from .m200_2024_template_adjudications import (
    compile_m200_2024_same_template_authority,
    promoted_candidate_ids as template_promoted_candidate_ids,
)


def verified_promoted_candidate_ids(*, casillas_root: Path | None = None) -> frozenset[str]:
    """Recompile each registered cohort and return only exact live receipts."""
    template = template_promoted_candidate_ids(
        compile_m200_2024_same_template_authority(), casillas_root=casillas_root
    )
    blocker = blocker_promoted_candidate_ids(
        compile_m200_2024_blocker_authority(), casillas_root=casillas_root
    )
    if template & blocker:
        raise RegistryValidationError("M200/2024 reviewed promotion cohorts overlap")
    return template | blocker
