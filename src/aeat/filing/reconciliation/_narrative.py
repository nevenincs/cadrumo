"""Trilingual ``Translatable`` builders for reconciliation reports.

Mirrors the pattern in :func:`aeat.verification._verify._compose_narrative`:
every Kent-facing string carries explicit ``es`` / ``en`` / ``hu``
translations, no partial localisation. The builders are pure
functions of the comparator inputs so the reconciler stays
deterministic and unit-testable without any I/O.

Two surfaces:

* :func:`compose_delta_narrative` — one trilingual string per
  :class:`CasillaDelta`, keyed off the
  :class:`FilingDivergenceKind` variant. Embeds the casilla id, the
  delta amount when defined, and the local / remote raw values when
  defined.
* :func:`compose_report_narrative` — one trilingual string per
  :class:`ReconciliationReport`, summarising the terminal-triad
  member, the modelo / period anchor, and the count of divergences.
"""

from __future__ import annotations

from decimal import Decimal

from ...i18n import Translatable
from ._kind import FilingDivergenceKind
from ._schema import ReconciliationStatus


def _format_value(value: str | None) -> str:
    """Render a raw value for the narrative; falls back to a localised dash."""
    if value is None or value == "":
        return "-"
    return value


def _format_delta(delta: Decimal | None) -> str:
    """Render the signed monetary delta for the narrative."""
    if delta is None:
        return "-"
    return f"{delta} EUR"


def compose_delta_narrative(
    *,
    casilla_id: str,
    kind: FilingDivergenceKind,
    local_value: str | None,
    remote_value: str | None,
    delta: Decimal | None,
) -> Translatable:
    """Build the trilingual narrative for one :class:`CasillaDelta`.

    Args:
        casilla_id: Stable casilla identifier the delta refers to.
        kind: The :class:`FilingDivergenceKind` variant the delta
            instantiates; selects the narrative template.
        local_value: The local draft's printed value, or ``None`` when
            the local draft does not carry the casilla.
        remote_value: AEAT's printed value, or ``None`` when AEAT does
            not carry the casilla.
        delta: The signed monetary delta when both sides report a
            coercible decimal value; ``None`` otherwise.

    Returns:
        A :class:`aeat.i18n.Translatable` carrying ``es`` / ``en`` /
        ``hu`` strings populated for the requested variant.
    """
    local = _format_value(local_value)
    remote = _format_value(remote_value)
    delta_text = _format_delta(delta)

    if kind is FilingDivergenceKind.CASILLA_VALUE_MISMATCH:
        return {
            "es": (f"Casilla {casilla_id}: divergencia material - local {local}, AEAT {remote}, delta {delta_text}."),
            "en": (f"Casilla {casilla_id}: material divergence - local {local}, AEAT {remote}, delta {delta_text}."),
            "hu": (f"{casilla_id} casilla: jelentős eltérés - helyi {local}, AEAT {remote}, eltérés {delta_text}."),
        }
    if kind is FilingDivergenceKind.CASILLA_MISSING_LOCAL:
        return {
            "es": (f"Casilla {casilla_id}: AEAT informa {remote} pero el borrador local no lleva esta casilla."),
            "en": (f"Casilla {casilla_id}: AEAT reports {remote} but the local draft does not carry this casilla."),
            "hu": (
                f"{casilla_id} casilla: AEAT {remote} értéket jelent, "
                "de a helyi piszkozat nem tartalmazza ezt a casillát."
            ),
        }
    if kind is FilingDivergenceKind.CASILLA_EXTRA_LOCAL:
        return {
            "es": (f"Casilla {casilla_id}: el borrador local lleva {local} pero AEAT no informa esta casilla."),
            "en": (f"Casilla {casilla_id}: the local draft carries {local} but AEAT does not report this casilla."),
            "hu": (f"{casilla_id} casilla: a helyi piszkozat {local} értéket tartalmaz, de az AEAT nem jelzi."),
        }
    if kind is FilingDivergenceKind.FILING_STATUS_DIVERGENCE:
        return {
            "es": (
                f"Estado de la presentacion: divergencia entre el estado local y el estado remoto "
                f"(local {local}, AEAT {remote})."
            ),
            "en": (f"Filing status divergence between local and remote (local {local}, AEAT {remote})."),
            "hu": (f"A bevallás állapota eltér a helyi és a távoli oldal között (helyi {local}, AEAT {remote})."),
        }
    if kind is FilingDivergenceKind.ROUNDING_ONLY:
        return {
            "es": (
                f"Casilla {casilla_id}: diferencia dentro del margen de redondeo "
                f"(local {local}, AEAT {remote}, delta {delta_text})."
            ),
            "en": (
                f"Casilla {casilla_id}: delta within rounding tolerance "
                f"(local {local}, AEAT {remote}, delta {delta_text})."
            ),
            "hu": (
                f"{casilla_id} casilla: a kerekítési toleranciába esik "
                f"(helyi {local}, AEAT {remote}, eltérés {delta_text})."
            ),
        }
    if kind is FilingDivergenceKind.FILING_NOT_YET_FOUND:
        return {
            "es": ("AEAT no tiene constancia de esta presentacion todavia. ¿Has subido realmente esta declaracion?"),
            "en": ("AEAT has no record of this filing yet. Has the declaration actually been uploaded?"),
            "hu": ("Az AEAT még nem rendelkezik erről a bevallásról. Valóban feltöltötték már a bevallást?"),
        }
    raise ValueError(f"Unhandled FilingDivergenceKind variant: {kind!r}")


def compose_report_narrative(
    *,
    status: ReconciliationStatus,
    modelo: str,
    period: str,
    delta_count: int,
) -> Translatable:
    """Build the report-level trilingual narrative.

    Args:
        status: The Kent-observable terminal triad member the report
            resolves to.
        modelo: AEAT modelo code the comparison ran against.
        period: Period identifier the comparison ran against.
        delta_count: Total count of :class:`CasillaDelta` entries on
            the report. For :attr:`ReconciliationStatus.NOT_YET_FOUND`
            this is the sentinel count (always one).

    Returns:
        A :class:`aeat.i18n.Translatable` carrying ``es`` / ``en`` /
        ``hu`` strings populated for the report status.
    """
    if status is ReconciliationStatus.MATCH:
        return {
            "es": (f"Modelo {modelo} {period}: conciliado. {delta_count} divergencias dentro del margen de redondeo."),
            "en": (f"Modelo {modelo} {period}: reconciled. {delta_count} divergences within rounding tolerance."),
            "hu": (f"{modelo} modell {period}: egyeztetve. {delta_count} eltérés a kerekítési toleranciában."),
        }
    if status is ReconciliationStatus.DIVERGENT:
        return {
            "es": (f"Modelo {modelo} {period}: divergente. {delta_count} divergencias - revisa la lista detallada."),
            "en": (f"Modelo {modelo} {period}: divergent. {delta_count} divergences - inspect the itemised list."),
            "hu": (f"{modelo} modell {period}: eltérés. {delta_count} eltérés - nézd át a tételes listát."),
        }
    if status is ReconciliationStatus.NOT_YET_FOUND:
        return {
            "es": (
                f"Modelo {modelo} {period}: AEAT no tiene constancia de esta presentacion todavia. "
                "¿Has subido realmente esta declaracion?"
            ),
            "en": (
                f"Modelo {modelo} {period}: AEAT has no record of this filing yet. "
                "Has the declaration actually been uploaded?"
            ),
            "hu": (
                f"{modelo} modell {period}: az AEAT még nem rendelkezik erről a bevallásról. "
                "Valóban feltöltötték már a bevallást?"
            ),
        }
    raise ValueError(f"Unhandled ReconciliationStatus variant: {status!r}")


__all__ = ["compose_delta_narrative", "compose_report_narrative"]
