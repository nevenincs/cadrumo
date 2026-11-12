"""A Modelo 100 on a work-income payer record: the boxes no certificate fills, stated by the filer.

The payer record fills the gross, in-kind, reduction and expense boxes. The employer's
contributions and the protected-estate contribution are in no certificate, so each blocks the
return until the filer types a figure or states that there is none, all four at once through one
action. Real behaviour throughout: an isolated encrypted profile, the bundled authority, the
production admission and edit executor, and every Modelo 100 year the support envelope admits.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.retencion_soportada_seed import seed_payer_certificate
from ....application.modelo.absence_statement_submission import (
    ModeloAbsenceStatementNothingOpenError,
    absence_statement_submission,
)
from ....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloScalarEditIntentV1,
)
from ....application.modelo.trabajo_income_findings import trabajo_income_findings
from ....application.modelo.work_form_models import ModeloWorkForm
from ....application.modelo.work_form_service import load_modelo_work_form
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.external_constants import OutputLanguage
from ....core.retencion_soportada import RetencionSoportadaClase
from ....domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.modelos.calculation_revision_operator_layer import ATTESTED_ZERO
from ....domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingSeverity
from ....domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from ....domain.user_profile.values import UserProfileFact
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FACTS = (UserProfileFact(path="tax_residence.ccaa", value="madrid"), *RENTA_UNMARRIED_TAXPAYER_FACTS)
_CARRIES = (
    "renta-base-liquidable-negativa-general-anterior",
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio",
)
#: The four income boxes no payer certificate states, by the binding that carries each.
_STATEMENT_BINDINGS = {
    "0008": "renta-trabajo-contribucion-empresarial-prevision",
    "0009": "renta-trabajo-contribucion-empresarial-seguro-dependencia",
    "0010": "renta-trabajo-aportacion-patrimonio-protegido",
    "0024": "renta-trabajo-aportacion-empresa-decision-trabajador",
}
_GROSS = Decimal("20300.00")
_EXPENSES = Decimal("610.00")
_TRABAJO = AbsenceAttestationFamily.RENTA_TRABAJO_INCOME_NOT_STATED


def _renta_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None
    admitted: list[int] = []
    for year in sorted(support.years):
        try:
            published_authority_operation().snapshot(
                "100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
            )
        except FilingYearOutsideSupportEnvelopeError:
            continue
        admitted.append(year)
    return tuple(admitted)


def _attest(binding_id: str) -> ModeloBindingEditIntentV1:
    return ModeloBindingEditIntentV1(
        address=ModeloEditBindingAddressV1(binding_id=binding_id), kind=ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT
    )


def _form(work: SeededOperatorWork, language: OutputLanguage = OutputLanguage.EN) -> ModeloWorkForm:
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


def _findings(
    work: SeededOperatorWork, *, profile_values: dict[str, str] | None = None
) -> tuple[ModeloVerificationFinding, ...]:
    unit = work.work_unit
    revision = work.operation.snapshot(
        "100", filing_year=unit.filing_year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    ).revision
    head: CalculationRevision = work.require_head()
    return trabajo_income_findings(
        str(unit.modelo),
        revision,
        head,
        profile_values=profile_values or {},
        effective_date=date(unit.filing_year, 12, 31),
        operation=work.operation,
    )


def _blocking_boxes(findings: tuple[ModeloVerificationFinding, ...]) -> set[str]:
    return {
        str(finding.casilla_id)
        for finding in findings
        if finding.severity is ModeloVerificationFindingSeverity.BLOCKING and finding.casilla_id is not None
    }


def _record_certificate(work: SeededOperatorWork, year: int) -> None:
    seed_payer_certificate(
        operation=work.operation,
        taxpayer_tax_id="00000000T",
        ejercicio=year,
        payer_tax_id="B00000001",
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion=Decimal("1200.00"),
        importe_integro_dinerario=_GROSS,
        gastos_deducibles=_EXPENSES,
    )


@pytest.mark.parametrize("year", _renta_years())
def test_each_unstated_income_box_blocks_until_the_one_action_states_all_four_and_a_typed_figure_withdraws_one(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as work,
    ):
        _record_certificate(work, year)
        assert work.apply(binding=tuple(_attest(binding_id) for binding_id in _CARRIES)).refusal is None
        head = work.require_head()

        # The record fills the boxes it states, from the certificate alone.
        values = head.casilla_values
        assert values[next(c for c in values if str(c) == "0003")] == _GROSS
        assert values[next(c for c in values if str(c) == "0013")] == _EXPENSES

        # The four boxes no certificate states block, and the deductions only the filer can evidence are served.
        findings = _findings(work)
        assert _blocking_boxes(findings) == set(_STATEMENT_BINDINGS)
        assert [f for f in findings if f.message_locale_key.endswith("trabajo_deduction_not_computed")]

        # One action, next to the finding, names all four boxes in its words and apart from the carry words.
        offered = {attestation.family: attestation for attestation in _form(work).carry_attestations}
        assert set(offered) == {_TRABAJO}
        statement = offered[_TRABAJO]
        assert set(statement.binding_ids) == set(_STATEMENT_BINDINGS.values())
        assert all(box in statement.statement_words for box in _STATEMENT_BINDINGS)
        assert "earlier" not in statement.statement_words
        spanish = next(iter(_form(work, OutputLanguage.ES).carry_attestations))
        assert spanish.statement_words != statement.statement_words

        # Applying it stages four statements of none in one submission, kept apart from a typed zero.
        submission = absence_statement_submission(work.baseline(), offered.values(), family=_TRABAJO)
        assert len(submission.binding_intents) == 4
        assert work.apply(binding=submission.binding_intents).refusal is None
        layer = work.require_head().operator_layer
        assert layer is not None
        assert set(layer.attested_binding_ids) >= set(_STATEMENT_BINDINGS.values())
        assert all(layer.binding_overrides[binding_id] == ATTESTED_ZERO for binding_id in _STATEMENT_BINDINGS.values())
        assert _blocking_boxes(_findings(work)) == set()
        assert _form(work).carry_attestations == ()
        with pytest.raises(ModeloAbsenceStatementNothingOpenError):
            absence_statement_submission(work.baseline(), _form(work).carry_attestations, family=_TRABAJO)

        # A figure typed over one box is the filer's figure and withdraws only that box's statement.
        typed = _STATEMENT_BINDINGS["0008"]
        retyped = work.apply(
            binding=(
                ModeloBindingEditIntentV1(
                    address=ModeloEditBindingAddressV1(binding_id=typed),
                    kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
                    value=Decimal("1500"),
                ),
            )
        )
        assert retyped.refusal is None
        relayer = work.require_head().operator_layer
        assert relayer is not None
        assert typed not in relayer.attested_binding_ids
        assert set(relayer.attested_binding_ids) >= set(_STATEMENT_BINDINGS.values()) - {typed}
        assert _blocking_boxes(_findings(work)) == set()

        # Removing the override leaves that box neither typed nor stated: it blocks again.
        removed = work.apply(
            binding=(
                ModeloBindingEditIntentV1(
                    address=ModeloEditBindingAddressV1(binding_id=typed),
                    kind=ModeloEditBindingIntentKind.REMOVE_OVERRIDE,
                ),
            )
        )
        assert removed.refusal is None
        assert _blocking_boxes(_findings(work)) == {"0008"}
        assert {a.family for a in _form(work).carry_attestations} == {_TRABAJO}
        assert next(iter(_form(work).carry_attestations)).binding_ids == (typed,)


@pytest.mark.parametrize("year", _renta_years())
def test_a_stated_disability_blocks_the_unstated_increase_and_a_stated_expense_above_its_limit_blocks(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as work,
    ):
        _record_certificate(work, year)
        assert work.apply(binding=tuple(_attest(binding_id) for binding_id in _CARRIES)).refusal is None
        disability = {"renta_taxpayer.disability_grade": "ge_33_lt_65"}

        # Without a stated disability the increase is not in question; with one, it blocks until stated.
        assert "0021" not in _blocking_boxes(_findings(work))
        assert "0021" in _blocking_boxes(_findings(work, profile_values=disability))

        def stated(casilla: str, value: str) -> ModeloScalarEditIntentV1:
            return ModeloScalarEditIntentV1(
                address=ModeloEditScalarAddressV1(casilla_id=casilla),
                kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                value=value,
            )

        assert work.apply(scalar=(stated("0021", "0"),)).refusal is None
        assert "0021" not in _blocking_boxes(_findings(work, profile_values=disability))

        # The legal limits are 500 for the professional-body fees and 300 for the legal defence.
        assert work.apply(scalar=(stated("0015", "500"), stated("0016", "300"))).refusal is None
        assert not {"0015", "0016"} & _blocking_boxes(_findings(work))
        assert work.apply(scalar=(stated("0015", "500.01"), stated("0016", "300.01"))).refusal is None
        assert {"0015", "0016"} <= _blocking_boxes(_findings(work))


@pytest.mark.parametrize("year", _renta_years())
def test_a_return_with_no_work_income_record_asks_for_no_statement_of_the_four_boxes(tmp_path: Path, year: int) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as work,
    ):
        assert work.apply(binding=tuple(_attest(binding_id) for binding_id in _CARRIES)).refusal is None
        assert _blocking_boxes(_findings(work)) == set()
        assert _TRABAJO not in {a.family for a in _form(work).carry_attestations}


@pytest.mark.parametrize("year", _renta_years()[-1:])
def test_the_work_income_statement_is_offered_only_once_the_open_carries_are_stated(tmp_path: Path, year: int) -> None:
    """Both families are never open at once: a return with an open carry has no calculation to rest a record on.

    The carries must be answered before the first calculation, and the work-income statement is
    offered from the calculation on, so the carry family comes first and the work-income family
    follows without any refusal beside it. Withdrawing a carry statement afterwards leaves the
    return uncalculable, and the edit refuses that withdrawal.
    """
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as work,
    ):
        _record_certificate(work, year)
        carry = AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING
        before = {attestation.family: attestation for attestation in _form(work).carry_attestations}
        assert set(before) == {carry}
        with pytest.raises(ModeloAbsenceStatementNothingOpenError):
            absence_statement_submission(work.baseline(), before.values(), family=_TRABAJO)

        stated = absence_statement_submission(work.baseline(), before.values(), family=carry)
        assert work.apply(binding=stated.binding_intents).refusal is None
        after = {attestation.family: attestation for attestation in _form(work).carry_attestations}
        assert set(after) == {_TRABAJO}
        submission = absence_statement_submission(work.baseline(), after.values(), family=_TRABAJO)
        assert work.apply(binding=submission.binding_intents).refusal is None

        withdrawn = work.apply(
            binding=(
                ModeloBindingEditIntentV1(
                    address=ModeloEditBindingAddressV1(binding_id=_CARRIES[0]),
                    kind=ModeloEditBindingIntentKind.REMOVE_OVERRIDE,
                ),
            )
        )
        assert withdrawn.refusal is not None
