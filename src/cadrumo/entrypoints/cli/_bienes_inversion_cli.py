"""Typer registration for the capital-goods IVA regularización register.

The commands delegate register persistence to
:class:`BienesInversionRegisterService` and emit
typed payloads from :mod:`._bienes_inversion_payloads`. The
register feeds the LIVA arts. 107-110 regularización (Modelo 303 casilla 43 /
Modelo 390); the annual compute itself is the pure domain function
:func:`compute_regularizacion_anual`.
"""

from __future__ import annotations

import typer

from ...application.bienes_inversion import BienesInversionRegisterService
from ...core.i18n import tr
from ...domain.bienes_inversion import (
    BienInversionDisposal,
    BienInversionDisposalRegime,
    BienInversionIvaRecord,
    BienInversionKind,
)
from ._bienes_inversion_payloads import (
    BienesInversionDeclareResult,
    BienesInversionListResult,
    BienInversionRecordPayload,
)
from ._command_policy import command_execution_policy
from ._common import _bad, _emit_envelope, parse_decimal_amount
from ._common import active_bucket_id_or_refuse as _register_bucket_id
from ._ledger_execution_policies import LEDGER_READ, LEDGER_WRITE, declare_metadata_group


def register_bienes_inversion_commands(app: typer.Typer) -> None:
    """Mount the bienes-de-inversión register command group on the ledger app."""
    app.add_typer(bienes_inversion_app, name="bienes-inversion")


bienes_inversion_app = typer.Typer(
    name="bienes-inversion",
    help=tr(
        "cli.app.ledger.bienes_inversion.group_help",
        default="Capital-goods IVA deduction regularización register (LIVA arts. 107-110).",
    ),
    no_args_is_help=True,
)
declare_metadata_group(bienes_inversion_app)


def _parse_kind(raw: BienInversionKind) -> BienInversionKind:
    return raw


def _parse_disposal_regime(raw: str) -> BienInversionDisposalRegime:
    try:
        return BienInversionDisposalRegime(raw)
    except ValueError as exc:
        accepted = ", ".join(member.value for member in BienInversionDisposalRegime)
        raise _bad(
            tr(
                "cli.app.ledger.bienes_inversion.unknown_disposal_regime",
                default="Unknown disposal regime {regime!r}; accepted: {accepted}",
                regime=raw,
                accepted=accepted,
            ),
        ) from exc


def _record_payload(record: BienInversionIvaRecord) -> BienInversionRecordPayload:
    data = record.model_dump(mode="json")
    data["deduccion_efectuada"] = str(record.deduccion_efectuada)
    return BienInversionRecordPayload.model_validate(data)


@bienes_inversion_app.command(
    "declare",
    help=tr(
        "cli.app.ledger.bienes_inversion.declare_help",
        default="Declare one capital good tracked for IVA regularización.",
    ),
)
@command_execution_policy(LEDGER_WRITE)
def bienes_inversion_declare(
    ctx: typer.Context,
    identifier: str = typer.Argument(
        ...,
        help=tr("cli.app.ledger.bienes_inversion.identifier_help", default="Stable register identifier."),
    ),
    description: str = typer.Option(
        ...,
        "--description",
        help=tr("cli.app.ledger.bienes_inversion.description_help", default="Human description of the good."),
    ),
    acquisition_year: int = typer.Option(
        ...,
        "--acquisition-year",
        help=tr("cli.app.ledger.bienes_inversion.acquisition_year_help", default="Year the good was acquired."),
    ),
    acquisition_ledger_id: str = typer.Option(
        ...,
        "--acquisition-ledger-id",
    ),
    cuota_soportada: str = typer.Option(
        ...,
        "--cuota-soportada",
        help=tr(
            "cli.app.ledger.bienes_inversion.cuota_soportada_help",
            default="Total input IVA borne on acquisition (positive).",
        ),
    ),
    prorrata_inicial_pct: str = typer.Option(
        ...,
        "--prorrata-inicial",
        help=tr(
            "cli.app.ledger.bienes_inversion.prorrata_inicial_help",
            default="Definitive deduction percentage of the acquisition year (0-100).",
        ),
    ),
    kind: BienInversionKind = typer.Option(
        ...,
        "--kind",
        help=tr(
            "cli.app.ledger.bienes_inversion.kind_help",
            default="Regularisation window: mueble (4yr) or inmueble (9yr).",
        ),
    ),
    art108_elegible: bool = typer.Option(
        True,
        "--art108-elegible/--no-art108-elegible",
        help=tr(
            "cli.app.ledger.bienes_inversion.art108_help",
            default="Whether the good qualifies as a bien de inversión under LIVA art. 108.",
        ),
    ),
    asset_record_ref: str | None = typer.Option(
        None,
        "--asset-ref",
        help=tr(
            "cli.app.ledger.bienes_inversion.asset_ref_help",
            default="Optional cross-reference to an AssetRecord identifier.",
        ),
    ),
    prorrata_sector_id: str | None = typer.Option(
        None,
        "--sector",
    ),
    disposal_year: int | None = typer.Option(
        None,
        "--disposal-year",
        help=tr("cli.app.ledger.bienes_inversion.disposal_year_help", default="Optional art-110 disposal year."),
    ),
    disposal_regime: str | None = typer.Option(
        None,
        "--disposal-regime",
        help=tr(
            "cli.app.ledger.bienes_inversion.disposal_regime_help",
            default="Disposal regime (sujeta_no_exenta or exenta_o_no_sujeta); required with --disposal-year.",
        ),
    ),
) -> None:
    """Persist one :class:`BienInversionIvaRecord`."""
    bucket_id = _register_bucket_id()
    disposal: BienInversionDisposal | None = None
    if disposal_year is not None or disposal_regime is not None:
        if disposal_year is None or disposal_regime is None:
            raise _bad(
                tr(
                    "cli.app.ledger.bienes_inversion.disposal_requires_both",
                    default="--disposal-year and --disposal-regime must be supplied together.",
                ),
            )
        disposal = BienInversionDisposal(year=disposal_year, regime=_parse_disposal_regime(disposal_regime))
    record = BienInversionIvaRecord(
        identifier=identifier,
        description=description,
        acquisition_year=acquisition_year,
        cuota_soportada=parse_decimal_amount(cuota_soportada, label="cuota-soportada"),
        prorrata_inicial_pct=parse_decimal_amount(prorrata_inicial_pct, label="prorrata-inicial"),
        kind=_parse_kind(kind),
        art108_elegible=art108_elegible,
        asset_record_ref=asset_record_ref,
        acquisition_ledger_id=acquisition_ledger_id,
        prorrata_sector_id=prorrata_sector_id,
        disposal=disposal,
    )
    register = BienesInversionRegisterService().declare(record)
    payload = BienesInversionDeclareResult(
        bucket_id=bucket_id,
        record=_record_payload(record),
        count=len(register.records),
    )
    _emit_envelope(
        ctx,
        command="ledger.bienes_inversion.declare",
        result=payload,
        lines=(
            f"bucket\t{bucket_id}",
            f"identifier\t{record.identifier}",
            f"acquisition_year\t{record.acquisition_year}",
            f"kind\t{record.kind.value}",
            f"cuota_soportada\t{record.cuota_soportada}",
            f"prorrata_inicial_pct\t{record.prorrata_inicial_pct}",
            f"deduccion_efectuada\t{record.deduccion_efectuada}",
            f"count\t{len(register.records)}",
        ),
    )


@bienes_inversion_app.command(
    "list",
    help=tr(
        "cli.app.ledger.bienes_inversion.list_help",
        default="List every tracked capital good on the active profile register.",
    ),
)
@command_execution_policy(LEDGER_READ)
def bienes_inversion_list(ctx: typer.Context) -> None:
    """List register records via :class:`BienesInversionRegisterService`."""
    bucket_id = _register_bucket_id()
    register = BienesInversionRegisterService().list_all()
    rows = [_record_payload(record) for record in register.records]
    payload = BienesInversionListResult(bucket_id=bucket_id, rows=rows, count=len(rows))
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for record in register.records:
        lines.append(
            f"{record.identifier}\t{record.acquisition_year}\t{record.kind.value}\t"
            f"cuota={record.cuota_soportada}\tprorrata={record.prorrata_inicial_pct}",
        )
    _emit_envelope(
        ctx,
        command="ledger.bienes_inversion.list",
        result=payload,
        lines=lines,
    )
