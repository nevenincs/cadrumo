"""Strict current-HEAD Modelo Workspace C1-C5 interface exit receipt schemas.

This module is the ONE place the Modelo Workspace interface receipt vocabulary
is defined: the discriminated proof cell, the closed compatibility-axis and
checklist taxonomies, and the ``ModeloWorkspaceC{1..5}ExitReceiptV1`` schemas
plus their ``validate_modelo_workspace_c{1..5}_exit_receipt`` validators.

It implements ONLY the interface-owned exit receipts. The dependency receipts
an exit receipt consumes on its way in (``ModeloWorkspaceC2DependencyReceiptV1``,
``ModeloEditContractC3DependencyReceiptV1``,
``TuiOperationFinancialOperandDependencyReceiptV1``, and the C0 operation
observation receipt) are architecture-owned: their substantive checks live in
the modules that mint them. An exit validator here never re-implements those
checks; it takes a ``dependency_validators`` delegate keyed by the dependency's
schema name and folds the delegate's own accumulated violations into its own,
which is what "delegated validation of architecture-owned incoming receipts"
means in practice. A required dependency with no delegate supplied is reported
as unavailable rather than silently accepted -- an exit cannot go green on an
unproven predecessor.

Every validator here follows the accumulating ``validate(...) -> list[str]``
convention used across the registry-binding validators: never raise on a
business-rule violation, always return every violation found.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION: Final[int] = 1
_COMMIT_HEX_LENGTH: Final[int] = 40
_DIGEST_PREFIX: Final[str] = "sha256:"
_PLACEHOLDER_REASONS: Final[frozenset[str]] = frozenset({"", "n/a", "na", "unmeasured", "tbd", "todo"})


class ModeloWorkspaceCohort(StrEnum):
    """The five interface exit cohorts this module mints receipts for."""

    C1 = "c1"
    C2 = "c2"
    C3 = "c3"
    C4 = "c4"
    C5 = "c5"


class ModeloWorkspaceCompatibilityAxis(StrEnum):
    """The closed set of distinct compatibility coordinates a receipt may carry.

    Every exit receipt declares a proof for every axis. An axis the cohort does
    not consume must carry a ``NOT_APPLICABLE`` proof; an axis it does consume
    may never be waived that way.
    """

    WORKSPACE = "workspace"
    EDIT = "edit"
    PUBLIC_DEFINITION = "public_definition"
    DEFINITION_DIGEST = "definition_digest"
    OBSERVATION = "observation"
    REVIEW = "review"
    REFRESH_TARGET = "refresh_target"
    FINANCIAL_PROTOCOL = "financial_protocol"


COHORT_CONSUMED_AXES: Final[Mapping[ModeloWorkspaceCohort, frozenset[ModeloWorkspaceCompatibilityAxis]]] = {
    ModeloWorkspaceCohort.C1: frozenset({ModeloWorkspaceCompatibilityAxis.REVIEW}),
    ModeloWorkspaceCohort.C2: frozenset(
        {
            ModeloWorkspaceCompatibilityAxis.WORKSPACE,
            ModeloWorkspaceCompatibilityAxis.PUBLIC_DEFINITION,
            ModeloWorkspaceCompatibilityAxis.DEFINITION_DIGEST,
        },
    ),
    ModeloWorkspaceCohort.C3: frozenset(
        {
            ModeloWorkspaceCompatibilityAxis.WORKSPACE,
            ModeloWorkspaceCompatibilityAxis.EDIT,
            ModeloWorkspaceCompatibilityAxis.OBSERVATION,
            ModeloWorkspaceCompatibilityAxis.REFRESH_TARGET,
            ModeloWorkspaceCompatibilityAxis.FINANCIAL_PROTOCOL,
        },
    ),
    ModeloWorkspaceCohort.C4: frozenset(
        {
            ModeloWorkspaceCompatibilityAxis.EDIT,
            ModeloWorkspaceCompatibilityAxis.REFRESH_TARGET,
        },
    ),
    ModeloWorkspaceCohort.C5: frozenset(ModeloWorkspaceCompatibilityAxis),
}

# The named "Required proof" checklist items from the companion ADR's D10
# table, one closed set per cohort. Unlike a compatibility axis, a checklist
# item is never optional for a cohort that declares it and can never be
# NOT_APPLICABLE -- ADR D10 lists these among the facts a waiver may never
# substitute for.
REQUIRED_CHECKLIST_ITEMS: Final[Mapping[ModeloWorkspaceCohort, frozenset[str]]] = {
    ModeloWorkspaceCohort.C1: frozenset(
        {
            "modelo_work_review_relocation",
            "locale_geometry_theme_keyboard_non_colour",
            "no_legacy_production_import",
        },
    ),
    ModeloWorkspaceCohort.C2: frozenset(
        {
            "c1_route_atomic_replacement",
            "destination_factory_census",
            "projection_coverage",
            "baseline_facets",
            "refusal_states",
            "schema_row_provenance_matrix",
            "production_composition",
        },
    ),
    ModeloWorkspaceCohort.C3: frozenset(
        {
            "compatibility_tuple",
            "edit_row_state_machine",
            "parse_and_validation_focus",
            "review_only_submit",
            "stale_refusal",
            "atomic_result_refresh",
            "locale_switch",
            "operation_handoff_consumption",
            "sensitive_non_retention",
        },
    ),
    ModeloWorkspaceCohort.C4: frozenset(
        {
            "zero_unclassified_action_candidates",
            "interaction_and_terminal_refresh",
            "rename_proof",
            "discard_proof",
            "verify_proof",
            "file_proof",
            "export_proof",
            "amend_proof",
            "amendment_wizard_disposition",
        },
    ),
    ModeloWorkspaceCohort.C5: frozenset(
        {
            "four_locale_matrix",
            "three_geometry_matrix",
            "two_theme_matrix",
            "keyboard_path",
            "non_colour",
            "large_schema_row_matrix",
            "refusal_conflict",
            "route_action_anti_vacuity",
            "no_transitional_tui",
            "installed_root_app_proof",
        },
    ),
}

# The closed, canonically-ordered set of predecessor schema names each cohort's
# exit receipt must declare a digest for. C1 has no in-plan predecessor: its
# only entrance facts are the governing records asserted below.
REQUIRED_PREDECESSOR_SCHEMA_NAMES: Final[Mapping[ModeloWorkspaceCohort, tuple[str, ...]]] = {
    ModeloWorkspaceCohort.C1: (),
    ModeloWorkspaceCohort.C2: (
        "ModeloWorkspaceC1ExitReceiptV1",
        "ModeloWorkspaceC2DependencyReceiptV1",
    ),
    ModeloWorkspaceCohort.C3: (
        "ModeloEditContractC3DependencyReceiptV1",
        "ModeloWorkspaceC2ExitReceiptV1",
        "TuiOperationFinancialOperandDependencyReceiptV1",
        "TuiOperationObservationDependencyReceiptV1",
    ),
    ModeloWorkspaceCohort.C4: ("ModeloWorkspaceC3ExitReceiptV1",),
    ModeloWorkspaceCohort.C5: ("ModeloWorkspaceC4ExitReceiptV1",),
}

_COMPANION_ADR_STEM: Final[str] = "2026-08-24-tui-modelo-workspace-interface-adr"


class ModeloWorkspaceReceiptProofKind(StrEnum):
    """The discriminant of :class:`ModeloWorkspaceReceiptProofV1`."""

    PASSED = "passed"
    NOT_APPLICABLE = "not_applicable"


class ModeloWorkspaceReceiptProofV1(BaseModel):
    """A single discriminated proof cell.

    ``PASSED`` carries the executable evidence identity and digest that proved
    it; ``NOT_APPLICABLE`` carries a stable code, an owning authority, a bounded
    reason, an evidence reference, and a reopening condition. Neither shape may
    borrow fields from the other, and a placeholder reason (``"n/a"``,
    ``"unmeasured"`` and siblings) is rejected outright.
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    kind: ModeloWorkspaceReceiptProofKind
    evidence_identity: str | None = None
    evidence_digest: str | None = None
    not_applicable_code: str | None = None
    owning_authority: str | None = None
    reason: str | None = None
    evidence_reference: str | None = None
    reopening_condition: str | None = None

    @model_validator(mode="after")
    def _check_discriminant(self) -> ModeloWorkspaceReceiptProofV1:
        waiver_fields = (
            self.not_applicable_code,
            self.owning_authority,
            self.reason,
            self.evidence_reference,
            self.reopening_condition,
        )
        if self.kind is ModeloWorkspaceReceiptProofKind.PASSED:
            if not self.evidence_identity or not self.evidence_digest:
                raise ValueError("a PASSED proof must carry a non-empty evidence_identity and evidence_digest")
            if not self.evidence_digest.startswith(_DIGEST_PREFIX):
                raise ValueError(f"evidence_digest must be prefixed {_DIGEST_PREFIX!r}")
            if any(waiver_fields):
                raise ValueError("a PASSED proof may not also carry NOT_APPLICABLE waiver fields")
            return self
        missing = [
            name
            for name, value in (
                ("not_applicable_code", self.not_applicable_code),
                ("owning_authority", self.owning_authority),
                ("reason", self.reason),
                ("evidence_reference", self.evidence_reference),
                ("reopening_condition", self.reopening_condition),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"a NOT_APPLICABLE proof must carry every waiver field; missing {missing}")
        if self.reason is not None and self.reason.strip().lower() in _PLACEHOLDER_REASONS:
            raise ValueError("a NOT_APPLICABLE reason must be a bounded stated reason, not a free-form placeholder")
        if self.evidence_identity or self.evidence_digest:
            raise ValueError("a NOT_APPLICABLE proof may not also carry PASSED evidence fields")
        return self


class AcceptedGoverningRecordV1(BaseModel):
    """A governing ADR/decision identity a receipt is anchored to.

    Only ``status == "accepted"`` is a legal value here: a proposed or draft
    record cannot govern a receipt, so the shape itself rejects the
    non-accepted-authority case at construction.
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    stem: str = Field(min_length=1)
    status: Literal["accepted"]
    accepting_commit: str = Field(min_length=_COMMIT_HEX_LENGTH, max_length=_COMMIT_HEX_LENGTH)
    body_hash: str

    @model_validator(mode="after")
    def _check_shapes(self) -> AcceptedGoverningRecordV1:
        if not all(char in "0123456789abcdef" for char in self.accepting_commit.lower()):
            raise ValueError("accepting_commit must be a hex commit sha")
        if not self.body_hash.startswith(_DIGEST_PREFIX) or self.body_hash == _DIGEST_PREFIX:
            raise ValueError(f"body_hash must be a non-empty value prefixed {_DIGEST_PREFIX!r}")
        return self


class PredecessorReceiptDigestV1(BaseModel):
    """One predecessor receipt's schema identity and digest.

    A predecessor digest is mandatory wherever the cohort declares one: it has
    no ``NOT_APPLICABLE`` counterpart.
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    schema_name: str = Field(min_length=1)
    receipt_stem: str = Field(min_length=1)
    digest: str

    @model_validator(mode="after")
    def _check_digest(self) -> PredecessorReceiptDigestV1:
        if not self.digest.startswith(_DIGEST_PREFIX) or self.digest == _DIGEST_PREFIX:
            raise ValueError(f"digest must be a non-empty value prefixed {_DIGEST_PREFIX!r}")
        return self


class ModeloWorkspaceExitReceiptBaseV1(BaseModel):
    """Shared shape for every ``ModeloWorkspaceC{1..5}ExitReceiptV1``."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    cohort: ModeloWorkspaceCohort
    schema_version: int = Field(ge=1)
    current_head_commit: str = Field(min_length=_COMMIT_HEX_LENGTH, max_length=_COMMIT_HEX_LENGTH)
    governing_records: tuple[AcceptedGoverningRecordV1, ...] = Field(min_length=1)
    predecessor_digests: tuple[PredecessorReceiptDigestV1, ...]
    compatibility: Mapping[ModeloWorkspaceCompatibilityAxis, ModeloWorkspaceReceiptProofV1]
    checklist: Mapping[str, ModeloWorkspaceReceiptProofV1]

    @model_validator(mode="after")
    def _check_structure(self) -> ModeloWorkspaceExitReceiptBaseV1:
        self._check_commit_hex()
        self._check_axes()
        self._check_checklist()
        self._check_predecessor_shape()
        return self

    def _check_commit_hex(self) -> None:
        if not all(char in "0123456789abcdef" for char in self.current_head_commit.lower()):
            raise ValueError("current_head_commit must be a hex commit sha")

    def _check_axes(self) -> None:
        missing_axes = set(ModeloWorkspaceCompatibilityAxis) - set(self.compatibility)
        if missing_axes:
            raise ValueError(f"compatibility mapping omits axes: {sorted(missing_axes)}")
        extra_axes = set(self.compatibility) - set(ModeloWorkspaceCompatibilityAxis)
        if extra_axes:
            raise ValueError(f"compatibility mapping carries unsupported axes: {sorted(extra_axes)}")
        consumed = COHORT_CONSUMED_AXES[self.cohort]
        for axis, proof in self.compatibility.items():
            consumes_axis = axis in consumed
            if consumes_axis and proof.kind is ModeloWorkspaceReceiptProofKind.NOT_APPLICABLE:
                raise ValueError(f"axis {axis} is consumed by {self.cohort} and cannot be NOT_APPLICABLE")
            if not consumes_axis and proof.kind is ModeloWorkspaceReceiptProofKind.PASSED:
                raise ValueError(f"axis {axis} is not consumed by {self.cohort}; declare it NOT_APPLICABLE, not PASSED")

    def _check_checklist(self) -> None:
        required = REQUIRED_CHECKLIST_ITEMS[self.cohort]
        actual = set(self.checklist)
        if actual != required:
            missing = sorted(required - actual)
            extra = sorted(actual - required)
            raise ValueError(
                f"checklist for {self.cohort} must be exactly {sorted(required)}; missing={missing} extra={extra}",
            )
        waived = sorted(
            key for key, proof in self.checklist.items() if proof.kind is ModeloWorkspaceReceiptProofKind.NOT_APPLICABLE
        )
        if waived:
            raise ValueError(f"checklist items {waived} are required proof and can never be NOT_APPLICABLE")

    def _check_predecessor_shape(self) -> None:
        stems = [digest.receipt_stem for digest in self.predecessor_digests]
        if len(stems) != len(set(stems)):
            raise ValueError("predecessor_digests contains duplicate receipt_stem entries")
        required_names = REQUIRED_PREDECESSOR_SCHEMA_NAMES[self.cohort]
        present_names = tuple(digest.schema_name for digest in self.predecessor_digests)
        if set(present_names) != set(required_names):
            missing = sorted(set(required_names) - set(present_names))
            extra = sorted(set(present_names) - set(required_names))
            raise ValueError(
                f"predecessor_digests for {self.cohort} must declare exactly {sorted(required_names)}; "
                f"missing={missing} extra={extra}",
            )
        expected_order = tuple(sorted(required_names))
        if present_names != expected_order:
            raise ValueError(
                f"predecessor_digests for {self.cohort} must be declared in canonical order "
                f"{expected_order}, got {present_names}",
            )


class ModeloWorkspaceC1ExitReceiptV1(ModeloWorkspaceExitReceiptBaseV1):
    """The C1 bounded-review exit receipt."""

    cohort: Literal[ModeloWorkspaceCohort.C1] = ModeloWorkspaceCohort.C1

    @model_validator(mode="after")
    def _check_companion(self) -> ModeloWorkspaceC1ExitReceiptV1:
        if not any(record.stem == _COMPANION_ADR_STEM for record in self.governing_records):
            raise ValueError(
                f"C1 requires the accepted companion ADR stem {_COMPANION_ADR_STEM!r} among governing_records",
            )
        return self


class ModeloWorkspaceC2ExitReceiptV1(ModeloWorkspaceExitReceiptBaseV1):
    """The C2 complex-read-workspace exit receipt."""

    cohort: Literal[ModeloWorkspaceCohort.C2] = ModeloWorkspaceCohort.C2


class ModeloWorkspaceC3ExitReceiptV1(ModeloWorkspaceExitReceiptBaseV1):
    """The C3 staged-editor exit receipt."""

    cohort: Literal[ModeloWorkspaceCohort.C3] = ModeloWorkspaceCohort.C3


class ModeloWorkspaceC4ExitReceiptV1(ModeloWorkspaceExitReceiptBaseV1):
    """The C4 lifecycle-actions exit receipt."""

    cohort: Literal[ModeloWorkspaceCohort.C4] = ModeloWorkspaceCohort.C4


class ModeloWorkspaceC5ExitReceiptV1(ModeloWorkspaceExitReceiptBaseV1):
    """The C5 visual-closure exit receipt."""

    cohort: Literal[ModeloWorkspaceCohort.C5] = ModeloWorkspaceCohort.C5


DependencyValidator = Callable[[], Sequence[str]]


def validate_modelo_workspace_exit_receipt(
    receipt: ModeloWorkspaceExitReceiptBaseV1,
    *,
    predecessor_available: Mapping[str, bool] | None = None,
    expected_predecessor_digests: Mapping[str, str] | None = None,
    dependency_validators: Mapping[str, DependencyValidator] | None = None,
    action_denominator_validator: DependencyValidator | None = None,
) -> list[str]:
    """Accumulate every violation of a Modelo Workspace exit receipt.

    ``predecessor_available`` maps a required predecessor schema name to
    whether ITS OWN owning exit or dependency receipt is currently green;
    ``expected_predecessor_digests`` maps the same keys to the authoritative
    digest that predecessor is currently known to carry, catching a drifted or
    reordered predecessor even when it is nominally available.
    ``dependency_validators`` delegates the substantive check of an
    architecture-owned incoming dependency receipt to its own validator, and
    ``action_denominator_validator`` is the mandatory
    ``validate_modelo_workspace_action_denominator`` invocation every exit
    validator must perform before returning green.
    """
    errors: list[str] = []
    availability = predecessor_available or {}
    if receipt.schema_version != SCHEMA_VERSION:
        errors.append(
            f"{receipt.cohort}: schema_version {receipt.schema_version} does not match current {SCHEMA_VERSION}",
        )

    for digest in receipt.predecessor_digests:
        available = availability.get(digest.schema_name, False)
        if not available:
            errors.append(
                f"{receipt.cohort}: predecessor {digest.schema_name} is not proven green; "
                "its owning exit or dependency receipt must pass before this cohort can close",
            )
        if expected_predecessor_digests is not None:
            expected = expected_predecessor_digests.get(digest.schema_name)
            if expected is not None and expected != digest.digest:
                errors.append(
                    f"{receipt.cohort}: predecessor {digest.schema_name} digest drifted; "
                    f"expected {expected!r}, receipt declares {digest.digest!r}",
                )

    delegates = dependency_validators or {}
    for schema_name, delegate in delegates.items():
        if schema_name not in {digest.schema_name for digest in receipt.predecessor_digests}:
            continue
        errors.extend(
            f"{receipt.cohort}: delegated validation of {schema_name} failed: {message}" for message in delegate()
        )

    if action_denominator_validator is None:
        errors.append(
            f"{receipt.cohort}: no action-denominator validator supplied; every exit MUST invoke "
            "validate_modelo_workspace_action_denominator against current HEAD before returning green",
        )
    else:
        errors.extend(
            f"{receipt.cohort}: action denominator rejected: {message}" for message in action_denominator_validator()
        )

    return errors


def _validate_cohort(
    receipt: ModeloWorkspaceExitReceiptBaseV1,
    expected_cohort: ModeloWorkspaceCohort,
    *,
    predecessor_available: Mapping[str, bool] | None,
    expected_predecessor_digests: Mapping[str, str] | None,
    dependency_validators: Mapping[str, DependencyValidator] | None,
    action_denominator_validator: DependencyValidator | None,
) -> list[str]:
    if receipt.cohort is not expected_cohort:
        raise TypeError(f"expected a {expected_cohort} exit receipt, got {receipt.cohort}")
    return validate_modelo_workspace_exit_receipt(
        receipt,
        predecessor_available=predecessor_available,
        expected_predecessor_digests=expected_predecessor_digests,
        dependency_validators=dependency_validators,
        action_denominator_validator=action_denominator_validator,
    )


def validate_modelo_workspace_c1_exit_receipt(
    receipt: ModeloWorkspaceC1ExitReceiptV1,
    *,
    predecessor_available: Mapping[str, bool] | None = None,
    expected_predecessor_digests: Mapping[str, str] | None = None,
    dependency_validators: Mapping[str, DependencyValidator] | None = None,
    action_denominator_validator: DependencyValidator | None = None,
) -> list[str]:
    """Accumulate every violation of a C1 exit receipt."""
    return _validate_cohort(
        receipt,
        ModeloWorkspaceCohort.C1,
        predecessor_available=predecessor_available,
        expected_predecessor_digests=expected_predecessor_digests,
        dependency_validators=dependency_validators,
        action_denominator_validator=action_denominator_validator,
    )


def validate_modelo_workspace_c2_exit_receipt(
    receipt: ModeloWorkspaceC2ExitReceiptV1,
    *,
    predecessor_available: Mapping[str, bool] | None = None,
    expected_predecessor_digests: Mapping[str, str] | None = None,
    dependency_validators: Mapping[str, DependencyValidator] | None = None,
    action_denominator_validator: DependencyValidator | None = None,
) -> list[str]:
    """Accumulate every violation of a C2 exit receipt."""
    return _validate_cohort(
        receipt,
        ModeloWorkspaceCohort.C2,
        predecessor_available=predecessor_available,
        expected_predecessor_digests=expected_predecessor_digests,
        dependency_validators=dependency_validators,
        action_denominator_validator=action_denominator_validator,
    )


def validate_modelo_workspace_c3_exit_receipt(
    receipt: ModeloWorkspaceC3ExitReceiptV1,
    *,
    predecessor_available: Mapping[str, bool] | None = None,
    expected_predecessor_digests: Mapping[str, str] | None = None,
    dependency_validators: Mapping[str, DependencyValidator] | None = None,
    action_denominator_validator: DependencyValidator | None = None,
) -> list[str]:
    """Accumulate every violation of a C3 exit receipt."""
    return _validate_cohort(
        receipt,
        ModeloWorkspaceCohort.C3,
        predecessor_available=predecessor_available,
        expected_predecessor_digests=expected_predecessor_digests,
        dependency_validators=dependency_validators,
        action_denominator_validator=action_denominator_validator,
    )


def validate_modelo_workspace_c4_exit_receipt(
    receipt: ModeloWorkspaceC4ExitReceiptV1,
    *,
    predecessor_available: Mapping[str, bool] | None = None,
    expected_predecessor_digests: Mapping[str, str] | None = None,
    dependency_validators: Mapping[str, DependencyValidator] | None = None,
    action_denominator_validator: DependencyValidator | None = None,
) -> list[str]:
    """Accumulate every violation of a C4 exit receipt."""
    return _validate_cohort(
        receipt,
        ModeloWorkspaceCohort.C4,
        predecessor_available=predecessor_available,
        expected_predecessor_digests=expected_predecessor_digests,
        dependency_validators=dependency_validators,
        action_denominator_validator=action_denominator_validator,
    )


def validate_modelo_workspace_c5_exit_receipt(
    receipt: ModeloWorkspaceC5ExitReceiptV1,
    *,
    predecessor_available: Mapping[str, bool] | None = None,
    expected_predecessor_digests: Mapping[str, str] | None = None,
    dependency_validators: Mapping[str, DependencyValidator] | None = None,
    action_denominator_validator: DependencyValidator | None = None,
) -> list[str]:
    """Accumulate every violation of a C5 exit receipt."""
    return _validate_cohort(
        receipt,
        ModeloWorkspaceCohort.C5,
        predecessor_available=predecessor_available,
        expected_predecessor_digests=expected_predecessor_digests,
        dependency_validators=dependency_validators,
        action_denominator_validator=action_denominator_validator,
    )
