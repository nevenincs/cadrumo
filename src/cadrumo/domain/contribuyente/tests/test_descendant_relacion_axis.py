"""The relación axis and the two Art. 58.2 entry-event anchors.

LIRPF draws the descendant line twice and the two lines do not coincide:
Art. 58.1 assimilates "tutela y acogimiento" for the tranche amounts, while
Art. 58.2 grants the under-three increase, age-independently, only "en los
supuestos de adopción o acogimiento, tanto preadoptivo como permanente". The
gap between those two sentences is a real household — a temporal acogimiento
carer — and every test here exists because that household is silently
mis-served by any model that cannot name it.

The assertions are STRUCTURAL rather than numeric: which statutory limb fires
for which relación, and which date anchors the window. No euro figure is
computed or expected, so nothing here re-derives a registry formula against
itself. The monetary side is grounded separately against the bundled AEAT
worked example, whose child is adopted — which evidences the adopción route
only, and is precisely why the acogimiento and tutela routes need their own
structural coverage.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ....core import ART_58_2_ENTITLING_RELACIONES, DescendantRelacion
from .._descendant_facts import (
    descendant_facts_from_list,
    descendant_list_from_facts,
    parse_descendiente_flag,
)
from ..family import DescendantInfo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A filing year comfortably after every entry event used below.
_YEAR = 2024

#: Born long before the filing year, so the ordinary under-three limb is dead
#: and only the age-independent entry-event limb can grant the increase. Every
#: entitlement assertion below is therefore about the limb under test.
_OLD_BIRTH = date(2010, 1, 1)


def _older_child(relacion: DescendantRelacion, **dates: date) -> DescendantInfo:
    return DescendantInfo(birth_date=_OLD_BIRTH, relacion=relacion, **dates)


# ── the boundary the axis exists to draw ────────────────────────────────────


def test_temporal_acogimiento_takes_the_tranche_and_not_the_increase() -> None:
    """The household that has no honest value without this member.

    Art. 58.1 assimilates acogimiento generally, so a temporal carer is a
    descendant for the tranche amounts. Art. 58.2 qualifies its acogimiento as
    "tanto preadoptivo como permanente", so the same carer is excluded from the
    increase. With a single collapsed acogimiento member this carer would have
    had to select the entitling one and would have taken an increase the
    statute withholds -- an over-grant produced by the axis meant to correct an
    under-grant.
    """
    carer = _older_child(DescendantRelacion.ACOGIMIENTO_TEMPORAL)

    assert carer.meets_non_income_conditions(_YEAR) is True
    assert carer.is_eligible_minimo_incremento_menor_tres(_YEAR) is False


def test_tutela_takes_the_tranche_and_not_the_increase() -> None:
    """Art. 58.1 names tutela; Art. 58.2 omits it. One word of scope difference."""
    guardian = _older_child(DescendantRelacion.TUTELA)

    assert guardian.meets_non_income_conditions(_YEAR) is True
    assert guardian.is_eligible_minimo_incremento_menor_tres(_YEAR) is False


@pytest.mark.parametrize("relacion", sorted(ART_58_2_ENTITLING_RELACIONES))
def test_every_entitling_relacion_opens_the_window_with_its_own_anchor(
    relacion: DescendantRelacion,
) -> None:
    """Both members the statute names take the increase, each from its own date."""
    field = (
        "inscripcion_registro_civil_date" if relacion is DescendantRelacion.ADOPTADO else "acogimiento_resolucion_date"
    )
    child = _older_child(relacion, **{field: date(_YEAR, 3, 1)})

    assert child.is_eligible_minimo_incremento_menor_tres(_YEAR) is True


def test_the_increase_is_age_independent_for_an_entitling_relacion() -> None:
    """Art. 58.2: "con independencia de la edad del menor".

    A child adopted at fourteen qualifies. The engine's age-only predicate
    granted this household nothing for three years running, which is the defect
    the entry-event limb closes.
    """
    teenager = DescendantInfo(
        birth_date=date(2010, 1, 1),
        relacion=DescendantRelacion.ADOPTADO,
        inscripcion_registro_civil_date=date(2024, 6, 1),
    )

    assert teenager.age_at_year_end(_YEAR) == 14
    assert teenager.is_eligible_minimo_incremento_menor_tres(_YEAR) is True


# ── the window is a CAP, not a restart ──────────────────────────────────────


def test_a_fostered_then_adopted_child_gets_three_periods_in_total_not_six() -> None:
    """The authority's own worked example, and the reason both dates are kept.

    Where circumstances change -- an adoption following a fostering -- the
    increase continues for the REMAINING periods up to a maximum of three. A
    model anchoring on whichever event it happened to hold would restart the
    count on the adoption and grant six periods where the law allows three,
    which under-declares.
    """
    child = DescendantInfo(
        birth_date=_OLD_BIRTH,
        relacion=DescendantRelacion.ADOPTADO,
        acogimiento_resolucion_date=date(2019, 5, 1),
        inscripcion_registro_civil_date=date(2022, 6, 1),
    )

    assert child.art_58_2_entry_date() == date(2019, 5, 1)
    granted = [year for year in range(2019, 2026) if child.is_eligible_minimo_incremento_menor_tres(year)]
    assert granted == [2019, 2020, 2021]


def test_the_madrid_window_anchors_on_the_adoption_while_art_58_2_anchors_earlier() -> None:
    """Three consumers, two anchors for one child -- why one general date fails.

    The autonomic nacimiento/adopción deducción keys on nacimiento and adopción
    only, so it counts from the inscription. Art. 58.2 counts from the first
    entitling event, which for this child is the earlier fostering. A single
    entry-event field would have to serve both and would silently apply one
    statute's window to the other's deducción.
    """
    child = DescendantInfo(
        birth_date=_OLD_BIRTH,
        relacion=DescendantRelacion.ADOPTADO,
        acogimiento_resolucion_date=date(2019, 5, 1),
        inscripcion_registro_civil_date=date(2022, 6, 1),
    )

    assert child.entry_year() == 2022
    assert child.art_58_2_entry_date() == date(2019, 5, 1)


# ── coherence: refuse the excluded case, allow the incomplete one ────────────


@pytest.mark.parametrize(
    ("relacion", "field"),
    [
        (DescendantRelacion.TUTELA, "inscripcion_registro_civil_date"),
        (DescendantRelacion.TUTELA, "acogimiento_resolucion_date"),
        (DescendantRelacion.ACOGIMIENTO_TEMPORAL, "inscripcion_registro_civil_date"),
        (DescendantRelacion.ACOGIMIENTO_TEMPORAL, "acogimiento_resolucion_date"),
        (DescendantRelacion.DESCENDIENTE, "inscripcion_registro_civil_date"),
        (DescendantRelacion.DESCENDIENTE, "acogimiento_resolucion_date"),
        (DescendantRelacion.ACOGIMIENTO_PREADOPTIVO_O_PERMANENTE, "inscripcion_registro_civil_date"),
    ],
)
def test_an_entry_date_under_an_excluded_relacion_refuses(
    relacion: DescendantRelacion,
    field: str,
) -> None:
    """Silent tolerance is how the excluded case becomes reachable.

    These records have exactly one date field the operator could reach for, so
    tolerating a value there would leave an entitling anchor sitting on a
    record the statute excludes -- and any consumer reading the date without
    re-checking the relación would grant the increase.
    """
    with pytest.raises((ValidationError, ValueError)):
        DescendantInfo(birth_date=_OLD_BIRTH, relacion=relacion, **{field: date(2020, 1, 1)})


@pytest.mark.parametrize(
    "relacion",
    [DescendantRelacion.TUTELA, DescendantRelacion.ACOGIMIENTO_TEMPORAL, DescendantRelacion.DESCENDIENTE],
)
def test_the_predicate_withholds_even_if_an_excluded_record_somehow_holds_a_date(
    relacion: DescendantRelacion,
) -> None:
    """The second layer, tested independently of the first.

    ``model_construct`` deliberately bypasses validation to build the record the
    coherence rule forbids. Nothing in production can produce it today -- which
    is exactly why this test exists: without it the predicate's own relación
    check is unreachable, so a future door that constructed records by another
    path, or a weakened validator, would silently start granting the Art. 58.2
    increase to a tutela guardian or a temporal carer with no test going red.

    Verified by mutation: deleting the relación check from
    :meth:`DescendantInfo.art_58_2_entry_date` leaves every other test in this
    module green and fails only this one.
    """
    smuggled = DescendantInfo.model_construct(
        birth_date=_OLD_BIRTH,
        relacion=relacion,
        inscripcion_registro_civil_date=date(2024, 1, 1),
        acogimiento_resolucion_date=date(2024, 1, 1),
        convive_con_contribuyente=True,
        discapacidad_grado=None,
    )

    assert smuggled.art_58_2_entry_date() is None
    assert smuggled.is_eligible_minimo_incremento_menor_tres(_YEAR) is False
    assert smuggled.art_58_2_window_anchor_missing(_YEAR) is False


@pytest.mark.parametrize("relacion", sorted(ART_58_2_ENTITLING_RELACIONES))
def test_an_entitling_relacion_without_its_date_is_valid_and_withholds(
    relacion: DescendantRelacion,
) -> None:
    """Incomplete is recordable; the grant is deferred, not the record refused.

    An operator may know a child is adopted before they hold the inscription
    date. Refusing the record would block them from stating a true fact, so the
    window simply cannot be measured and the increase is withheld -- the
    under-granting direction -- with the missing anchor reported so it does not
    stay silent.
    """
    child = _older_child(relacion)

    assert child.art_58_2_entry_date() is None
    assert child.is_eligible_minimo_incremento_menor_tres(_YEAR) is False
    assert child.art_58_2_window_anchor_missing(_YEAR) is True


@pytest.mark.parametrize(
    ("child", "reason"),
    [
        (
            DescendantInfo(birth_date=date(2023, 1, 1), relacion=DescendantRelacion.ADOPTADO),
            "already under three, so the ordinary limb grants it anyway",
        ),
        (
            DescendantInfo(birth_date=_OLD_BIRTH, relacion=DescendantRelacion.ACOGIMIENTO_TEMPORAL),
            "excluded from the limb, so it has no anchor to be missing",
        ),
        (
            DescendantInfo(
                birth_date=_OLD_BIRTH,
                relacion=DescendantRelacion.ADOPTADO,
                convive_con_contribuyente=False,
            ),
            "not cohabiting, so no mínimo applies at all",
        ),
    ],
)
def test_the_missing_anchor_report_stays_silent_where_nothing_is_lost(
    child: DescendantInfo,
    reason: str,
) -> None:
    """A report that fires on states costing nothing trains the operator to ignore it."""
    assert child.art_58_2_window_anchor_missing(_YEAR) is False, reason


def test_an_unstated_relacion_with_an_inscription_reads_as_adoptado() -> None:
    """Same information, no guess.

    Nothing but an adoption carries a Registro Civil inscription for this
    purpose, so a record supplying one has already stated its relación. This is
    a reading rather than an inference about a case the operator left open --
    which is why the acogimiento date, compatible with two members the statute
    treats oppositely, gets no equivalent.
    """
    child = DescendantInfo(birth_date=_OLD_BIRTH, inscripcion_registro_civil_date=date(2024, 2, 1))

    assert child.relacion is DescendantRelacion.ADOPTADO
    assert child.is_eligible_minimo_incremento_menor_tres(_YEAR) is True


def test_an_unstated_relacion_defaults_to_the_ordinary_descendant() -> None:
    """Absence of the fact means an ordinary descendant, the overwhelming case."""
    assert DescendantInfo(birth_date=_OLD_BIRTH).relacion is DescendantRelacion.DESCENDIENTE


# ── the entry doors carry the axis ──────────────────────────────────────────


def test_the_flag_parser_reads_every_relacion_member() -> None:
    """No member is reachable only through the model.

    A member the CLI cannot express is a member the operator does not have, and
    the temporal carer would be back to choosing an entitling relación.
    """
    for member in DescendantRelacion:
        parsed = parse_descendiente_flag(f"NACIMIENTO=2010-01-01,RELACION={member.value}")
        assert parsed.relacion is member


def test_the_flag_parser_refuses_a_relacion_outside_the_closed_set() -> None:
    """An unreadable token refuses rather than resolving to the ordinary default.

    The default is not a neutral fallback here: resolving a corrupted
    ``acogimiento_temporal`` onto it would strip the record of the one
    distinction keeping the Art. 58.2 increase away from that carer.
    """
    with pytest.raises((ValueError, ValidationError)):
        parse_descendiente_flag("NACIMIENTO=2010-01-01,RELACION=acogimiento")


def test_the_flag_parser_carries_both_entry_dates_for_a_fostered_then_adopted_child() -> None:
    """The cap shape has to be expressible non-interactively, not only in the wizard."""
    parsed = parse_descendiente_flag(
        "NACIMIENTO=2010-01-01,RELACION=adoptado,ACOGIMIENTO=2019-05-01,INSCRIPCION=2022-06-01",
    )

    assert parsed.art_58_2_entry_date() == date(2019, 5, 1)


# ── persistence boundary ────────────────────────────────────────────────────


def _maximal_descendants() -> tuple[DescendantInfo, ...]:
    """One record per relación, every defaultable field set to a NON-default value.

    A save-drops-field regression is invisible when the fixture uses the
    default, so nothing here is left at one: the ordinary record carries an
    explicit relación that happens to equal the default and is checked by
    equality, and the two entitling records carry every date their relación
    permits.
    """
    common = {
        "discapacidad_grado": 33,
        "convive_con_contribuyente": False,
        "custodia_compartida": True,
        "presenta_declaracion_propia": True,
        "prorrata_minimo": True,
        "meses_madre_trabajo_2024": 7,
        "gastos_guarderia_euros": 1200,
        "nif": "00000000T",
    }
    return (
        DescendantInfo(birth_date=date(2011, 2, 3), relacion=DescendantRelacion.DESCENDIENTE, **common),
        DescendantInfo(
            birth_date=date(2012, 3, 4),
            relacion=DescendantRelacion.ADOPTADO,
            acogimiento_resolucion_date=date(2018, 4, 5),
            inscripcion_registro_civil_date=date(2020, 5, 6),
            **common,
        ),
        DescendantInfo(
            birth_date=date(2013, 4, 5),
            relacion=DescendantRelacion.ACOGIMIENTO_PREADOPTIVO_O_PERMANENTE,
            acogimiento_resolucion_date=date(2019, 6, 7),
            **common,
        ),
        DescendantInfo(birth_date=date(2014, 5, 6), relacion=DescendantRelacion.ACOGIMIENTO_TEMPORAL, **common),
        DescendantInfo(birth_date=date(2015, 6, 7), relacion=DescendantRelacion.TUTELA, **common),
    )


def test_every_relacion_survives_the_fact_boundary_with_strict_equality() -> None:
    """Save to flat facts, reload, and assert the records are identical.

    Strict equality over the whole tuple rather than a field spot-check: a
    partial comparison is how a dropped field survives a roundtrip test.
    """
    original = _maximal_descendants()

    reloaded = descendant_list_from_facts(dict(descendant_facts_from_list(original)))

    assert reloaded == original


def test_deleting_the_stored_relacion_changes_the_reloaded_record() -> None:
    """Anti-tautology proof: the roundtrip above is actually carrying the field.

    If this passed while the boundary was broken, every roundtrip assertion in
    this module would be meaningless. Deleting the stored token must be
    OBSERVABLE -- and observable in the safe direction: the temporal carer's
    record degrades to an ordinary descendant, which withholds nothing it was
    entitled to, rather than silently becoming an entitling one.
    """
    temporal = DescendantInfo(birth_date=_OLD_BIRTH, relacion=DescendantRelacion.ACOGIMIENTO_TEMPORAL)
    facts = dict(descendant_facts_from_list((temporal,)))
    assert facts.pop("renta_family.descendiente.0.relacion") == "acogimiento_temporal"

    (reloaded,) = descendant_list_from_facts(facts)

    assert reloaded != temporal
    assert reloaded.relacion is DescendantRelacion.DESCENDIENTE
    assert reloaded.is_eligible_minimo_incremento_menor_tres(_YEAR) is False


def test_corrupting_the_stored_relacion_refuses_rather_than_coercing() -> None:
    """A present-but-unreadable token is refused, not resolved to the default."""
    child = DescendantInfo(birth_date=_OLD_BIRTH, relacion=DescendantRelacion.TUTELA)
    facts = dict(descendant_facts_from_list((child,)))
    facts["renta_family.descendiente.0.relacion"] = "acogimiento"

    with pytest.raises((ValueError, ValidationError)):
        descendant_list_from_facts(facts)


def test_a_stored_entry_date_under_an_excluded_relacion_refuses_on_reload() -> None:
    """The excluded case cannot be smuggled in by editing the fact index.

    The coherence rule is enforced by the canonical record itself, so it holds
    on every read path rather than only at the doors that happen to check.
    """
    child = DescendantInfo(birth_date=_OLD_BIRTH, relacion=DescendantRelacion.ACOGIMIENTO_TEMPORAL)
    facts = dict(descendant_facts_from_list((child,)))
    facts["renta_family.descendiente.0.acogimiento_resolucion"] = "2020-01-01"

    with pytest.raises((ValueError, ValidationError)):
        descendant_list_from_facts(facts)
