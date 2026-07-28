"""What a filed return is reconciled against, what must hold for it, and the folds.

Verification asks two questions of a filed modelo. First, do the numbers AEAT
received agree with the numbers this application computes? A revision answers
that by declaring verification *expectations*, and this module owns both halves
of that answer — the per-expectation declaration and the snapshot-wide fold the
application verification surface actually consumes. Second, do the filing's
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

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from ._errors import RegistryValidationError
from ._ids import CasillaId, VerificationExpectationId
from ._schema_base import LegalRefs, RegistryModel, SourceRefs
from ._schema_scalars import DecimalValue

__all__ = [
    "KNOWN_PROFILE_FLAG_ADVISORY_FIELDS",
    "KNOWN_VERIFICATION_PREDICATE_OPERATORS",
    "RegistryVerificationPolicy",
    "VerificationExpectationDefinition",
    "VerificationPredicateDefinition",
]


class VerificationExpectationDefinition(RegistryModel):
    id: VerificationExpectationId
    computed_casilla_ids: tuple[CasillaId, ...]
    reconcile_when_present_casilla_ids: tuple[CasillaId, ...] = ()
    externally_grounded_casilla_ids: tuple[CasillaId, ...] = ()
    reconciliation_total_casilla_ids: Mapping[Literal["ingresar", "devolver"], CasillaId] = Field(
        default_factory=dict,
    )
    tolerance: DecimalValue
    rounding: str
    min_coverage: DecimalValue = Field(ge=Decimal("0"), le=Decimal("1"))
    discrepancy_causes: tuple[
        Literal["extraction_unreliable", "unmodelled_rule", "rounding", "correctness_divergence"],
        ...,
    ] = Field(min_length=1)
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


@dataclass(frozen=True, slots=True)
class RegistryVerificationPolicy:
    """Folded verification policy across a snapshot's verification expectations.

    Owns the registry-grounded projection (union of computed casilla ids, the
    union of reconcile-when-present casilla ids, the strictest tolerance, the
    strictest coverage floor) so the application verification surface consumes
    it rather than re-deriving the fold.

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
    computed_casilla_ids: frozenset[CasillaId]
    reconcile_when_present_casilla_ids: frozenset[CasillaId]
    externally_grounded_casilla_ids: frozenset[CasillaId]
    tolerance: Decimal
    min_coverage: Decimal


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
