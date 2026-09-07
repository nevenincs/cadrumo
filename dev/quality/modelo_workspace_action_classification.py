"""The closed classification vocabulary the Modelo action denominator is written in.

Three things live here and nowhere else: the closed set of dispositions a
candidate action may carry, the typed row that records one classification with
its evidence, and the factory that builds such a row.

They sit apart from both the table that instantiates them and the gate that
consumes them, because both halves need them. Folding the vocabulary in with
the table would make the gate import its own types from a data declaration,
which inverts the dependency the boundary rule states; folding it in with the
gate would make the table import mechanism to declare data.

The split is also what lets the two halves grow independently. Rows are added
as the product gains modelo actions, and mechanism is added as the gate learns
to observe more of each action; before the split those two kinds of growth
shared one size ceiling and competed for it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

MODELO_IDENTITY_PREFIX: Final[str] = "modelo."
_PLACEHOLDER_REASONS: Final[frozenset[str]] = frozenset({"", "n/a", "na", "unmeasured", "tbd", "todo"})


class ModeloWorkspaceActionDisposition(StrEnum):
    """Closed classification outcome for one Modelo action candidate."""

    C1_BOUNDED_REVIEW = "c1_bounded_review"
    C1_OR_C2_READ_PENDING = "c1_or_c2_read_pending"
    C4_MUTATION_PENDING = "c4_mutation_pending"
    FLOW_OWNED = "flow_owned"
    DEFERRED = "deferred"
    NOT_VISUAL = "not_visual"


class ModeloWorkspaceActionClassificationV1(BaseModel):
    """One closed, hand-reviewed row: an action identity plus its disposition.

    ``command_key``, ``write_route``, ``side_effects``, and
    ``has_action_catalogue_entry`` are the recorded mechanical SIGNATURE this
    row was classified against; the validator re-observes the live signature
    and reds on drift rather than silently re-classifying.
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    action_identity: str = Field(min_length=1)
    disposition: ModeloWorkspaceActionDisposition
    command_key: str = Field(min_length=1)
    write_route: str = Field(min_length=1)
    side_effects: tuple[str, ...]
    has_action_catalogue_entry: bool
    owning_authority: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    evidence_reference: str = Field(min_length=1)
    reopening_condition: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_reason_is_not_a_placeholder(self) -> ModeloWorkspaceActionClassificationV1:
        if self.reason.strip().lower() in _PLACEHOLDER_REASONS:
            raise ValueError(f"classification reason for {self.action_identity!r} must be a real, bounded reason")
        if not self.action_identity.startswith(MODELO_IDENTITY_PREFIX):
            raise ValueError(f"{self.action_identity!r} is outside the Modelo action denominator's scope")
        return self


def modelo_action_classification(
    action_identity: str,
    disposition: ModeloWorkspaceActionDisposition,
    *,
    command_key: str,
    write_route: str,
    side_effects: tuple[str, ...],
    has_action_catalogue_entry: bool,
    owning_authority: str,
    reason: str,
    evidence_reference: str,
    reopening_condition: str,
) -> ModeloWorkspaceActionClassificationV1:
    """Build one reviewed classification row from its named evidence.

    The factory exists so a table row reads as a declaration rather than as a
    model construction, and so every row is forced through the same validated
    shape: a row that omits its authority, reason, evidence or reopening
    condition cannot be written at all.
    """
    return ModeloWorkspaceActionClassificationV1(
        action_identity=action_identity,
        disposition=disposition,
        command_key=command_key,
        write_route=write_route,
        side_effects=side_effects,
        has_action_catalogue_entry=has_action_catalogue_entry,
        owning_authority=owning_authority,
        reason=reason,
        evidence_reference=evidence_reference,
        reopening_condition=reopening_condition,
    )


__all__: tuple[str, ...] = (
    "MODELO_IDENTITY_PREFIX",
    "ModeloWorkspaceActionClassificationV1",
    "ModeloWorkspaceActionDisposition",
    "modelo_action_classification",
)
