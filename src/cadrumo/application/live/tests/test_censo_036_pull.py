"""Proofs for deriving censal enrolment from the taxpayer's filed Modelo 036.

The projection is pure, so these drive it with real
:class:`~cadrumo.adapters.outbound.aeat.sede.Declaracion` rows built from
the adapter's own strict model — the same shape the live register walk
returns — rather than through a double. The live read itself is gated
behind the opt-in live marker elsewhere; what is worth pinning here is the
classification and the lifecycle ordering, because getting either wrong
silently misstates whether the taxpayer is enrolled at all.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ....adapters.outbound.aeat.sede import Declaracion
from ....core import Modelo, Period
from ....domain.calculations.registry import CensoModeloEventKind
from .._censo_036_pull import (
    CENSO_FILED_ON_FACT_PATH,
    CENSO_STATUS_FACT_PATH,
    censo_facts_from_filed_036,
    classify_censal_event,
    current_censal_state,
    filed_036_declarations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _row(
    *,
    modelo: str = Modelo.M036.value,
    year: int = 2024,
    day: int = 15,
    tipo: str | None = None,
    observaciones: str | None = None,
) -> Declaracion:
    return Declaracion(
        modelo=modelo,
        ejercicio=year,
        period=Period.from_year_and_code(year, "0A"),
        expediente_id=f"EXP{year}{day:02d}000000",
        estado="ALTA",
        tipo_solicitud=tipo,
        observaciones=observaciones,
        presented_at=datetime(year, 3, day, 12, 0, tzinfo=UTC),
    )


# ── classification ──────────────────────────────────────────────────────────


def test_a_baja_is_not_read_as_an_alta_when_its_prose_names_one() -> None:
    """Baja must win over alta in the same string.

    A deregistration row routinely describes the enrolment it reverses, so
    an alta-first check would classify the taxpayer as newly enrolled at
    the exact moment they stopped being enrolled.
    """
    assert (
        classify_censal_event(tipo_solicitud="Baja en el censo", observaciones="anula el alta anterior")
        is CensoModeloEventKind.BAJA
    )


def test_alta_and_modificacion_classify_from_their_own_prose() -> None:
    assert classify_censal_event(tipo_solicitud="Alta en el censo", observaciones=None) is CensoModeloEventKind.ALTA
    assert (
        classify_censal_event(tipo_solicitud="Modificación de datos", observaciones=None)
        is CensoModeloEventKind.MODIFICACION
    )


def test_an_unrecognised_label_defaults_to_the_least_assertive_reading() -> None:
    """Modificación is the default because it asserts least.

    ALTA would claim a first enrolment that may never have happened; BAJA
    would claim a deregistration and suppress obligations the taxpayer
    still has. Neither is safe to guess.
    """
    assert classify_censal_event(tipo_solicitud=None, observaciones=None) is CensoModeloEventKind.MODIFICACION
    assert (
        classify_censal_event(tipo_solicitud="Presentación telemática", observaciones=None)
        is CensoModeloEventKind.MODIFICACION
    )


# ── projection and lifecycle ────────────────────────────────────────────────


def test_non_036_rows_are_dropped_from_a_mixed_capture() -> None:
    rows = (_row(tipo="Alta"), _row(modelo=Modelo.M303.value, tipo="Alta"))
    assert len(filed_036_declarations(rows)) == 1


def test_the_most_recent_filing_determines_the_current_state() -> None:
    """A later modificación supersedes the alta it amends."""
    filings = filed_036_declarations(
        (
            _row(year=2022, tipo="Alta en el censo"),
            _row(year=2024, tipo="Modificación de datos"),
        ),
    )
    current = current_censal_state(filings)
    assert current is not None
    assert current.event_kind is CensoModeloEventKind.MODIFICACION
    assert current.ejercicio == 2024


def test_a_later_baja_supersedes_an_earlier_alta() -> None:
    filings = filed_036_declarations(
        (
            _row(year=2021, tipo="Alta en el censo"),
            _row(year=2023, tipo="Baja en el censo"),
        ),
    )
    current = current_censal_state(filings)
    assert current is not None
    assert current.event_kind is CensoModeloEventKind.BAJA


def test_filings_are_ordered_oldest_first_regardless_of_input_order() -> None:
    filings = filed_036_declarations((_row(year=2024, tipo="Alta"), _row(year=2020, tipo="Alta")))
    assert [filing.ejercicio for filing in filings] == [2020, 2024]


# ── facts ───────────────────────────────────────────────────────────────────


def test_facts_carry_the_current_state_and_the_date_it_came_from() -> None:
    """The filing date lands as a real date, not a string.

    ``UserProfileFact`` parses an ISO day into ``datetime.date``, so the
    fact reaches storage as a typed value the schema's DATE validation and
    the deadline engine can both use directly.
    """
    filings = filed_036_declarations((_row(year=2024, day=7, tipo="Alta en el censo"),))
    facts = {fact.path: fact.value for fact in censo_facts_from_filed_036(filings)}
    assert facts[CENSO_STATUS_FACT_PATH] == CensoModeloEventKind.ALTA.value
    assert facts[CENSO_FILED_ON_FACT_PATH] == date(2024, 3, 7)


def test_no_filing_asserts_nothing_about_the_taxpayer() -> None:
    """Silence, not a default: stamping one would invent an enrolment."""
    assert censo_facts_from_filed_036(()) == ()


def test_the_status_fact_uses_the_path_the_registry_binding_reads() -> None:
    """The pulled value must feed the existing binding, not a second channel.

    The 036 revision's ``modelo-036-profile-censo-status`` binding selects
    ``censo.status``; writing anywhere else would leave the engine reading
    a value nothing populates.
    """
    assert CENSO_STATUS_FACT_PATH == "censo.status"
