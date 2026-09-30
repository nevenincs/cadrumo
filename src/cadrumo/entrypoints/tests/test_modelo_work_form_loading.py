"""A declaration's editor form says what the filer entered only from the recorded operator layer.

Driven over real encrypted storage through the production calculation and edit
executors, then read back through the form loading service with the pinned
authority's published layout. A value the filer typed reads as entered and
stays so after a recalculation; a declaration nobody has calculated knows it
holds no entries; the admission the caller holds decides what is offered for
editing, and one for another declaration offers nothing.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ...application.modelo.edit_models import (
    ModeloEditAdmissionResultV1,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloScalarEditIntentV1,
)
from ...application.modelo.work_form_models import (
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormLayoutProvenance,
    ModeloFormOrigin,
    ModeloWorkForm,
    address_key,
)
from ...application.modelo.work_form_service import ModeloWorkFormLoadV1, load_modelo_work_form
from ...core.casilla_id import validated_casilla_id
from ...core.external_constants import OutputLanguage
from .modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_C06 = validated_casilla_id("06")


def _load(work: SeededOperatorWork, admission: ModeloEditAdmissionResultV1 | None) -> ModeloWorkFormLoadV1:
    unit = work.work_unit
    return load_modelo_work_form(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=work.operation,
        work_unit_repository=work.ports.work_unit_repository,
        calculation_repository=work.ports.calculation_repository,
        verification_repository=VerificationReportCatalogueRepository(bucket_id=unit.bucket_id),
        admission=admission,
        language=OutputLanguage.ES,
    )


def _field(form: ModeloWorkForm, casilla_id: str) -> ModeloFormField:
    return next(field for field in form.fields() if address_key(field.address) == ("casilla", casilla_id))


@pytest.mark.timeout(240)
def test_a_typed_value_reads_as_entered_and_survives_a_recalculation(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        fresh = _load(work, work.admit())
        applied = work.apply(
            scalar=(
                ModeloScalarEditIntentV1(
                    address=ModeloEditScalarAddressV1(casilla_id=_C06),
                    kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                    value="100",
                ),
            )
        )
        assert applied.refusal is None
        edited = _load(work, work.admit())
        work.recalculate()
        recalculated = _load(work, None)

    assert fresh.form.operator_entries_known
    assert fresh.form.layout_provenance is not ModeloFormLayoutProvenance.INSPECTION_ONLY
    assert _field(fresh.form, "06").origin is not ModeloFormOrigin.ENTERED
    assert _field(fresh.form, "06").editability is ModeloFormEditability.EDITABLE_VALUE
    entered = _field(edited.form, "06")
    assert entered.origin is ModeloFormOrigin.ENTERED
    assert entered.value == Decimal("100")
    assert _field(recalculated.form, "06").origin is ModeloFormOrigin.ENTERED
    assert _field(recalculated.form, "06").editability is ModeloFormEditability.NO_ADMISSION
    assert not edited.verified
    assert not edited.filed


@pytest.mark.timeout(240)
def test_an_admission_for_another_declaration_offers_nothing(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        other = work.sibling("2T")
        form = _load(work, other.admit()).form

    assert _field(form, "06").editability is ModeloFormEditability.NO_ADMISSION
    assert not form.edit_admitted
