"""Generate the desktop host's calendar test input from the product's own calendar read models.

It builds one calendar over the horizon year of the bundled authority's filing-year envelope for a
synthetic declared taxpayer, with the rows it holds off the schedule and one observed message,
and serialises the registered ``overview.calendar`` request and served result as the product does.
The host tests compare what the host serves against these bytes, so every name and value they
check is the product's. No runtime, profile, credential store or network is opened.
"""

import argparse
import json
from datetime import date
from pathlib import Path
from uuid import UUID

from dev.packaging.native.build_directory import require_enrolled_build
from dev.packaging.native.build_paths import build_paths

from cadrumo.application.overview.calendar import build_overview_calendar
from cadrumo.application.overview.calendar_models import (
    OverviewCalendarEvent,
    OverviewCalendarEventType,
    OverviewCalendarRange,
)
from cadrumo.application.overview.read_calendar_projection import OverviewCalendarSnapshot
from cadrumo.application.overview.read_payload import OverviewCalendarRead
from cadrumo.application.overview.read_request import OverviewReadKind, OverviewReadRequest
from cadrumo.application.overview.read_result import OverviewReadProjection
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.contribuyente.entity_type import EntityType
from cadrumo.domain.contribuyente.renta_codes import FiscalResidency
from cadrumo.domain.deadlines.models import (
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
    ModeloEnrollment,
    TaxpayerProfile,
)

_FIXTURE_NAME = "calendar-read-contract.json"
_PROFILE_ID = UUID(int=1)


def _taxpayer() -> TaxpayerProfile:
    """A synthetic declared autonomo in estimacion directa."""
    return TaxpayerProfile(
        tax_id="X0001500M",
        entity_type=EntityType.from_registry("natural_person"),
        irpf_income_categories=frozenset({IrpfIncomeCategory.from_registry("actividad_economica")}),
        irpf_estimation_regime=IrpfEstimationRegime.from_registry("directa_normal"),
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_professionals_with_retencion=False,
        art109_activity_income_withholding_ge_70pct=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
        fiscal_residency=FiscalResidency.from_registry("resident_irpf"),
        enrollment=ModeloEnrollment(large_company=False),
    )


def _message(on: date) -> OverviewCalendarEvent:
    return OverviewCalendarEvent(
        event_type=OverviewCalendarEventType.MESSAGE,
        event_date=on,
        source="aeat_sede_notifications",
        summary="Synthetic notification",
        reference_id="SYNTHETIC-1",
        source_url="https://example.invalid/notification",
    )


def document() -> dict[str, object]:
    """The registered request and its served result, through the real strict models and serializer."""
    with bundled_indexed_authority().operation() as operation:
        envelope = operation.supported_filing_years()
        served = OverviewCalendarRange(from_date=date(envelope.horizon, 1, 1), to_date=date(envelope.horizon, 12, 31))
        today = date(envelope.horizon, 6, 1)
        calendar = build_overview_calendar(
            _taxpayer(),
            served,
            operation=operation,
            today=today,
            raw_values={},
            show_suppressed=True,
            events=(_message(today),),
        )
        snapshot = OverviewCalendarSnapshot.from_calendar(calendar, envelope=envelope)
    request = OverviewReadRequest(
        profile_id=_PROFILE_ID,
        kind=OverviewReadKind.CALENDAR,
        output_language=OutputLanguage.ES,
        from_date=served.from_date,
        to_date=served.to_date,
        show_suppressed=True,
    )
    result = OverviewReadProjection(
        profile_id=_PROFILE_ID, request=request, payload=OverviewCalendarRead(calendar=snapshot)
    )
    return {
        "request": request.model_dump(mode="json", exclude_none=True),
        "result": result.model_dump(mode="json"),
    }


def destination(build_directory: Path, output: Path) -> Path:
    """Require the exact declared testing member and refuse links before writing."""
    build = require_enrolled_build(build_directory)
    expected = build_paths(build)["desktop_testing"] / _FIXTURE_NAME
    if ".." in output.parts or not output.is_absolute() or output != expected:
        raise ValueError("Fixture output must be the enrolled desktop testing member")
    member = build
    for part in expected.relative_to(build).parts:
        member /= part
        if member.is_symlink() or member.is_junction():
            raise ValueError("Fixture output must not use symlinks or junctions")
    if expected.resolve() != expected:
        raise ValueError("Fixture output must remain in its physical build directory")
    return expected


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = destination(args.build_dir, args.output)
    rendered = json.dumps(document(), sort_keys=True, indent=2) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    # Recheck after directory creation before opening the output member.
    target = destination(args.build_dir, args.output)
    target.write_text(rendered, encoding="utf-8", newline="\n")
