"""What a filed return is reconciled against, what must hold for it, and the folds.

Verification asks two questions of a filed modelo. First, do the numbers AEAT
received agree with the numbers this application computes? A revision answers
that by declaring verification *expectations*, and this module owns both halves
of that answer — the per-expectation declaration and the snapshot-wide fold the
living modelo reconciliation surface consumes. Second, do the filing's
values satisfy the cross-casilla invariants the form's law implies? A revision
answers that by declaring verification *predicates*, and this module owns that
declaration together with the closed operator vocabulary the registry-build
validator checks every predicate expression against.

Both questions live here because they are the two layers of one verification
strategy and neither is meaningful alone: an expectation says which casillas are
compared, a predicate says which relations between casillas must hold, and a
filing is granted VERIFICADO_COMPLETO only when both are satisfied. The operator
vocabulary travels with the predicate model rather than with the validator that
reads it, because the model's own docstring is where each operator's semantics
are documented — separating the two would document one concept in two modules.

The three casilla axes are deliberately distinct and are the reason the two
models belong together. ``computed_casilla_ids`` are the coverage-gated
reconciliation targets: fail to reconcile enough of them and the filing is
NEEDS_REVIEW. ``reconcile_when_present_casilla_ids`` are reconciled when the
filing prints them but are excluded from the coverage denominator, so enrolling
a situational casilla can never lower coverage and flip a legitimate filing's
verdict. ``externally_grounded_casilla_ids`` is orthogonal to both: of the
casillas a filing reconciles, which are backed by an AEAT-authoritative oracle
rather than only by this application's own engine — the difference between a
number that agrees with itself and a number checked against the authority.

Those relationships are invariants, not conventions, so they are enforced on the
declaration: each tuple is unique, the when-present set is disjoint from the
computed set, and the externally-grounded set is a subset of their union. A
casilla claimed as externally grounded but reconciled by nothing would advertise
oracle backing for a value no filing ever compares.

:class:`RegistryVerificationPolicy` is the fold of those declarations across a
whole snapshot, and it is a frozen dataclass rather than a registry model
because nothing authors it: it is derived by
:meth:`RegistrySnapshot.verification_policy` from the expectations a revision
already declared. Folding it once here keeps the application surface from
re-deriving the union, the strictest tolerance, and the strictest coverage
floor at each call site, where the three could quietly disagree.
"""

from __future__ import annotations

import re as _re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, field_validator, model_validator

from cadrumo.domain.calculations.registry.schema_scalars import WorkbookCellRefStr

from ....core import CasillaId
from .aeat_hosts import first_aeat_host
from .errors import RegistryValidationError
from .ids import (
    CrossReferenceId,
    OracleId,
    SourceRefId,
    VerificationExpectationId,
    WorkbookFixtureId,
    WorkbookOutputId,
    WorkbookParityRefId,
)
from .schema_base import EvidenceTier, LegalRefs, RegistryModel, SourceRefs
from .schema_scalars import DecimalValue

__all__ = [
    "KNOWN_PROFILE_FLAG_ADVISORY_FIELDS",
    "KNOWN_VERIFICATION_PREDICATE_OPERATORS",
    "VERIFICATION_PREDICATE_SPECIFICATIONS",
    "DiscrepancyCause",
    "LiveCrossReferenceDecision",
    "ParsedVerificationPredicate",
    "ProfilePredicateDefinition",
    "RegistryVerificationPolicy",
    "VerificationExpectationDefinition",
    "VerificationPredicateDefinition",
    "VerificationPredicateOperator",
    "VerificationPredicateSpecification",
    "VerificationPredicateSyntax",
    "VerificationRoundingCode",
    "WorkbookParityReference",
    "fold_reconciliation_total_casilla_ids",
    "parse_verification_predicate_expression",
    "verification_predicate_operator_name",
]


ProfileFactValue = bool | int | str


def _validate_open_or_public_authentication(
    surface: str,
    requires_authentication: bool,
    cross_reference_id: CrossReferenceId,
) -> None:
    if surface == "open_simulator" and requires_authentication:
        raise RegistryValidationError(
            f"cross-reference {cross_reference_id!r} open simulator must not require authentication",
        )
    if surface == "public_read_surface" and requires_authentication:
        raise RegistryValidationError(
            f"cross-reference {cross_reference_id!r} public read surface must not require authentication",
        )


def _validate_authenticated_read_authentication(
    surface: str,
    requires_authentication: bool,
    requires_aeat_authorization: bool,
    cross_reference_id: CrossReferenceId,
) -> None:
    if surface != "authenticated_read_surface":
        return
    if not requires_authentication:
        raise RegistryValidationError(
            f"cross-reference {cross_reference_id!r} authenticated read surface must require authentication",
        )
    if not requires_aeat_authorization:
        raise RegistryValidationError(
            f"cross-reference {cross_reference_id!r} authenticated read surface must require authorization",
        )


def _validate_authenticated_simulator_authentication(
    surface: str,
    requires_authentication: bool,
    cross_reference_id: CrossReferenceId,
) -> None:
    if surface == "authenticated_simulator" and not requires_authentication:
        raise RegistryValidationError(
            f"cross-reference {cross_reference_id!r} authenticated simulator must require authentication",
        )


class ProfilePredicateDefinition(RegistryModel):
    """Declare one profile condition that controls verification applicability."""

    field: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z_][A-Za-z0-9_.-]*$")
    op: Literal["equals", "not_equals"]
    value: ProfileFactValue
    explanation: str = Field(min_length=1)
    legal_refs: LegalRefs
    source_refs: SourceRefs


class LiveCrossReferenceDecision(RegistryModel):
    """Declare a resolved live cross-reference and its supporting evidence."""

    id: CrossReferenceId
    evidence_tier: EvidenceTier
    surface: Literal[
        "open_simulator",
        "integration_test_service",
        "public_read_surface",
        "authenticated_read_surface",
        "authenticated_simulator",
        "static_official_documentation",
    ]
    guard_policy_id: str
    allowed_hosts: tuple[str, ...] = ()
    allowed_methods: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = Field(min_length=1)
    synthetic_data_allowed: bool
    requires_authentication: bool
    requires_aeat_authorization: bool
    legal_refs: LegalRefs
    source_refs: SourceRefs
    # Optional: id of an oracle adapter registered in LiveParityCatalogue.
    # When set, the calculation engine looks up the bound adapter to drive
    # synthetic-payload verification under the cross-reference's policy.
    # Resolution against the catalogue happens at calculation time, not at
    # registry-load time, so the registry remains loadable when adapters
    # are imported lazily.
    oracle_id: OracleId | None = None
    # Optional applicability gate: when non-empty the cross-reference is
    # only applicable to a taxpayer profile whose values satisfy these
    # predicates under the chosen mode. An empty tuple (the default) means
    # the cross-reference is unconditionally applicable. Used to gate
    # optional surfaces (GROI / IXVI for ROI-enrolled subjects, OSS
    # bindings for OSS-enrolled subjects, etc.).
    applicability_condition_mode: Literal["all", "any"] = "all"
    applicability_predicates: tuple[ProfilePredicateDefinition, ...] = ()

    @field_validator("oracle_id")
    @classmethod
    def _oracle_id_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        # kebab-case ASCII identifier: lowercase alpha start, alphanumerics
        # plus hyphens, no trailing hyphen.
        if not value[0].isalpha() or not value[0].islower():
            raise RegistryValidationError("oracle_id must start with a lowercase ASCII letter")
        if value.endswith("-"):
            raise RegistryValidationError("oracle_id must not end with a hyphen")
        for char in value:
            if not (char.islower() and char.isascii()) and not char.isdigit() and char != "-":
                raise RegistryValidationError(
                    f"oracle_id contains unsupported character {char!r}; "
                    f"only lowercase ASCII letters, digits, and hyphens are permitted",
                )
        return value

    @model_validator(mode="after")
    def _validate_cross_reference(self) -> LiveCrossReferenceDecision:
        self._validate_evidence_tier_alignment()
        self._validate_allowed_hosts_declared()
        self._validate_authentication_constraints()
        self._validate_synthetic_data_constraints()
        for method in self.allowed_methods:
            self._validate_allowed_method(method)
        if self.applicability_condition_mode == "any" and not self.applicability_predicates:
            raise RegistryValidationError(f"cross-reference {self.id!r} any-mode requires applicability predicates")
        return self

    def _validate_evidence_tier_alignment(self) -> None:
        """The evidence_tier must match the surface's regulatory class.

        Live surfaces (simulators, integration test services) carry
        executable parity evidence; read surfaces and static
        documentation carry observation evidence only.
        """
        if (
            self.surface in {"open_simulator", "integration_test_service", "authenticated_simulator"}
            and self.evidence_tier != "executable_parity_evidence"
        ):
            raise RegistryValidationError(
                f"cross-reference {self.id!r} live surface requires executable parity evidence",
            )
        if (
            self.surface in {"public_read_surface", "authenticated_read_surface"}
            and self.evidence_tier == "executable_parity_evidence"
        ):
            raise RegistryValidationError(
                f"cross-reference {self.id!r} read surface is observation evidence, not parity",
            )
        if self.surface == "static_official_documentation" and self.evidence_tier == "executable_parity_evidence":
            raise RegistryValidationError(
                f"cross-reference {self.id!r} static documentation is not executable parity evidence",
            )

    def _validate_allowed_hosts_declared(self) -> None:
        """Every non-static surface must declare its allowed_hosts."""
        if (
            self.surface
            in {
                "open_simulator",
                "integration_test_service",
                "public_read_surface",
                "authenticated_read_surface",
                "authenticated_simulator",
            }
            and not self.allowed_hosts
        ):
            raise RegistryValidationError(f"cross-reference {self.id!r} must declare allowed_hosts")

    def _validate_authentication_constraints(self) -> None:
        """Per-surface auth + AEAT-authorization requirements.

        Open simulators and public reads must not require auth;
        authenticated reads must require both auth and AEAT
        authorization; authenticated simulators must require auth.
        """
        _validate_open_or_public_authentication(self.surface, self.requires_authentication, self.id)
        _validate_authenticated_read_authentication(
            self.surface,
            self.requires_authentication,
            self.requires_aeat_authorization,
            self.id,
        )
        _validate_authenticated_simulator_authentication(self.surface, self.requires_authentication, self.id)

    def _validate_synthetic_data_constraints(self) -> None:
        """Read surfaces and static docs must not accept synthetic data.

        Additionally, no cross-reference whose ``allowed_hosts`` include an
        AEAT-owned host (suffix match against ``agenciatributaria.gob.es``
        or ``aeat.es``) may declare ``synthetic_data_allowed = true``.
        Synthetic taxpayer, counterparty, declaration, profile, or form
        data is prohibited on AEAT-hosted live surfaces; the surface
        shape (``open_simulator`` / ``authenticated_simulator``) does not
        license synthetic input against AEAT infrastructure.
        """
        if self.surface in {"public_read_surface", "authenticated_read_surface"} and self.synthetic_data_allowed:
            raise RegistryValidationError(f"cross-reference {self.id!r} read surface must not accept synthetic data")
        if self.surface == "static_official_documentation" and self.synthetic_data_allowed:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} static documentation cannot accept synthetic data",
            )
        if self.synthetic_data_allowed:
            aeat_host = first_aeat_host(self.allowed_hosts)
            if aeat_host is not None:
                raise RegistryValidationError(
                    f"cross-reference {self.id!r} declares synthetic_data_allowed = true "
                    f"on AEAT-hosted allowed host {aeat_host!r}; synthetic data is prohibited "
                    f"on AEAT-hosted live surfaces",
                )

    def _validate_allowed_method(self, method: str) -> None:
        """Per-surface HTTP method allowlist + uppercase shape requirement."""
        if method.upper() != method:
            raise RegistryValidationError(f"cross-reference {self.id!r} allowed_methods must be uppercase")
        if self.surface in {"public_read_surface", "authenticated_read_surface"} and method not in {
            "GET",
            "HEAD",
            "OPTIONS",
        }:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} read surface method {method!r} is not read-only",
            )
        # authenticated_simulator declares the AEAT-prescribed query
        # method (POST is the GROI / IXVI form-submit mechanism). The
        # remote-state guard's HTTP-method check stays strict for
        # ``kind="http"`` operations; only the cross-reference's
        # allowed_methods declaration is widened.
        if self.surface == "authenticated_simulator" and method not in {"GET", "HEAD", "OPTIONS", "POST"}:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} authenticated simulator method "
                f"{method!r} not in (GET, HEAD, OPTIONS, POST)",
            )


class WorkbookParityReference(RegistryModel):
    """Declare the workbook evidence used for an executable parity check."""

    id: WorkbookParityRefId
    workbook_source: SourceRefId
    fixture_id: WorkbookFixtureId
    formula_coverage: Literal["formula_form", "static_layout", "record_design_layout", "unsupported_binary_xls"]
    runner_required: bool
    output_cells: Mapping[WorkbookOutputId, WorkbookCellRefStr] = Field(default_factory=dict)
    tolerance: DecimalValue = Decimal("0.00")
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_workbook_reference(self) -> WorkbookParityReference:
        if self.formula_coverage == "formula_form" and not self.runner_required:
            raise RegistryValidationError(f"workbook parity reference {self.id!r} formula coverage requires a runner")
        if self.formula_coverage != "formula_form" and self.runner_required:
            raise RegistryValidationError(f"workbook parity reference {self.id!r} runner requires formula coverage")
        if self.runner_required and not self.output_cells:
            raise RegistryValidationError(f"workbook parity reference {self.id!r} requires output_cells")
        if self.workbook_source not in self.source_refs:
            raise RegistryValidationError(
                f"workbook parity reference {self.id!r} source_refs must include workbook_source",
            )
        return self


class VerificationRoundingCode(StrEnum):
    """Closed rounding vocabulary for a verification expectation's comparison.

    Declared here rather than reusing :class:`RegistryRoundingCode`: that enum
    is the FORMULA rounding authority and deliberately has no "do not round"
    mode, because every computed casilla is rounded by some legal rule. A
    verification expectation is a different axis -- it says how the filed and
    computed values are brought into comparable form before the tolerance is
    applied -- and ``none`` (compare the raw values) is a legitimate member
    there. Widening the formula enum to admit it would let a formula declare a
    mode the law never grants.

    ``rounding`` was a bare ``str``, so ``rounding = "bogus"`` was accepted at
    registry build and produced exactly the same policy and verifier behaviour
    as the valid declaration -- a legal verification obligation could drift
    from the runtime authority with nothing to notice.
    """

    MONEY_2 = "money-2"
    NONE = "none"


def _coerce_verification_rounding(value: object) -> object:
    """Hydrate a raw TOML rounding token into :class:`VerificationRoundingCode`.

    The registry authoring tree stays free-form TOML; the typed vocabulary is
    applied here, at the one loader boundary, so an unknown token fails the
    registry build rather than flowing into the policy as opaque text.
    """
    if isinstance(value, str) and not isinstance(value, VerificationRoundingCode):
        return VerificationRoundingCode(value)
    return value


VerificationRoundingCodeValue = Annotated[VerificationRoundingCode, BeforeValidator(_coerce_verification_rounding)]


class DiscrepancyCause(StrEnum):
    """Closed vocabulary of causes a verification discrepancy may be attributed to."""

    EXTRACTION_UNRELIABLE = "extraction_unreliable"
    UNMODELLED_RULE = "unmodelled_rule"
    ROUNDING = "rounding"
    CORRECTNESS_DIVERGENCE = "correctness_divergence"


def _coerce_discrepancy_cause(value: object) -> object:
    """Hydrate a raw TOML cause token into :class:`DiscrepancyCause`."""
    if isinstance(value, str) and not isinstance(value, DiscrepancyCause):
        return DiscrepancyCause(value)
    return value


DiscrepancyCauseValue = Annotated[
    DiscrepancyCause,
    BeforeValidator(_coerce_discrepancy_cause),
]


class VerificationExpectationDefinition(RegistryModel):
    """Declare one expected relationship between calculated and filed casillas."""

    id: VerificationExpectationId
    computed_casilla_ids: tuple[CasillaId, ...]
    reconcile_when_present_casilla_ids: tuple[CasillaId, ...] = ()
    externally_grounded_casilla_ids: tuple[CasillaId, ...] = ()
    reconciliation_total_casilla_ids: Mapping[Literal["ingresar", "devolver"], CasillaId] = Field(
        default_factory=lambda: dict[Literal["ingresar", "devolver"], CasillaId](),
    )
    tolerance: DecimalValue = Field(ge=Decimal("0"))
    rounding: VerificationRoundingCodeValue
    min_coverage: DecimalValue = Field(ge=Decimal("0"), le=Decimal("1"))
    discrepancy_causes: tuple[DiscrepancyCauseValue, ...] = Field(min_length=1)
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("computed_casilla_ids")
    @classmethod
    def _computed_casilla_ids_unique(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("verification expectation computed_casilla_ids must be unique")
        return value

    @field_validator("reconcile_when_present_casilla_ids")
    @classmethod
    def _reconcile_when_present_unique(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError(
                "verification expectation reconcile_when_present_casilla_ids must be unique",
            )
        return value

    @field_validator("externally_grounded_casilla_ids")
    @classmethod
    def _externally_grounded_unique(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError(
                "verification expectation externally_grounded_casilla_ids must be unique",
            )
        return value

    @model_validator(mode="after")
    def _reconcile_when_present_disjoint(self) -> VerificationExpectationDefinition:
        overlap = set(self.reconcile_when_present_casilla_ids) & set(self.computed_casilla_ids)
        if overlap:
            raise RegistryValidationError(
                "verification expectation reconcile_when_present_casilla_ids must be disjoint from "
                f"computed_casilla_ids (overlap: {sorted(overlap)})",
            )
        return self

    @model_validator(mode="after")
    def _externally_grounded_subset(self) -> VerificationExpectationDefinition:
        reconciled = set(self.computed_casilla_ids) | set(self.reconcile_when_present_casilla_ids)
        outside = set(self.externally_grounded_casilla_ids) - reconciled
        if outside:
            raise RegistryValidationError(
                "verification expectation externally_grounded_casilla_ids must be a subset of "
                f"computed_casilla_ids | reconcile_when_present_casilla_ids (outside: {sorted(outside)})",
            )
        return self


def fold_reconciliation_total_casilla_ids(
    expectations: Iterable[VerificationExpectationDefinition],
) -> Mapping[Literal["ingresar", "devolver"], CasillaId]:
    """Fold every expectation's reconciliation-total casillas into one mapping.

    The canonical fold for this axis. Three surfaces need it — the verification
    policy, the filing subview and the result summary — and each previously
    open-coded its own loop with a different tie-break, so the same revision
    could in principle name one casilla as the ``ingresar`` total on one surface
    and a different one on another.

    AMBIGUITY IS REFUSED RATHER THAN RESOLVED. The other folded axes have a
    defensible ordering — union for a set, strictest for a tolerance — but there
    is no "stricter" of two casilla ids, so any tie-break here would be an
    invention rather than a rule, and whichever surface adopted it first would
    silently become the authority. Two expectations naming DIFFERENT casillas
    for one kind is a registry-authoring fault, so it raises; naming the same
    casilla twice is harmless and folds to one entry.

    Raises:
        RegistryValidationError: When two expectations declare different casilla
            ids for the same reconciliation kind.
    """
    folded: dict[Literal["ingresar", "devolver"], CasillaId] = {}
    for expectation in expectations:
        for kind, casilla_id in expectation.reconciliation_total_casilla_ids.items():
            existing = folded.get(kind)
            if existing is not None and existing != casilla_id:
                raise RegistryValidationError(
                    f"verification expectations declare conflicting reconciliation totals for {kind!r}: "
                    f"{existing!r} and {casilla_id!r}",
                )
            folded[kind] = casilla_id
    return dict(sorted(folded.items()))


@dataclass(frozen=True, slots=True)
class RegistryVerificationPolicy:
    """Folded verification policy across a snapshot's verification expectations.

    Owns the registry-grounded projection (union of computed casilla ids, the
    union of reconcile-when-present casilla ids, the strictest tolerance, the
    strictest coverage floor) so application consumers do not re-derive the
    fold.

    ``computed_casilla_ids`` are the coverage-gated reconciliation targets: a
    filing that fails to reconcile them below ``min_coverage`` is NEEDS_REVIEW.
    ``reconcile_when_present_casilla_ids`` are value-reconciled when the filing
    prints them (a filed-vs-computed divergence surfaces a discrepancy) but are
    excluded from the coverage denominator, so enrolling a situational casilla
    can never lower coverage and flip a legitimate filing's verdict.

    ``externally_grounded_casilla_ids`` is the third, orthogonal axis: of the
    casillas a filing reconciles (``computed_casilla_ids`` or
    ``reconcile_when_present_casilla_ids``), which have an AEAT-authoritative
    independent oracle expected value backing their reconciliation, rather than
    only the app's own engine.
    """

    expectation_ids: tuple[VerificationExpectationId, ...]
    #: The folded reconciliation-total casillas, from
    #: :func:`fold_reconciliation_total_casilla_ids`. Carried on the policy so a
    #: consumer that already holds one does not re-derive the fold.
    reconciliation_total_casilla_ids: Mapping[Literal["ingresar", "devolver"], CasillaId]
    computed_casilla_ids: frozenset[CasillaId]
    reconcile_when_present_casilla_ids: frozenset[CasillaId]
    externally_grounded_casilla_ids: frozenset[CasillaId]
    tolerance: Decimal
    min_coverage: Decimal
    #: The rounding modes the folded expectations declare. Carried rather than
    #: dropped: the fold previously discarded ``rounding`` entirely, so the
    #: declaration was unreachable from the surface that consumes the policy
    #: and no reader could tell a valid declaration from a meaningless one.
    rounding_codes: frozenset[VerificationRoundingCode] = frozenset()
    #: The discrepancy causes the folded expectations declare, likewise carried
    #: rather than dropped.
    discrepancy_causes: frozenset[DiscrepancyCause] = frozenset()


KNOWN_PROFILE_FLAG_ADVISORY_FIELDS: frozenset[str] = frozenset(
    {
        "art109_activity_income_withholding_ge_70pct",
        # ue_eee_status: TaxpayerProfile derived property (True iff
        # country_of_fiscal_residence is an EU/EEA code, post-Brexit). Consumed
        # by profile_flag_enabled directly and by
        # casilla_equals_implies_profile_flag for the M210 IRNR
        # tipo_renta="ue_residente" residence cross-check.
        "ue_eee_status",
    },
)


KNOWN_VERIFICATION_PREDICATE_OPERATORS: frozenset[str] = frozenset(
    {
        # advisory_when_positive(["casilla_id"]) — single-casilla positive
        # advisory: FIRES (ADVISORY shown) iff the one named casilla resolves
        # strictly > 0. The minimal "this box is populated, review the
        # downstream treatment" prompt for a value the calculation chain does
        # not yet fully model. ADVISORY-only (no BLOCKING_RULE branch). Authored
        # for the Modelo 100 anualidades por alimentos a favor de los hijos
        # (casilla 0527): the separate-escala treatment (LIRPF art. 64 / art. 75)
        # is applied without the statutory mínimo-por-descendientes gating in the
        # current cuota chain, so a payer declaring anualidades may be
        # under-taxed — surfaced as a non-blocking prompt to review the cuota,
        # per no-silent-under-declaration, pending the full separate-escala
        # modelling. Single casilla id, so it routes through the generic
        # _casilla_list_predicate_failures (arity 1) at registry build; see the
        # advisory_when_positive branch in _evaluate_advisory_predicate_fires.
        "advisory_when_positive",
        "advisory_when_ratio_ge",
        "all_nonzero",
        # at_most_one_positive(["id1", "id2", ...]) — mutual-exclusion
        # invariant: no more than one listed casilla may resolve strictly > 0.
        # As a BLOCKING_RULE it refuses overstatement shapes where alternative
        # calculation lanes are both populated. As an ADVISORY it fires on the
        # same contradiction without blocking. Authored for Modelo 202
        # modalidad art. 40.3 clave 32, whose official instructions say
        # "clave [18] (o clave [26])": B1 and B2 resultado-previo lanes are
        # alternatives, and the arithmetic formula can only add the two
        # zero-default lanes safely when at most one is positive.
        "at_most_one_positive",
        "any_nonzero",
        "cap_le_when_positive",
        # casilla_equals_implies_nonzero(["antecedent_casilla_id", "literal",
        # "consequent_casilla_id"]) — categorical-conditional material
        # implication: when the operator-entered raw text value of the named
        # TEXT antecedent casilla equals the literal, the named consequent
        # (Decimal) casilla must be non-zero. ADVISORY-only (no BLOCKING_RULE
        # branch is implemented), mirroring the existing equals (BLOCKING-only)
        # / advisory_when_ratio_ge (ADVISORY-only) asymmetry. Authored for the
        # M210 IRNR inmobiliaria branch (tipo_renta == "inmobiliaria" implies a
        # non-zero base_imponible), the one shape implies_nonzero cannot
        # express because its trigger is a categorical equality, not a
        # numeric antecedent. See the casilla_equals_implies_nonzero branch in
        # _evaluate_advisory_predicate_fires.
        "casilla_equals_implies_nonzero",
        # casilla_equals_implies_profile_flag(["antecedent_casilla_id", "literal",
        # "profile_field"]) — categorical-antecedent / profile-state-consequent
        # conditional advisory: FIRES (ADVISORY shown) when the operator-entered
        # raw text value of the named TEXT antecedent casilla equals the literal
        # AND the named boolean TaxpayerProfile field/property is False.
        # ADVISORY-only (no BLOCKING_RULE branch is implemented), sibling of
        # casilla_equals_implies_nonzero (whose consequent reads a Decimal
        # casilla) and profile_flag_enabled (whose antecedent is
        # unconditional). Authored for the M210 IRNR
        # tipo_renta="ue_residente" reduced-rate election (TRLIRNR Art 25.1.a):
        # the categorical rate choice was not cross-checked against the
        # declared country_of_fiscal_residence, so a non-EU/EEA filer could
        # self-declare the reduced 19% rate reserved for EU/EEE residents. See
        # the casilla_equals_implies_profile_flag branch in
        # _evaluate_advisory_predicate_fires.
        "casilla_equals_implies_profile_flag",
        # casilla_equals_implies_diverges(["antecedent_casilla_id", "literal",
        # "casilla_a_id", "casilla_b_id"]) — categorical-conditional
        # divergence check: when the operator-entered raw text value of the
        # named TEXT antecedent casilla equals the literal, the two named
        # (Decimal) casillas must not differ by more than one cent.
        # ADVISORY-only (no BLOCKING_RULE branch is implemented), sibling of
        # casilla_equals_implies_nonzero (consequent test "== 0") and
        # advisory_when_computed_diverges (no categorical gate). Authored for
        # the M131/M100 estimación-objetiva índice corrector de exceso (b.3),
        # incompatible per Orden HAC/1347/2024 Anexo II instrucción 2.3 with
        # the índices correctores especiales (a.2 autotaxi, a.4 transporte de
        # mercancías/mudanzas) for the activities that carry both. See the
        # casilla_equals_implies_diverges branch in
        # _evaluate_advisory_predicate_fires.
        "casilla_equals_implies_diverges",
        # deduccion_requires_adquisicion_before(["amount_casilla_id",
        # "acquisition_date_casilla_id", "construction_date_casilla_id",
        # "cutoff_iso"]) — eligibility-conditional advisory: FIRES (ADVISORY
        # shown) when the named amount (Decimal) casilla is strictly positive
        # (a deducción is claimed) AND neither eligibility signal is present —
        # the acquisition-date TEXT casilla holding a date strictly before the
        # cutoff, nor the construction-date TEXT casilla being non-empty. The
        # one no-silent-over-declaration shape the numeric/categorical operators
        # cannot express because its trigger combines a claimed amount with a
        # DATE-threshold eligibility test read from the operator-entered raw
        # text. ADVISORY-only (no BLOCKING_RULE branch). Authored for the
        # Modelo 100 deducción por inversión en vivienda habitual, whose
        # transitional régimen (LIRPF DT 18ª) admits only dwellings acquired
        # before 01-01-2013 (or pre-2013 construction). See the
        # deduccion_requires_adquisicion_before branch in
        # _evaluate_advisory_predicate_fires.
        "deduccion_requires_adquisicion_before",
        # advisory_when_computed_diverges(["declared_id", "computed_id"]) —
        # table-driven-engine-vs-operator-declared discrepancy: FIRES (ADVISORY
        # shown) when the named COMPUTED reference casilla resolves strictly >
        # 0 (the table-driven engine has coverage for the declared activity)
        # AND it differs from the named operator-declared casilla by more than
        # one cent. A zero computed casilla holds trivially (the engine has no
        # table coverage for the declared epígrafe/módulos — nothing to
        # compare against, so no advisory). ADVISORY-only (no BLOCKING_RULE
        # branch is implemented): the computed reference intentionally omits
        # fases 2ª/3ª correcting factors the taxpayer may legitimately claim,
        # so a discrepancy is a prompt to review, not a refusal. Authored for
        # the M131 estimación-objetiva módulos engine (casilla 01 "Suma de
        # rendimientos netos" vs the internal
        # modulos-rendimiento-neto-actividad reference), guarding against a
        # silent under-declaration. See the
        # advisory_when_computed_diverges branch in
        # _evaluate_advisory_predicate_fires.
        "advisory_when_computed_diverges",
        # equals(["lhs_id", "rhs_id"]) — consistency invariant: the two named
        # casillas must hold the same value. Authored for the M303 official
        # Diseño box projections (Stage 2): each numbered box copies a semantic
        # source, so box == source must hold for VERIFICADO_COMPLETO. The
        # projection cannot drift within one evaluation; the predicate's value is
        # catching a future mis-edit (a box re-flipped to manual, or a projection
        # pointed at the wrong source). See the equals branch in
        # _evaluate_predicate_expression.
        "equals",
        "implies_any_nonzero",
        "implies_nonzero",
        "profile_field_required",
        # profile_flag_enabled("profile_field_name") — profile-state advisory:
        # FIRES (ADVISORY shown) iff the named boolean TaxpayerProfile field is
        # true. ADVISORY-only. Authored for the M130 Art. 109 activity-income
        # coverage fact, where the legal 70% test is declared in the
        # profile/deadline layer, not inferred from a casilla-amount ratio.
        "profile_flag_enabled",
        # roll_forward_balances(["closing_id", "opening_id", "applied_id",
        # "base_id"]) — carry-forward stock continuity: the closing balance must
        # reconcile to opening − applied + max(0, −base) within a one-cent
        # tolerance. The arithmetic continuity primitive the predicate language
        # lacked; authored for the Modelo 200 BIN total-pendiente roll-forward
        # (00671 = 00670 − DP200014:00547 + max(0, −DP200014:00552)) and general
        # to any "stock = prior stock − consumed + newly-generated-from-a-signed-
        # base" carry (BIN, pending credits, recargo carryforward). As a
        # BLOCKING_RULE it holds when the balance reconciles; as an ADVISORY it
        # fires when it does not. See the roll_forward_balances branch in
        # _evaluate_predicate_expression / _evaluate_advisory_predicate_fires.
        "roll_forward_balances",
    },
)


class VerificationPredicateOperator(StrEnum):
    """The closed registry-authored verification-predicate operator vocabulary."""

    ADVISORY_WHEN_POSITIVE = "advisory_when_positive"
    ADVISORY_WHEN_RATIO_GE = "advisory_when_ratio_ge"
    ALL_NONZERO = "all_nonzero"
    AT_MOST_ONE_POSITIVE = "at_most_one_positive"
    ANY_NONZERO = "any_nonzero"
    CAP_LE_WHEN_POSITIVE = "cap_le_when_positive"
    CASILLA_EQUALS_IMPLIES_DIVERGES = "casilla_equals_implies_diverges"
    CASILLA_EQUALS_IMPLIES_NONZERO = "casilla_equals_implies_nonzero"
    CASILLA_EQUALS_IMPLIES_PROFILE_FLAG = "casilla_equals_implies_profile_flag"
    DEDUCCION_REQUIRES_ADQUISICION_BEFORE = "deduccion_requires_adquisicion_before"
    ADVISORY_WHEN_COMPUTED_DIVERGES = "advisory_when_computed_diverges"
    EQUALS = "equals"
    IMPLIES_ANY_NONZERO = "implies_any_nonzero"
    IMPLIES_NONZERO = "implies_nonzero"
    PROFILE_FIELD_REQUIRED = "profile_field_required"
    PROFILE_FLAG_ENABLED = "profile_flag_enabled"
    ROLL_FORWARD_BALANCES = "roll_forward_balances"


class VerificationPredicateSyntax(StrEnum):
    """The syntax families accepted by the verification-predicate DSL."""

    CASILLA_LIST = "casilla_list"
    RATIO = "ratio"
    PROFILE_FIELD_REQUIRED = "profile_field_required"
    PROFILE_FLAG_ENABLED = "profile_flag_enabled"
    CASILLA_LITERAL_CASILLA = "casilla_literal_casilla"
    CASILLA_LITERAL_PROFILE_FIELD = "casilla_literal_profile_field"
    CASILLA_LITERAL_CASILLA_PAIR = "casilla_literal_casilla_pair"
    CASILLA_TRIPLE_CUTOFF = "casilla_triple_cutoff"


@dataclass(frozen=True, slots=True)
class VerificationPredicateSpecification:
    """The grammar and casilla-arity contract of one predicate operator."""

    operator: VerificationPredicateOperator
    syntax: VerificationPredicateSyntax
    minimum_casilla_ids: int = 0
    maximum_casilla_ids: int | None = None


@dataclass(frozen=True, slots=True)
class ParsedVerificationPredicate:
    """A syntax-checked verification-predicate expression and its captures.

    Casilla references remain raw text until registry validation resolves them
    against a revision or the runtime validates its hostile-string boundary.
    """

    operator: VerificationPredicateOperator
    arguments: tuple[str, ...]
    casilla_ids: tuple[str, ...] = ()
    literal: str = ""
    threshold: str = ""
    profile_field: str = ""
    applicability_filter: str = ""
    cutoff: str = ""


def _predicate_specification(
    operator: VerificationPredicateOperator,
    syntax: VerificationPredicateSyntax,
    *,
    minimum_casilla_ids: int = 0,
    maximum_casilla_ids: int | None = None,
) -> VerificationPredicateSpecification:
    return VerificationPredicateSpecification(
        operator=operator,
        syntax=syntax,
        minimum_casilla_ids=minimum_casilla_ids,
        maximum_casilla_ids=maximum_casilla_ids,
    )


VERIFICATION_PREDICATE_SPECIFICATIONS: Mapping[
    VerificationPredicateOperator,
    VerificationPredicateSpecification,
] = MappingProxyType(
    {
        VerificationPredicateOperator.ADVISORY_WHEN_POSITIVE: _predicate_specification(
            VerificationPredicateOperator.ADVISORY_WHEN_POSITIVE,
            VerificationPredicateSyntax.CASILLA_LIST,
            minimum_casilla_ids=1,
            maximum_casilla_ids=1,
        ),
        VerificationPredicateOperator.ADVISORY_WHEN_RATIO_GE: _predicate_specification(
            VerificationPredicateOperator.ADVISORY_WHEN_RATIO_GE,
            VerificationPredicateSyntax.RATIO,
            minimum_casilla_ids=2,
            maximum_casilla_ids=2,
        ),
        VerificationPredicateOperator.ALL_NONZERO: _predicate_specification(
            VerificationPredicateOperator.ALL_NONZERO,
            VerificationPredicateSyntax.CASILLA_LIST,
            minimum_casilla_ids=1,
        ),
        VerificationPredicateOperator.AT_MOST_ONE_POSITIVE: _predicate_specification(
            VerificationPredicateOperator.AT_MOST_ONE_POSITIVE,
            VerificationPredicateSyntax.CASILLA_LIST,
            minimum_casilla_ids=2,
        ),
        VerificationPredicateOperator.ANY_NONZERO: _predicate_specification(
            VerificationPredicateOperator.ANY_NONZERO,
            VerificationPredicateSyntax.CASILLA_LIST,
            minimum_casilla_ids=1,
        ),
        VerificationPredicateOperator.CAP_LE_WHEN_POSITIVE: _predicate_specification(
            VerificationPredicateOperator.CAP_LE_WHEN_POSITIVE,
            VerificationPredicateSyntax.CASILLA_LIST,
            minimum_casilla_ids=2,
            maximum_casilla_ids=2,
        ),
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_DIVERGES: _predicate_specification(
            VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_DIVERGES,
            VerificationPredicateSyntax.CASILLA_LITERAL_CASILLA_PAIR,
            minimum_casilla_ids=3,
            maximum_casilla_ids=3,
        ),
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_NONZERO: _predicate_specification(
            VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_NONZERO,
            VerificationPredicateSyntax.CASILLA_LITERAL_CASILLA,
            minimum_casilla_ids=2,
            maximum_casilla_ids=2,
        ),
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_PROFILE_FLAG: _predicate_specification(
            VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_PROFILE_FLAG,
            VerificationPredicateSyntax.CASILLA_LITERAL_PROFILE_FIELD,
            minimum_casilla_ids=1,
            maximum_casilla_ids=1,
        ),
        VerificationPredicateOperator.DEDUCCION_REQUIRES_ADQUISICION_BEFORE: _predicate_specification(
            VerificationPredicateOperator.DEDUCCION_REQUIRES_ADQUISICION_BEFORE,
            VerificationPredicateSyntax.CASILLA_TRIPLE_CUTOFF,
            minimum_casilla_ids=3,
            maximum_casilla_ids=3,
        ),
        VerificationPredicateOperator.ADVISORY_WHEN_COMPUTED_DIVERGES: _predicate_specification(
            VerificationPredicateOperator.ADVISORY_WHEN_COMPUTED_DIVERGES,
            VerificationPredicateSyntax.CASILLA_LIST,
            minimum_casilla_ids=2,
            maximum_casilla_ids=2,
        ),
        VerificationPredicateOperator.EQUALS: _predicate_specification(
            VerificationPredicateOperator.EQUALS,
            VerificationPredicateSyntax.CASILLA_LIST,
            minimum_casilla_ids=2,
            maximum_casilla_ids=2,
        ),
        VerificationPredicateOperator.IMPLIES_ANY_NONZERO: _predicate_specification(
            VerificationPredicateOperator.IMPLIES_ANY_NONZERO,
            VerificationPredicateSyntax.CASILLA_LIST,
            minimum_casilla_ids=2,
        ),
        VerificationPredicateOperator.IMPLIES_NONZERO: _predicate_specification(
            VerificationPredicateOperator.IMPLIES_NONZERO,
            VerificationPredicateSyntax.CASILLA_LIST,
            minimum_casilla_ids=2,
            maximum_casilla_ids=2,
        ),
        VerificationPredicateOperator.PROFILE_FIELD_REQUIRED: _predicate_specification(
            VerificationPredicateOperator.PROFILE_FIELD_REQUIRED,
            VerificationPredicateSyntax.PROFILE_FIELD_REQUIRED,
        ),
        VerificationPredicateOperator.PROFILE_FLAG_ENABLED: _predicate_specification(
            VerificationPredicateOperator.PROFILE_FLAG_ENABLED,
            VerificationPredicateSyntax.PROFILE_FLAG_ENABLED,
        ),
        VerificationPredicateOperator.ROLL_FORWARD_BALANCES: _predicate_specification(
            VerificationPredicateOperator.ROLL_FORWARD_BALANCES,
            VerificationPredicateSyntax.CASILLA_LIST,
            minimum_casilla_ids=4,
            maximum_casilla_ids=4,
        ),
    },
)


_PREDICATE_LIST_PATTERN = _re.compile(r"^(?P<operator>[a-z_]+)\(\[(?P<arguments>[^\]]*)\]\)$")
_RATIO_PATTERN = _re.compile(
    r'^\w+\(\["(?P<numerator>[^"]+)",\s*"(?P<denominator>[^"]+)",\s*"(?P<threshold>[^"]+)"\]\)$',
)
_PROFILE_FIELD_REQUIRED_PATTERN = _re.compile(r'^\w+\("(?P<field>[^"]+)", "(?P<filter>[^"]+)"\)$')
_PROFILE_FLAG_ENABLED_PATTERN = _re.compile(r'^\w+\("(?P<field>[^"]+)"\)$')


def verification_predicate_operator_name(expression: str) -> str | None:
    """Return the leading DSL operator name, or ``None`` when no call begins."""
    stripped = expression.strip()
    paren_idx = stripped.find("(")
    if paren_idx <= 0:
        return None
    return stripped[:paren_idx]


def _predicate_argument_tokens(arguments: str) -> tuple[str, ...]:
    return tuple(token.strip().strip('"').strip("'") for token in arguments.split(",") if token.strip())


@dataclass(frozen=True, slots=True)
class _PredicateListCapture:
    """The positional captures a non-homogeneous list predicate exposes."""

    argument_count: int
    casilla_indices: tuple[int, ...]
    literal_index: int | None = None
    profile_field_index: int | None = None
    cutoff_index: int | None = None


_LIST_PREDICATE_CAPTURES: Mapping[VerificationPredicateSyntax, _PredicateListCapture] = MappingProxyType(
    {
        VerificationPredicateSyntax.CASILLA_LITERAL_CASILLA: _PredicateListCapture(
            argument_count=3,
            casilla_indices=(0, 2),
            literal_index=1,
        ),
        VerificationPredicateSyntax.CASILLA_LITERAL_PROFILE_FIELD: _PredicateListCapture(
            argument_count=3,
            casilla_indices=(0,),
            literal_index=1,
            profile_field_index=2,
        ),
        VerificationPredicateSyntax.CASILLA_LITERAL_CASILLA_PAIR: _PredicateListCapture(
            argument_count=4,
            casilla_indices=(0, 2, 3),
            literal_index=1,
        ),
        VerificationPredicateSyntax.CASILLA_TRIPLE_CUTOFF: _PredicateListCapture(
            argument_count=4,
            casilla_indices=(0, 1, 2),
            cutoff_index=3,
        ),
    },
)


def _parse_list_predicate(
    operator: VerificationPredicateOperator,
    stripped: str,
    syntax: VerificationPredicateSyntax,
) -> ParsedVerificationPredicate | None:
    """Parse a bracketed predicate list, preserving wrong-arity evidence."""
    match = _PREDICATE_LIST_PATTERN.match(stripped)
    if match is None:
        return None
    arguments = _predicate_argument_tokens(match.group("arguments"))
    capture = _LIST_PREDICATE_CAPTURES.get(syntax)
    if capture is None:
        return ParsedVerificationPredicate(operator=operator, arguments=arguments, casilla_ids=arguments)
    if len(arguments) != capture.argument_count:
        return ParsedVerificationPredicate(operator=operator, arguments=arguments)
    literal = arguments[capture.literal_index] if capture.literal_index is not None else ""
    profile_field = arguments[capture.profile_field_index] if capture.profile_field_index is not None else ""
    cutoff = arguments[capture.cutoff_index] if capture.cutoff_index is not None else ""
    return ParsedVerificationPredicate(
        operator=operator,
        arguments=arguments,
        casilla_ids=tuple(arguments[index] for index in capture.casilla_indices),
        literal=literal,
        profile_field=profile_field,
        cutoff=cutoff,
    )


def _parse_ratio_predicate(
    operator: VerificationPredicateOperator,
    stripped: str,
    _syntax: VerificationPredicateSyntax,
) -> ParsedVerificationPredicate | None:
    """Parse a numerator, denominator, threshold predicate expression."""
    match = _RATIO_PATTERN.match(stripped)
    if match is None:
        return None
    numerator = match.group("numerator")
    denominator = match.group("denominator")
    threshold = match.group("threshold")
    return ParsedVerificationPredicate(
        operator=operator,
        arguments=(numerator, denominator, threshold),
        casilla_ids=(numerator, denominator),
        threshold=threshold,
    )


def _parse_profile_field_required_predicate(
    operator: VerificationPredicateOperator,
    stripped: str,
    _syntax: VerificationPredicateSyntax,
) -> ParsedVerificationPredicate | None:
    """Parse a profile-field applicability predicate expression."""
    match = _PROFILE_FIELD_REQUIRED_PATTERN.match(stripped)
    if match is None:
        return None
    field = match.group("field")
    applicability_filter = match.group("filter")
    return ParsedVerificationPredicate(
        operator=operator,
        arguments=(field, applicability_filter),
        profile_field=field,
        applicability_filter=applicability_filter,
    )


def _parse_profile_flag_enabled_predicate(
    operator: VerificationPredicateOperator,
    stripped: str,
    _syntax: VerificationPredicateSyntax,
) -> ParsedVerificationPredicate | None:
    """Parse a profile-flag advisory predicate expression."""
    match = _PROFILE_FLAG_ENABLED_PATTERN.match(stripped)
    if match is None:
        return None
    field = match.group("field")
    return ParsedVerificationPredicate(operator=operator, arguments=(field,), profile_field=field)


_PredicateExpressionParser = Callable[
    [VerificationPredicateOperator, str, VerificationPredicateSyntax],
    ParsedVerificationPredicate | None,
]

_PREDICATE_EXPRESSION_PARSERS: Mapping[VerificationPredicateSyntax, _PredicateExpressionParser] = MappingProxyType(
    {
        VerificationPredicateSyntax.CASILLA_LIST: _parse_list_predicate,
        VerificationPredicateSyntax.RATIO: _parse_ratio_predicate,
        VerificationPredicateSyntax.PROFILE_FIELD_REQUIRED: _parse_profile_field_required_predicate,
        VerificationPredicateSyntax.PROFILE_FLAG_ENABLED: _parse_profile_flag_enabled_predicate,
        VerificationPredicateSyntax.CASILLA_LITERAL_CASILLA: _parse_list_predicate,
        VerificationPredicateSyntax.CASILLA_LITERAL_PROFILE_FIELD: _parse_list_predicate,
        VerificationPredicateSyntax.CASILLA_LITERAL_CASILLA_PAIR: _parse_list_predicate,
        VerificationPredicateSyntax.CASILLA_TRIPLE_CUTOFF: _parse_list_predicate,
    },
)


def parse_verification_predicate_expression(expression: str) -> ParsedVerificationPredicate | None:
    """Parse one runtime-supported verification-predicate DSL expression.

    ``None`` means the expression is unknown or malformed. Registry validation
    turns that state into an authoring-time refusal; the runtime retains its
    defensive fallback for anything that bypasses registry validation.
    """
    operator_name = verification_predicate_operator_name(expression)
    if operator_name is None:
        return None
    try:
        operator = VerificationPredicateOperator(operator_name)
    except ValueError:
        return None
    specification = VERIFICATION_PREDICATE_SPECIFICATIONS[operator]
    stripped = expression.strip()
    parser = _PREDICATE_EXPRESSION_PARSERS.get(specification.syntax)
    if parser is None:
        raise AssertionError(f"unsupported verification predicate syntax {specification.syntax!r}")
    return parser(operator, stripped, specification.syntax)


class VerificationPredicateDefinition(RegistryModel):
    """A cross-casilla invariant that must hold for VERIFICADO_COMPLETO to be granted.

    Layer 2 of the hybrid verification strategy.  Layer 1 handles
    single-casilla required gates via ``CasillaDefinition.required``; this
    class handles multi-casilla structural invariants (e.g. ``if ingresos
    is non-zero then rendimiento neto must also be present``).

    ``expression`` uses a minimal predicate DSL:

    - ``advisory_when_positive(["casilla_id"])`` — single-casilla positive
      advisory: FIRES (ADVISORY shown) iff the one named casilla value is
      strictly ``> 0``. A zero or absent value holds trivially (no advisory).
      ADVISORY-only: no ``BLOCKING_RULE`` branch is implemented (a positive box
      is not itself an error — the advisory only prompts an operator review).
      Authored for the Modelo 100 anualidades por alimentos a favor de los
      hijos (casilla 0527), whose separate-escala treatment (LIRPF art. 64 for
      the state scale, art. 75 for the autonomic scale) is applied in the
      current cuota chain without the statutory mínimo-por-descendientes
      gating, so a payer declaring anualidades may be under-taxed; the advisory
      surfaces a non-blocking prompt to review the cuota pending the full
      separate-escala modelling, per no-silent-under-declaration. Routes through
      the generic single-casilla-list validation (exact arity 1) at registry
      build. See the ``advisory_when_positive`` branch in
      ``_evaluate_advisory_predicate_fires``.
    - ``all_nonzero(["id1", "id2", ...])`` — every listed casilla value must
      be non-zero (i.e. the filing invariant requires them all to be present
      and non-zero simultaneously).
    - ``any_nonzero(["id1", "id2", ...])`` — at least one listed casilla
      value must be non-zero.
    - ``at_most_one_positive(["id1", "id2", ...])`` — no more than one
      listed casilla may be strictly positive. Missing values read as zero.
      Authored for alternative result lanes such as Modelo 202 art. 40.3
      claves 18/26, where the downstream formula uses both zero-default
      lanes but the official instruction permits only one positive lane.
    - ``cap_le_when_positive(["limited_id", "ceiling_id"])`` — when the
      ceiling casilla is strictly positive, the limited casilla MUST NOT
      exceed the ceiling, enforcing AEAT cap rules like Modelo 131 C11 ≤ C10
      and Modelo 130 C15 ≤ C14 ("en ningún caso podrá
      figurar... un importe superior a la cantidad positiva consignada").
      Predicate holds when ceiling ≤ 0; the cap applies only when the
      operator's gross liability is positive.
    - ``implies_nonzero(["antecedent_id", "consequent_id"])`` — material
      implication with a strictly-positive antecedent test: predicate
      holds iff ``casilla_values[antecedent] <= 0`` OR
      ``casilla_values[consequent] != 0``. Authored for AEAT cuota-mínima
      invariants of the shape "cuando C01 sea positivo, C07 debe ser
      distinta de cero" (M131 EO cuota mínima, M130/M303 régimen
      simplificado analogues). The antecedent is strictly-positive rather
      than non-zero to mirror the regulatory phrasing; a casilla with a
      negative value does not trigger the implication. A missing
      consequent value evaluates to ``Decimal(0)`` and therefore
      violates the predicate when the antecedent is positive.
    - ``implies_any_nonzero(["antecedent_id", "c1_id", "c2_id", ...])`` —
      the N-consequent generalisation of ``implies_nonzero``: predicate
      holds iff ``casilla_values[antecedent] <= 0`` OR **at least one**
      listed consequent is non-zero. Authored for the Modelo 303
      official-Diseño contradiction where a computed total
      (``iva.cuota-devengada-total``, ``iva.cuota-deducible-total``) is
      strictly positive but **every** constituent official numbered box
      (the dr303 base/cuota tranche cells the operator transcribes to the
      AEAT sede) is still zero — a silent under-declaration the verify
      gate would otherwise grant with zero findings. ADVISORY (the
      official numbered boxes are an operator-entered layer the calculate
      path does not auto-populate, so the contradiction is surfaced as a
      non-blocking alert rather than a refusal). The first consequent
      slot onward is the constituent set; a single consequent reduces to
      ``implies_nonzero``.
    - ``profile_field_required("profile_field_name", "applicability_filter")``
      — profile-state-aware conditional non-zero requirement. Returns
      ``True`` (predicate holds) when the named ``applicability_filter``
      evaluates ``False`` against the TaxpayerProfile, OR when the named
      profile field is present and non-empty. Returns ``False``
      (predicate violated) only when the applicability filter activates
      AND the profile field is ``None`` / empty. A sibling of
      ``implies_nonzero`` — the conditional non-zero requirement is the
      same semantic shape, but the gating signal is profile state (e.g.
      fiscal_residency, ue_eee_status) rather than another casilla value.
      First use site: M210 representante-fiscal gate (TRLIRNR Art 10).
    - ``profile_flag_enabled("profile_field_name")`` — profile-state
      advisory: predicate FIRES (ADVISORY shown) iff the named boolean
      TaxpayerProfile field is true. ADVISORY-only. Authored for the Modelo
      130 Art. 109 activity-income coverage profile fact: the legal 70%
      threshold is an income-coverage/profile fact, not a ratio between
      retenciones amount and gross income casillas.
    - ``casilla_equals_implies_nonzero(["antecedent_casilla_id", "literal",
      "consequent_casilla_id"])`` — categorical-conditional material
      implication: predicate FIRES (ADVISORY shown) iff the operator-entered
      raw text value of the named antecedent (TEXT) casilla equals the
      literal AND the named consequent (Decimal) casilla is zero. A missing
      or differing antecedent value holds trivially (no advisory), same
      convention as the numeric-antecedent operators. ADVISORY-only: no
      ``BLOCKING_RULE`` branch is implemented, mirroring the existing
      ``equals`` (BLOCKING-only) / ``advisory_when_ratio_ge`` (ADVISORY-only)
      asymmetry. Authored for the M210 IRNR inmobiliaria branch, the one
      shape ``implies_nonzero`` cannot express because its trigger is a
      categorical equality (``tipo_renta == "inmobiliaria"``) rather than
      a numeric antecedent, guarding against a silent under-declaration.
    - ``deduccion_requires_adquisicion_before(["amount_casilla_id",
      "acquisition_date_casilla_id", "construction_date_casilla_id",
      "cutoff_iso"])`` — eligibility-conditional advisory: FIRES (ADVISORY
      shown) iff the named amount (Decimal) casilla is strictly positive (a
      deducción is claimed) AND no pre-cutoff eligibility signal is recorded,
      i.e. the acquisition-date TEXT casilla does NOT hold a date strictly
      before ``cutoff_iso`` AND the construction-date TEXT casilla is empty. A
      claimed amount with a pre-cutoff acquisition date, a non-empty
      construction date, or a zero/absent amount holds trivially (no advisory).
      ADVISORY-only: no ``BLOCKING_RULE`` branch is implemented, mirroring the
      ``casilla_equals_implies_nonzero`` / ``advisory_when_ratio_ge``
      ADVISORY-only convention. Authored for the Modelo 100 deducción por
      inversión en vivienda habitual, whose transitional régimen (LIRPF DT 18ª)
      admits only dwellings acquired before 01-01-2013 (or pre-2013
      construction); a post-2013 acquirer claiming the abolished deducción
      would silently over-declare the deducción (under-declare tax), the
      no-silent-under-declaration shape neither ``implies_nonzero`` (numeric
      antecedent) nor ``casilla_equals_implies_nonzero`` (categorical text
      equality) can express because its trigger is a DATE threshold.
    - ``casilla_equals_implies_diverges(["antecedent_casilla_id", "literal",
      "casilla_a_id", "casilla_b_id"])`` — categorical-conditional divergence
      check: predicate FIRES (ADVISORY shown) iff the operator-entered raw
      text value of the named antecedent (TEXT) casilla equals the literal
      AND the two named (Decimal) casillas differ by more than one cent. A
      missing or differing antecedent value, or two casillas within a cent of
      each other, holds trivially (no advisory). Sibling of
      ``casilla_equals_implies_nonzero`` (that operator's consequent test is
      "== 0"; this operator's is "casilla_a != casilla_b"). ADVISORY-only: no
      ``BLOCKING_RULE`` branch is implemented, mirroring the
      ``casilla_equals_implies_nonzero`` / ``advisory_when_computed_diverges``
      ADVISORY-only convention. Authored for the M131/M100 estimación-objetiva
      índice corrector de exceso (b.3): Orden HAC/1347/2024 Anexo II
      instrucción 2.3 declares the índice corrector de exceso INCOMPATIBLE
      with the índices correctores especiales (a.2 autotaxi, a.4 transporte de
      mercancías/mudanzas) for the activities that carry both — a
      no-silent-under-declaration shape neither ``implies_nonzero`` (numeric
      antecedent) nor ``advisory_when_computed_diverges`` (no categorical
      gate) can express because the trigger combines a categorical epígrafe
      equality with a Decimal-pair divergence.
    """

    predicate_id: str = Field(min_length=1, max_length=128)
    legal_refs: LegalRefs
    expression: str = Field(min_length=1, max_length=512)
    finding_kind: Literal["BLOCKING_RULE", "ADVISORY"] = "BLOCKING_RULE"
