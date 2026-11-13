"""Half-period cohabitation, judicial incapacity, the PCTMINASDLG key and the art. 60.2 note, through the real resolver.

The expected values are the law's and the design's, written here rather than read back
from the registry: LIRPF art. 59.1 grants 1.150 euros for an ascendant of 65 or more or
with a disability; art. 61 norma 5ª requires cohabitation for at least half the period;
art. 60.3 counts a judicial incapacity as a grade of 65 % or more; and the Modelo 100
XSD codes PCTMINASDLG as 1 (33 % to under 65 %), 2 (the same with assistance of third
persons or reduced mobility), 3 (65 % or more) and 4 (judicial incapacitation).

Every supported year is enumerated from the registry's support envelope. The key is
asserted wherever the edition binds PCTMINASDLG, which the registry declares.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.user_profile.values import create_user_profile_record

from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_edition
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context,
    published_snapshot,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ...aggregation.source_mesh import CalculationSourceResolution
from ..calculation_notes import GATE_REFUSED_REASONS, PROFILE_REASONS, note_fact_text
from ..profile_binding import resolve_profile_sourced_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_BUCKET = "0de41ce4-0000-4000-8000-000000000593"
_T0 = datetime(1980, 8, 5, 10, 0, tzinfo=UTC)
_MINIMO = "renta-profile-minimo-ascendientes-estatal"
_KEY_BINDING = "renta-family-ascendant-disability-grade"
_GROUP = "renta_family.ascendiente"
_NOT_COMPUTED = "ascendant_disability_minimum_not_computed"

# LIRPF art. 59.1.
_BASE = Decimal("1150")


def _snapshot(year: int) -> RegistrySnapshot:
    return published_snapshot("100", filing_year=year, period="0A")


def _binds_the_key(year: int) -> bool:
    return any(binding.id == _KEY_BINDING for binding in _snapshot(year).revision.bindings)


def _born(year: int, age: int) -> date:
    """A birth date that gives ``age`` full years at 31 December of ``year``."""
    return date(year - age, 6, 1)


def _row(year: int, age: int, **changes: str | None) -> dict[str, str]:
    """An entitled ascendant living with the filer alone, below both income figures."""
    row: dict[str, str | None] = {
        "birth_date": _born(year, age).isoformat(),
        "convivientes": "1",
        "convivencia_mitad_periodo": "true",
        "rentas_anuales": "1000.00",
        **changes,
    }
    return {leaf: value for leaf, value in row.items() if value is not None}


def _record(*rows: dict[str, str]) -> UserProfileRecord:
    facts = [UserProfileFact(path="renta_family.ascendientes_count", value=str(len(rows)))]
    for index, row in enumerate(rows):
        facts.extend(UserProfileFact(path=f"{_GROUP}.{index}.{leaf}", value=value) for leaf, value in row.items())
    return create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET,
        facts=tuple(facts),
        created_at=_T0,
        updated_at=_T0,
        context=leased_profile_create_context(),
    )


def _resolve(year: int, *rows: dict[str, str], operation: PinnedAuthorityOperation) -> CalculationSourceResolution:
    return resolve_profile_sourced_bindings(
        _snapshot(year), bucket_id=_BUCKET, profile_record=_record(*rows), operation=operation
    )


# The identity leaves the design requires of every row are another gate's notes.
_IDENTITY_LEAVES = frozenset({"nif", "apellidos_nombre"})


def _owed(resolution: CalculationSourceResolution) -> set[str]:
    """The deciding leaves the mínimo's notes name."""
    return {
        str(dict(diagnostic.fact.values)["leaf"])
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "household_row_fact_unstated" and diagnostic.fact is not None
    } - _IDENTITY_LEAVES


def _not_computed_rows(resolution: CalculationSourceResolution) -> tuple[str, ...] | None:
    notes = [diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == _NOT_COMPUTED]
    if not notes:
        return None
    (note,) = notes
    assert note.fact is not None
    return note.fact.row_refs


@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_half_period_cohabitation_unstated_withholds_and_a_stated_no_excludes(
    year: int, authority_operation: PinnedAuthorityOperation
) -> None:
    unstated = _resolve(year, _row(year, 70, convivencia_mitad_periodo=None), operation=authority_operation)
    assert _MINIMO in unstated.unresolved_binding_ids
    assert _owed(unstated) == {"convivencia_mitad_periodo"}

    excluded = _resolve(year, _row(year, 70, convivencia_mitad_periodo="false"), operation=authority_operation)
    assert excluded.binding_values[_MINIMO] == Decimal("0")
    assert not _owed(excluded)

    entitled = _resolve(year, _row(year, 70), operation=authority_operation)
    assert entitled.binding_values[_MINIMO] == _BASE


def test_a_stated_zero_cohabitants_excludes_and_an_unstated_count_is_owed(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    year = newest_authored_edition("100")

    excluded = _resolve(year, _row(year, 70, convivientes="0"), operation=authority_operation)
    owed = _resolve(year, _row(year, 70, convivientes=None), operation=authority_operation)

    assert excluded.binding_values[_MINIMO] == Decimal("0")
    assert not _owed(excluded)
    assert _MINIMO in owed.unresolved_binding_ids
    assert _owed(owed) == {"convivientes"}


@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_a_judicial_incapacity_governs_over_a_lower_stated_grade_under_the_minimum_age(
    year: int, authority_operation: PinnedAuthorityOperation
) -> None:
    judicial = _resolve(
        year, _row(year, 50, discapacidad="0", incapacidad_judicial="true"), operation=authority_operation
    )
    assert judicial.binding_values[_MINIMO] == _BASE

    undecided = _resolve(year, _row(year, 50, discapacidad="0"), operation=authority_operation)
    assert _MINIMO in undecided.unresolved_binding_ids
    assert _owed(undecided) == {"incapacidad_judicial"}

    none = _resolve(year, _row(year, 50, discapacidad="0", incapacidad_judicial="false"), operation=authority_operation)
    assert none.binding_values[_MINIMO] == Decimal("0")

    both_unstated = _resolve(year, _row(year, 50), operation=authority_operation)
    assert _owed(both_unstated) == {"discapacidad", "incapacidad_judicial"}


@pytest.mark.parametrize(
    ("facts", "code"),
    [
        ({"discapacidad": "33", "discapacidad_asistencia": "false", "incapacidad_judicial": "false"}, "1"),
        ({"discapacidad": "33", "discapacidad_asistencia": "true", "incapacidad_judicial": "false"}, "2"),
        ({"discapacidad": "65", "incapacidad_judicial": "false"}, "3"),
        ({"discapacidad": "65", "discapacidad_asistencia": "true", "incapacidad_judicial": "false"}, "3"),
        ({"discapacidad": "33", "incapacidad_judicial": "true"}, "4"),
        ({"discapacidad": "0", "incapacidad_judicial": "true"}, "4"),
        ({"incapacidad_judicial": "true"}, "4"),
        ({"discapacidad": "0", "incapacidad_judicial": "false"}, None),
        # A fact the key turns on and the row does not state leaves the key undecided, never guessed.
        ({"discapacidad": "33", "incapacidad_judicial": "false"}, None),
        ({"discapacidad": "65"}, None),
        ({}, None),
    ],
)
@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_the_disability_key_is_derived_from_grade_assistance_and_judicial_incapacity(
    year: int, facts: dict[str, str], code: str | None, authority_operation: PinnedAuthorityOperation
) -> None:
    resolution = _resolve(year, _row(year, 80), _row(year, 70, **facts), operation=authority_operation)

    assert (_KEY_BINDING, 1) not in resolution.row_binding_values
    if not _binds_the_key(year):
        assert (_KEY_BINDING, 2) not in resolution.row_binding_values
        return
    assert resolution.row_binding_values.get((_KEY_BINDING, 2)) == code


def test_a_stored_key_is_not_read_and_the_derived_one_replaces_it(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    year = newest_authored_edition("100")
    assert _binds_the_key(year)
    planted = _row(year, 70, discapacidad="0", incapacidad_judicial="false", minimo_discapacidad_clave="4")

    resolution = _resolve(year, planted, operation=authority_operation)

    assert (_KEY_BINDING, 1) not in resolution.row_binding_values


@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_an_entitled_ascendant_with_a_disability_raises_the_not_computed_note(
    year: int, authority_operation: PinnedAuthorityOperation
) -> None:
    rows = (
        _row(year, 70, discapacidad="0", incapacidad_judicial="false"),
        _row(year, 70, discapacidad="33", incapacidad_judicial="false"),
        # Ruled out by its income, so no disability minimum is reached.
        _row(year, 70, discapacidad="65", rentas_anuales="9000.00"),
        _row(year, 50, discapacidad="0", incapacidad_judicial="true"),
    )

    resolution = _resolve(year, *rows, operation=authority_operation)

    assert resolution.binding_values[_MINIMO] == 3 * _BASE
    assert _not_computed_rows(resolution) == ("1", "3")


def test_the_not_computed_note_blocks_reads_in_every_language_and_is_absent_without_a_disability(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    year = newest_authored_edition("100")

    clean = _resolve(
        year, _row(year, 80, discapacidad="0", incapacidad_judicial="false"), operation=authority_operation
    )
    noted = _resolve(year, _row(year, 80, discapacidad="65"), operation=authority_operation)

    assert _not_computed_rows(clean) is None
    assert _not_computed_rows(noted) == ("0",)
    assert _NOT_COMPUTED in GATE_REFUSED_REASONS
    assert _NOT_COMPUTED in PROFILE_REASONS
    (note,) = (diagnostic for diagnostic in noted.diagnostics if diagnostic.reason == _NOT_COMPUTED)
    assert note.fact is not None
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        text = note_fact_text(note.fact, locale=language)
        assert "1" in text and "{" not in text, (language, text)
