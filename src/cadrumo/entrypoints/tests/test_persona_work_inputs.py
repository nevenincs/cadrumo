"""A persona's work inputs are entered through the declaration edit before the return's first calculation.

The registry decides what may be given: a casilla the return's edition supplies
itself is refused, and so is a given casilla an expectation of the same return
names by a registry identity. Real behaviour throughout: the bundled authority,
a materialised persona and the production registered operations.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from decimal import Decimal

import pytest

from ...application.modelo.operation_shared import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from ...application.modelo.work_calculation_contracts import (
    ModeloWorkCalculatePublicResultV3,
    ModeloWorkCalculateRequest,
)
from ...application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateProjection,
    ModeloWorkCreateRequest,
    ModeloWorkCreateSuccess,
)
from ...application.operations.public_period import PublicPeriod
from ...application.operations.public_scalar import restore_scalar
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...tests.persona_types import Expectations, ExpectedValue, Persona, WorkInput, YearEnvelope, YearToken
from ...tests.personas import read_persona
from .persona_materialisation import materialised_persona
from .persona_operations import run_operation, settle_operation
from .persona_work_inputs import WorkInputError, check_work_inputs, resolved_casillas
from .persona_world import (
    PERSONA_ACTOR,
    MaterialisedPersona,
    PersonaMaterialisationError,
    PersonaWorld,
    ReplayScope,
    year_envelope,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PERSONA = "sociedad-limitada"
#: The refusal the calculation raises for a Modelo 200 with ledger rows and no accounting result.
_ACCOUNTING_RESULT_REFUSAL = r"modelo\.work\.calculate settled refused \(REFUSED_MODELO_AGGREGATION_INPUT_CONFLICT\)"


@pytest.fixture(scope="module")
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as opened:
        yield opened


@pytest.fixture(scope="module")
def envelope(operation: PinnedAuthorityOperation) -> YearEnvelope:
    return year_envelope(operation)


@pytest.fixture(scope="module")
def persona(envelope: YearEnvelope) -> Persona:
    return read_persona(_PERSONA, envelope=envelope)


def _given(persona: Persona) -> WorkInput:
    (entry,) = persona.work_inputs
    return entry


def _edition(persona: Persona, envelope: YearEnvelope, operation: PinnedAuthorityOperation) -> ModeloRevision:
    entry = _given(persona)
    return operation.revision_for_context(entry.modelo, filing_year=entry.year.resolve(envelope), period=entry.period)


def _giving(persona: Persona, role: str, *, year: YearToken | None = None) -> Persona:
    given = _given(persona)
    entry = dataclasses.replace(given, year=year or given.year, roles=((role, "1.00"),), sources=((role, "Cuentas"),))
    return dataclasses.replace(persona, work_inputs=(entry,))


def _role_naming(revision: ModeloRevision, casilla: str) -> str | None:
    """The registry identity that names ``casilla`` and no other casilla of ``revision``, if any."""
    (definition,) = (item for item in revision.casillas if str(item.id) == casilla)
    for key in (definition.continuidad_id, definition.semantic_role):
        if key is None:
            continue
        try:
            named = resolved_casillas(revision, _keyed(key), where="probe")
        except WorkInputError:
            # The key names several casillas, so it names none of them alone.
            continue
        if named == ((casilla, "1.00"),):
            return key
    return None


def _keyed(role: str) -> WorkInput:
    return WorkInput(
        modelo="",
        year=YearToken.parse("horizon", where="probe"),
        period="",
        roles=((role, "1.00"),),
        sources=(),
        reason="",
    )


def _named_casilla(revision: ModeloRevision, eligible: Callable[[str], bool]) -> tuple[str, str]:
    """The first eligible casilla of ``revision`` one registry identity names alone, with that identity."""
    return next(
        (str(casilla.id), role)
        for casilla in revision.casillas
        if eligible(str(casilla.id)) and (role := _role_naming(revision, str(casilla.id))) is not None
    )


def _asserting(
    persona: Persona,
    entry: WorkInput,
    *,
    roles: tuple[tuple[str, str], ...] = (),
    casillas: tuple[tuple[str, str], ...] = (),
) -> Persona:
    """The persona with one more expectation of the work input's return, stating ``roles`` and ``casillas``."""
    asserting = ExpectedValue(
        modelo=entry.modelo,
        period=entry.period,
        year=entry.year,
        counterparty=None,
        casillas=casillas,
        concepts=(),
        parameters=(),
        derivation=None,
        legal_ref=(),
        grounding="unverified",
        reason=None,
        roles=roles,
    )
    expectations = persona.expectations
    return dataclasses.replace(
        persona,
        expectations=Expectations(
            obligations=expectations.obligations,
            deadlines=expectations.deadlines,
            values=(*expectations.values, asserting),
        ),
    )


def test_the_persona_gives_only_a_casilla_its_edition_leaves_to_the_operator(
    persona: Persona, envelope: YearEnvelope, operation: PinnedAuthorityOperation
) -> None:
    check_work_inputs(persona, envelope, operation)


def test_a_given_role_naming_a_casilla_the_edition_computes_is_refused(
    persona: Persona, envelope: YearEnvelope, operation: PinnedAuthorityOperation
) -> None:
    revision = _edition(persona, envelope, operation)
    kinds = {str(casilla.id): casilla.input_kind for casilla in revision.casillas}
    computed, role = _named_casilla(revision, lambda casilla: kinds[casilla] is InputKind.COMPUTED)
    with pytest.raises(WorkInputError, match=f"supplies casilla {computed} itself"):
        check_work_inputs(_giving(persona, role), envelope, operation)


def test_a_given_role_naming_a_casilla_a_formula_of_the_edition_produces_is_refused(
    persona: Persona, envelope: YearEnvelope, operation: PinnedAuthorityOperation
) -> None:
    revision = _edition(persona, envelope, operation)
    targets = {str(formula.target_casilla_id) for formula in revision.formulas}
    target, role = _named_casilla(revision, lambda casilla: casilla in targets)
    with pytest.raises(WorkInputError, match=f"supplies casilla {target} itself"):
        check_work_inputs(_giving(persona, role), envelope, operation)


def test_a_given_role_no_edition_declares_is_refused(
    persona: Persona, envelope: YearEnvelope, operation: PinnedAuthorityOperation
) -> None:
    role, _ = _given(persona).roles[0]
    misspelt = f"{role}-sin-casilla"
    with pytest.raises(WorkInputError, match=f"role {misspelt} names no casilla in any edition"):
        check_work_inputs(_giving(persona, misspelt), envelope, operation)


def _first_declaring_year(role: str, editions: Mapping[int, ModeloRevision]) -> int:
    """The first envelope year whose edition declares ``role`` on any casilla."""
    return min(
        year
        for year, edition in editions.items()
        if any(role in (casilla.continuidad_id, casilla.semantic_role) for casilla in edition.casillas)
    )


def _latest_introduced_manual_role(editions: Mapping[int, ModeloRevision], *, floor: int) -> tuple[int, str]:
    """The identity naming a manual casilla alone that the latest edition above the floor introduces, with that year.

    The latest one keeps the lowered envelope as wide as the registry allows.
    """
    named = {
        role
        for edition in editions.values()
        for casilla in edition.casillas
        if casilla.input_kind is InputKind.MANUAL and (role := _role_naming(edition, str(casilla.id))) is not None
    }
    return max((year, role) for role in named if (year := _first_declaring_year(role, editions)) > floor)


def test_a_role_only_a_later_edition_declares_is_admitted_under_a_horizon_before_it(
    persona: Persona, envelope: YearEnvelope, operation: PinnedAuthorityOperation
) -> None:
    entry = _given(persona)
    editions = {
        year: operation.revision_for_context(entry.modelo, filing_year=year, period=entry.period)
        for year in range(envelope.floor, envelope.horizon + 1)
    }
    year, role = _latest_introduced_manual_role(editions, floor=envelope.floor)
    lowered = dataclasses.replace(envelope, horizon=year - 1)
    later = _giving(read_persona(_PERSONA, envelope=lowered), role, year=YearToken.parse("horizon", where="probe"))
    # No edition the lowered envelope reaches declares the role, yet the role is admitted.
    assert all(
        resolved_casillas(edition, _given(later), where="probe") == ()
        for covered, edition in editions.items()
        if covered <= lowered.horizon
    )
    check_work_inputs(later, lowered, operation)


def test_a_given_role_naming_several_casillas_of_the_edition_is_refused_as_ambiguous(
    persona: Persona, envelope: YearEnvelope, operation: PinnedAuthorityOperation
) -> None:
    shared = _shared_role(_edition(persona, envelope, operation))
    with pytest.raises(WorkInputError, match=f"role {shared} names several casillas"):
        check_work_inputs(_giving(persona, shared), envelope, operation)


def test_a_given_role_the_selected_edition_lacks_is_left_unentered_there(
    persona: Persona, envelope: YearEnvelope, operation: PinnedAuthorityOperation
) -> None:
    entry = _given(persona)
    editions = {
        year: operation.revision_for_context(entry.modelo, filing_year=year, period=entry.period)
        for year in range(envelope.floor, envelope.horizon + 1)
    }
    # A manual casilla one edition names alone by a registry identity that another edition of the envelope lacks.
    year, role = next(
        (lacking, role)
        for declaring in editions.values()
        for casilla in declaring.casillas
        if casilla.input_kind is InputKind.MANUAL and (role := _role_naming(declaring, str(casilla.id))) is not None
        for lacking, edition in editions.items()
        if not resolved_casillas(edition, _keyed(role), where="probe")
    )
    offset = envelope.horizon - year
    token = YearToken.parse("horizon" if offset == 0 else f"horizon-{offset}", where="probe")
    lacking = _giving(persona, role, year=token)
    check_work_inputs(lacking, envelope, operation)
    assert resolved_casillas(editions[year], _given(lacking), where="probe") == ()


def _shared_role(revision: ModeloRevision) -> str:
    """A semantic role several casillas of ``revision`` share, which no ``continuidad_id`` shadows."""
    continuidad = {casilla.continuidad_id for casilla in revision.casillas if casilla.continuidad_id is not None}
    roles = Counter(
        casilla.semantic_role
        for casilla in revision.casillas
        if casilla.semantic_role is not None and casilla.semantic_role not in continuidad
    )
    return next(role for role, count in sorted(roles.items()) if count > 1)


def test_an_expected_role_naming_several_casillas_of_the_edition_is_refused_as_ambiguous(
    persona: Persona, envelope: YearEnvelope, operation: PinnedAuthorityOperation
) -> None:
    entry = _given(persona)
    shared = _shared_role(_edition(persona, envelope, operation))
    with pytest.raises(WorkInputError, match=f"expected role {shared} names several casillas"):
        check_work_inputs(_asserting(persona, entry, roles=((shared, "1.00"),)), envelope, operation)


def test_a_given_value_an_expectation_of_its_return_names_by_role_is_refused(
    persona: Persona, envelope: YearEnvelope, operation: PinnedAuthorityOperation
) -> None:
    entry = _given(persona)
    revision = _edition(persona, envelope, operation)
    definitions = {str(item.id): item for item in revision.casillas}
    # A given casilla whose semantic role names it alone, so the expectation asserts exactly that value back.
    casilla, amount, role = next(
        (casilla, amount, role)
        for casilla, amount in resolved_casillas(revision, entry, where="probe")
        if (role := definitions[casilla].semantic_role) is not None
        and resolved_casillas(revision, _keyed(role), where="probe") == ((casilla, "1.00"),)
    )
    asserted_back = _asserting(persona, entry, roles=((role, amount),))
    with pytest.raises(WorkInputError, match=f"gives casilla {casilla}, which the expected role {role} names"):
        check_work_inputs(asserted_back, envelope, operation)


def test_a_given_value_an_expectation_of_its_return_states_by_casilla_is_refused(
    persona: Persona, envelope: YearEnvelope, operation: PinnedAuthorityOperation
) -> None:
    entry = _given(persona)
    casilla, amount = resolved_casillas(_edition(persona, envelope, operation), entry, where="probe")[0]
    with pytest.raises(WorkInputError, match=f"gives casilla {casilla}, which an expectation of the return states"):
        check_work_inputs(_asserting(persona, entry, casillas=((casilla, amount),)), envelope, operation)


@pytest.fixture(scope="module")
def company(tmp_path_factory: pytest.TempPathFactory) -> Iterator[MaterialisedPersona]:
    with materialised_persona(_PERSONA, tmp_path_factory.mktemp("persona"), ReplayScope.FULL) as materialised:
        yield materialised


def _calculate(world: PersonaWorld, entry: WorkInput) -> ModeloWorkCalculatePublicResultV3:
    created = settle_operation(
        world,
        MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        ModeloWorkCreateRequest(
            profile_id=world.profile_id,
            modelo=entry.modelo,
            period=PublicPeriod(filing_year=entry.year.resolve(world.envelope), code=entry.period),
            actor=PERSONA_ACTOR,
        ),
    )
    assert isinstance(created, ModeloWorkCreateProjection)
    assert isinstance(created.outcome, ModeloWorkCreateSuccess)
    work_unit_id = created.outcome.unit.work_unit_id
    return run_operation(
        world,
        MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        ModeloWorkCalculateRequest(work_unit_id=work_unit_id, actor=PERSONA_ACTOR),
        ModeloWorkCalculatePublicResultV3,
        subject=work_unit_id,
    )


def test_the_modelo_200_refuses_without_the_entered_accounting_result_and_calculates_with_it(
    company: MaterialisedPersona,
) -> None:
    entry = _given(company.persona)
    without = dataclasses.replace(company.world, work_inputs=())
    with pytest.raises(PersonaMaterialisationError, match=_ACCOUNTING_RESULT_REFUSAL):
        _calculate(without, entry)

    # The refused calculation left the work unit without one, so the values are entered before its first.
    calculated = _calculate(company.world, entry)

    values = {item.key: restore_scalar(item.value) for item in calculated.calculation.casilla_values}
    edition = company.world.operation.revision_for_context(
        entry.modelo, filing_year=entry.year.resolve(company.world.envelope), period=entry.period
    )
    entered = resolved_casillas(edition, entry, where="probe")
    assert entered
    for casilla, amount in entered:
        assert values[casilla] == Decimal(amount)
