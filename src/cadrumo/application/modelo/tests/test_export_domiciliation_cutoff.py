"""Domiciliation cutoff coverage at the application export seam."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core.errors.error_codes import get_registered_error_code
from ....core.payment_election import PaymentElection
from ....core.period import Period
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..action_errors import ModeloDomiciliationPastCutoffError
from ..export import ModeloExportCommand, _require_domiciliation_before_cutoff

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(2026, 1, 1, tzinfo=UTC)
_BUCKET_ID = "6e84e19e-58f8-4241-b2d1-6ab9bcc3dd7b"


# Modelo 303 2026 monthly period 01 declares payment_cutoff_on 2026-02-25; the
# 2026 quarterly 1T window declares none. Clocks are UTC; the gate compares the
# Europe/Madrid civil date (UTC+1 in February).
@pytest.mark.parametrize(
    ("period_code", "exported_at", "expected"),
    (
        ("01", datetime(2026, 2, 25, 22, 59, tzinfo=UTC), "admitted"),
        ("01", datetime(2026, 2, 25, 23, 0, tzinfo=UTC), "refused"),
        ("1T", datetime(2026, 7, 1, 12, 0, tzinfo=UTC), "advisory"),
    ),
    ids=("on-the-madrid-cutoff-day", "after-the-madrid-cutoff-day", "no-declared-cutoff"),
)
def test_domiciliation_is_refused_after_the_window_payment_cutoff_in_madrid(
    period_code: str,
    exported_at: datetime,
    expected: str,
    operation: PinnedAuthorityOperation,
) -> None:
    """U closes on the registry's payment_cutoff_on; an undeclared cutoff advises instead of refusing."""
    period = Period.from_year_and_code(2026, period_code)
    snapshot = operation.snapshot("303", filing_year=period.filing_year, period=period.registry_token)
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=period.filing_year,
            period=period,
            revision_id=snapshot.revision.id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=period.filing_year,
        period=period,
        revision_id=snapshot.revision.id,
        name=f"303-{period.filing_year}-{period.registry_token}",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    command = ModeloExportCommand(
        calculation_revision_id="a" * 64,
        output_path=Path("unused.txt"),
        actor="operator",
        payment_election=PaymentElection.DOMICILIACION,
    )

    def gate(disposition: ResultDisposition | None) -> bool:
        return _require_domiciliation_before_cutoff(
            command,
            work_unit=work_unit,
            resolved_result_disposition=disposition,
            exported_at=exported_at,
            operation=operation,
        )

    assert gate(ResultDisposition.INGRESO) is False
    if expected == "refused":
        with pytest.raises(ModeloDomiciliationPastCutoffError) as refused:
            gate(ResultDisposition.DOMICILIACION)
        assert get_registered_error_code(refused.value).code == "REFUSED_MODELO_DOMICILIATION_PAST_CUTOFF"
        assert refused.value.context == {
            "calculation_revision_id": "a" * 64,
            "modelo": "303",
            "filing_year": "2026",
            "period": "01",
            "payment_cutoff_on": "2026-02-25",
            "export_on": "2026-02-26",
        }
    else:
        assert gate(ResultDisposition.DOMICILIACION) is (expected == "advisory")
