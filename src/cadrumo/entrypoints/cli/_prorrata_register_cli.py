"""Behavior handlers for the cross-period IVA prorrata register.

The commands delegate register persistence to
:class:`ProrrataRegisterService` and emit typed payloads from
:mod:`._prorrata_register_payloads`. This is the operator ingress that reaches
the LIVA art. 106 prorrata-especial apportionment and the arts. 9.1.c / 101
per-sector apportionment on the live M303 aggregation path: ``elect-especial``
writes an ``ESPECIAL`` :class:`~domain.prorrata_register.ProrrataRegisterEntry`
so :func:`~application.aggregation._iva_ledger._apply_especial_apportionment` fires, and
``declare-sector`` writes a :class:`~domain.prorrata_register.SectorDefinition`
so the register becomes sectorized and
:func:`~application.aggregation._iva_ledger._apply_sector_apportionment` fires. Fail-closed:
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
from pydantic import ValidationError

from ...application.prorrata_register import ProrrataRegisterService
from ...core import (
    ProrrataEspecialTransitionKind,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from ...core.i18n import tr
from ...domain.prorrata_register import (
    ProrrataEspecialTransitionEvidence,
    ProrrataRegister,
    ProrrataRegisterEntry,
    ProrrataRegisterValidationError,
    SectorDefinition,
)
from ._common import _bad, _emit_envelope, parse_decimal_amount
from ._common import active_bucket_id_or_refuse as _register_bucket_id
from ._prorrata_register_payloads import (
    ProrrataDeclareSectorResult,
    ProrrataElectEspecialResult,
    ProrrataElectGeneralResult,
    ProrrataElectResult,
    ProrrataEntryPayload,
    ProrrataListResult,
    ProrrataRevokeEspecialResult,
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

# Shared Typer option aliases for the two election verbs (``elect-especial`` and
# ``elect-general``), which carry a byte-identical --ejercicio/--provenance/
# --reference/--sector signature. Declared once so the help keys live in one home
# and ``--help`` renders identically for both verbs. ``--percentage`` is kept
# per-verb: its help key and copy diverge (especial cites art. 106.Uno regla 3.ª,
# general cites art. 104.Uno + 105.Uno).


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
    especial_transition: ProrrataEspecialTransitionEvidence | None,
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
            especial_transition=especial_transition,
            sector_id=sector_id,
            provisional_percentage=percentage,
            provisional_provenance=resolved_provenance,
            authorisation_reference=resolved_reference,
        )
    except (ProrrataRegisterValidationError, ValidationError) as exc:
        raise _bad(str(exc)) from exc
    service = ProrrataRegisterService()
    try:
        register = (
            service.declare_especial_transition(entry) if especial_transition is not None else service.declare(entry)
        )
    except (ProrrataRegisterValidationError, ValidationError) as exc:
        raise _bad(str(exc)) from exc
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
            f"especial_transition\t{entry.especial_transition.kind.value if entry.especial_transition else ''}",
            f"evidence_reference\t{entry.especial_transition.evidence_reference if entry.especial_transition else ''}",
            f"count\t{len(register.entries)}",
        ),
    )


def prorrata_elect_especial(
    ctx: typer.Context,
    ejercicio: int,
    percentage: str,
    evidence_reference: str | None = None,
    provenance: ProrrataProvisionalProvenance = ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
    reference: str | None = None,
    sector: str | None = None,
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
        especial_transition=(
            ProrrataEspecialTransitionEvidence(
                kind=ProrrataEspecialTransitionKind.OPCION,
                evidence_reference=evidence_reference,
            )
            if evidence_reference is not None
            else None
        ),
        result_class=ProrrataElectEspecialResult,
        command="ledger.prorrata.elect_especial",
    )


def prorrata_elect_general(
    ctx: typer.Context,
    ejercicio: int,
    percentage: str,
    provenance: ProrrataProvisionalProvenance = ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
    reference: str | None = None,
    sector: str | None = None,
) -> None:
    """Persist a ``GENERAL`` :class:`ProrrataRegisterEntry` for the ejercicio.

    A move *away* from an especial regime is the separate ``revoke-especial``
    verb, which requires the revocation evidence: this verb records a plain
    general election and never manufactures a transition.
    """
    _elect(
        ctx,
        regime=ProrrataRegisterRegime.GENERAL,
        ejercicio=ejercicio,
        percentage_raw=percentage,
        provenance=provenance,
        reference=reference,
        sector_id=sector,
        especial_transition=None,
        result_class=ProrrataElectGeneralResult,
        command="ledger.prorrata.elect_general",
    )


def prorrata_revoke_especial(
    ctx: typer.Context,
    ejercicio: int,
    evidence_reference: str,
    percentage: str,
    provenance: ProrrataProvisionalProvenance = ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
    reference: str | None = None,
    sector: str | None = None,
) -> None:
    """Persist a typed prorrata-especial revocation for the ejercicio."""
    _elect(
        ctx,
        regime=ProrrataRegisterRegime.GENERAL,
        ejercicio=ejercicio,
        percentage_raw=percentage,
        provenance=provenance,
        reference=reference,
        sector_id=sector,
        especial_transition=ProrrataEspecialTransitionEvidence(
            kind=ProrrataEspecialTransitionKind.REVOCACION,
            evidence_reference=evidence_reference,
        ),
        result_class=ProrrataRevokeEspecialResult,
        command="ledger.prorrata.revoke_especial",
    )


def prorrata_declare_sector(
    ctx: typer.Context,
    sector_id: str,
    letra: SectorDiferenciadoLetra,
    activity_code: tuple[str, ...] = (),
) -> None:
    """Persist one :class:`SectorDefinition` onto the register partition."""
    bucket_id = _register_bucket_id()
    try:
        definition = SectorDefinition(
            sector_id=sector_id,
            letra=letra,
            member_activity_codes=tuple(activity_code),
        )
    except ProrrataRegisterValidationError as exc:
        raise _bad(str(exc)) from exc
    register = ProrrataRegisterService().declare_sector(definition)
    payload = ProrrataDeclareSectorResult(
        bucket_id=bucket_id,
        sector=_sector_payload(definition),
        count=len(register.sector_definitions),
    )
    _emit_envelope(
        ctx,
        command="ledger.prorrata.declare_sector",
        result=payload,
        lines=(
            f"bucket\t{bucket_id}",
            f"sector_id\t{definition.sector_id}",
            f"letra\t{definition.letra.value}",
            f"member_activity_codes\t{','.join(definition.member_activity_codes)}",
            f"count\t{len(register.sector_definitions)}",
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
