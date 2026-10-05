"""Workbench edits reach the declaration through the production contract, over real storage.

The workbench's installed reader and actions run against a seeded declaration
with the real edit admission, parser, preflight, renewal and edit executor. Only
the operation supervisor is stood in for: the door's submission is recorded and
the recorded request is run through the production executor, as the supervised
operation would run it.

* a box carried from another filing, which the form offers to replace, takes the
  filer's value and gives it back to its source, addressed to the binding that
  feeds it;
* a declaration last calculated outside the workbench is reported as not
  recording which values the filer typed, and names the box whose value
  applying would return to its source.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from ......application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ......application.modelo.work_form_models import (
    ModeloFormBindingAddressV1,
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    address_key,
)
from ......core.casilla_id import validated_casilla_id
from ......core.external_constants import OutputLanguage
from .....tests.modelo_operator_work_storage import SEEDED_AT, SeededOperatorWork, seeded_operator_work
from ....tests.modelo_workbench_session import RecordedSubmissions, application_workbench
from ..installed import InstalledModeloWorkbench
from ..ports import WorkbenchParsed
from ..session import WorkbenchEditSession

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_OVERRIDE_EDITABILITIES = {ModeloFormEditability.OVERRIDABLE_SOURCE, ModeloFormEditability.EDITABLE_OVERRIDE}


@dataclass
class _Workbench:
    work: SeededOperatorWork
    installed: InstalledModeloWorkbench
    submissions: RecordedSubmissions

    def field(self, key: tuple[str, str]) -> ModeloFormField:
        form = self.installed.load(OutputLanguage.EN).form
        return next(item for item in form.fields() if address_key(item.address) == key)

    def apply(self, session: WorkbenchEditSession) -> None:
        """Submit the staged changes through the installed actions, then run the recorded request for real."""
        asyncio.run(self.installed.apply(session.payload()))
        request = self.submissions.pop()
        refusal = self.work.execute(request)
        assert refusal is None, f"the edit executor refused the workbench's submission: {refusal!r}"


@contextmanager
def _workbench(tmp_path: Path) -> Generator[_Workbench]:
    submissions = RecordedSubmissions()
    with seeded_operator_work(tmp_path) as work:
        installed = application_workbench(work.work_unit, operation=work.operation, submissions=submissions)
        yield _Workbench(work=work, installed=installed, submissions=submissions)


@pytest.mark.timeout(300)
def test_a_carried_box_takes_the_filers_value_and_gives_it_back_to_its_source(tmp_path: Path) -> None:
    with _workbench(tmp_path) as bench:
        bench.work.recalculate()
        form = bench.installed.load(OutputLanguage.EN).form
        carried = next(
            item
            for item in form.fields()
            if isinstance(item.address, ModeloFormCasillaAddressV1) and item.editability in _OVERRIDE_EDITABILITIES
        )
        key = address_key(carried.address)
        parsed = bench.installed.parse(carried, "100", OutputLanguage.EN)
        assert isinstance(parsed, WorkbenchParsed), parsed

        session = WorkbenchEditSession(OutputLanguage.EN)
        assert session.stage_value(carried, parsed.value, parsed.display) is None
        preflight = asyncio.run(bench.installed.preflight(session.payload()))
        bench.apply(session)
        overridden = bench.field(key)

        restoring = WorkbenchEditSession(OutputLanguage.EN)
        assert restoring.stage_restore(overridden) is None
        bench.apply(restoring)
        restored = bench.field(key)

    assert isinstance(session.payload()[0].address, ModeloFormBindingAddressV1)
    assert not [finding for finding in preflight.findings if finding.blocking]
    assert overridden.origin is ModeloFormOrigin.OVERRIDES_SOURCE
    assert overridden.value == Decimal("100")
    assert restored.origin is not ModeloFormOrigin.OVERRIDES_SOURCE


@pytest.mark.timeout(300)
def test_a_declaration_calculated_elsewhere_names_the_value_applying_returns_to_source(tmp_path: Path) -> None:
    c06 = validated_casilla_id("06")
    with _workbench(tmp_path) as bench:
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            bench.work.work_unit_id, ports=bench.work.ports, clock=SEEDED_AT, casilla_inputs={c06: Decimal("100")}
        )
        form = bench.installed.load(OutputLanguage.EN).form
        typed_elsewhere = next(
            item for item in form.fields() if item.address == ModeloFormCasillaAddressV1(casilla_id=c06)
        )
        target = next(
            item
            for item in form.fields()
            if item.editability is ModeloFormEditability.EDITABLE_VALUE and item.address != typed_elsewhere.address
        )
        session = WorkbenchEditSession(OutputLanguage.EN)
        parsed = bench.installed.parse(target, "50", OutputLanguage.EN)
        assert isinstance(parsed, WorkbenchParsed), parsed
        session.stage_value(target, parsed.value, parsed.display)
        preflight = asyncio.run(bench.installed.preflight(session.payload()))

    assert not form.operator_entries_known
    assert typed_elsewhere.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
    assert preflight.operator_entries_unknown
