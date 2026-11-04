"""Every canonical persona replays into a profile through production operations and reads back as declared."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ...application.user_profile.projections import record_to_path_values
from ...application.wizard.catalogue import build_setup_flow
from ...application.wizard.imputation_election import YEAR_QUESTION_ID
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...tests.personas import persona_ids
from ..ledger_action_composition import compose_ledger_action_ports
from .persona_materialisation import household_leaves, load_profile_record, materialised_persona, patch_answers

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: What no production operation can record of each persona, read off its files: the declarative blocks,
#: certificates the persona backs with no certificate document, rows whose IVA cuota single classification
#: refuses (recargo de equivalencia, intra-community service reverse charge, and a payment net of retención
#: under an expense category the registry does not relate to withheld activity income), and invoices to
#: anonymous consumers, which the invoice operation cannot name.
_NOT_LOADED: dict[str, set[str]] = {
    "arrendador-jubilado": {"rental_properties", "withholding_certificates"},
    "asalariada-familia": {"withholding_certificates"},
    "autonomo-fontanero": {"ledger.invoice"},
    "intracomunitario-desarrollador": {"ledger.iva_amount"},
    "minorista-recargo": {"ledger.iva_amount"},
    "sociedad-limitada": {"officers"},
    "traductora-profesional": {"ledger.iva_amount", "ledger.invoice"},
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
    assert len(stored.transactions) == len(persona.ledger)
    assert set(materialised.transactions) == {row.ref for row in persona.ledger}
    assert set(materialised.invoices) == {
        row.ref for row in persona.ledger if row.invoice_kind is not None and row.counterparty is not None
    }
    assert set(materialised.evidence) == {document.id for document in persona.documents}
    assert {item.block for item in materialised.not_loaded} == _NOT_LOADED[persona_id]
