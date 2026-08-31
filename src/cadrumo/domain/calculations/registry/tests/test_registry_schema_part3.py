"""Registry validation of verification expectations and verification predicates.

Split from ``test_registry_schema_part2`` when that module crossed its size
ceiling. The cut is thematic rather than positional: this module holds the
whole ``_schema_verification`` surface -- the field validation of
:class:`VerificationExpectationDefinition` and the operator-by-operator
validation of :class:`VerificationPredicateDefinition` -- and part2 keeps the
concerns it never shared with them (extraction profiles, application and
communication links, export fields, dispatch tables, deadline windows and
keyed-bracket parameter tables).

That boundary also repairs a split concern rather than creating one. The
predicate-operator cases had drifted into two separate regions of part2, with
the ``advisory_when_ratio_ge`` family sitting at the end of the file, far from
the ``advisory_when_positive`` cases it is a direct sibling of. Both families
are adjacent here.

Each predicate operator is covered in the same shape: its malformed forms are
refused, and where a committed revision uses the operator for real, that
revision is asserted to still validate -- so a tightened rule that would reject
shipped registry data fails here rather than at a taxpayer's calculation.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.resources._boundary import bundled_path
from .._validate import RegistryValidator
from ..errors import RegistryValidationError
from ..schema_verification import VerificationExpectationDefinition, VerificationPredicateDefinition
from ._registry_schema_support import _NUMERIC_CASILLA_01, _committed_modelo, _with_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_verification_expectation_rejects_negative_tolerance() -> None:
    with pytest.raises(ValidationError, match="tolerance"):
        VerificationExpectationDefinition(
            id="test.negative-tolerance",
            computed_casilla_ids=(_NUMERIC_CASILLA_01,),
            tolerance=Decimal("-0.01"),
            rounding="money-2",
            min_coverage=Decimal("1"),
            discrepancy_causes=("rounding",),
            legal_refs=("ley-35-2006:art-1",),
            source_refs=("aeat-dr-130-2019-v12",),
        )


def test_verification_expectation_accepts_zero_tolerance() -> None:
    expectation = VerificationExpectationDefinition(
        id="test.zero-tolerance",
        computed_casilla_ids=(_NUMERIC_CASILLA_01,),
        tolerance=Decimal("0"),
        rounding="money-2",
        min_coverage=Decimal("1"),
        discrepancy_causes=("rounding",),
        legal_refs=("ley-35-2006:art-1",),
        source_refs=("aeat-dr-130-2019-v12",),
    )

    assert expectation.tolerance == Decimal("0")


def test_validator_rejects_verification_predicate_with_unknown_operator() -> None:
    """Predicate with an unknown DSL operator must fail at registry-load.

    The runtime DSL evaluator falls through to ``return True`` for any
    unrecognised expression — silent-pass is the documented behaviour
    so unknown DSL extensions don't block. That same behaviour means
    a typo like ``cap_lt_when_positive`` for ``cap_le_when_positive``
    silently passes the predicate gate and the cap rule is lost
    without diagnostic.

    The predicate hardening rejects unknown operators at registry-load
    time. The known set is enumerated in
    ``_validate_surfaces._KNOWN_VERIFICATION_PREDICATE_OPERATORS``:
    ``all_nonzero``, ``any_nonzero``, ``cap_le_when_positive``.
    Typos are caught before any calculation runs.
    """

    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    typo_predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-typo-predicate",
        legal_refs=("rd-439-2007:art-110",),
        expression='cap_lt_when_positive(["15", "14"])',  # typo: lt instead of le
        finding_kind="BLOCKING_RULE",
    )
    mutated = revision.model_copy(
        update={"verification_predicates": (*revision.verification_predicates, typo_predicate)},
    )

    with pytest.raises(RegistryValidationError, match="unknown operator 'cap_lt_when_positive'"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_roll_forward_balances_with_wrong_arity() -> None:
    """A roll_forward_balances predicate must name exactly four casilla ids.

    The runtime evaluator's bad-arity branch returns None → treated as holding
    (BLOCKING) / never firing (ADVISORY), so a malformed continuity predicate
    would silently do nothing. The authoring-time validator rejects it at
    registry load. Uses existing M130 casillas (01/02/03) so the failure is the
    arity, not an unknown-casilla reference.
    """

    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    bad_arity = VerificationPredicateDefinition(
        predicate_id="modelo-130-bad-roll-forward",
        legal_refs=("rd-439-2007:art-110",),
        expression='roll_forward_balances(["01", "02", "03"])',  # three ids; needs four
        finding_kind="ADVISORY",
    )
    mutated = revision.model_copy(
        update={"verification_predicates": (*revision.verification_predicates, bad_arity)},
    )

    with pytest.raises(RegistryValidationError, match="must name exactly four casilla ids"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_verification_predicate_unknown_casilla_refs() -> None:
    """Every casilla-list predicate operator must resolve ids against the revision."""

    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    cases = (
        ("all_nonzero", 'all_nonzero(["01", "missing-casilla"])'),
        ("at_most_one_positive", 'at_most_one_positive(["01", "missing-casilla"])'),
        ("any_nonzero", 'any_nonzero(["01", "missing-casilla"])'),
        ("cap_le_when_positive", 'cap_le_when_positive(["15", "missing-casilla"])'),
        ("equals", 'equals(["01", "missing-casilla"])'),
        ("implies_nonzero", 'implies_nonzero(["01", "missing-casilla"])'),
        ("implies_any_nonzero", 'implies_any_nonzero(["01", "02", "missing-casilla"])'),
        ("roll_forward_balances", 'roll_forward_balances(["01", "02", "03", "missing-casilla"])'),
    )
    validator = RegistryValidator(catalogues, source_root=bundled_path())
    for operator_name, expression in cases:
        predicate = VerificationPredicateDefinition(
            predicate_id=f"modelo-130-{operator_name}-missing-casilla",
            legal_refs=("rd-439-2007:art-110",),
            expression=expression,
            finding_kind="ADVISORY",
        )
        mutated = revision.model_copy(
            update={"verification_predicates": (*revision.verification_predicates, predicate)},
        )

        with pytest.raises(
            RegistryValidationError,
            match=rf"{operator_name} references unknown casilla 'missing-casilla'",
        ):
            validator.validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_known_verification_predicate_with_malformed_casilla_list() -> None:
    """Known operators must use the parseable casilla-list form, not silent-pass syntax."""

    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-malformed-any-nonzero",
        legal_refs=("rd-439-2007:art-110",),
        expression='any_nonzero("01")',
        finding_kind="ADVISORY",
    )
    mutated = revision.model_copy(
        update={"verification_predicates": (*revision.verification_predicates, predicate)},
    )

    with pytest.raises(RegistryValidationError, match=r"any_nonzero expression .* is malformed"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_verification_predicate_with_malformed_expression() -> None:
    """Predicate whose expression is not a parseable DSL call fails."""

    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    malformed_predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-malformed-predicate",
        legal_refs=("rd-439-2007:art-110",),
        expression="just a string with no call shape",
        finding_kind="BLOCKING_RULE",
    )
    mutated = revision.model_copy(
        update={"verification_predicates": (*revision.verification_predicates, malformed_predicate)},
    )

    with pytest.raises(RegistryValidationError, match="not a recognised DSL call"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_accepts_known_verification_predicate_operators() -> None:
    """The cap_le_when_positive predicate declared by the registry must pass.

    Pins that the committed M130 cap predicate
    (modelo-130-c15-cap-by-c14, expression
    cap_le_when_positive(["15", "14"])) validates cleanly. A
    future operator-set reduction that drops cap_le_when_positive
    from the known set would surface here, not at runtime.
    """

    modelo, catalogues = _committed_modelo("130")
    # No mutation — committed M130 carries the predicate.
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_validator_rejects_casilla_equals_implies_nonzero_malformed_m130_predicates() -> None:
    """M130 categorical-conditional predicate authoring errors are rejected."""

    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    validator = RegistryValidator(catalogues, source_root=bundled_path())
    cases = (
        (
            "bad-arity",
            'casilla_equals_implies_nonzero(["01", "07"])',
            "must name exactly three tokens",
        ),
        (
            "unknown-antecedent",
            'casilla_equals_implies_nonzero(["missing-casilla", "general", "07"])',
            "unknown antecedent casilla 'missing-casilla'",
        ),
        (
            "unknown-consequent",
            'casilla_equals_implies_nonzero(["01", "general", "missing-casilla"])',
            "unknown consequent casilla 'missing-casilla'",
        ),
        (
            "empty-literal",
            'casilla_equals_implies_nonzero(["01", "", "07"])',
            "literal must be non-empty",
        ),
        (
            "non-text-antecedent",
            'casilla_equals_implies_nonzero(["01", "general", "07"])',
            r"antecedent casilla '01' must be a text-family casilla",
        ),
    )
    for case_id, expression, match in cases:
        predicate = VerificationPredicateDefinition(
            predicate_id=f"modelo-130-casilla-equals-implies-nonzero-{case_id}",
            legal_refs=("rd-439-2007:art-110",),
            expression=expression,
            finding_kind="ADVISORY",
        )
        mutated = revision.model_copy(
            update={"verification_predicates": (*revision.verification_predicates, predicate)},
        )

        try:
            with pytest.raises(RegistryValidationError, match=match):
                validator.validate_modelo(_with_revision(modelo, mutated))
        except AssertionError as exc:
            raise AssertionError(case_id) from exc


def test_validator_rejects_casilla_equals_implies_nonzero_text_consequent() -> None:
    """The consequent must resolve through the Decimal casilla-values projection."""

    modelo, catalogues = _committed_modelo("210")
    revision = modelo.revisions["2025"]
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-210-casilla-equals-implies-nonzero-text-consequent",
        legal_refs=("trlirnr-rdleg-5-2004:art-24",),
        expression='casilla_equals_implies_nonzero(["tipo_renta", "inmobiliaria", "tipo_renta"])',
        finding_kind="ADVISORY",
    )
    mutated = revision.model_copy(
        update={"verification_predicates": (*revision.verification_predicates, predicate)},
    )

    with pytest.raises(
        RegistryValidationError,
        match=r"consequent casilla 'tipo_renta' must be a numeric casilla, not a text-family one",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_accepts_committed_m210_casilla_equals_implies_nonzero_predicate() -> None:
    """The committed M210 inmobiliaria casilla_equals_implies_nonzero predicate validates cleanly.

    Pins that the registry-build validator accepts the new operator's mixed
    casilla-id/literal/casilla-id argument shape for the predicate the
    m210 categorical-conditional predicate decision authored
    (modelo-210-2025-inmobiliaria-implica-base-imponible, expression
    casilla_equals_implies_nonzero(["tipo_renta", "inmobiliaria",
    "base_imponible"])). A future operator-set reduction that drops
    casilla_equals_implies_nonzero from the known set would surface here.
    """

    modelo, catalogues = _committed_modelo("210")
    revision = modelo.revisions["2025"]
    predicate = next(
        p
        for p in revision.verification_predicates
        if p.predicate_id == "modelo-210-2025-inmobiliaria-implica-base-imponible"
    )
    assert predicate.expression == 'casilla_equals_implies_nonzero(["tipo_renta", "inmobiliaria", "base_imponible"])'
    assert predicate.finding_kind == "ADVISORY"

    # No mutation — committed M210 carries the predicate.
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_validator_rejects_deduccion_requires_adquisicion_before_malformed_m130_predicates() -> None:
    """M130 vivienda eligibility predicate authoring errors are rejected."""

    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    validator = RegistryValidator(catalogues, source_root=bundled_path())
    cases = (
        (
            "bad-arity",
            'deduccion_requires_adquisicion_before(["01", "07", "07"])',
            "must name exactly four tokens",
        ),
        (
            "unknown-amount",
            'deduccion_requires_adquisicion_before(["missing-casilla", "01", "07", "2013-01-01"])',
            "unknown amount casilla 'missing-casilla'",
        ),
        (
            "non-text-date",
            'deduccion_requires_adquisicion_before(["01", "07", "07", "2013-01-01"])',
            r"acquisition-date casilla '07' must carry a parseable date",
        ),
        (
            "bad-cutoff",
            'deduccion_requires_adquisicion_before(["01", "07", "07", "not-a-date"])',
            "must be an ISO date literal",
        ),
    )
    for case_id, expression, match in cases:
        predicate = VerificationPredicateDefinition(
            predicate_id=f"modelo-130-deduccion-requires-adquisicion-before-{case_id}",
            legal_refs=("rd-439-2007:art-110",),
            expression=expression,
            finding_kind="ADVISORY",
        )
        mutated = revision.model_copy(
            update={"verification_predicates": (*revision.verification_predicates, predicate)},
        )

        try:
            with pytest.raises(RegistryValidationError, match=match):
                validator.validate_modelo(_with_revision(modelo, mutated))
        except AssertionError as exc:
            raise AssertionError(case_id) from exc


def test_validator_accepts_committed_m100_deduccion_requires_adquisicion_before_predicate() -> None:
    """The committed M100 vivienda-habitual eligibility predicate validates cleanly.

    Pins that the registry-build validator accepts the operator's mixed
    casilla-id/date-literal argument shape for the predicate shipped on the
    2024 and 2025 M100 revisions (LIRPF DT 18ª eligibility advisory). A future
    operator-set reduction that drops deduccion_requires_adquisicion_before
    from the known set would surface here.
    """

    modelo, catalogues = _committed_modelo("100")
    predicate = next(
        p
        for p in modelo.revisions["2024"].verification_predicates
        if p.predicate_id == "modelo-100-2024-deduccion-vivienda-habitual-requiere-adquisicion-anterior-2013"
    )
    assert predicate.expression == 'deduccion_requires_adquisicion_before(["0547", "0708", "0690", "2013-01-01"])'
    assert predicate.finding_kind == "ADVISORY"

    # No mutation — committed M100 carries the predicate.
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_validator_rejects_advisory_when_positive_malformed_m130_predicates() -> None:
    """M130 single-casilla positive advisory authoring errors are rejected."""

    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    validator = RegistryValidator(catalogues, source_root=bundled_path())
    cases = (
        ("bad-arity", 'advisory_when_positive(["01", "07"])', "must name exactly 1 casilla ids"),
        (
            "unknown-casilla",
            'advisory_when_positive(["missing-casilla"])',
            "references unknown casilla 'missing-casilla'",
        ),
    )
    for case_id, expression, match in cases:
        predicate = VerificationPredicateDefinition(
            predicate_id=f"modelo-130-advisory-when-positive-{case_id}",
            legal_refs=("rd-439-2007:art-110",),
            expression=expression,
            finding_kind="ADVISORY",
        )
        mutated = revision.model_copy(
            update={"verification_predicates": (*revision.verification_predicates, predicate)},
        )

        try:
            with pytest.raises(RegistryValidationError, match=match):
                validator.validate_modelo(_with_revision(modelo, mutated))
        except AssertionError as exc:
            raise AssertionError(case_id) from exc


def test_committed_m100_anualidades_advisory_retired_after_separate_escala_compute() -> None:
    """The interim M100 anualidades cuota-review advisory is retired on 2024/2025.

    The LIRPF art. 64 / art. 75 anualidades separate-escala détermination now
    computes the correct cuota (escala(0527)+escala(0505-0527) minus
    escala(mínimo+1.980), floored at 0), superseding the interim
    advisory_when_positive(["0527"]) safeguard. Pins that the predicate is gone
    from both revisions so it cannot silently re-appear alongside the compute,
    and that the registry still validates cleanly without it.
    """

    modelo, catalogues = _committed_modelo("100")
    for year in ("2024", "2025"):
        predicate_ids = {p.predicate_id for p in modelo.revisions[year].verification_predicates}
        assert f"modelo-100-{year}-anualidades-alimentos-hijos-revisar-cuota-escala-separada" not in predicate_ids, (
            f"the interim anualidades advisory must stay retired on the {year} revision now the compute has landed"
        )

    # The committed M100 revisions validate cleanly with the advisory retired.
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


@pytest.mark.parametrize(
    ("threshold", "why"),
    (
        pytest.param("Infinity", "compares False to every ratio: the advisory can never fire", id="infinity"),
        pytest.param("NaN", "builds without raising, then raises at the comparison", id="nan"),
        pytest.param("1e5", "scientific notation is not how a registry threshold is written", id="scientific"),
        pytest.param("+1", "a leading plus is not part of the canonical grammar", id="leading-plus"),
        pytest.param("1_000", "an underscore separator is Python syntax, not a written number", id="underscore"),
        pytest.param("nonsense", "not a number at all", id="not-numeric"),
    ),
)
def test_validator_rejects_advisory_when_ratio_ge_unreadable_threshold(threshold: str, why: str) -> None:
    """A ratio advisory must carry a plain decimal threshold, refused at registry load.

    The runtime builds this literal with a bare ``Decimal`` and compares it, and
    a bare ``Decimal`` accepts more than a written number: ``Infinity`` compares
    ``False`` to every ratio, so the advisory becomes permanently silent, and
    ``NaN`` builds cleanly and then raises at ``>=``. An advisory exists to warn
    about under-declaration, so one that cannot fire is worse than absent -- it
    reads as a checked box. Refusing at build means a registry cannot ship one.
    """

    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-ratio-bad-threshold",
        legal_refs=("rd-439-2007:art-110",),
        expression=f'advisory_when_ratio_ge(["01", "02", "{threshold}"])',
        finding_kind="ADVISORY",
    )
    mutated = revision.model_copy(
        update={"verification_predicates": (*revision.verification_predicates, predicate)},
    )

    with pytest.raises(RegistryValidationError, match="is not a plain decimal number") as caught:
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))

    assert threshold in str(caught.value), f"the refusal must echo the rejected threshold ({why})"


@pytest.mark.parametrize(
    "threshold",
    (
        pytest.param("0.5", id="one-decimal"),
        pytest.param("0.333", id="three-decimal-ratio"),
        pytest.param("1", id="integer"),
        pytest.param("0", id="zero"),
    ),
)
def test_validator_accepts_advisory_when_ratio_ge_plain_threshold(threshold: str) -> None:
    """The refusal is narrow: an ordinary written ratio still builds.

    ``0.333`` is the case that matters. A ratio threshold is not a euro amount,
    so a two-fractional-digit cap would refuse legitimate thresholds; the
    canonical grammar is applied here for its SHAPE only, with fraction digits
    unconstrained.
    """

    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-ratio-ok-threshold",
        legal_refs=("rd-439-2007:art-110",),
        expression=f'advisory_when_ratio_ge(["01", "02", "{threshold}"])',
        finding_kind="ADVISORY",
    )
    mutated = revision.model_copy(
        update={"verification_predicates": (*revision.verification_predicates, predicate)},
    )

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_advisory_when_ratio_ge_unknown_casilla() -> None:
    """Both ratio operands must resolve against the revision, like every other operator."""

    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-ratio-unknown-casilla",
        legal_refs=("rd-439-2007:art-110",),
        expression='advisory_when_ratio_ge(["01", "missing-casilla", "0.5"])',
        finding_kind="ADVISORY",
    )
    mutated = revision.model_copy(
        update={"verification_predicates": (*revision.verification_predicates, predicate)},
    )

    with pytest.raises(RegistryValidationError, match="unknown denominator casilla 'missing-casilla'"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_advisory_when_ratio_ge_wrong_arity() -> None:
    """Three tokens exactly: numerator, denominator, threshold."""

    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-ratio-bad-arity",
        legal_refs=("rd-439-2007:art-110",),
        expression='advisory_when_ratio_ge(["01", "02"])',  # threshold missing
        finding_kind="ADVISORY",
    )
    mutated = revision.model_copy(
        update={"verification_predicates": (*revision.verification_predicates, predicate)},
    )

    with pytest.raises(RegistryValidationError, match=r"advisory_when_ratio_ge expression.*is malformed"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))
