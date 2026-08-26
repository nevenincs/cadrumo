"""Which monetary targets the blank-box guard is armed on, and which it is not.

The guard refuses a captured token identical to the box's own printed number,
because a BLANK money box on a real AEAT render leaves exactly that token as
the last thing on its line. It reads the printed number from ``form_number``,
and a target whose ``form_number`` is unset is left UNGUARDED rather than
refused -- failing closed on a bare integer would refuse genuine values (a
perceptor count of 3, an explicit printed ``0`` in a rectificaciones box), so
the lenient reading is deliberate.

The cost of that leniency is that an unarmed target is silent. Nothing fails,
nothing warns, and a blank box returns its own box number as a monetary
amount. This module makes the arming state visible instead: the estate-wide
set of unguarded monetary targets is asserted to be exactly the set that is
genuinely blocked on evidence, so a newly-added unguarded target fails here
rather than shipping quietly.

The blocked set is Modelo 193's three resumen totals. Its bundled corpus states
no box numbers at all -- nine files across the diseño-de-registro and
instruction trees contain the word "casilla" zero times, including 49,009
characters of extracted text from the nota informativa -- and it has no
specimen. Its casilla structure is identical to Modelo 180's, which makes
inferring 01/02/03 tempting and inadmissible: that inference is precisely what
this line of work exists to refuse. They stay unarmed until AEAT publishes a
box number or a render appears.

The search behind that negative was validated against Modelo 180, whose
equivalent help page does state ``Casilla01``/``02``/``03``, so the sweep is
known to find box numbers where they exist rather than merely finding nothing.

See Also:
    :func:`~adapters.inbound.declaracion._parser._printed_box_numbers`
        The lenient reader whose arming state this module measures.
    :mod:`~adapters.inbound.declaracion.tests.test_printed_box_number_source`
        That the printed number is ``form_number`` and never ``number``.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloRevision

from .....domain.calculations.registry.authority import bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

# value_kind values that make an unarmed target a fabricated-AMOUNT hazard.
# A non-monetary target (an ejercicio year, a tipo-declaracion token) also goes
# unguarded, but a box number landing there is a wrong string rather than a
# wrong euro figure, and those casillas are `required` so a blank one means a
# malformed document rather than a legitimate blank.
_MONETARY_VALUE_KINDS = frozenset({"amount"})

# Modelo 193's resumen totals: monetary, named_label, and blocked for want of
# any published box number or specimen. Their `number` values are fichero-BOE
# positional ranges, which is correct for what that field means and is exactly
# why they cannot stand in for a printed box number.
_BLOCKED_ON_EVIDENCE: frozenset[tuple[str, str, str]] = frozenset(
    {
        ("193", "2024-y-siguientes", "decl.base-total"),
        ("193", "2024-y-siguientes", "decl.retenciones-total"),
        ("193", "2024-y-siguientes", "decl.total-perceptores"),
    },
)

# Read off AEAT's own published instructions, which state the printed numbers
# directly and so need no specimen:
#   instr_mod_349            "Casilla 01 Numero total de operadores intracomunitarios."
#                            "Casilla 02 Importe de las operaciones intracomunitarias."
#                            "Casilla 03 Numero total de operadores intracomunitarios con
#                             rectificaciones."
#                            "Casilla 04 Importe de las rectificaciones."
#   modelo-180-ayuda-        "Casilla01 Numero total de perceptores relacionados"
#   resumen-datos            "Casilla02 Base retenciones e ingresos a cuenta"
#                            "Casilla03 Retenciones e ingresos a cuenta."
# These are the AEAT documents' numbers, not values read back from the casillas
# under test, so the assertion fails if the registry drifts away from them.
_INSTRUCTION_GROUNDED_FORM_NUMBERS: dict[tuple[str, str, str], str] = {
    ("349", "2020-y-siguientes", "decl.numero-operadores"): "01",
    ("349", "2020-y-siguientes", "decl.importe-operaciones"): "02",
    ("349", "2020-y-siguientes", "decl.numero-rectificaciones"): "03",
    ("349", "2020-y-siguientes", "decl.importe-rectificaciones"): "04",
    ("180", "2023-y-siguientes", "decl.total-perceptores"): "01",
    ("180", "2023-y-siguientes", "decl.base-total"): "02",
    ("180", "2023-y-siguientes", "decl.retenciones-total"): "03",
}


def _is_armed(revision: ModeloRevision, casilla_id: str) -> bool:
    """Whether the guard can resolve a printed box number for ``casilla_id``.

    Mirrors ``_printed_box_numbers``: ``form_number`` first, then ``number``
    but only when it is a plausible printed box number, which is what keeps the
    numerically-named casillas working without re-admitting the record-design
    strings that caused the original defect.
    """
    for casilla in revision.casillas:
        if str(casilla.id) != casilla_id:
            continue
        if casilla.form_number:
            return True
        number = casilla.number or ""
        return bool(number.strip().isdigit())
    return False


def _monetary_named_label_targets() -> list[tuple[str, str, str, bool]]:
    """Return every declaracion_pdf monetary named_label target and its arming.

    Selection matches production (``surface`` plus ``accepted_artefact_kinds``),
    never ``artefact_kind``, which silently missed 18 of 29 profiles when a gate
    was last authored against it.
    """
    authority = bundled_authority()
    rows: list[tuple[str, str, str, bool]] = []
    seen: set[tuple[str, str, str]] = set()
    for modelo in authority.modelos:
        for revision in modelo.revisions.values():
            for profile in revision.extraction_profiles:
                if profile.surface != "declaracion_pdf":
                    continue
                if "declaration_pdf" not in profile.accepted_artefact_kinds:
                    continue
                for target in profile.target_casillas:
                    if target.match_strategy != "named_label":
                        continue
                    if target.value_kind not in _MONETARY_VALUE_KINDS:
                        continue
                    key = (str(modelo.id), revision.id, str(target.casilla_id))
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append((*key, _is_armed(revision, key[2])))
    return rows


def test_the_unguarded_monetary_targets_are_exactly_the_evidence_blocked_ones() -> None:
    """No monetary target is silently unguarded beyond the known-blocked set.

    An unarmed target produces a fabricated amount from a blank box and reports
    nothing, so the only defence is knowing the complete set. Adding a target
    without a printed box number fails here.

    Arming Modelo 193 later also fails here, which is intended: closing an
    evidence gap should be a deliberate edit to this set, not a silent change
    in behaviour.
    """
    unguarded = {(m, r, c) for m, r, c, armed in _monetary_named_label_targets() if not armed}

    newly_unguarded = unguarded - _BLOCKED_ON_EVIDENCE
    assert not newly_unguarded, (
        "monetary named_label targets are unguarded beyond the evidence-blocked set, so a blank box "
        f"on each returns its own printed number as an amount: {sorted(newly_unguarded)}. Populate "
        "form_number from an AEAT-published box number or a bundled render; never infer one from a "
        "sibling modelo's layout"
    )

    now_armed = _BLOCKED_ON_EVIDENCE - unguarded
    assert not now_armed, (
        f"{sorted(now_armed)} are recorded as blocked for want of a published box number but are now "
        "armed; if AEAT published one or a specimen appeared, remove them from _BLOCKED_ON_EVIDENCE "
        "and cite the evidence"
    )


@pytest.mark.parametrize(
    "modelo_id,revision_id,casilla_id,expected",
    [(m, r, c, n) for (m, r, c), n in sorted(_INSTRUCTION_GROUNDED_FORM_NUMBERS.items())],
    ids=[f"M{m}-{c}" for m, _r, c in sorted(_INSTRUCTION_GROUNDED_FORM_NUMBERS)],
)
def test_instruction_grounded_form_numbers_match_the_published_numbers(
    modelo_id: str,
    revision_id: str,
    casilla_id: str,
    expected: str,
) -> None:
    """Each armed informativa target carries the number AEAT's instructions state.

    These seven were grounded without any specimen, because AEAT publishes the
    box numbers in prose. The expected values come from those documents rather
    than from the casillas under test, so the assertion is a real check on the
    registry and not a restatement of it.

    Dropping ``form_number`` here would not fail anything else: the guard would
    simply stop firing, silently, which is the state all seven were in before.
    """
    revision = next(
        rev
        for modelo in bundled_authority().modelos
        if str(modelo.id) == modelo_id
        for rev_id, rev in modelo.revisions.items()
        if rev_id == revision_id
    )
    casilla = next(c for c in revision.casillas if str(c.id) == casilla_id)

    assert casilla.form_number == expected, (
        f"M{modelo_id} {casilla_id!r} carries form_number={casilla.form_number!r}, but AEAT's "
        f"published instructions state box {expected!r}. An empty value leaves the blank-box guard "
        f"disarmed for this target with nothing reporting it"
    )


def test_the_arming_sweep_actually_finds_targets() -> None:
    """The set assertions above are vacuous if the sweep enumerates nothing.

    A profile-selection mistake (matching ``artefact_kind`` instead of
    ``surface``) would empty the walk and make every assertion above pass while
    checking no target at all.
    """
    rows = _monetary_named_label_targets()

    assert len(rows) > 50, (
        f"the monetary named_label sweep found only {len(rows)} targets, which is too few to be a real walk of the estate"
    )
    assert any(armed for *_rest, armed in rows), (
        "the sweep found no armed target, so _is_armed is not resolving printed numbers"
    )
    assert any(not armed for *_rest, armed in rows), (
        "the sweep found no unarmed target, so the blocked-set assertion is not being exercised"
    )
