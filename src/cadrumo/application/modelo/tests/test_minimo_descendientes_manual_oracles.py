"""AEAT manual worked-example oracles for the Art. 58/61 mínimo por descendientes.

Ground truth is the bundled AEAT Manual práctico de Renta 2024, Parte 1,
Capítulo 14 ("Ejemplos prácticos"), declared in
``corpus/manual_oracles/modelo-100-2024-minimo-descendientes-prorrateo-asturias.json``
and ``…-declaracion-propia-valenciana.json``.

Every expected figure here is a number AEAT printed. Nothing is recomputed from
the predicate under test, and nothing is derived as a complement of another
assertion: the prorrateo pair asserts 4.550 AND 9.100 as two separately printed
totals that happen to stand in a 2:1 relation, rather than asserting one and
halving it.

Three hazards govern what these tests may assert, all recorded in the fixture
notes and all reproduced by the author against the extraction before use:

* The Asturias example states the comunidad exercised NO normative competence,
  so estatal and autonómico carry the same figure and casilla 0514 can be
  asserted alongside 0513. The Valencian example states the opposite, so only
  the estatal casilla 0513 is asserted there.
* In the Valencian example the excluded child holds 4.050 euros — BELOW the
  Art. 58.1 ceiling of 8.000. That child is excluded by the Art. 61 norma 2ª
  own-return rule alone, so this oracle grounds norma 2ª and not the cap.
* The conjunta table of the Asturias example carries an extraction artefact on
  the "Total mínimo por contribuyente" row (5.500 estatal against 5.550
  autonómico, contradicting both the line above it and the example's own
  footnote). Only the "Total mínimo por descendientes" rows are asserted, which
  are what casillas 0513/0514 hold.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....core.resources import bundled_path, resources
from ....domain.calculations.registry import ManualWorkedExamplePayload, RegistrySnapshot
from .._profile_binding import (
    inject_derived_anualidades_eligibility_facts,
    inject_derived_minimo_descendientes_facts,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_ORACLE_YEAR = 2024
_ASTURIAS_ORACLE = "modelo-100-2024-minimo-descendientes-prorrateo-asturias.json"
_VALENCIANA_ORACLE = "modelo-100-2024-minimo-descendientes-declaracion-propia-valenciana.json"


def _oracle(name: str) -> ManualWorkedExamplePayload:
    """Read a bundled fixture through the registry's own strict payload model.

    Deliberately NOT a local ``json.loads`` helper. The registry already owns
    the model these payloads are parsed through, and it refuses an undeclared
    key rather than ignoring it — so a fixture that drifts from the shape the
    grounding fold consumes fails here rather than being read two different
    ways by two different readers.
    """
    path = Path(bundled_path("corpus", "manual_oracles")) / name
    return ManualWorkedExamplePayload.model_validate_json(path.read_text(encoding="utf-8"))


def _expected(name: str, casilla_id: str) -> Decimal:
    """Return the AEAT-printed figure for *casilla_id*, from the fixture on disk."""
    return Decimal(_oracle(name).expected_by_casilla_id[casilla_id])


def _snapshot() -> RegistrySnapshot:
    return resources().modelos.authority.snapshot("100", filing_year=_ORACLE_YEAR, period="0A")


def _aggregates(facts: dict[str, object]) -> tuple[Decimal, Decimal]:
    narrowed: Any = facts
    inject_derived_minimo_descendientes_facts(narrowed, _snapshot())
    return (
        facts[f"renta_family.descendientes_minimos_aggregate_{_ORACLE_YEAR}"],  # type: ignore[return-value]
        facts[f"renta_family.descendientes_minimos_aggregate_autonomico_{_ORACLE_YEAR}"],  # type: ignore[return-value]
    )


# ---------------------------------------------------------------------------
# The fixtures are real, loadable, and declare what these tests claim.
# ---------------------------------------------------------------------------


def test_both_oracle_fixtures_load_and_declare_their_provenance() -> None:
    for name in (_ASTURIAS_ORACLE, _VALENCIANA_ORACLE):
        payload = _oracle(name)
        assert payload.modelo == "100", name
        assert payload.filing_year == _ORACLE_YEAR, name
        assert payload.source_kind == "aeat_manual_worked_example", name
        assert payload.raw_evidence_locator.startswith("corpus/manuals/renta/2024/"), name
        assert payload.expected_by_casilla_id, name


def test_the_valenciana_oracle_grounds_only_the_estatal_casilla() -> None:
    """The CCAA hazard is structural, not a comment.

    Comunitat Valenciana exercised normative competence, so its autonómico
    column carries divergent tranches the engine does not wire. If a later
    author adds 0514 to that fixture the assertion below fails, which is the
    point: the omission must stay deliberate rather than decay into an
    oversight.
    """
    assert set(_oracle(_VALENCIANA_ORACLE).expected_by_casilla_id) == {"0513"}
    assert set(_oracle(_ASTURIAS_ORACLE).expected_by_casilla_id) == {"0513", "0514"}


# ---------------------------------------------------------------------------
# Oracle A - Art. 61 norma 1a prorrateo, both sides AEAT-printed.
# ---------------------------------------------------------------------------


def _asturias_children() -> dict[str, object]:
    """Matrimonio, three cohabiting children aged 27 (discapacidad 33 %), 22 and 19.

    The manual states no child holds rentas above 8.000 nor files their own
    return, so both income conditions are satisfied and only the prorrateo is
    in play. The eldest is 27 and qualifies through the discapacidad limb.
    """
    return {
        "renta_family.descendiente.0.birth_date": f"{_ORACLE_YEAR - 27}-01-01",
        "renta_family.descendiente.0.discapacidad": "33",
        "renta_family.descendiente.1.birth_date": f"{_ORACLE_YEAR - 22}-01-01",
        "renta_family.descendiente.2.birth_date": f"{_ORACLE_YEAR - 19}-01-01",
        "renta_taxpayer.marital_status": "casado",
    }


def test_asturias_individual_matches_the_printed_prorated_total() -> None:
    """AEAT prints 4.550 for each spouse filing individually, each tranche at 50 %."""
    estatal, autonomico = _aggregates({**_asturias_children(), "filing_export.declaration_type": "1"})
    assert estatal == _expected(_ASTURIAS_ORACLE, "0513")
    assert autonomico == _expected(_ASTURIAS_ORACLE, "0514")


def test_asturias_conjunta_matches_the_printed_full_total() -> None:
    """AEAT prints 9.100 for the joint return, at the full tranches.

    Anti-tautology pair for the test above, with an AEAT-printed figure on BOTH
    sides: married spouses form one unidad familiar (LIRPF art. 82.1.1ª), so no
    second contribuyente remains to prorate with and the tranches are whole.
    """
    facts = {**_asturias_children(), "filing_export.declaration_type": "2"}
    estatal, autonomico = _aggregates(facts)
    assert estatal == Decimal("9100")
    assert autonomico == Decimal("9100")
    # The two printed totals stand in the 2:1 relation norma 1a describes.
    assert _expected(_ASTURIAS_ORACLE, "0513") * 2 == estatal


def test_asturias_oracle_does_not_assert_the_artefacted_contribuyente_row() -> None:
    """The extraction artefact is excluded by construction, not by discipline.

    The conjunta table renders the mínimo del contribuyente as 5.500 in the
    estatal column against 5.550 in the autonómico one. Neither figure belongs
    to casilla 0513/0514, and this asserts the fixture never smuggled one in.
    """
    expected = _oracle(_ASTURIAS_ORACLE).expected_by_casilla_id.values()
    assert Decimal("5500") not in {Decimal(value) for value in expected}
    assert Decimal("5550") not in {Decimal(value) for value in expected}


# ---------------------------------------------------------------------------
# Oracle B - Art. 61 norma 2a own-return exclusion.
# ---------------------------------------------------------------------------


def _valenciana_children(*, youngest_files_own_return: bool) -> dict[str, object]:
    """Pareja de hecho, three cohabiting children aged 18, 12 and 6.

    The youngest holds 4.050 euros of rendimientos del capital mobiliario —
    below the 8.000 Art. 58.1 ceiling, so the cap does NOT exclude this child.
    """
    facts: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": f"{_ORACLE_YEAR - 18}-01-01",
        "renta_family.descendiente.1.birth_date": f"{_ORACLE_YEAR - 12}-01-01",
        "renta_family.descendiente.2.birth_date": f"{_ORACLE_YEAR - 6}-01-01",
        "renta_family.descendiente.2.rentas_anuales": "4050",
        "renta_taxpayer.marital_status": "pareja_hecho_registrada",
        "filing_export.declaration_type": "1",
    }
    if youngest_files_own_return:
        facts["renta_family.descendiente.2.declaracion_propia"] = "true"
    return facts


def test_valenciana_individual_matches_the_printed_estatal_total() -> None:
    """AEAT prints 2.550 estatal: 1.200 + 1.350 + 0 for the excluded youngest."""
    estatal, _ = _aggregates(_valenciana_children(youngest_files_own_return=True))
    assert estatal == _expected(_VALENCIANA_ORACLE, "0513")


def test_the_youngest_child_is_excluded_by_norma_2a_and_not_by_the_cap() -> None:
    """Anti-tautology pair isolating WHICH condition excludes.

    4.050 is below the Art. 58.1 ceiling, so removing only the own-return flag
    must restore that child's full tranche. If the cap were doing the work the
    total would not move, and this test would fail.
    """
    without_own_return, _ = _aggregates(_valenciana_children(youngest_files_own_return=False))
    printed_with_exclusion = _expected(_VALENCIANA_ORACLE, "0513")
    assert without_own_return > printed_with_exclusion
    # The restored child is the third by birth order, so it takes the 4.000
    # tranche at the same 50 % prorrateo the other two carry.
    assert without_own_return == printed_with_exclusion + Decimal("4000") * Decimal("0.5")


# ---------------------------------------------------------------------------
# One predicate, three consuming surfaces.
# ---------------------------------------------------------------------------


def test_the_same_predicate_change_moves_both_aggregates_together() -> None:
    """Estatal and autonómico are driven by one predicate, proven on a real oracle.

    Asturias exercised no normative competence, so the two casillas must agree
    exactly — both when the prorrateo applies and when it does not. A predicate
    wired into only one of the two injectors fails this.
    """
    individual = _aggregates({**_asturias_children(), "filing_export.declaration_type": "1"})
    conjunta = _aggregates({**_asturias_children(), "filing_export.declaration_type": "2"})
    assert individual[0] == individual[1]
    assert conjunta[0] == conjunta[1]
    assert individual[0] != conjunta[0]


def test_the_anualidades_flag_consumes_the_same_eligibility_predicate() -> None:
    """The third consumer moves with the other two, in the opposite direction.

    A descendant excluded by the Art. 58.1 cap generates no mínimo, so the payer
    IS sin derecho and the Art. 64/75 separate escala applies (flag 1). Dropping
    the exclusion restores the mínimo and withdraws the régimen (flag 0), which
    is the mutation pair proving the flag reads the predicate rather than a
    constant.
    """
    key = f"renta_family.anualidades_sin_minimo_descendientes_{_ORACLE_YEAR}"

    excluded: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": f"{_ORACLE_YEAR - 10}-01-01",
        "renta_family.descendiente.0.custodia_compartida": "true",
        "renta_family.descendiente.0.rentas_anuales": "8001",
    }
    narrowed_excluded: Any = excluded
    inject_derived_anualidades_eligibility_facts(narrowed_excluded, _snapshot())
    assert excluded[key] == Decimal("1")

    eligible: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": f"{_ORACLE_YEAR - 10}-01-01",
        "renta_family.descendiente.0.custodia_compartida": "true",
    }
    narrowed_eligible: Any = eligible
    inject_derived_anualidades_eligibility_facts(narrowed_eligible, _snapshot())
    assert eligible[key] == Decimal("0")
