"""ModeloDraft vs Justificante reconciler.

Implements :func:`reconcile`, which produces a
:class:`ReconciliationReport` describing whether the operator's local
approved draft matches what AEAT has on file.

The compare is deliberately narrow: it consumes only the fields the
justificante PDF exposes directly (``modelo``, ``period``, ``tax_id``,
totals, ``presented_at``). Per-casilla reconciliation against the full
declaration requires a modelo-specific parser and is intentionally out
of scope for this module.

The reconciler is read-only — it never mutates either side. See
:class:`ModeloDivergenceKind` for the closed taxonomy of divergence
reasons and :class:`ReconciliationReport` for the returned record shape.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Final, Protocol

from ....core import Period
from ....core.decimal import format_decimal
from ....core.logging import get_logger
from ....core.time import now as _utc_now
from ....domain.filing import ModeloBuilderError
from ._kind import ModeloDivergenceKind
from ._schema import (
    FieldMismatch,
    JustificanteRefSummary,
    ModeloDraftRef,
    ReconciliationReport,
    ReconciliationStatus,
)

_logger = get_logger(__name__)

if TYPE_CHECKING:
    from ....domain.filing import ModeloDraft
    from ....domain.justificante import Justificante


class _RegistryReconciliationSubview(Protocol):
    @property
    def schema_version(self) -> str: ...

    @property
    def period_selector_periods(self) -> tuple[str, ...]: ...

    @property
    def verification_expectation_ids(self) -> tuple[str, ...]: ...

    @property
    def reconciliation_total_casillas(self) -> Mapping[str, str]: ...


class _RegistryReconciliationProvider(Protocol):
    def get_subview(self, modelo: str) -> _RegistryReconciliationSubview: ...


# Shared with aeat.application.verification: "one cent" is the operator-visible
# rounding floor on every monetary comparison across the CLI.
_TOLERANCE: Final[Decimal] = Decimal("0.01")
_QUARTER_RE: Final[re.Pattern[str]] = re.compile(r"^(?P<year>\d{4})Q(?P<quarter>[1-4])$", re.IGNORECASE)
_ANNUAL_RE: Final[re.Pattern[str]] = re.compile(r"^(?P<year>\d{4})A$", re.IGNORECASE)
_REMOTE_QUARTER_RE: Final[re.Pattern[str]] = re.compile(r"^(?P<quarter>[1-4])T$", re.IGNORECASE)
_REMOTE_ANNUAL_RE: Final[re.Pattern[str]] = re.compile(r"^0A$", re.IGNORECASE)
_REMOTE_YEAR_RE: Final[re.Pattern[str]] = re.compile(r"^\d{4}$")


def reconcile(
    draft: ModeloDraft,
    justificante: Justificante | None,
    *,
    schema_provider: _RegistryReconciliationProvider,
    now: datetime | None = None,
) -> ReconciliationReport:
    """Compare a local draft against AEAT's authoritative justificante.

    Compares the narrow set of metadata fields present on a parsed
    :class:`aeat.domain.justificante.Justificante` against the
    corresponding fields on a local
    :class:`aeat.domain.filing.ModeloDraft`, classifying each
    disagreement using :class:`ModeloDivergenceKind`.

    Args:
        draft: Local approved :class:`aeat.domain.filing.ModeloDraft`.
        justificante: Parsed AEAT-side
            :class:`aeat.domain.justificante.Justificante`, or ``None``
            when the sede has no record of a matching submission yet.
        schema_provider: Registry-backed filing provider for the draft
            modelo and period.
        now: Override for the report's ``reconciled_at`` timestamp.
            Supports deterministic testing. Defaults to
            the canonical clock helper.

    Returns:
        A frozen :class:`ReconciliationReport` whose
        :attr:`ReconciliationReport.status` is one of
        :attr:`ReconciliationStatus.COINCIDE`,
        :attr:`ReconciliationStatus.DIVERGENTE`, or
        :attr:`ReconciliationStatus.NOT_YET_FOUND`, accompanied by
        per-field mismatches and a multilingual narrative summary.
    """
    subview = _require_registry_reconciliation_surface(draft, schema_provider=schema_provider)
    reconciled_at = now or _utc_now()
    draft_ref = ModeloDraftRef(
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
                    kind=ModeloDivergenceKind.FILING_NOT_YET_FOUND,
                    field_name="justificante",
                    draft_value=f"modelo={draft.modelo} period={draft.period!s}",
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
                kind=ModeloDivergenceKind.MODELO_MISMATCH,
                field_name="modelo",
                draft_value=draft.modelo,
                remote_value=remote.modelo,
            ),
        )

    supported_periods = set(subview.period_selector_periods)
    if not _periods_match(draft.period, remote.period, supported_periods=supported_periods, ejercicio=remote.ejercicio):
        mismatches.append(
            FieldMismatch(
                kind=ModeloDivergenceKind.PERIOD_MISMATCH,
                field_name="period",
                draft_value=str(draft.period),
                remote_value=str(remote.period),
            ),
        )

    if _canonical_tax_id(draft.profile_tax_id) != _canonical_tax_id(remote.tax_id):
        mismatches.append(
            FieldMismatch(
                kind=ModeloDivergenceKind.TAX_ID_MISMATCH,
                field_name="tax_id",
                draft_value=draft.profile_tax_id,
                remote_value=remote.tax_id,
            ),
        )

    # Total mismatches are only surfaced when the draft itself records
    # a derived figure; per-modelo total-derivation is a follow-up,
    # so we stay strict-silent when the draft has no equivalent field.
    draft_totals = _derive_draft_totals(draft, total_casillas=subview.reconciliation_total_casillas)
    if (
        draft_totals.ingresar is not None
        and remote.total_a_ingresar is not None
        and abs(draft_totals.ingresar - remote.total_a_ingresar) > _TOLERANCE
    ):
        mismatches.append(
            FieldMismatch(
                kind=ModeloDivergenceKind.TOTAL_INGRESAR_MISMATCH,
                field_name="total_a_ingresar",
                draft_value=format_decimal(draft_totals.ingresar),
                remote_value=format_decimal(remote.total_a_ingresar),
            ),
        )
    if (
        draft_totals.devolver is not None
        and remote.total_a_devolver is not None
        and abs(draft_totals.devolver - remote.total_a_devolver) > _TOLERANCE
    ):
        mismatches.append(
            FieldMismatch(
                kind=ModeloDivergenceKind.TOTAL_DEVOLVER_MISMATCH,
                field_name="total_a_devolver",
                draft_value=format_decimal(draft_totals.devolver),
                remote_value=format_decimal(remote.total_a_devolver),
            ),
        )

    if mismatches:
        status = ReconciliationStatus.DIVERGENTE
        narrative = _narrative_divergent(draft, remote, mismatches)
        _logger.warning(
            "reconciliation divergent draft_id=%s modelo=%s period=%s mismatches=%d",
            draft.draft_id,
            draft.modelo,
            draft.period,
            len(mismatches),
        )
    else:
        status = ReconciliationStatus.COINCIDE
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


def _derive_draft_totals(draft: ModeloDraft, *, total_casillas: Mapping[str, str]) -> _DraftTotals:
    """Compute the draft's operator-visible ingresar / devolver figures.

    The registry declares which computed casillas carry the payable and
    refundable totals. Reconciliation only projects totals that are explicitly
    declared by that active registry snapshot.

    Args:
        draft: The local draft whose totals would be derived.
        total_casillas: Mapping from role key (``"ingresar"``,
            ``"devolver"``) to casilla id, as declared by the active
            registry snapshot.

    Returns:
        A :class:`_DraftTotals` with both fields set to ``None``.
    """
    values = {value.casilla_id: value.value for value in draft.values}
    return _DraftTotals(
        ingresar=_decimal_total(values, total_casillas.get("ingresar")),
        devolver=_decimal_total(values, total_casillas.get("devolver")),
    )


def _decimal_total(values: Mapping[str, object], casilla_id: str | None) -> Decimal | None:
    if casilla_id is None:
        return None
    value = values.get(casilla_id)
    if value is None:
        return None
    if isinstance(value, bool):
        raise ModeloBuilderError(f"registry reconciliation total casilla {casilla_id!r} is not numeric")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    raise ModeloBuilderError(f"registry reconciliation total casilla {casilla_id!r} is not numeric")


def _require_registry_reconciliation_surface(
    draft: ModeloDraft,
    *,
    schema_provider: _RegistryReconciliationProvider,
) -> _RegistryReconciliationSubview:
    subview = schema_provider.get_subview(draft.modelo)
    if draft.schema_version != subview.schema_version:
        raise ModeloBuilderError("reconciliation requires a draft built from the active registry snapshot")
    if not subview.verification_expectation_ids:
        raise ModeloBuilderError("reconciliation requires registry verification expectations")
    registry_token = draft.period.registry_token
    if registry_token not in subview.period_selector_periods:
        raise ModeloBuilderError("reconciliation requires a draft period declared by the active registry snapshot")
    return subview


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


def _periods_match(
    draft_period: Period,
    remote_period: Period | str,
    *,
    supported_periods: set[str],
    ejercicio: str | None,
) -> bool:
    if isinstance(remote_period, Period):
        return (
            remote_period == draft_period
            and remote_period.registry_token in supported_periods
            and draft_period.registry_token in supported_periods
        )
    draft_period_code = draft_period.registry_token
    draft_year_str = str(draft_period.filing_year)
    if draft_period_code.endswith("T") and draft_period_code[0] in "1234":
        draft_normalised = f"{draft_year_str}q{draft_period_code[0]}"
    elif draft_period_code == "0A":
        draft_normalised = f"{draft_year_str}a"
    else:
        draft_normalised = f"{draft_year_str}-{draft_period_code}"
    return draft_normalised == _normalise_period(
        remote_period,
        ejercicio=ejercicio or draft_year_str,
        supported_periods=supported_periods,
    )


def _normalise_period(
    period: str,
    *,
    ejercicio: str | None = None,
    supported_periods: set[str],
) -> str:
    """Lower-case and strip a period label for tolerant comparison.

    AEAT can print quarterly tokens, annual tokens, or only the fiscal
    year on annual receipts. This helper maps those receipt tokens to
    the same canonical labels used by filing drafts when the ejercicio
    is available.

    Args:
        period: Raw period label from either side of the compare.
        ejercicio: Optional fiscal year from the AEAT-side justificante.
        supported_periods: Set of canonical period tokens declared by
            the active registry snapshot for the modelo under comparison.

    Returns:
        The stripped, lower-cased period label.
    """
    stripped = period.strip()
    if match := _QUARTER_RE.fullmatch(stripped):
        token = f"{match.group('quarter')}T"
        if token not in supported_periods:
            return stripped.lower()
        return f"{match.group('year')}q{match.group('quarter')}"
    if match := _ANNUAL_RE.fullmatch(stripped):
        if "0A" not in supported_periods:
            return stripped.lower()
        return f"{match.group('year')}a"
    if ejercicio is not None and (match := _REMOTE_QUARTER_RE.fullmatch(stripped)):
        token = f"{match.group('quarter')}T"
        if token not in supported_periods:
            return stripped.lower()
        return f"{ejercicio}q{match.group('quarter')}"
    if ejercicio is not None and _REMOTE_ANNUAL_RE.fullmatch(stripped) and "0A" in supported_periods:
        return f"{ejercicio}a"
    if (
        ejercicio is not None
        and _REMOTE_YEAR_RE.fullmatch(stripped)
        and stripped == ejercicio
        and "0A" in supported_periods
    ):
        return f"{ejercicio}a"
    return stripped.lower()


def _canonical_tax_id(value: str) -> str:
    """Canonicalise a NIF / NIE for tolerant comparison (strip + upper)."""
    return value.strip().upper()


def _narrative_not_yet_found(draft: ModeloDraft) -> str:
    """Build the multilingual narrative for the NOT_YET_FOUND verdict."""
    es = (
        f"AEAT no tiene constancia del modelo {draft.modelo} del período "
        f"{draft.period}. Asegúrate de haberlo presentado correctamente."
    )
    return es


def _narrative_match(draft: ModeloDraft, remote: JustificanteRefSummary) -> str:
    """Build the multilingual narrative for the MATCH verdict."""
    es = f"Modelo {draft.modelo} {draft.period}: coincide con lo registrado en AEAT (CSV {remote.csv})."
    return es


def _narrative_divergent(
    draft: ModeloDraft,
    remote: JustificanteRefSummary,
    mismatches: list[FieldMismatch],
) -> str:
    """Build the multilingual narrative for the DIVERGENT verdict."""
    fields = ", ".join(m.field_name for m in mismatches)
    es = f"Modelo {draft.modelo} {draft.period}: divergencia frente a AEAT (CSV {remote.csv}) en: {fields}."
    return es


__all__ = ["reconcile"]
