"""FilingDraft vs Justificante reconciler.

Implements :func:`reconcile`, which produces a
:class:`ReconciliationReport` describing whether the operator's local
approved draft matches what AEAT has on file.

The compare is deliberately narrow: it consumes only the fields the
justificante PDF exposes directly (``modelo``, ``period``, ``tax_id``,
totals, ``presented_at``). Per-casilla reconciliation against the full
declaration requires a modelo-specific parser and is intentionally out
of scope for this module.

The reconciler is read-only — it never mutates either side. See
:class:`FilingDivergenceKind` for the closed taxonomy of divergence
reasons and :class:`ReconciliationReport` for the returned record shape.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from ....core.i18n import Translatable
from ....core.logging import get_logger
from ._kind import FilingDivergenceKind
from ._schema import (
    FieldMismatch,
    FilingDraftRef,
    JustificanteRefSummary,
    ReconciliationReport,
    ReconciliationStatus,
)

_logger = get_logger(__name__)

if TYPE_CHECKING:
    from ....domain.filing import FilingDraft
    from ....domain.justificante import Justificante


# Shared with aeat.application.verification: "one cent" is the Kent-visible
# rounding floor on every monetary comparison across the CLI.
_TOLERANCE: Final[Decimal] = Decimal("0.01")


def reconcile(
    draft: FilingDraft,
    justificante: Justificante | None,
    *,
    now: datetime | None = None,
) -> ReconciliationReport:
    """Compare a local draft against AEAT's authoritative justificante.

    Compares the narrow set of metadata fields present on a parsed
    :class:`aeat.domain.justificante.Justificante` against the
    corresponding fields on a local
    :class:`aeat.domain.filing.FilingDraft`, classifying each
    disagreement using :class:`FilingDivergenceKind`.

    Args:
        draft: Local approved :class:`aeat.domain.filing.FilingDraft`.
        justificante: Parsed AEAT-side
            :class:`aeat.domain.justificante.Justificante`, or ``None``
            when the sede has no record of a matching submission yet.
        now: Override for the report's ``reconciled_at`` timestamp.
            Supports deterministic testing. Defaults to
            ``datetime.now(UTC)``.

    Returns:
        A frozen :class:`ReconciliationReport` whose
        :attr:`ReconciliationReport.status` is one of
        :attr:`ReconciliationStatus.MATCH`,
        :attr:`ReconciliationStatus.DIVERGENT`, or
        :attr:`ReconciliationStatus.NOT_YET_FOUND`, accompanied by
        per-field mismatches and a multilingual narrative summary.
    """
    reconciled_at = now or datetime.now(tz=UTC)
    draft_ref = FilingDraftRef(
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        profile_tax_id=draft.profile_tax_id,
    )

    if justificante is None:
        _logger.debug(
            "reconciliation not-yet-found draft_id=%s modelo=%s period=%s",
            draft.draft_id,
            draft.modelo,
            draft.period,
        )
        return ReconciliationReport(
            status=ReconciliationStatus.NOT_YET_FOUND,
            draft_ref=draft_ref,
            justificante=None,
            mismatches=(
                FieldMismatch(
                    kind=FilingDivergenceKind.FILING_NOT_YET_FOUND,
                    field_name="justificante",
                    draft_value=f"modelo={draft.modelo} period={draft.period}",
                    remote_value="<no record>",
                ),
            ),
            reconciled_at=reconciled_at,
            narrative=_narrative_not_yet_found(draft),
        )

    remote = _summarise_justificante(justificante)
    mismatches: list[FieldMismatch] = []

    if draft.modelo != remote.modelo:
        mismatches.append(
            FieldMismatch(
                kind=FilingDivergenceKind.MODELO_MISMATCH,
                field_name="modelo",
                draft_value=draft.modelo,
                remote_value=remote.modelo,
            )
        )

    if _normalise_period(draft.period) != _normalise_period(remote.period):
        mismatches.append(
            FieldMismatch(
                kind=FilingDivergenceKind.PERIOD_MISMATCH,
                field_name="period",
                draft_value=draft.period,
                remote_value=remote.period,
            )
        )

    if _canonical_tax_id(draft.profile_tax_id) != _canonical_tax_id(remote.tax_id):
        mismatches.append(
            FieldMismatch(
                kind=FilingDivergenceKind.TAX_ID_MISMATCH,
                field_name="tax_id",
                draft_value=draft.profile_tax_id,
                remote_value=remote.tax_id,
            )
        )

    # Total mismatches are only surfaced when the draft itself records
    # a derived figure; per-modelo total-derivation is a follow-up,
    # so we stay strict-silent when the draft has no equivalent field.
    draft_totals = _derive_draft_totals(draft)
    if (
        draft_totals.ingresar is not None
        and remote.total_a_ingresar is not None
        and abs(draft_totals.ingresar - remote.total_a_ingresar) > _TOLERANCE
    ):
        mismatches.append(
            FieldMismatch(
                kind=FilingDivergenceKind.TOTAL_INGRESAR_MISMATCH,
                field_name="total_a_ingresar",
                draft_value=_format_decimal(draft_totals.ingresar),
                remote_value=_format_decimal(remote.total_a_ingresar),
            )
        )
    if (
        draft_totals.devolver is not None
        and remote.total_a_devolver is not None
        and abs(draft_totals.devolver - remote.total_a_devolver) > _TOLERANCE
    ):
        mismatches.append(
            FieldMismatch(
                kind=FilingDivergenceKind.TOTAL_DEVOLVER_MISMATCH,
                field_name="total_a_devolver",
                draft_value=_format_decimal(draft_totals.devolver),
                remote_value=_format_decimal(remote.total_a_devolver),
            )
        )

    if mismatches:
        status = ReconciliationStatus.DIVERGENT
        narrative = _narrative_divergent(draft, remote, mismatches)
        _logger.warning(
            "reconciliation divergent draft_id=%s modelo=%s period=%s mismatches=%d",
            draft.draft_id,
            draft.modelo,
            draft.period,
            len(mismatches),
        )
    else:
        status = ReconciliationStatus.MATCH
        narrative = _narrative_match(draft, remote)
        _logger.info(
            "reconciliation matched draft_id=%s modelo=%s period=%s csv=%s",
            draft.draft_id,
            draft.modelo,
            draft.period,
            remote.csv,
        )

    return ReconciliationReport(
        status=status,
        draft_ref=draft_ref,
        justificante=remote,
        mismatches=tuple(mismatches),
        reconciled_at=reconciled_at,
        narrative=narrative,
    )


class _DraftTotals:
    """Internal bag of draft-side totals derived for comparison.

    Attributes:
        ingresar: Derived ingresar figure, or ``None`` when no
            modelo-specific projection is available.
        devolver: Derived devolver figure, or ``None`` when no
            modelo-specific projection is available.
    """

    __slots__ = ("devolver", "ingresar")

    def __init__(self, ingresar: Decimal | None, devolver: Decimal | None) -> None:
        """Initialise the totals bag.

        Args:
            ingresar: Derived ingresar figure or ``None``.
            devolver: Derived devolver figure or ``None``.
        """
        self.ingresar = ingresar
        self.devolver = devolver


def _derive_draft_totals(draft: FilingDraft) -> _DraftTotals:
    """Compute the draft's operator-visible ingresar / devolver figures.

    The draft itself does not carry a pre-computed total — totals are
    surface-level projections of specific casilla values. Until a
    per-modelo projection map is introduced this returns ``None`` on
    both sides, which causes :func:`reconcile` to skip total comparison
    and surface any modelo / period / tax_id mismatch on its own.

    Args:
        draft: The local draft whose totals would be derived.

    Returns:
        A :class:`_DraftTotals` with both fields set to ``None``.
    """
    del draft  # Reserved for a modelo-specific total-derivation follow-up.
    return _DraftTotals(ingresar=None, devolver=None)


def _summarise_justificante(justificante: Justificante) -> JustificanteRefSummary:
    """Project a parsed Justificante into the trimmed reconciliation summary."""
    return JustificanteRefSummary(
        csv=justificante.csv,
        modelo=justificante.modelo,
        period=justificante.period,
        ejercicio=justificante.ejercicio,
        tax_id=justificante.tax_id,
        presented_at=justificante.presented_at,
        presentation_id=justificante.presentation_id,
        total_a_ingresar=justificante.total_a_ingresar,
        total_a_devolver=justificante.total_a_devolver,
    )


def _normalise_period(period: str) -> str:
    """Lower-case and strip a period label for tolerant comparison.

    The operator might record "2023" in the draft while AEAT prints
    "0A" for the same annual period. This helper normalises whitespace and
    case only; the remaining year-vs-period-code gap is out of scope
    for the MVP and surfaces as a
    :attr:`FilingDivergenceKind.PERIOD_MISMATCH` divergence.

    Args:
        period: Raw period label from either side of the compare.

    Returns:
        The stripped, lower-cased period label.
    """
    return period.strip().lower()


def _canonical_tax_id(value: str) -> str:
    """Canonicalise a NIF / NIE for tolerant comparison (strip + upper)."""
    return value.strip().upper()


def _format_decimal(value: Decimal) -> str:
    """Render a :class:`Decimal` in fixed-point notation for mismatch records."""
    return format(value, "f")


def _narrative_not_yet_found(draft: FilingDraft) -> Translatable:
    """Build the multilingual narrative for the NOT_YET_FOUND verdict."""
    es = (
        f"AEAT no tiene constancia del modelo {draft.modelo} del período "
        f"{draft.period}. Asegúrate de haberlo presentado correctamente."
    )
    en = (
        f"AEAT has no record of modelo {draft.modelo} for period "
        f"{draft.period}. Confirm the filing was actually submitted."
    )
    hu = (
        f"Az AEAT-nál nincs bejegyzés a {draft.modelo} modellről a "
        f"{draft.period} időszakra. Ellenőrizd, valóban benyújtottad-e."
    )
    ca = (
        f"L'AEAT no té constància del model {draft.modelo} del període "
        f"{draft.period}. Assegura't d'haver-lo presentat correctament."
    )
    return Translatable(es=es, en=en, hu=hu, ca=ca)


def _narrative_match(draft: FilingDraft, remote: JustificanteRefSummary) -> Translatable:
    """Build the multilingual narrative for the MATCH verdict."""
    es = f"Modelo {draft.modelo} {draft.period}: coincide con lo registrado en AEAT (CSV {remote.csv})."
    en = f"Modelo {draft.modelo} {draft.period}: matches AEAT's record (CSV {remote.csv})."
    hu = f"{draft.modelo} modell {draft.period}: egyezik az AEAT bejegyzésével (CSV {remote.csv})."
    ca = f"Model {draft.modelo} {draft.period}: coincideix amb el que està registrat a l'AEAT (CSV {remote.csv})."
    return Translatable(es=es, en=en, hu=hu, ca=ca)


def _narrative_divergent(
    draft: FilingDraft,
    remote: JustificanteRefSummary,
    mismatches: list[FieldMismatch],
) -> Translatable:
    """Build the multilingual narrative for the DIVERGENT verdict."""
    fields = ", ".join(m.field_name for m in mismatches)
    es = f"Modelo {draft.modelo} {draft.period}: divergencia frente a AEAT (CSV {remote.csv}) en: {fields}."
    en = f"Modelo {draft.modelo} {draft.period}: divergence vs AEAT (CSV {remote.csv}) in: {fields}."
    hu = f"{draft.modelo} modell {draft.period}: eltérés az AEAT-hez képest (CSV {remote.csv}) mezők: {fields}."
    ca = f"Model {draft.modelo} {draft.period}: divergència respecte l'AEAT (CSV {remote.csv}) en: {fields}."
    return Translatable(es=es, en=en, hu=hu, ca=ca)


__all__ = ["reconcile"]
