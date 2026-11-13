"""The form offers each statement the edit admits on one carry in served words, and marks a figure stated.

A first-quarter Modelo 130 reads the previous ejercicio's net activity income from
that year's Modelo 100 (RIRPF art. 110.3.c). With no such return held, the edit
admits a figure the filer states for it, and the form offers that statement with
its words and the return it stands in for; once stated, the carry is marked as a
figure the filer stated for that return. A Modelo 100 carry of a negative base
pending from earlier years (Ley 35/2006 art. 50.3) admits the statement that no
amount is pending, and the form offers it on that carry until it is made.

Real behaviour throughout: an isolated encrypted profile, the bundled authority,
the production admission, edit executor and form service, with every year taken
from the published support envelope.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
)
from ....application.modelo.work_form_models import ModeloFormBindingAddressV1, ModeloFormField, ModeloWorkForm
from ....application.modelo.work_form_service import load_modelo_work_form
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from ....domain.user_profile.values import UserProfileFact
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PRIOR_INCOME = "irpf.previous_year_economic_activity_net_income"
#: The carries of the negative general base still pending from the four previous ejercicios.
_PENDING_CARRIES = (
    "renta-base-liquidable-negativa-general-anterior",
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio",
)
#: The negative savings balances (rcm and gyp) of the four earlier ejercicios, which LIRPF art. 49 reads from the previous return.
_PENDING_SAVINGS_BALANCES = tuple(
    f"renta-saldo-negativo-{kind}-ahorro-{origin}-pendiente-inicio"
    for kind in ("gyp", "rcm")
    for origin in ("em1", "em2", "em3", "em4")
)
_PENDING_BASE = _PENDING_CARRIES[0]
_RENTA_FACTS = (UserProfileFact(path="tax_residence.ccaa", value="madrid"), *RENTA_UNMARRIED_TAXPAYER_FACTS)
_WORDS = "application.modelo.work_form.binding_statement"


def _year_after_the_floor() -> int:
    support = published_supported_filing_years()
    assert support is not None
    # The year after the floor reads a Modelo 100 of the floor, which the envelope admits.
    return support.floor + 1


def _form(work: SeededOperatorWork, language: OutputLanguage) -> ModeloWorkForm:
    unit = work.work_unit
    return load_modelo_work_form(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=work.operation,
        work_unit_repository=work.ports.work_unit_repository,
        calculation_repository=work.ports.calculation_repository,
        verification_repository=work.ports.verification_repository,
        admission=work.admit(),
        language=language,
    ).form


def _carry_field(form: ModeloWorkForm, binding_id: str) -> ModeloFormField:
    (field,) = [
        item
        for item in form.fields()
        if isinstance(item.edit_address, ModeloFormBindingAddressV1) and item.edit_address.binding_id == binding_id
    ]
    return field


def _words(key: str, language: OutputLanguage) -> str:
    words = lookup_translation(f"{_WORDS}.{key}", locale=language.value)
    assert words is not None
    return words


@pytest.mark.parametrize("language", [OutputLanguage.EN, OutputLanguage.ES])
def test_a_carry_without_its_earlier_return_offers_a_stated_figure_then_marks_it(
    tmp_path: Path, language: OutputLanguage
) -> None:
    year = _year_after_the_floor()
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="130", filing_year=year, period_code="1T") as work,
    ):
        before = _carry_field(_form(work, language), _PRIOR_INCOME)
        intent = ModeloBindingEditIntentV1(
            address=ModeloEditBindingAddressV1(binding_id=_PRIOR_INCOME),
            kind=ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE,
            value=Decimal("12846.30"),
        )
        assert work.apply(binding=(intent,)).refusal is None
        after = _carry_field(_form(work, language), _PRIOR_INCOME)

    (offered,) = [item for item in before.statements if item.intent is ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE]
    assert offered.binding_id == _PRIOR_INCOME
    assert offered.action_words == _words("attest_prior_value.action", language)
    assert offered.statement_words == _words("attest_prior_value.statement", language)
    assert offered.effect_words == _words("attest_prior_value.effect", language)
    assert offered.source_words is not None
    assert "100" in offered.source_words
    assert str(year - 1) in offered.source_words
    assert before.stated_prior_value is None
    assert "stated_prior_value" not in before.model_dump(mode="json")

    stated = after.stated_prior_value
    assert stated is not None
    assert stated.source_words == offered.source_words
    assert stated.source_words in stated.origin_words
    assert after.origin_words == stated.origin_words
    assert after.stated_absent is None
    assert ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE not in {item.intent for item in after.statements}


@pytest.mark.parametrize("language", [OutputLanguage.EN, OutputLanguage.HU])
def test_a_pending_carry_offers_the_statement_of_no_amount_until_it_is_made(
    tmp_path: Path, language: OutputLanguage
) -> None:
    support = published_supported_filing_years()
    assert support is not None
    with (
        profile_adapter_composition(),
        seeded_operator_work(
            tmp_path, modelo="100", filing_year=support.horizon, period_code="0A", extra_facts=_RENTA_FACTS
        ) as renta,
    ):
        before = _carry_field(_form(renta, language), _PENDING_BASE)
        intents = tuple(
            ModeloBindingEditIntentV1(
                address=ModeloEditBindingAddressV1(binding_id=binding_id),
                kind=ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT,
            )
            for binding_id in (*_PENDING_CARRIES, *_PENDING_SAVINGS_BALANCES)
        )
        applied = renta.apply(binding=intents)
        assert applied.refusal is None, applied.refusal
        after = _carry_field(_form(renta, language), _PENDING_BASE)

    (offered,) = [item for item in before.statements if item.intent is ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT]
    assert offered.action_words == _words("attest_no_amount.action", language)
    assert offered.statement_words == _words("attest_no_amount.statement", language)
    assert offered.effect_words == _words("attest_no_amount.effect", language)
    assert offered.source_words is None

    assert after.stated_absent is not None
    assert after.stated_prior_value is None
    assert ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT not in {item.intent for item in after.statements}
