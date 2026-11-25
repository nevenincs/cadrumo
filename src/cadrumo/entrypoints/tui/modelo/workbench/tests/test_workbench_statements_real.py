"""A statement the form serves reaches the declaration through the workbench, and a stated box can be withdrawn.

The workbench's installed reader and actions run against a seeded Modelo 100
with the real edit admission, form, preflight, renewal and edit executor, for
every year the registry's support envelope admits. Only the operation
supervisor is stood in for: the door's submission is recorded and run through
the production executor, as the supervised operation would run it.

* every statement the form serves stages, on every box it names, the intent
  the edit contract admits there; applying it leaves each box stated, apart
  from a value typed, and the form serves the statement no more;
* a stated box offers its withdrawal, addressed to the binding the statement
  was made on, as the form allows a change of it.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest

from ......adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ......application.modelo.work_form_field_vocabulary import ModeloFormBindingAddressV1, address_key
from ......application.modelo.work_form_models import ModeloWorkForm, edit_address
from ......core.authority_grade import RegistryAuthorityGrade
from ......core.external_constants import OutputLanguage
from ......domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from ......domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ......domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from ......domain.user_profile.values import UserProfileFact
from .....adapter_composition import profile_adapter_composition
from .....tests.modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work
from ....tests.modelo_workbench_session import RecordedSubmissions, application_workbench
from ..factory import InstalledModeloWorkbench
from ..ports import WorkbenchChangeKind
from ..session import WorkbenchEditSession, statement_fields

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FACTS = (UserProfileFact(path="tax_residence.ccaa", value="madrid"), *RENTA_UNMARRIED_TAXPAYER_FACTS)


def _renta_years() -> tuple[int, ...]:
    """The Modelo 100 years the envelope admits at calculation grade."""
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


@dataclass
class _Workbench:
    work: SeededOperatorWork
    installed: InstalledModeloWorkbench
    submissions: RecordedSubmissions

    def form(self) -> ModeloWorkForm:
        return self.installed.load(OutputLanguage.EN).form

    def apply(self, session: WorkbenchEditSession) -> None:
        """Submit the staged changes through the installed actions, then run the recorded request for real."""
        asyncio.run(self.installed.apply(session.payload()))
        refusal = self.work.execute(self.submissions.pop())
        assert refusal is None, f"the edit executor refused the workbench's submission: {refusal!r}"


@contextmanager
def _renta_workbench(tmp_path: Path, year: int) -> Generator[_Workbench]:
    submissions = RecordedSubmissions()
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as work,
    ):
        installed = application_workbench(work.work_unit, operation=work.operation, submissions=submissions)
        yield _Workbench(work=work, installed=installed, submissions=submissions)


@pytest.mark.parametrize("year", _renta_years())
def test_every_served_statement_applies_through_the_workbench_and_a_stated_box_can_be_withdrawn(
    tmp_path: Path, year: int
) -> None:
    with _renta_workbench(tmp_path, year) as bench:
        offered = bench.form()
        served = offered.carry_attestations
        assert served, "the seeded declaration serves no statement"
        session = WorkbenchEditSession(OutputLanguage.EN)
        for statement in served:
            assert session.stage_statement(offered, statement)
        preflight = asyncio.run(bench.installed.preflight(session.payload()))
        named = {
            address_key(field.address) for statement in served for field in statement_fields(offered, statement) or ()
        }
        bench.apply(session)
        settled = bench.form()
        stated = [field for field in settled.fields() if address_key(field.address) in named]

        withdrawing = WorkbenchEditSession(OutputLanguage.EN)
        offered_withdrawal = withdrawing.stage_clear(stated[0]) is None or withdrawing.stage_restore(stated[0]) is None

    assert all(change.kind is WorkbenchChangeKind.STATE_ABSENT for change in session.payload())
    assert len(session.payload()) == sum(len(statement.binding_ids) for statement in served)
    assert not [finding for finding in preflight.findings if finding.blocking]
    assert len(stated) == len(named)
    assert all(field.stated_absent is not None for field in stated)
    assert settled.carry_attestations == ()
    # Withdrawing goes to the binding the statement was made on, which the edit contract takes as removing it.
    assert offered_withdrawal
    (withdrawal,) = withdrawing.payload()
    assert withdrawal.address == edit_address(stated[0])
    assert isinstance(withdrawal.address, ModeloFormBindingAddressV1)
    assert withdrawal.kind in {WorkbenchChangeKind.CLEAR, WorkbenchChangeKind.RESTORE}
