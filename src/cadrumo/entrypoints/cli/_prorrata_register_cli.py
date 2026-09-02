"""Behavior handlers for the cross-period IVA prorrata register.

The commands delegate register persistence to
:class:`ProrrataRegisterService` and emit typed payloads from
:mod:`._prorrata_register_payloads`. This is the operator ingress that reaches
the LIVA art. 106 prorrata-especial apportionment and the arts. 9.1.c / 101
per-sector apportionment on the live M303 aggregation path: ``elect-especial``
writes an ``ESPECIAL`` :class:`~domain.prorrata_register.ProrrataRegisterEntry`
so :func:`~application.aggregation.iva_ledger._apply_especial_apportionment` fires, and
``declare-sector`` writes a :class:`~domain.prorrata_register.SectorDefinition`
so the register becomes sectorized and
:func:`~application.aggregation.iva_ledger._apply_sector_apportionment` fires. Fail-closed:
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

from ...application.prorrata_register.sector_lifecycle import (
    seed_sector_carried_definitive_from_register,
    settle_sector_definitive,
)
from ...application.prorrata_register.seed import (
    ProrrataPriorDefinitivaSeed,
    ProrrataSeedFinding,
    cross_check_prorrata_entry_against_prior_observation,
    evaluate_carried_prior_definitiva_seed,
)
from ...application.prorrata_register.service import ProrrataRegisterService
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.prorrata_register import (
    ProrrataEspecialTransitionKind,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from ...domain.prorrata_register.register import (
    ProrrataEspecialTransitionEvidence,
    ProrrataRegister,
    ProrrataRegisterEntry,
    ProrrataRegisterValidationError,
    SectorDefinition,
)
from ._common import active_bucket_id_or_refuse as _register_bucket_id
from ._common import bad, emit_envelope
from ._decimal_parsing import parse_decimal_amount
from ._prorrata_register_payloads import (
    ProrrataDeclareSectorResult,
    ProrrataElectEspecialResult,
    ProrrataElectGeneralResult,
    ProrrataElectResult,
    ProrrataEntryPayload,
    ProrrataListResult,
    ProrrataRevokeEspecialResult,
    ProrrataSeedFindingPayload,
    ProrrataSeedResult,
    ProrrataSeedSectorResult,
    ProrrataSeedSourcePayload,
    ProrrataSettleSectorResult,
    SectorDefinitionPayload,
)

#: Machine-readable notice codes for the carried-seed advisory channel. They are
#: transport tokens, never localised presentation text.
_SEED_LOCAL_AUTHORITY_NOTICE_CODE = "ledger.prorrata.seed.local_authority"
_SEED_ADVISORY_NOTICE_CODE = "ledger.prorrata.seed.advisory"

#: Stable authority identifier emitted on the seed source payload. The carried
#: percentage is the taxpayer's own locally stored prior observation, never a
#: value AEAT issued for the seeded ejercicio.
_SEED_AUTHORITY = "local_prior_observation"

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
        raise bad(
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
        raise bad(
            tr(
                "cli.app.ledger.prorrata.reference_required",
                default="Provenance {provenance!r} (LIVA art. 105.Dos / 105.Tres) requires --reference.",
                provenance=raw.value,
            ),
        )
    if not referenced and reference is not None:
        raise bad(
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
        raise bad(str(exc)) from exc
    service = ProrrataRegisterService()
    try:
        register = (
            service.declare_especial_transition(entry) if especial_transition is not None else service.declare(entry)
        )
    except (ProrrataRegisterValidationError, ValidationError) as exc:
        raise bad(str(exc)) from exc
    payload = result_class(
        bucket_id=bucket_id,
        entry=_entry_payload(entry),
        count=len(register.entries),
    )
    emit_envelope(
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
        raise bad(str(exc)) from exc
    register = ProrrataRegisterService().declare_sector(definition)
    payload = ProrrataDeclareSectorResult(
        bucket_id=bucket_id,
        sector=_sector_payload(definition),
        count=len(register.sector_definitions),
    )
    emit_envelope(
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


def _seed_finding_payload(finding: ProrrataSeedFinding) -> ProrrataSeedFindingPayload:
    return ProrrataSeedFindingPayload(
        code=finding.code,
        blocking=finding.blocking,
        message=finding.message,
        source_modelo=finding.source_modelo,
        source_filing_year=finding.source_filing_year,
        source_period=finding.source_period,
        stamped_revision_id=finding.stamped_revision_id,
        selected_revision_id=finding.selected_revision_id,
    )


def _refuse_blocking_findings(findings: tuple[ProrrataSeedFinding, ...]) -> None:
    """Refuse the seed while any finding blocks trusting the carry.

    The application layer's blocking findings are the point of the seed
    evaluation, so every one of them is named in the refusal rather than being
    collapsed into a single boolean outcome.
    """
    blocking = tuple(finding for finding in findings if finding.blocking)
    if not blocking:
        return
    raise bad(
        tr(
            "cli.app.ledger.prorrata.seed_blocked",
            default=(
                "The carried prior-definitive prorrata seed is blocked and nothing was written. "
                "Blocking findings: {detail}"
            ),
            detail=" | ".join(f"[{finding.code}] {finding.message}" for finding in blocking),
        ),
    )


def _seed_source_payload(seed: ProrrataPriorDefinitivaSeed) -> ProrrataSeedSourcePayload:
    return ProrrataSeedSourcePayload(
        modelo=seed.source_modelo,
        filing_year=seed.source_filing_year,
        period=seed.source_period,
        casilla_id=str(seed.source_casilla_id),
        stamped_revision_id=seed.stamped_revision_id,
        authority=_SEED_AUTHORITY,
    )


def _seed_notices(
    seed: ProrrataPriorDefinitivaSeed,
    advisories: tuple[ProrrataSeedFinding, ...],
) -> tuple[Notice, ...]:
    origin = Notice(
        severity=NoticeSeverity.INFO,
        code=_SEED_LOCAL_AUTHORITY_NOTICE_CODE,
        message=tr(
            "cli.app.ledger.prorrata.seed_local_authority",
            default=(
                "The provisional percentage was carried locally from your stored {modelo} "
                "{filing_year} {period} settlement observation (LIVA art. 105.Uno). It is not a "
                "percentage AEAT issued for this ejercicio."
            ),
            modelo=seed.source_modelo,
            filing_year=seed.source_filing_year,
            period=seed.source_period,
        ),
        context={
            "source_modelo": seed.source_modelo,
            "source_filing_year": str(seed.source_filing_year),
            "source_period": seed.source_period,
            "stamped_revision_id": seed.stamped_revision_id,
            "authority": _SEED_AUTHORITY,
        },
    )
    advisory_notices = tuple(
        Notice(
            severity=NoticeSeverity.WARNING,
            code=_SEED_ADVISORY_NOTICE_CODE,
            message=finding.message,
            context={"finding_code": finding.code},
        )
        for finding in advisories
    )
    return (origin, *advisory_notices)


def prorrata_seed(
    ctx: typer.Context,
    ejercicio: int,
    sector: str | None = None,
) -> None:
    """Seed the LIVA art. 105.Uno carried prior-definitive entry for an ejercicio.

    The percentage is resolved by
    :func:`~application.prorrata_register.seed.evaluate_carried_prior_definitiva_seed`
    and any entry already standing at the key is cross-checked through
    :func:`~application.prorrata_register.seed.cross_check_prorrata_entry_against_prior_observation`
    before anything is written. A blocking finding refuses the command; an
    absent prior observation refuses as absent rather than seeding a zero.
    """
    bucket_id = _register_bucket_id()
    evaluation = evaluate_carried_prior_definitiva_seed(ejercicio=ejercicio, sector_id=sector)
    _refuse_blocking_findings(evaluation.findings)
    seed = evaluation.seed
    if seed is None:
        raise bad(
            tr(
                "cli.app.ledger.prorrata.seed_source_absent",
                default=(
                    "No stamped Modelo 303 settlement observation for {prior_ejercicio} carries a "
                    "definitive prorrata percentage, so ejercicio {ejercicio} cannot be seeded. "
                    "The prior definitive is missing, not zero: capture the prior settlement first."
                ),
                prior_ejercicio=ejercicio - 1,
                ejercicio=ejercicio,
            ),
        )

    service = ProrrataRegisterService()
    findings = evaluation.findings
    existing = service.get(ejercicio, sector_id=sector)
    if existing is not None:
        cross_findings = cross_check_prorrata_entry_against_prior_observation(existing)
        _refuse_blocking_findings(cross_findings)
        standing_provenance = existing.provisional_provenance
        if (
            standing_provenance is not None
            and standing_provenance is not ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA
        ):
            raise bad(
                tr(
                    "cli.app.ledger.prorrata.seed_regulated_override_standing",
                    default=(
                        "Ejercicio {ejercicio} already carries a {provenance} provisional prorrata, "
                        "which outranks the art. 105.Uno carry. Nothing was written; replace that "
                        "declaration explicitly before seeding."
                    ),
                    ejercicio=ejercicio,
                    provenance=standing_provenance.value,
                ),
            )
        findings = (*findings, *cross_findings)

    try:
        register = service.declare(seed.entry)
    except (ProrrataRegisterValidationError, ValidationError) as exc:
        raise bad(str(exc)) from exc

    advisories = tuple(finding for finding in findings if finding.advisory)
    payload = ProrrataSeedResult(
        bucket_id=bucket_id,
        entry=_entry_payload(seed.entry),
        source=_seed_source_payload(seed),
        findings=[_seed_finding_payload(finding) for finding in findings],
        count=len(register.entries),
    )
    notices = _seed_notices(seed, advisories)
    emit_envelope(
        ctx,
        command="ledger.prorrata.seed",
        result=payload,
        lines=(
            f"bucket\t{bucket_id}",
            f"ejercicio\t{seed.entry.ejercicio}",
            f"sector_id\t{seed.entry.sector_id or ''}",
            f"provisional_percentage\t{seed.entry.provisional_percentage}",
            f"provisional_provenance\t{ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA.value}",
            f"source\t{seed.source_modelo}:{seed.source_filing_year}:{seed.source_period}",
            f"source_casilla_id\t{seed.source_casilla_id}",
            f"stamped_revision_id\t{seed.stamped_revision_id}",
            f"authority\t{_SEED_AUTHORITY}",
            f"findings\t{len(findings)}",
            *(f"notice\t{notice.code}\t{notice.message}" for notice in notices),
            f"count\t{len(register.entries)}",
        ),
        notices=notices,
    )


def prorrata_seed_sector(
    ctx: typer.Context,
    ejercicio: int,
    sector_id: str,
) -> None:
    """Seed one differentiated sector's provisional from its own prior definitive.

    LIVA art. 105.Uno applied per sector (art. 101.Uno): the source is the
    register's own ``(ejercicio - 1, sector_id)`` settled definitive, never the
    whole-entity Modelo 303 observation.
    """
    bucket_id = _register_bucket_id()
    service = ProrrataRegisterService()
    register = service.list_all()
    entry = seed_sector_carried_definitive_from_register(register, ejercicio=ejercicio, sector_id=sector_id)
    if entry is None:
        raise bad(
            tr(
                "cli.app.ledger.prorrata.seed_sector_prior_definitive_absent",
                default=(
                    "Sector {sector_id} holds no settled definitive percentage for {prior_ejercicio}, "
                    "so ejercicio {ejercicio} cannot be seeded. The prior definitive is missing, not "
                    "zero: settle {prior_ejercicio} for this sector first."
                ),
                sector_id=sector_id,
                prior_ejercicio=ejercicio - 1,
                ejercicio=ejercicio,
            ),
        )
    try:
        updated = service.declare(entry)
    except (ProrrataRegisterValidationError, ValidationError) as exc:
        raise bad(str(exc)) from exc
    payload = ProrrataSeedSectorResult(
        bucket_id=bucket_id,
        entry=_entry_payload(entry),
        prior_ejercicio=ejercicio - 1,
        count=len(updated.entries),
    )
    emit_envelope(
        ctx,
        command="ledger.prorrata.seed_sector",
        result=payload,
        lines=(
            f"bucket\t{bucket_id}",
            f"ejercicio\t{entry.ejercicio}",
            f"sector_id\t{entry.sector_id or ''}",
            f"prior_ejercicio\t{ejercicio - 1}",
            f"provisional_percentage\t{entry.provisional_percentage}",
            f"provisional_provenance\t{ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA.value}",
            f"source_observation_ref\t{entry.source_observation_ref or ''}",
            f"count\t{len(updated.entries)}",
        ),
    )


def prorrata_settle_sector(
    ctx: typer.Context,
    ejercicio: int,
    sector_id: str,
    con_derecho_volume: str,
    sin_derecho_volume: str,
) -> None:
    """Settle one sector's year-end definitive from its own annual volumes.

    LIVA art. 105.Cuatro applied per sector: the definitive percentage is
    derived by
    :func:`~application.prorrata_register.sector_lifecycle.settle_sector_definitive`
    from the sector's own con-derecho / sin-derecho volumes, never re-derived
    here.
    """
    bucket_id = _register_bucket_id()
    con_derecho = parse_decimal_amount(con_derecho_volume, label="con-derecho-volume", signed=False)
    sin_derecho = parse_decimal_amount(sin_derecho_volume, label="sin-derecho-volume", signed=False)
    service = ProrrataRegisterService()
    entry = service.get(ejercicio, sector_id=sector_id)
    if entry is None:
        raise bad(
            tr(
                "cli.app.ledger.prorrata.settle_sector_entry_absent",
                default=(
                    "No register entry exists for ejercicio {ejercicio} sector {sector_id}, so there "
                    "is nothing to settle. Elect the sector's regime for that ejercicio first."
                ),
                ejercicio=ejercicio,
                sector_id=sector_id,
            ),
        )
    try:
        settled = settle_sector_definitive(
            entry,
            con_derecho_volume=con_derecho,
            sin_derecho_volume=sin_derecho,
        )
        updated = service.declare(settled)
    except (ProrrataRegisterValidationError, ValidationError) as exc:
        raise bad(str(exc)) from exc
    payload = ProrrataSettleSectorResult(
        bucket_id=bucket_id,
        entry=_entry_payload(settled),
        count=len(updated.entries),
    )
    emit_envelope(
        ctx,
        command="ledger.prorrata.settle_sector",
        result=payload,
        lines=(
            f"bucket\t{bucket_id}",
            f"ejercicio\t{settled.ejercicio}",
            f"sector_id\t{settled.sector_id or ''}",
            f"definitive_percentage\t{settled.definitive_percentage}",
            f"definitive_volume_con_derecho\t{settled.definitive_volume_con_derecho}",
            f"definitive_volume_sin_derecho\t{settled.definitive_volume_sin_derecho}",
            f"count\t{len(updated.entries)}",
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
    emit_envelope(
        ctx,
        command="ledger.prorrata.list",
        result=payload,
        lines=lines,
    )
