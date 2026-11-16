"""Canonical read-only currentness fact of one generated export target."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cadrumo.domain.calculations.registry.errors import RegistryError

from .render_check import RenderComparison


class TargetCurrentnessState(StrEnum):
    """Read-only state of one named generated export target."""

    CURRENT = "current"
    STALE = "stale"
    DRIFTED = "drifted"
    NEVER_COMMITTED = "never-committed"


@dataclass(frozen=True, slots=True)
class TargetCurrentnessFact:
    """Canonical generated-tree currentness fact and its comparison evidence."""

    modelo: str
    revision: str
    state: TargetCurrentnessState
    differing: tuple[str, ...] = ()
    only_committed: tuple[str, ...] = ()
    only_rendered: tuple[str, ...] = ()
    serialization_only: tuple[str, ...] = ()
    provenance_fields: tuple[str, ...] = ()
    detail: str = ""


def target_currentness_comparison_fact(
    modelo: str,
    revision: str,
    comparison: RenderComparison,
    error: OSError | RegistryError | ValueError,
) -> TargetCurrentnessFact:
    """Classify a refused check as stale attestation or substantive drift from its byte comparison."""
    state = TargetCurrentnessState.STALE if comparison.provenance_only else TargetCurrentnessState.DRIFTED
    # A stale manifest's refusal names the digest that failed; the members that
    # differ from a fresh render say which input moved.
    detail = str(error)
    if comparison.provenance_fields:
        detail = f"{detail}; manifest members differing from a fresh render: " + ", ".join(comparison.provenance_fields)
    return TargetCurrentnessFact(
        modelo=modelo,
        revision=revision,
        state=state,
        differing=comparison.differing,
        only_committed=comparison.only_committed,
        only_rendered=comparison.only_rendered,
        serialization_only=comparison.serialization_only,
        provenance_fields=comparison.provenance_fields,
        detail=detail,
    )
