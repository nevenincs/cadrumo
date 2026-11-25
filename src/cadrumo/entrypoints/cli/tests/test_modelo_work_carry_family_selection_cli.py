"""The prior-carry attestation command renders the family it names and the amount it states.

Both cases drive the production admission and edit executor over an isolated encrypted profile for every Modelo 100 year the registry support envelope admits.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....application.modelo.absence_statement_submission import (
    prior_carry_absence_submission,
)
from ....application.modelo.carry_amount_statement import (
    prior_carry_statement_submission,
    resolve_prior_carry_amounts,
)
from ....application.modelo.edit_models import (
    ModeloEditBindingIntentKind,
)
from ....core.casilla_id import validated_casilla_id
from ...adapter_composition import profile_adapter_composition
from ...tests.modelo_operator_work_storage import seeded_operator_work
from ...tests.profile_persistence.m100_carry_family_support import (
    FACTS,
    FAMILIES,
    GENERAL,
    apply_statement,
    carry_form,
    choose_carries,
    first_carry_box,
    open_carry_families,
    renta_years,
)
from ..modelo_work_carry_attestation_cli import attest_prior_carries_lines, attest_prior_carries_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("year", renta_years())
def test_with_one_open_family_and_no_option_the_review_and_receipt_name_that_family(tmp_path: Path, year: int) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=FACTS) as renta,
    ):
        general_only = tuple(item for item in carry_form(renta).carry_attestations if item.family is GENERAL)
        chosen = choose_carries(renta, offered=general_only)
        assert chosen == general_only
        submission = prior_carry_absence_submission(renta.baseline(), chosen)
        result = attest_prior_carries_result(submission, chosen, [], {}, None)
        selection = "".join(f" --family {item.family.value}" for item in chosen)
        lines = attest_prior_carries_lines(result, str(renta.work_unit_id), selection)

    assert [statement.family for statement in result.statements] == [GENERAL.value]
    assert f"family	{GENERAL.value}" in lines
    assert all(f"carry	{GENERAL.value}	" in line for line in lines if line.startswith("carry	"))
    assert any(f"--family {GENERAL.value}" in line for line in lines)


@pytest.mark.parametrize("year", renta_years())
def test_one_statement_gives_an_amount_for_one_carry_and_nothing_pending_for_the_rest(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=FACTS) as renta,
    ):
        statements = choose_carries(renta, families=FAMILIES)
        general = next(item for item in statements if item.family is GENERAL)
        carry = general.binding_ids[0]
        box = first_carry_box(renta, carry)
        amounts = resolve_prior_carry_amounts(renta.baseline(), carry_form(renta), statements, [f"{box}=1234.50"])
        assert amounts == {carry: Decimal("1234.50")}
        submission = prior_carry_statement_submission(renta.baseline(), statements, amounts)
        by_binding = {intent.address.binding_id: intent for intent in submission.binding_intents}
        assert by_binding[carry].kind is ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE
        assert by_binding[carry].value == Decimal("1234.50")
        others = [intent for binding_id, intent in by_binding.items() if binding_id != carry]
        assert others
        assert {intent.kind for intent in others} == {ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT}

        result = attest_prior_carries_result(submission, statements, [], amounts, None)
        lines = attest_prior_carries_lines(result, str(renta.work_unit_id), "")
        assert any(line.startswith(f"carry\t{GENERAL.value}\t{carry}\t") and "1234.50" in line for line in lines)
        assert sum(line.startswith("carry\t") for line in lines) == len(by_binding)

        assert apply_statement(renta, submission) is None
        assert open_carry_families(renta) == set()
        head = renta.recalculate()

    assert Decimal(str(head.binding_overrides[carry])) == Decimal("1234.50")
    assert head.operator_layer is not None
    assert carry not in head.operator_layer.attested_binding_ids
    assert set(head.operator_layer.attested_binding_ids) == set(by_binding) - {carry}
    assert head.casilla_values[validated_casilla_id(box, surface="test")] == Decimal("1234.50")
