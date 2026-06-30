"""Typed models for the operator golden-task eval.

A :class:`GoldenScenario` is the declared expectation for one workflow: the modelo
context, the skill that owns the workflow, the expected tool trajectory (in
registry-key form), and whether the result must carry registry provenance. A
:class:`GoldenResult` is the runner's per-dimension verdict.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


class GoldenScenario(BaseModel):
    """One declared workflow expectation, loaded from a scenario TOML file.

    Attributes:
        name: Scenario identifier (e.g. ``"modelo-130-direct-estimation"``).
        modelo: The AEAT modelo code the workflow prepares (e.g. ``"130"``).
        filing_year: The filing year the scenario resolves the revision for.
        period: The AEAT period token (e.g. ``"1T"``).
        skill_name: The shipped skill directory whose playbook the trajectory
            must be consistent with.
        expected_trajectory: The ordered tool trajectory in registry-key form
            (e.g. ``("modelo.work.create", "modelo.work.calculate", ...)``).
        provenance_required: When true, every casilla on the resolved revision
            must carry non-empty ``legal_refs`` and ``source_refs``.
    """

    model_config = _STRICT_FROZEN

    name: str = Field(min_length=1)
    modelo: str = Field(min_length=1)
    filing_year: int = Field(ge=2000, le=2100)
    period: str = Field(min_length=1)
    skill_name: str = Field(min_length=1)
    expected_trajectory: tuple[str, ...] = Field(min_length=1)
    provenance_required: bool = True


class GoldenResult(BaseModel):
    """Per-dimension verdict for one golden scenario run.

    Each boolean is one assertion dimension; ``failures`` carries a human-readable
    reason for every dimension that did not hold. The scenario passes only when
    every dimension is true.
    """

    model_config = _STRICT_FROZEN

    scenario: str = Field(min_length=1)
    trajectory_resolves: bool
    lifecycle_ordered: bool
    skill_consistent: bool
    provenance_present: bool
    failures: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """True when every assertion dimension held and no failures were recorded."""
        return (
            self.trajectory_resolves
            and self.lifecycle_ordered
            and self.skill_consistent
            and self.provenance_present
            and not self.failures
        )
