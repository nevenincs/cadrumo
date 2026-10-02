"""One wire slot is edited, recalculated and exported through the casilla that owns it."""

from __future__ import annotations

from pathlib import Path

import pytest

from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ...application.filing.draft_construction import build_draft
from ...application.filing.runtime import ModeloOperatorProfile, build_runtime_schema_provider
from ...application.modelo.edit_models import (
    ModeloEditAdmittedV1,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloScalarEditIntentV1,
)
from ...application.modelo.revision_replay_inputs import revision_filing_replay_inputs
from ...application.modelo.work_form_models import ModeloFormEditability, ModeloFormOrigin, ModeloWorkForm, address_key
from ...application.modelo.work_form_service import load_modelo_work_form
from ...core.external_constants import OutputLanguage
from ...domain.calculations.export_field_kind import CasillaFieldKind
from ...domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from .modelo_operator_work_storage import SEEDED_AT, SeededOperatorWork, seeded_operator_work

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CASILLA = "decl.solicitante.nace-1"


def _form(work: SeededOperatorWork) -> ModeloWorkForm:
    unit = work.work_unit
    admission = work.admit()
    assert isinstance(admission, ModeloEditAdmittedV1), admission
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
        language=OutputLanguage.EN,
        reference_on=SEEDED_AT.date(),
    ).form


def test_the_nace_slot_is_written_through_its_casilla(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path, modelo="360", filing_year=2025, period_code="AD-HOC") as work:
        form = _form(work)
        assert ("casilla", _CASILLA) in {address_key(field.address) for field in form.fields()}
        casilla = next(field for field in form.fields() if address_key(field.address) == ("casilla", _CASILLA))
        assert casilla.editability is ModeloFormEditability.EDITABLE_VALUE
        applied = work.apply(
            scalar=(
                ModeloScalarEditIntentV1(
                    address=ModeloEditScalarAddressV1(casilla_id=_CASILLA),
                    kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                    value="12345",
                ),
            ),
        )
        assert applied.refusal is None, applied.refusal
        head = work.require_head()
        assert head.input_values_by_casilla_id[_CASILLA] == "12345"
        updated = _form(work)
        field = next(field for field in updated.fields() if address_key(field.address) == ("casilla", _CASILLA))
        assert field.value == "12345"
        assert field.origin is ModeloFormOrigin.ENTERED
        recalculated = work.recalculate()
        assert recalculated.input_values_by_casilla_id[_CASILLA] == "12345"
        assert (
            next(field for field in _form(work).fields() if address_key(field.address) == ("casilla", _CASILLA)).value
            == "12345"
        )
        unit = work.work_unit
        provider = build_runtime_schema_provider(
            filing_year=unit.filing_year, period=unit.period, modelos=("360",), operation=work.operation
        )
        draft = build_draft(
            modelo="360",
            period=unit.period,
            profile=ModeloOperatorProfile(tax_id="00000000T", display_name="Synthetic wire-input test"),
            inputs=revision_filing_replay_inputs(revision=recalculated, work_unit=unit, operation=work.operation),
            schema_provider=provider,
        )
        snapshot = provider.get_snapshot("360")
        record = next(
            record
            for layout in snapshot.revision.export_layouts
            for record in layout.records
            if record.record_type == "page_01"
        )
        wire = next(field for field in record.fields if field.casilla_id == _CASILLA)
        assert (record.record_type, wire.offset, wire.length) == ("page_01", 799, 5)
        assert wire.kind is CasillaFieldKind.CASILLA
        assert wire.binding is None
        value = next(value for value in draft.values if value.casilla_id == _CASILLA)
        assert value.value == "12345"
        assert render_fixed_width_export_field(wire, value.value) == "12345"
