"""Resolve the pinned authority state for the income-tax acceptance campaign.

This is development tooling, deliberately outside the product CLI.  It reports
the latest completed calendar year separately from the first compatible M130 /
M100 calculation-and-layout coordinate.  Export write admission remains a
separate result: an incomplete layout must be reported, never hidden by
choosing an older coordinate.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from typing import Protocol

from cadrumo.application.filing.export_parity import assert_xml_declaration_aux_declared
from cadrumo.application.filing.export import export_layout_renderability_reason_code
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.filing.errors import FilingExportError
from cadrumo.domain.filing.software_identity import aeat_aux_version

_M130_PERIODS = ("1T", "4T")
_M100_PERIOD = "0A"


class _SupportEnvelope(Protocol):
    floor: int


class _AuthorityOperation(Protocol):
    generation: object

    def supported_filing_years(self) -> _SupportEnvelope: ...

    def snapshot(self, modelo_id: str, *, filing_year: int, period: str) -> object: ...


@dataclass(frozen=True, slots=True)
class ExportAdmission:
    """One declared layout's local-byte and write-door status."""

    layout_id: str
    format: str
    renderability: str | None
    admission: str
    refusal_code: str | None
    undeclared_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CoordinateResolution:
    """The selected revision and layout result for one Modelo coordinate."""

    modelo: str
    period: str
    revision: str
    exports: tuple[ExportAdmission, ...]


@dataclass(frozen=True, slots=True)
class IncomeTaxAuthorityResolution:
    """JSON-safe P01 authority report for an explicit development run."""

    as_of: str
    latest_completed_year: int
    selection_mode: str
    requested_year: int | None
    selected_year: int | None
    support_gap_years: int | None
    authority_generation: str
    modelo_130: tuple[CoordinateResolution, ...]
    modelo_100: CoordinateResolution | None
    excluded_years: tuple[tuple[int, str], ...]

    def to_dict(self) -> dict[str, object]:
        """Return a stable machine-readable receipt fragment."""
        return asdict(self)


def resolve_income_tax_authority(
    operation: _AuthorityOperation,
    *,
    as_of: date,
    year: int | None = None,
) -> IncomeTaxAuthorityResolution:
    """Resolve the explicit year or latest compatible completed year.

    ``as_of`` selects the completed calendar year only.  It is intentionally
    not forwarded as a revision ``on`` date: that selector reads the tax period
    or a declared filing window, while this campaign's as-of date is an
    observation timestamp after the tax year has closed.
    """
    latest_completed_year = as_of.year - 1
    support = operation.supported_filing_years()
    candidates = (year,) if year is not None else tuple(range(latest_completed_year, support.floor - 1, -1))
    excluded: list[tuple[int, str]] = []

    for candidate in candidates:
        try:
            m130 = tuple(_resolve_coordinate(operation, "130", candidate, period) for period in _M130_PERIODS)
            m100 = _resolve_coordinate(operation, "100", candidate, _M100_PERIOD)
        except RegistryError as exc:
            excluded.append((candidate, f"{type(exc).__name__}: {exc}"))
            continue
        return IncomeTaxAuthorityResolution(
            as_of=as_of.isoformat(),
            latest_completed_year=latest_completed_year,
            selection_mode="explicit_year" if year is not None else "latest_supported",
            requested_year=year,
            selected_year=candidate,
            support_gap_years=latest_completed_year - candidate,
            authority_generation=_logical_generation(operation),
            modelo_130=m130,
            modelo_100=m100,
            excluded_years=tuple(excluded),
        )

    return IncomeTaxAuthorityResolution(
        as_of=as_of.isoformat(),
        latest_completed_year=latest_completed_year,
        selection_mode="explicit_year" if year is not None else "latest_supported",
        requested_year=year,
        selected_year=None,
        support_gap_years=None,
        authority_generation=_logical_generation(operation),
        modelo_130=(),
        modelo_100=None,
        excluded_years=tuple(excluded),
    )


def resolve_published_income_tax_authority(*, as_of: date, year: int | None = None) -> IncomeTaxAuthorityResolution:
    """Resolve through one runtime authority operation and retain its generation pin."""
    with bundled_indexed_authority().operation() as operation:
        return resolve_income_tax_authority(operation, as_of=as_of, year=year)


def _resolve_coordinate(
    operation: _AuthorityOperation,
    modelo: str,
    filing_year: int,
    period: str,
) -> CoordinateResolution:
    snapshot = operation.snapshot(modelo, filing_year=filing_year, period=period)
    revision = snapshot.revision
    return CoordinateResolution(
        modelo=modelo,
        period=period,
        revision=str(revision.id),
        exports=tuple(_admit_layout(layout) for layout in revision.export_layouts),
    )


def _admit_layout(layout: object) -> ExportAdmission:
    renderability = export_layout_renderability_reason_code(layout)
    if renderability is not None:
        return ExportAdmission(
            layout_id=str(layout.id),
            format=layout.format.value,
            renderability=renderability.value,
            admission="blocked",
            refusal_code="application.filing.export.errors.layout_not_renderable",
            undeclared_fields=(),
        )
    try:
        # ``Aux/VERSION`` is producer identity, not selected-authority data.
        # The canonical domain contract owns normalization and fails closed for
        # package versions that cannot occupy AEAT's four-character field.
        assert_xml_declaration_aux_declared(layout, aux_version=aeat_aux_version())
    except FilingExportError as exc:
        context = exc.context or {}
        raw_fields = context.get("undeclared_fields", ())
        fields = tuple(str(item) for item in raw_fields) if isinstance(raw_fields, tuple) else ()
        return ExportAdmission(
            layout_id=str(layout.id),
            format=layout.format.value,
            renderability=None,
            admission="blocked",
            refusal_code=exc.translated_message,
            undeclared_fields=fields,
        )
    return ExportAdmission(
        layout_id=str(layout.id),
        format=layout.format.value,
        renderability=None,
        admission="admitted",
        refusal_code=None,
        undeclared_fields=(),
    )


def _logical_generation(operation: _AuthorityOperation) -> str:
    generation = operation.generation
    logical_generation = getattr(generation, "logical_generation", None)
    if not isinstance(logical_generation, str):
        raise TypeError("income-tax authority resolver requires a generation-pinned operation")
    return logical_generation


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report pinned M130/M100 authority and export admission for acceptance work.",
    )
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--year", type=int, help="Resolve this explicit filing year.")
    choice.add_argument("--latest-supported", action="store_true", help="Resolve the latest compatible completed year.")
    parser.add_argument("--as-of", type=date.fromisoformat, required=True, help="Observation date (YYYY-MM-DD).")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the deterministic development report and write its JSON receipt to stdout."""
    args = _parser().parse_args(argv)
    report = resolve_published_income_tax_authority(as_of=args.as_of, year=args.year)
    print(json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":")))
    return 0 if report.selected_year is not None else 2


if __name__ == "__main__":  # pragma: no cover - module execution wrapper
    raise SystemExit(main())
