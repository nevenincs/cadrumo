"""Typer registration for the cross-period IVA prorrata register.

The commands delegate register persistence to
:class:`ProrrataRegisterService` and emit typed payloads from
:mod:`._prorrata_register_payloads`. This is the operator ingress that reaches
the LIVA art. 106 prorrata-especial apportionment and the arts. 9.1.c / 101
per-sector apportionment on the live M303 aggregation path: ``elect-especial``
writes an ``ESPECIAL`` :class:`~domain.prorrata_register.ProrrataRegisterEntry`
so :func:`~application.aggregation._apply_especial_apportionment` fires, and
``declare-sector`` writes a :class:`~domain.prorrata_register.SectorDefinition`
so the register becomes sectorized and
:func:`~application.aggregation._apply_sector_apportionment` fires. Fail-closed:
a taxpayer who elects nothing keeps the whole-entity general apportionment the
settlement auto-seed already produces.

The percentage the operator supplies is the art. 106.Uno regla-3.ª common-use
percentage (the art. 104.Dos general prorrata), applied to common-use inputs
under especial and to common (no-sector) inputs under sectores; its provenance
is the LIVA art. 105 ladder (carried prior definitive by default). The register
is authoritative profile-scoped taxpayer state, not an AEAT filing surface.
"""

from __future__ import annotations

import typer

from ...application.prorrata_register import ProrrataRegisterService
from ...core import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ...core.i18n import tr
from ...domain.prorrata_register import (
    ProrrataRegister,
    ProrrataRegisterEntry,
    ProrrataRegisterValidationError,
    SectorDefinition,
)
from ._common import _bad, _emit_envelope, parse_decimal_amount
from ._common import active_bucket_id_or_refuse as _register_bucket_id
from ._prorrata_register_payloads import (
    ProrrataElectEspecialResult,
    ProrrataElectGeneralResult,
    ProrrataElectResult,
    ProrrataEntryPayload,
    ProrrataListResult,
    SectorDefinitionPayload,
)

#: The art. 105 provenances an operator may declare at election time. The
#: art. 105.Cinco interrupted-activity percentage is computed by the seed walk
#: over the register's own volumes, never operator-supplied.
_ELECTABLE_PROVENANCES = (
    ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
    ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
    ProrrataProvisionalProvenance.INICIO_ACTIVIDAD,
)
_REFERENCED_PROVENANCES = frozenset(
    {
        ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
        ProrrataProvisionalProvenance.INICIO_ACTIVIDAD,
    }
)


def register_prorrata_register_commands(app: typer.Typer) -> None:
    """Mount the cross-period prorrata register command group on the ledger app."""
    app.add_typer(prorrata_app, name="prorrata")


prorrata_app = typer.Typer(
    name="prorrata",
    help=tr(
        "cli.app.ledger.prorrata.group_help",
        default=(
            "Cross-period IVA prorrata register: elect the regime (general / especial) and "
            "declare differentiated sectors (LIVA arts. 101 / 103 / 105 / 106)."
        ),
    ),
    no_args_is_help=True,
)


def _entry_payload(entry: ProrrataRegisterEntry) -> ProrrataEntryPayload:
    data = entry.model_dump(mode="json")
    for decimal_field in (
        "provisional_percentage",
        "definitive_percentage",
        "definitive_volume_con_derecho",
        "definitive_volume_sin_derecho",
    ):
        value = getattr(entry, decimal_field)
        data[decimal_field] = str(value) if value is not None else None
    return ProrrataEntryPayload.model_validate(data)


def _sector_payload(definition: SectorDefinition) -> SectorDefinitionPayload:
    return SectorDefinitionPayload(
        sector_id=definition.sector_id,
        letra=definition.letra.value,
        member_activity_codes=list(definition.member_activity_codes),
    )


def _resolve_provenance(
    raw: ProrrataProvisionalProvenance, reference: str | None
) -> tuple[
    ProrrataProvisionalProvenance,
    str | None,
]:
    if raw not in _ELECTABLE_PROVENANCES:
        accepted = ", ".join(member.value for member in _ELECTABLE_PROVENANCES)
        raise _bad(
            tr(
                "cli.app.ledger.prorrata.provenance_not_electable",
                default=(
                    "Provenance {provenance!r} is not operator-declarable; accepted: {accepted}. "
                    "The art. 105.Cinco interrupted percentage is computed from the register."
                ),
                provenance=raw.value,
                accepted=accepted,
            ),
        )
    referenced = raw in _REFERENCED_PROVENANCES
    if referenced and (reference is None or not reference.strip()):
        raise _bad(
            tr(
                "cli.app.ledger.prorrata.reference_required",
                default="Provenance {provenance!r} (LIVA art. 105.Dos / 105.Tres) requires --reference.",
                provenance=raw.value,
            ),
        )
    if not referenced and reference is not None:
        raise _bad(
            tr(
                "cli.app.ledger.prorrata.reference_not_permitted",
                default="--reference is permitted only with an aeat_autorizada or inicio_actividad provenance.",
            ),
        )
    return raw, reference


def _elect(
    ctx: typer.Context,
    *,
    regime: ProrrataRegisterRegime,
    ejercicio: int,
    percentage_raw: str,
    provenance: ProrrataProvisionalProvenance,
    reference: str | None,
    sector_id: str | None,
    result_class: type[ProrrataElectResult],
    command: str,
) -> None:
    bucket_id = _register_bucket_id()
    resolved_provenance, resolved_reference = _resolve_provenance(provenance, reference)
    percentage = parse_decimal_amount(percentage_raw, label="percentage", signed=False)
    try:
        entry = ProrrataRegisterEntry(
            ejercicio=ejercicio,
            regime=regime,
            sector_id=sector_id,
            provisional_percentage=percentage,
            provisional_provenance=resolved_provenance,
            authorisation_reference=resolved_reference,
        )
    except ProrrataRegisterValidationError as exc:
        raise _bad(str(exc)) from exc
    register = ProrrataRegisterService().declare(entry)
    payload = result_class(
        bucket_id=bucket_id,
        entry=_entry_payload(entry),
        count=len(register.entries),
    )
    _emit_envelope(
        ctx,
        command=command,
        result=payload,
        lines=(
            f"bucket\t{bucket_id}",
            f"ejercicio\t{entry.ejercicio}",
            f"regime\t{entry.regime.value}",
            f"sector_id\t{entry.sector_id or ''}",
            f"provisional_percentage\t{entry.provisional_percentage}",
            f"provisional_provenance\t{resolved_provenance.value}",
            f"count\t{len(register.entries)}",
        ),
    )


@prorrata_app.command(
    "elect-especial",
    help=tr(
        "cli.app.ledger.prorrata.elect_especial_help",
        default=(
            "Elect prorrata especial for an ejercicio (LIVA art. 103.Dos.1): per-input deduction "
            "routes by --input-classification on each ledger row."
        ),
    ),
)
def prorrata_elect_especial(
    ctx: typer.Context,
    ejercicio: int = typer.Option(
        ...,
        "--ejercicio",
        help=tr("cli.app.ledger.prorrata.ejercicio_help", default="Filing year the election covers."),
    ),
    percentage: str = typer.Option(
        ...,
        "--percentage",
        help=tr(
            "cli.app.ledger.prorrata.percentage_help",
            default="Common-use deduction percentage 0-100 (LIVA art. 106.Uno regla 3.a / art. 104.Dos).",
        ),
    ),
    provenance: ProrrataProvisionalProvenance = typer.Option(
        ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        "--provenance",
        help=tr(
            "cli.app.ledger.prorrata.provenance_help",
            default="LIVA art. 105 source of the provisional percentage.",
        ),
    ),
    reference: str | None = typer.Option(
        None,
        "--reference",
        help=tr(
            "cli.app.ledger.prorrata.reference_help",
            default="AEAT authorisation (art. 105.Dos) or inicio proposal (art. 105.Tres) reference.",
        ),
    ),
    sector: str | None = typer.Option(
        None,
        "--sector",
        help=tr(
            "cli.app.ledger.prorrata.sector_help",
            default="Differentiated-sector id this entry covers; omit for the whole-entity entry.",
        ),
    ),
) -> None:
    """Persist an ``ESPECIAL`` :class:`ProrrataRegisterEntry` for the ejercicio."""
    _elect(
        ctx,
        regime=ProrrataRegisterRegime.ESPECIAL,
        ejercicio=ejercicio,
        percentage_raw=percentage,
        provenance=provenance,
        reference=reference,
        sector_id=sector,
        result_class=ProrrataElectEspecialResult,
        command="ledger.prorrata.elect_especial",
    )


@prorrata_app.command(
    "elect-general",
    help=tr(
        "cli.app.ledger.prorrata.elect_general_help",
        default=(
            "Elect prorrata general for an ejercicio (LIVA art. 104): one deduction percentage "
            "applies to every deducible cuota."
        ),
    ),
)
def prorrata_elect_general(
    ctx: typer.Context,
    ejercicio: int = typer.Option(
        ...,
        "--ejercicio",
        help=tr("cli.app.ledger.prorrata.ejercicio_help", default="Filing year the election covers."),
    ),
    percentage: str = typer.Option(
        ...,
        "--percentage",
        help=tr(
            "cli.app.ledger.prorrata.general_percentage_help",
            default="Provisional deduction percentage 0-100 (LIVA art. 104.Uno + 105.Uno).",
        ),
    ),
    provenance: ProrrataProvisionalProvenance = typer.Option(
        ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        "--provenance",
        help=tr(
            "cli.app.ledger.prorrata.provenance_help",
            default="LIVA art. 105 source of the provisional percentage.",
        ),
    ),
    reference: str | None = typer.Option(
        None,
        "--reference",
        help=tr(
            "cli.app.ledger.prorrata.reference_help",
            default="AEAT authorisation (art. 105.Dos) or inicio proposal (art. 105.Tres) reference.",
        ),
    ),
    sector: str | None = typer.Option(
        None,
        "--sector",
        help=tr(
            "cli.app.ledger.prorrata.sector_help",
            default="Differentiated-sector id this entry covers; omit for the whole-entity entry.",
        ),
    ),
) -> None:
    """Persist a ``GENERAL`` :class:`ProrrataRegisterEntry` for the ejercicio."""
    _elect(
        ctx,
        regime=ProrrataRegisterRegime.GENERAL,
        ejercicio=ejercicio,
        percentage_raw=percentage,
        provenance=provenance,
        reference=reference,
        sector_id=sector,
        result_class=ProrrataElectGeneralResult,
        command="ledger.prorrata.elect_general",
    )


@prorrata_app.command(
    "list",
    help=tr(
        "cli.app.ledger.prorrata.list_help",
        default="List every register entry and declared differentiated sector on the active profile.",
    ),
)
def prorrata_list(ctx: typer.Context) -> None:
    """List the register via :class:`ProrrataRegisterService`."""
    bucket_id = _register_bucket_id()
    register: ProrrataRegister = ProrrataRegisterService().list_all()
    entries = [_entry_payload(entry) for entry in register.entries]
    sectors = [_sector_payload(definition) for definition in register.sector_definitions]
    payload = ProrrataListResult(
        bucket_id=bucket_id,
        entries=entries,
        sectors=sectors,
        count=len(entries),
    )
    lines = [f"bucket\t{bucket_id}", f"count\t{len(entries)}"]
    for entry in register.entries:
        lines.append(
            f"{entry.ejercicio}\t{entry.regime.value}\tsector={entry.sector_id or ''}\t"
            f"provisional={entry.provisional_percentage}\tdefinitive={entry.definitive_percentage}",
        )
    for definition in register.sector_definitions:
        lines.append(
            f"sector\t{definition.sector_id}\tletra={definition.letra.value}\t"
            f"codes={','.join(definition.member_activity_codes)}",
        )
    _emit_envelope(
        ctx,
        command="ledger.prorrata.list",
        result=payload,
        lines=lines,
    )
