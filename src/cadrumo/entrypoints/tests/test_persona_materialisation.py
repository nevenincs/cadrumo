"""Every canonical persona replays into a profile through production operations and reads back as declared."""

from __future__ import annotations

import time
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ...application.inventory.registered_projections import InventoryInspectProjection
from ...application.inventory.registered_requests import (
    INVENTORY_INSPECT_OPERATION_DEFINITION_ID,
    InventoryInspectRequest,
)
from ...application.ledger.counterparty_operation import (
    LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
    LedgerCounterpartyRequest,
    LedgerCounterpartyResult,
)
from ...application.modelo.filing_record_list_contracts import (
    ModeloFilingRecordListProjection,
    ModeloFilingRecordListRequest,
)
from ...application.modelo.filing_record_list_operation import MODELO_FILING_RECORD_LIST_OPERATION_DEFINITION_ID
from ...application.modelo.operation_shared import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from ...application.modelo.revision_selection_operation import (
    MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
    ModeloWorkRevisionProjection,
    ModeloWorkRevisionRequest,
)
from ...application.modelo.work_calculation_contracts import ModeloWorkCalculateRequest
from ...application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateRequest,
    ModeloWorkCreateSuccess,
)
from ...application.operations.error_detail import served_words_language
from ...application.operations.public_period import PublicPeriod
from ...application.retencion_soportada_certificado.contracts import RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID
from ...application.retencion_soportada_certificado.requests import RetencionSoportadaListRequest
from ...application.retencion_soportada_certificado.results import RetencionSoportadaListProjection
from ...application.user_profile.profile_operation_contracts import (
    PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
    ProfileRepeatableRowMutationOperationRequest,
    ProfileRepeatableRowValue,
)
from ...application.user_profile.projections import record_to_path_values
from ...application.wizard.catalogue import build_setup_flow
from ...application.wizard.imputation_election import YEAR_QUESTION_ID
from ...core.i18n.render import tr
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.contribuyente.inventory.records import MovementKind
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.modelos.filing_record import AeatConfirmationState, FilingOrigin, ModeloRecordStatus
from ...domain.user_profile.values import ProfileSetupState
from ...tests.personas import persona_ids
from ..ledger_action_composition import compose_ledger_action_ports
from .persona_materialisation import (
    PERSONA_ACTOR,
    MaterialisedPersona,
    PersonaMaterialisationError,
    PersonaWorld,
    ReplayScope,
    filing_key,
    household_leaves,
    informative_party_roles,
    load_profile_record,
    materialised_persona,
    patch_answers,
    persona_profile_id,
    run_operation,
    settle_operation,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: What no production operation can record of each persona, read off its files: the declarative blocks and
#: the employee's Seguridad Social contributions on a withholding certificate.
_NOT_LOADED: dict[str, set[str]] = {
    "arrendador-jubilado": {"rental_properties"},
    "asalariada-familia": {"withholding_certificates.cotizaciones_seguridad_social"},
    "autonomo-alta-reciente": set(),
    "autonomo-electricista": set(),
    "autonomo-fontanero": set(),
    "intracomunitario-desarrollador": set(),
    "minorista-recargo": set(),
    "sociedad-limitada": {"officers"},
    "traductora-profesional": set(),
}


@pytest.mark.parametrize("persona_id", persona_ids())
def test_a_persona_replays_through_production_operations(
    tmp_path: Path, operation: PinnedAuthorityOperation, persona_id: str
) -> None:
    paths = {
        question.id: question.profile_key
        for section in build_setup_flow(operation).sections
        for question in section.questions
    }
    with materialised_persona(persona_id, tmp_path) as materialised:
        persona, world = materialised.persona, materialised.world
        record = load_profile_record(world)
        stored = compose_ledger_action_ports(
            bucket_id=str(world.profile_id), operation=world.operation
        ).transaction_repository.load()
        withholding = [
            row
            for ejercicio in {item.ejercicio.resolve(world.envelope) for item in persona.withholding_certificates}
            for row in run_operation(
                world,
                RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID,
                RetencionSoportadaListRequest(profile_id=world.profile_id, ejercicio=ejercicio),
                RetencionSoportadaListProjection,
            ).rows
        ]
        books = {
            book.activity: run_operation(
                world,
                INVENTORY_INSPECT_OPERATION_DEFINITION_ID,
                InventoryInspectRequest(
                    profile_id=world.profile_id, actividad_id=book.activity, year=book.year.resolve(world.envelope)
                ),
                InventoryInspectProjection,
            ).ledger
            for book in persona.inventory
        }
    values = record_to_path_values(record)
    answers = dict(patch_answers(persona, world.envelope))
    election_years = {election.year.resolve(world.envelope) for election in persona.elections}

    assert {question: values.get(paths[question] or "") for question in answers if question != YEAR_QUESTION_ID} == {
        question: answer for question, answer in answers.items() if question != YEAR_QUESTION_ID
    }
    for year in election_years:
        within, before = (record_to_path_values(record, as_of=date(at, 12, 31)) for at in (year, year - 1))
        for election in persona.elections:
            assert (within.get(paths[election.question] or ""), before.get(paths[election.question] or "")) == (
                election.value,
                None,
            )
    assert {field.path: values.get(field.path) for field in persona.fields} == {
        field.path: field.value for field in persona.fields
    }
    assert {
        f"activities.{index}.{key}": values.get(f"activities.{index}.{key}")
        for index, activity in enumerate(persona.activities)
        for key, _ in activity.values
    } == {
        f"activities.{index}.{key}": value
        for index, activity in enumerate(persona.activities)
        for key, value in activity.values
    }
    for family, members in (("descendiente", persona.descendants), ("ascendiente", persona.ascendants)):
        expected = {
            f"renta_family.{family}.{index}.{key}": value
            for index, member in enumerate(members)
            for key, value in household_leaves(persona, member, world.envelope)
        }
        assert {path: values.get(path) for path in expected} == expected
    # A household family the persona states, an empty one included, is declared with its member count.
    assert {
        family: values.get(f"renta_family.{count}")
        for family, count in (("descendants", "descendientes_count"), ("ascendants", "ascendientes_count"))
        if family in persona.household_families
    } == {
        family: str(len(members))
        for family, members in (("descendants", persona.descendants), ("ascendants", persona.ascendants))
        if family in persona.household_families
    }
    assert len(stored.transactions) == len(persona.ledger)
    assert set(materialised.transactions) == {row.ref for row in persona.ledger}
    assert {
        row.ref: (
            stored.transactions[materialised.transactions[row.ref]].iva_amount,
            stored.transactions[materialised.transactions[row.ref]].recargo_amount,
        )
        for row in persona.ledger
    } == {row.ref: (row.iva_amount, row.recargo_amount) for row in persona.ledger}
    assert set(materialised.invoices) == {row.ref for row in persona.ledger if row.invoice_kind is not None}
    assert {
        (
            row.payer_legal_name,
            row.ejercicio,
            Decimal(row.importe_integro_dinerario.decimal),
            Decimal(row.retencion.decimal),
        )
        for row in withholding
    } == {
        (
            persona.identities.role(certificate.payer).legal_name,
            certificate.ejercicio.resolve(world.envelope),
            certificate.importe_integro,
            certificate.retencion,
        )
        for certificate in persona.withholding_certificates
    }
    assert set(materialised.evidence) == {document.id for document in persona.documents}
    # Each book opens at its stated stock, records one purchase for each ledger row it names, under that row's
    # ref, and holds the closing recorded on its movements.
    assert {
        activity: (
            None
            if ledger is None
            else (
                Decimal(ledger.opening_stock.decimal),
                sorted(
                    movement.movement_id
                    for movement in ledger.period_movements
                    if movement.kind is MovementKind.PURCHASE
                ),
                ledger.closing_authority_fingerprints is not None,
            )
        )
        for activity, ledger in books.items()
    } == {book.activity: (book.opening_stock, sorted(book.purchases), True) for book in persona.inventory}
    assert {item.block for item in materialised.not_loaded} == _NOT_LOADED[persona_id]
    # Every run registers the persona at the same identity, so what is read of it names the same profile.
    assert world.profile_id == persona_profile_id(persona_id)


def _profile_values(world: PersonaWorld) -> dict[str, str]:
    return record_to_path_values(load_profile_record(world))


def test_a_profile_scope_replay_records_the_profile_and_no_household_or_ledger(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    paths = {
        question.id: question.profile_key
        for section in build_setup_flow(operation).sections
        for question in section.questions
    }
    with materialised_persona("asalariada-familia", tmp_path, ReplayScope.PROFILE) as materialised:
        persona, world = materialised.persona, materialised.world
        values = _profile_values(world)
        setup_state = load_profile_record(world).setup_state
        stored = compose_ledger_action_ports(
            bucket_id=str(world.profile_id), operation=world.operation
        ).transaction_repository.load()
        withholding = run_operation(
            world,
            RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID,
            RetencionSoportadaListRequest(
                profile_id=world.profile_id,
                ejercicio=persona.withholding_certificates[0].ejercicio.resolve(world.envelope),
            ),
            RetencionSoportadaListProjection,
        ).rows
    answers = {
        question: answer
        for question, answer in patch_answers(persona, world.envelope)
        if question != YEAR_QUESTION_ID and question not in {election.question for election in persona.elections}
    }

    assert persona.descendants
    assert persona.ledger
    assert persona.withholding_certificates
    assert {question: values.get(paths[question] or "") for question in answers} == answers
    assert {
        f"renta_family.descendiente.{index}.{key}": values.get(f"renta_family.descendiente.{index}.{key}")
        for index, member in enumerate(persona.descendants)
        for key, _ in household_leaves(persona, member, world.envelope)
    } == {
        f"renta_family.descendiente.{index}.{key}": None
        for index, member in enumerate(persona.descendants)
        for key, _ in household_leaves(persona, member, world.envelope)
    }
    assert len(stored.transactions) == 0
    assert world.profile_id == persona_profile_id(persona.id)
    assert setup_state is ProfileSetupState.COMPLETE
    assert len({persona_profile_id(each) for each in persona_ids()}) == len(persona_ids())
    assert not withholding
    assert (materialised.scope, materialised.transactions, materialised.invoices, materialised.evidence) == (
        ReplayScope.PROFILE,
        {},
        {},
        {},
    )


def test_a_reused_replay_gives_each_consumer_an_isolated_profile(tmp_path: Path) -> None:
    marker = "Marker written to one consumer's copy only"

    def open_and_read(directory: Path, *, write: bool) -> tuple[dict[str, str], MaterialisedPersona, float]:
        started = time.perf_counter()
        with materialised_persona("autonomo-fontanero", directory, ReplayScope.FULL, reuse=True) as materialised:
            opened = time.perf_counter() - started
            world = materialised.world
            if write:
                record = load_profile_record(world)
                settle_operation(
                    world,
                    PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
                    ProfileRepeatableRowMutationOperationRequest(
                        profile_id=world.profile_id,
                        expected_revision=record.record_revision,
                        expected_content_digest=record.content_digest,
                        section_key="activities",
                        values=(ProfileRepeatableRowValue(field_key="description", value=marker),),
                    ),
                )
            stored = compose_ledger_action_ports(
                bucket_id=str(world.profile_id), operation=world.operation
            ).transaction_repository.load()
            assert set(stored.transactions) >= set(materialised.transactions.values())
            return _profile_values(world), materialised, opened

    first_values, first, miss = open_and_read(tmp_path / "first", write=True)
    second_values, second, hit = open_and_read(tmp_path / "second", write=False)
    print(f"reused replay: miss {miss:.1f}s, hit {hit:.1f}s")

    persona = first.persona
    assert marker in first_values.values()
    assert marker not in second_values.values()
    assert {path: value for path, value in first_values.items() if marker != value} == second_values
    assert (second.scope, second.transactions, second.invoices, second.evidence) == (
        ReplayScope.FULL,
        first.transactions,
        first.invoices,
        first.evidence,
    )
    assert set(second.transactions) == {row.ref for row in persona.ledger}
    assert first.world.profile_id == second.world.profile_id == persona_profile_id(persona.id)
    assert set(second.invoices) == {row.ref for row in persona.ledger if row.invoice_kind is not None}
    assert first.filings == second.filings == first.calculations == second.calculations == {}


def test_a_history_replay_files_and_calculates_each_declared_return_with_aeat_confirmation_pending(
    tmp_path: Path,
) -> None:
    with materialised_persona("autonomo-fontanero", tmp_path, ReplayScope.HISTORY) as materialised:
        persona, world = materialised.persona, materialised.world
        records = run_operation(
            world,
            MODELO_FILING_RECORD_LIST_OPERATION_DEFINITION_ID,
            ModeloFilingRecordListRequest(profile_id=world.profile_id),
            ModeloFilingRecordListProjection,
        ).records
        states = {
            key: run_operation(
                world,
                MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
                ModeloWorkRevisionRequest(profile_id=world.profile_id, calculation_revision_id=revision_id),
                ModeloWorkRevisionProjection,
            ).calculation_state
            for key, revision_id in (*materialised.filings.items(), *materialised.calculations.items())
        }
        # Casilla 05 of a later Modelo 130 quarter reads casilla 07 of the earlier quarters' filed returns; the
        # first quarter is calculated but unfiled, so the next quarter's calculation refuses naming that quarter.
        created = settle_operation(
            world,
            MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
            ModeloWorkCreateRequest(
                profile_id=world.profile_id,
                modelo="130",
                period=PublicPeriod(filing_year=persona.fiscal_year.resolve(world.envelope), code="2T"),
                actor=PERSONA_ACTOR,
            ),
        )
        outcome = getattr(created, "outcome", None)
        assert isinstance(outcome, ModeloWorkCreateSuccess)
        with pytest.raises(PersonaMaterialisationError, match="REFUSED_MODELO_PRIOR_PERIOD_UNFILED"):
            settle_operation(
                world,
                MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
                ModeloWorkCalculateRequest(work_unit_id=outcome.unit.work_unit_id, actor=PERSONA_ACTOR),
                subject=outcome.unit.work_unit_id,
            )
    declared_filed = {
        filing_key(filed.modelo, filed.year.resolve(world.envelope), period)
        for filed in persona.filed_returns
        for period in filed.periods
    }
    declared_calculated = {
        filing_key(calculated.modelo, calculated.year.resolve(world.envelope), period)
        for calculated in persona.calculated_returns
        for period in calculated.periods
    }

    assert persona.filed_returns
    assert persona.calculated_returns
    assert persona.leased_premises
    assert persona.aeat_filings
    assert materialised.scope is ReplayScope.HISTORY
    assert set(materialised.filings) == declared_filed
    assert set(materialised.calculations) == declared_calculated
    local = [record for record in records if record.origin is not FilingOrigin.AEAT]
    captured = [record for record in records if record.origin is FilingOrigin.AEAT]
    assert {
        filing_key(record.modelo, record.filing_year, record.period): record.calculation_revision_id for record in local
    } == materialised.filings
    assert {states[key] for key in materialised.filings} == {CalculationRevisionState.PRESENTADO}
    assert {states[key] for key in materialised.calculations} == {CalculationRevisionState.BORRADOR}
    assert {
        (record.confirmation, record.status, record.aeat_register, record.aeat_accepted, record.live_submission)
        for record in local
    } == {(AeatConfirmationState.PENDIENTE, ModeloRecordStatus.VIGENTE, None, False, False)}
    # A return filed with the AEAT is captured from its register: confirmed by the justificante it was filed under.
    assert {
        (
            filing_key(record.modelo, record.filing_year, record.period),
            record.confirmation,
            record.aeat_accepted,
            None if record.aeat_register is None else record.aeat_register.csv,
            None if record.aeat_register is None else record.aeat_register.justificante_number,
        )
        for record in captured
    } == {
        (
            filing_key(filing.modelo, filing.year.resolve(world.envelope), filing.period),
            AeatConfirmationState.CONFIRMADA,
            True,
            filing.csv,
            filing.justificante,
        )
        for filing in persona.aeat_filings
    }


def test_a_stopped_operation_settles_with_the_words_the_application_serves_for_it(tmp_path: Path) -> None:
    with materialised_persona("autonomo-fontanero", tmp_path, ReplayScope.PROFILE) as materialised:
        world = materialised.world
        with pytest.raises(PersonaMaterialisationError) as raised:
            settle_operation(
                world,
                MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
                ModeloWorkRevisionRequest(profile_id=world.profile_id, work_unit_id="abcdef012345"),
            )
    served = tr("errors.error.modelo_work_selector_unit_not_found", locale=served_words_language().value)

    assert str(raised.value) == (
        f"{MODELO_WORK_REVISION_OPERATION_DEFINITION_ID} settled failed (ERROR_MODELO_WORK_SELECTOR_UNIT_NOT_FOUND): "
        f"{served}"
    )
    assert "no detail" not in str(raised.value)


def test_a_replay_states_each_informative_party_filing_name_readable_through_the_counterparty_view(
    tmp_path: Path,
) -> None:
    with materialised_persona("autonomo-fontanero", tmp_path, ReplayScope.FULL) as materialised:
        persona, world = materialised.persona, materialised.world
        roles = informative_party_roles(persona)
        viewed = {
            role: run_operation(
                world,
                LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
                LedgerCounterpartyRequest(
                    profile_id=world.profile_id,
                    action="view",
                    tax_identifier=persona.identities.role(role).value,
                    country_code=persona.identities.role(role).country,
                ),
                LedgerCounterpartyResult,
            ).filing_name
            for role in roles
        }

    assert {"fontanero.comunidad", "fontanero.arrendador-taller", "fontanero.cliente-restaurante"} <= set(roles)
    assert "fontanero.titular" not in roles
    assert all(name is not None for name in viewed.values())
    comunidad = viewed["fontanero.comunidad"]
    assert comunidad is not None
    assert comunidad.party_kind == "entity"
    assert comunidad.razon_social == persona.identities.role("fontanero.comunidad").razon_social
    assert len(comunidad.razon_social or "") == 41
    assert [(rendering.width, rendering.text) for rendering in comunidad.renderings] == list(
        persona.identities.role("fontanero.comunidad").renderings
    )
    assert all(len(rendering.text) <= rendering.width == 40 for rendering in comunidad.renderings)
    assert comunidad.renderings
    taller = persona.identities.role("fontanero.arrendador-taller")
    stated = viewed["fontanero.arrendador-taller"]
    assert stated is not None
    assert stated.party_kind == "natural_person"
    assert (stated.primer_apellido, stated.segundo_apellido, stated.nombre) == (
        taller.primer_apellido,
        taller.segundo_apellido,
        taller.nombre,
    )
    assert stated.razon_social is None
    assert stated.no_second_surname is False
    assert stated.asserted_by == PERSONA_ACTOR
