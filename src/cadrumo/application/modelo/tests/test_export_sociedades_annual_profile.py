"""The annual Impuesto sobre Sociedades export resolves its own model profile and builds a snapshot."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.modelo import Modelo
from ....core.period import Period
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.form_codes import form_for_role
from ....domain.calculations.registry.tests.authored_editions import open_ended_revision, revision_first_exercise
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id
from ...filing.producer_snapshot import build_filing_producer_snapshot
from ...filing.producer_snapshot_m200 import Modelo200ProfileFacts
from ...filing.tests.producer_snapshot_support import (
    TAXPAYER_TAX_ID,
    elections,
    producer_snapshot_presenter,
    taxpayer_identity,
)
from ..export_accounts import resolve_export_model_profile
from ..export_ports import ModeloExportPorts
from .empty_borrador_revision_support import empty_borrador_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "5d0c7e1b-3a64-4f8e-b2a9-6c1d9e4f7a30"
_AT = datetime.fromtimestamp(0, tz=UTC)


def test_the_annual_sociedades_export_profile_builds_a_snapshot_with_no_projection_rows(
    operation: PinnedAuthorityOperation,
) -> None:
    modelo = form_for_role("sociedades.annual")
    exercise = revision_first_exercise(modelo, str(open_ended_revision(modelo).id))
    period = Period.from_year_and_code(exercise, "0A")
    snapshot = published_snapshot(
        modelo,
        filing_year=exercise,
        period="0A",
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    revision_id = str(snapshot.revision.id)
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=exercise,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=exercise,
        period=period,
        revision_id=revision_id,
        name="Annual return",
        created_at=_AT,
        updated_at=_AT,
        state=WorkUnitState.BORRADOR,
    )
    revision = empty_borrador_revision(work_unit, snapshot.snapshot_ref, (), at=_AT)
    workflow_profile = TaxpayerProfile(tax_id=TAXPAYER_TAX_ID, iva_regime=IVARegime("GENERAL"))

    model_profile, m303_filing_facts = resolve_export_model_profile(
        modelo=Modelo(modelo),
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        iva_profile=None,
        export_ports=cast(ModeloExportPorts, object()),
        operation=operation,
        m360_solicitud=None,
    )
    built = build_filing_producer_snapshot(
        modelo=Modelo(modelo),
        taxpayer_tax_id=TAXPAYER_TAX_ID,
        taxpayer_identity=taxpayer_identity(),
        presenter=producer_snapshot_presenter(),
        model_profile=model_profile,
        elections=elections(ResultDisposition.INGRESO),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=m303_filing_facts,
    )

    assert m303_filing_facts is None
    assert isinstance(built.model_profile, Modelo200ProfileFacts)
    rows = built.model_profile.projection_rows
    assert type(rows).model_fields
    assert all(getattr(rows, name) == () for name in type(rows).model_fields)
