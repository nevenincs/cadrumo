"""Modelo 100 régimen-de-atribución omission advisory.

The socio-side ``attribution_received`` profile fact group (S411) is the typed
home for a base imponible attributed to a member by an entity in the régimen de
atribución de rentas (LIRPF arts. 86-89). Per the
``2026-07-09-m184-socio-attribution-handoff-adr`` addendum (decision (a)), that
value is NOT auto-bound onto the M100 atribución casilla — casilla 1577 stays
relation-canonical, and the cross-bucket attributed value enters the member's
own M100 via a documented manual ``--binding`` override. This module is the
non-silent guard on that manual handoff: it emits a non-blocking
:class:`ModeloVerificationFinding` warning when the two halves of the handoff
disagree, so a forgotten transcription surfaces loudly rather than
under-declaring in silence (``no-silent-under-declaration``).

Two symmetric triggers, both ADVISORY / WARNING:

* Captured-but-unfolded: the profile declares ``attribution_received`` facts for
  the filing year, but the atribución casilla resolves empty — the member
  recorded the received share yet did not fold it into the M100.
* Declared-but-uncaptured: the atribución casilla carries a value, but no
  ``attribution_received`` facts back it for the filing year — an
  SC-membership signal (declared attributed income) with no provenance facts to
  explain it; the member is prompted to capture the facts.

See Also:
    :func:`~application.modelo._verification_actions._append_revision_advisory_findings`:
        Verification collector that appends this advisory beside the reduction
        and objective-estimation advisories.
    :class:`~aeat.domain.user_profile.UserProfileRecord`:
        Active taxpayer profile the advisory reads ``attribution_received``
        facts from.
    :class:`~aeat.domain.modelos.WorkUnit`:
        Supplies the modelo, filing year, and bucket that bound the advisory.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from ...core import Modelo
from ...core.decimal import coerce_decimal_strict
from ...domain.modelos import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.user_profile import ProfileNotFoundError, UserProfileFact, UserProfileRecord
from ..user_profile import UserProfileLifecycleRepository
from ._semantic_role_resolution import casilla_id_for_unique_revision_semantic_role

if TYPE_CHECKING:
    from ...domain.calculations.registry import CasillaId, LegalRefId, RegistrySnapshot
    from ...domain.modelos import WorkUnit

_ATRIBUCION_ACT_ECO_ROLE = "irpf_rendimiento_act_eco_atribuido_rdto_neto"
_RECEIVED_FACT_RE = re.compile(r"^attribution_received\.(?P<index>[0-9]+)\.(?P<field>[a-z][a-z0-9_]*)$")
_ATRIBUCION_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "ley-35-2006:art-86",
    "ley-35-2006:art-87",
    "ley-35-2006:art-88",
    "ley-35-2006:art-89",
)


def _attribution_received_omission_advisory_findings(
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    casilla_values: Mapping[CasillaId, Decimal],
    profile_record: UserProfileRecord | None = None,
) -> tuple[ModeloVerificationFinding, ...]:
    """Return the non-blocking M100 régimen-de-atribución handoff advisories.

    Args:
        work_unit: The :class:`WorkUnit` whose modelo, filing year, and bucket
            scope the advisory (applies to Modelo 100 only).
        snapshot: The :class:`RegistrySnapshot` whose revision declares the
            atribución casilla resolved structurally by semantic role.
        casilla_values: The resolved casilla values from the calculation
            revision under verification.
        profile_record: Optional :class:`UserProfileRecord` override for testing;
            loaded from the work unit's bucket when omitted.

    Returns:
        A tuple carrying at most one :class:`ModeloVerificationFinding` warning:
        empty when the handoff is coherent (both halves present, or both
        absent), one finding when exactly one half is present.
    """
    if str(getattr(work_unit.modelo, "value", work_unit.modelo)) != Modelo.M100.value:
        return ()

    casilla_id = casilla_id_for_unique_revision_semantic_role(
        snapshot.revision,
        _ATRIBUCION_ACT_ECO_ROLE,
        modelo_id=Modelo.M100.value,
    )
    if casilla_id is None:
        return ()

    casilla_value = casilla_values.get(casilla_id)
    casilla_has_value = casilla_value is not None and casilla_value != Decimal("0")

    record = profile_record
    if record is None:
        try:
            record = UserProfileLifecycleRepository(bucket_id=work_unit.bucket_id).load(work_unit.bucket_id)
        except ProfileNotFoundError:
            return ()

    total_base = _attribution_received_base_for_year(record.facts, work_unit.filing_year)
    facts_present = total_base is not None

    if facts_present and not casilla_has_value:
        return (
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.ADVISORY,
                severity=ModeloVerificationFindingSeverity.WARNING,
                message=(
                    "attribution_received facts declare an attributed base for this filing year "
                    f"(modelo=100 year={work_unit.filing_year} total={total_base} EUR) but the M100 "
                    f"regimen-de-atribucion casilla {casilla_id} resolves empty: the received share was "
                    "captured on the profile but not folded into the declaration."
                ),
                next_action=(
                    f"Fold the attributed base into casilla {casilla_id} on the M100 calculation, e.g. via "
                    f"`aeat app modelo work calculate ... --binding {casilla_id}={total_base}`, so the "
                    "regimen-de-atribucion income is declared."
                ),
                legal_refs=_ATRIBUCION_LEGAL_REFS,
                source_refs=(),
            ),
        )

    if casilla_has_value and not facts_present:
        return (
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.ADVISORY,
                severity=ModeloVerificationFindingSeverity.WARNING,
                message=(
                    f"the M100 regimen-de-atribucion casilla {casilla_id} declares an attributed base "
                    f"(modelo=100 year={work_unit.filing_year} value={casilla_value} EUR) but no "
                    "attribution_received facts back it for this filing year: the declared income carries "
                    "no captured provenance."
                ),
                next_action=(
                    "Capture the attribution_received facts (entity NIF, name, share percentage, attributed "
                    "base, filing year) on the taxpayer profile so the declared regimen-de-atribucion income "
                    "carries its Modelo 184 provenance."
                ),
                legal_refs=_ATRIBUCION_LEGAL_REFS,
                source_refs=(),
            ),
        )

    return ()


def _attribution_received_base_for_year(
    facts: tuple[UserProfileFact, ...],
    filing_year: int,
) -> Decimal | None:
    """Return the summed attributed base for ``filing_year``, or None when absent.

    Groups ``attribution_received.N.*`` facts by row index and keeps the rows
    whose ``filing_year`` matches and that carry a parseable
    ``base_imponible_attributed``. Returns the summed base of the matching rows,
    or ``None`` when no row applies to the year (so the caller can distinguish
    "no facts" from "facts summing to zero").
    """
    grouped: dict[int, dict[str, object]] = {}
    for fact in facts:
        match = _RECEIVED_FACT_RE.match(fact.path)
        if match is None or fact.value is None:
            continue
        grouped.setdefault(int(match.group("index")), {})[match.group("field")] = fact.value

    total = Decimal("0")
    matched = False
    for row in grouped.values():
        row_year = row.get("filing_year")
        if row_year is None or str(row_year).strip() != str(filing_year):
            continue
        base = row.get("base_imponible_attributed")
        if base is None:
            continue
        try:
            total += coerce_decimal_strict(base if isinstance(base, Decimal) else str(base).strip())
        except (InvalidOperation, ValueError):
            continue
        matched = True
    return total if matched else None


__all__ = ["_attribution_received_omission_advisory_findings"]
